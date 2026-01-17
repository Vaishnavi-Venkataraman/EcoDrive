import streamlit as st
import sqlite3
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
import numpy as np

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="EcoDrive Pro: Enterprise Telematics", layout="wide")

# --- THEME-AGNOSTIC STYLING ---
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-weight: bold !important; }
    [data-testid="stMetricLabel"] { font-size: 1.1rem !important; }
    [data-testid="stMetric"] {
        border: 1px solid rgba(128, 128, 128, 0.3);
        padding: 15px;
        border-radius: 10px;
        background-color: rgba(128, 128, 128, 0.05);
    }
    .status-card {
        padding: 15px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 10px;
        font-weight: bold;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.2);
    }
    .stDataFrame {
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE ENGINE ---
@st.cache_data(ttl=600)
def get_data(query):
    try:
        conn = sqlite3.connect('ecodrive.db', check_same_thread=False)
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Database Error: {e}")
        return pd.DataFrame()

# --- ANALYTICS LOGIC ---
def calculate_eco_score(idle_mins, safety_violations):
    # Ensure inputs are numbers
    idle_val = 0 if idle_mins is None or np.isnan(idle_mins) else idle_mins
    viol_val = 0 if safety_violations is None else safety_violations
    
    base_score = 100
    penalty = (idle_val * 0.3) + (viol_val * 10)
    return max(0, min(100, base_score - penalty))

# --- SIDEBAR & NAVIGATION ---
st.sidebar.title("🎛️ EcoDrive Pro")
nav = st.sidebar.radio("Navigation", ["Fleet Intelligence", "Safety Diagnostics"])

if nav == "Fleet Intelligence":
    st.title("🏆 Fleet Performance & City Hotspots")
    
    with st.spinner('Aggregating fleet-wide trends...'):
        fleet_stats_query = """
            SELECT tid, 
                   SUM(idle_minutes) as total_idle_mins, 
                   SUM(estimated_fuel_waste_gal) as fuel_wasted_gal
            FROM v_idle_events
            WHERE tid % 10 = 0
            GROUP BY tid
            ORDER BY fuel_wasted_gal DESC
            LIMIT 25
        """
        leaderboard_df = get_data(fleet_stats_query)

    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Top Fuel Wasters")
        st.dataframe(leaderboard_df.style.format({"fuel_wasted_gal": "{:.2f}", "total_idle_mins": "{:.1f}"}), use_container_width=True)

    with col2:
        st.subheader("Fuel Waste Distribution")
        st.bar_chart(leaderboard_df.set_index('tid')['fuel_wasted_gal'])

    st.subheader("🔥 Beijing Idling Hotspots")
    st.info("Visualizing high-density fuel waste zones across the city grid.")
    
    heatmap_data = get_data("SELECT latitude, longitude, idle_minutes FROM v_idle_events LIMIT 5000")
    if not heatmap_data.empty:
        h_map = folium.Map(location=[39.9042, 116.4074], zoom_start=11, tiles="CartoDB dark_matter")
        heat_data = [[row['latitude'], row['longitude'], row['idle_minutes']] for index, row in heatmap_data.iterrows()]
        HeatMap(heat_data).add_to(h_map)
        st_folium(h_map, width=1400, height=500, key="fleet_heatmap")

else:
    # --- SAFETY DIAGNOSTICS ---
    st.sidebar.header("Vehicle Selection")
    taxis_df = get_data("SELECT DISTINCT tid FROM trajectories LIMIT 500")
    taxi_id = st.sidebar.selectbox("Select Vehicle ID", taxis_df['tid'].tolist())

    st.title(f"🛡️ Safety & Risk Report: Vehicle {taxi_id}")

    # 1. Fetch Fresh Data
    route_df = get_data(f"SELECT * FROM trajectories WHERE tid = {taxi_id} ORDER BY timestamp")
    incidents_df = get_data(f"SELECT * FROM v_idle_events WHERE tid = {taxi_id} ORDER BY start_idle")

    # 2. Calculation (Perform BEFORE formatting time to strings)
    if not incidents_df.empty:
        total_idle = incidents_df['idle_minutes'].sum()
        # Capture critical violations (duration > 18 mins)
        num_violations = len(incidents_df[incidents_df['idle_minutes'] > 18])
    else:
        total_idle = 0
        num_violations = 0
    
    score = calculate_eco_score(total_idle, num_violations)

    # 3. Display Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Eco-Score", f"{score:.0f}/100")
    col2.metric("Total Idle", f"{total_idle:.1f}m")
    col3.metric("Safety Violations", num_violations)
    
    with col4:
        if score > 85:
            st.markdown('<div class="status-card" style="background-color: #2ecc71;">EXCELLENT</div>', unsafe_allow_html=True)
        elif score > 60:
            st.markdown('<div class="status-card" style="background-color: #f39c12;">CAUTION</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-card" style="background-color: #e74c3c;">HIGH RISK</div>', unsafe_allow_html=True)

    # 4. Spatial Mapping
    st.subheader("📍 Geospatial Incident Map")
    if not route_df.empty:
        m = folium.Map(location=[route_df.iloc[0]['latitude'], route_df.iloc[0]['longitude']], zoom_start=13, tiles="OpenStreetMap")
        folium.PolyLine(route_df[['latitude', 'longitude']].values.tolist(), color="#3498db", weight=2, opacity=0.6).add_to(m)
        
        # Add Markers using the original numeric data
        if not incidents_df.empty:
            for _, row in incidents_df.iterrows():
                # Logic: Red for > 18m, Orange for moderate
                is_critical = float(row['idle_minutes']) > 18
                folium.Marker(
                    location=[row['latitude'], row['longitude']],
                    icon=folium.Icon(color='red' if is_critical else 'orange', icon='exclamation-triangle', prefix='fa'),
                    popup=f"Idle: {row['idle_minutes']:.1f}m"
                ).add_to(m)
        
        st_folium(m, width=1400, height=500, key=f"map_taxi_{taxi_id}")
    else:
        st.warning(f"No trajectory GPS data found for Vehicle ID {taxi_id}.")

    # 5. Final Formatting for Display/Export
    if not incidents_df.empty:
        incidents_df['start_idle'] = pd.to_datetime(incidents_df['start_idle']).dt.strftime('%Y-%m-%d %H:%M:%S')
        incidents_df['end_idle'] = pd.to_datetime(incidents_df['end_idle']).dt.strftime('%Y-%m-%d %H:%M:%S')

    st.subheader("📝 Incident Detailed Log")
    st.dataframe(incidents_df, use_container_width=True)
    
    csv_data = incidents_df.to_csv(index=False).encode('utf-8')
    st.download_button("Download Safety Report (CSV)", csv_data, f"taxi_{taxi_id}_safety.csv", "text/csv")