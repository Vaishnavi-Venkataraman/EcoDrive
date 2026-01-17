import streamlit as st
import sqlite3
import pandas as pd
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="EcoDrive Intelligence", layout="wide")

st.markdown("""
    <style>
    /* Force metric text to be visible regardless of theme */
    [data-testid="stMetricValue"] {
        color: #004d40 !important;
        font-weight: bold !important;
    }
    [data-testid="stMetricLabel"] {
        color: #333333 !important;
        font-size: 1.1rem !important;
    }
    /* Style the metric cards */
    [data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border: 1px solid #e0e0e0;
    }
    .main { background-color: #f8f9fa; }
    </style>
    """, unsafe_allow_html=True)

def get_data(query):
    try:
        conn = sqlite3.connect('ecodrive.db')
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Database Error: {e}")
        return pd.DataFrame()

st.title("🚗 EcoDrive: Fleet Telematics & Safety Dashboard")
st.markdown("Processing **17.5M GPS data points** to identify fuel waste and high-risk driving behavior.")

st.sidebar.header("Fleet Controls")
with st.sidebar:
    taxis_df = get_data("SELECT DISTINCT tid FROM trajectories LIMIT 11000")
    if not taxis_df.empty:
        taxi_list = taxis_df['tid'].tolist()
        taxi_id = st.selectbox("Select Vehicle ID", taxi_list)
    else:
        st.error("No Taxi IDs found in Database.")
        taxi_id = None

    st.markdown("---")

if taxi_id:
    st.header("📊 Performance Overview")
    
    idle_query = f"""
        SELECT sum(idle_minutes) as total_idle, 
               sum(estimated_fuel_waste_gal) as fuel_waste 
        FROM v_idle_events 
        WHERE tid = {taxi_id}
    """
    metrics_df = get_data(idle_query)

    if not metrics_df.empty:
        total_idle = metrics_df['total_idle'].iloc[0] or 0.0
        fuel_lost = metrics_df['fuel_waste'].iloc[0] or 0.0
        cost_loss = fuel_lost * 3.80  # Estimated $3.80 per gallon

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Idling Time", f"{total_idle:.1f} Mins")
        col2.metric("Fuel Wasted", f"{fuel_lost:.2f} Gal")
        col3.metric("Estimated Cost Loss", f"${cost_loss:.2f}")

    st.header("🗺️ Trip Trajectory & Incident Mapping")
    tab1, tab2 = st.tabs(["Interactive Map", "Raw Incident Data"])

    with tab1:
        # Get trajectory for mapping
        route_query = f"SELECT latitude, longitude FROM trajectories WHERE tid = {taxi_id} ORDER BY timestamp LIMIT 2000"
        route_df = get_data(route_query)

        # Get idling incidents for red markers
        incidents_query = f"SELECT latitude, longitude, idle_minutes FROM v_idle_events WHERE tid = {taxi_id} AND idle_minutes > 5"
        incidents_df = get_data(incidents_query)

        if not route_df.empty:
            # Center map on the vehicle's first point
            center_lat = route_df.iloc[0]['latitude']
            center_lon = route_df.iloc[0]['longitude']
            
            m = folium.Map(location=[center_lat, center_lon], zoom_start=13, tiles="cartodbpositron")

            # 1. Draw Path (Blue Line)
            path_coords = route_df[['latitude', 'longitude']].values.tolist()
            folium.PolyLine(path_coords, color="#2E86C1", weight=4, opacity=0.8).add_to(m)

            # 2. Add Red Circle Markers for Idling Zones
            for _, row in incidents_df.iterrows():
                folium.CircleMarker(
                    location=[row['latitude'], row['longitude']],
                    radius=min(row['idle_minutes'], 20), # Cap radius for visibility
                    color="#E74C3C",
                    fill=True,
                    fill_color="#E74C3C",
                    popup=f"Idling: {row['idle_minutes']:.1f} mins"
                ).add_to(m)

            st_folium(m, width=1400, height=600)
        else:
            st.warning(f"No trajectory data available for Vehicle {taxi_id}.")

    with tab2:
        st.subheader(f"Detailed Incident Log: Vehicle {taxi_id}")
        if not incidents_df.empty:
            st.dataframe(incidents_df, use_container_width=True)
        else:
            st.write("No significant idling incidents recorded for this vehicle.")