import streamlit as st
import sqlite3
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
import numpy as np
import joblib

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="EcoDrive Pro: AI Telematics", layout="wide")

# --- THEME-AGNOSTIC STYLING ---
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-weight: bold !important; }
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

# --- ML MODEL LOADER ---
@st.cache_resource
def load_risk_model():
    try:
        return joblib.load('driver_risk_model.pkl')
    except:
        return None

# --- SIDEBAR & NAVIGATION ---
st.sidebar.title("🎛️ EcoDrive Pro AI")
nav = st.sidebar.radio("Navigation", ["Fleet Intelligence", "Safety Diagnostics"])

if nav == "Fleet Intelligence":
    st.title("🏆 Fleet Performance & City Hotspots")
    
    with st.spinner('Aggregating fleet-wide trends...'):
        fleet_query = "SELECT tid, SUM(idle_minutes) as total_idle_mins, SUM(estimated_fuel_waste_gal) as fuel_wasted_gal FROM v_idle_events WHERE tid % 10 = 0 GROUP BY tid ORDER BY fuel_wasted_gal DESC LIMIT 25"
        leaderboard_df = get_data(fleet_query)

    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Top Fuel Wasters")
        st.dataframe(leaderboard_df.style.format({"fuel_wasted_gal": "{:.2f}", "total_idle_mins": "{:.1f}"}), use_container_width=True)
    with col2:
        st.subheader("Fuel Waste Distribution")
        st.bar_chart(leaderboard_df.set_index('tid')['fuel_wasted_gal'])

    st.subheader("🔥 Beijing Idling Hotspots")
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

    # 1. Fetch Data
    route_df = get_data(f"SELECT * FROM trajectories WHERE tid = {taxi_id} ORDER BY timestamp")
    incidents_df = get_data(f"SELECT * FROM v_idle_events WHERE tid = {taxi_id} ORDER BY start_idle")

    # 2. Stats Calculation
    total_idle = incidents_df['idle_minutes'].sum() if not incidents_df.empty else 0
    num_violations = len(incidents_df[incidents_df['idle_minutes'] > 18]) if not incidents_df.empty else 0
    curr_score = max(0, 100 - (total_idle * 0.3) - (num_violations * 10))

    # 3. AI Predictive Insight
    st.subheader("🤖 AI Predictive Insight")
    model = load_risk_model()
    if model:
        avg_idle_val = total_idle / max(1, len(incidents_df))
        features = np.array([[avg_idle_val, len(incidents_df)]])
        risk_proba = model.predict_proba(features)[0][1]
        
        col_a, col_b = st.columns([1, 3])
        with col_a:
            st.metric("Predicted Risk Prob.", f"{risk_proba*100:.1f}%")
        with col_b:
            # Enhanced AI Logic: Aligning AI warning with the traditional Eco-Score
            if risk_proba > 0.6 or curr_score < 40:
                st.error("⚠️ HIGH PREDICTIVE RISK: AI predicts likely future fuel waste or safety incidents based on trip patterns.")
            else:
                st.success("✅ LOW PREDICTIVE RISK: AI predicts stable driving patterns.")
    else:
        st.warning("Run predictive_analytics.py to enable AI insights.")

    # 4. Metrics Display
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Eco-Score", f"{curr_score:.0f}/100")
    col2.metric("Total Idle", f"{total_idle:.1f}m")
    col3.metric("Safety Violations", num_violations)
    with col4:
        color = "#2ecc71" if curr_score > 85 else "#f39c12" if curr_score > 60 else "#e74c3c"
        st.markdown(f'<div class="status-card" style="background-color: {color};">{"EXCELLENT" if curr_score > 85 else "CAUTION" if curr_score > 60 else "HIGH RISK"}</div>', unsafe_allow_html=True)

    # 5. Map
    st.subheader("📍 Geospatial Incident Map")
    if not route_df.empty:
        m = folium.Map(location=[route_df.iloc[0]['latitude'], route_df.iloc[0]['longitude']], zoom_start=13, tiles="OpenStreetMap")
        folium.PolyLine(route_df[['latitude', 'longitude']].values.tolist(), color="#3498db", weight=2, opacity=0.6).add_to(m)
        if not incidents_df.empty:
            for _, row in incidents_df.iterrows():
                is_crit = float(row['idle_minutes']) > 18
                folium.Marker([row['latitude'], row['longitude']], icon=folium.Icon(color='red' if is_crit else 'orange', icon='exclamation-triangle', prefix='fa')).add_to(m)
        st_folium(m, width=1400, height=500, key=f"map_taxi_{taxi_id}")

    # 6. Detailed Log & Export CSV
    if not incidents_df.empty:
        # Format strings for CSV/Display to prevent Excel #### error
        incidents_df['start_idle'] = pd.to_datetime(incidents_df['start_idle']).dt.strftime('%Y-%m-%d %H:%M:%S')
        incidents_df['end_idle'] = pd.to_datetime(incidents_df['end_idle']).dt.strftime('%Y-%m-%d %H:%M:%S')
        
    st.subheader("📝 Incident Detailed Log")
    st.dataframe(incidents_df, use_container_width=True)
    
    # RESTORED EXPORT BUTTON
    st.download_button(
        label="📥 Download Safety Report (CSV)",
        data=incidents_df.to_csv(index=False).encode('utf-8'),
        file_name=f"safety_report_vehicle_{taxi_id}.csv",
        mime='text/csv'
    )