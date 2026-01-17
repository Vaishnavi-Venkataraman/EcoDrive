import streamlit as st
import sqlite3
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap
import numpy as np
import joblib

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="EcoDrive Pro: AI Enterprise", layout="wide")

# --- ADVANCED STYLING ---
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-weight: bold !important; }
    [data-testid="stMetric"] {
        border: 1px solid rgba(128, 128, 128, 0.3);
        padding: 15px; border-radius: 10px; background-color: rgba(128, 128, 128, 0.05);
    }
    .status-card {
        padding: 15px; border-radius: 10px; color: white; text-align: center;
        margin-bottom: 10px; font-weight: bold;
    }
    .persona-tag {
        padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 0.9rem;
        background-color: #3498db; color: white; display: inline-block;
    }
    </style>
    """, unsafe_allow_html=True)

# --- DATABASE & ML ASSET LOADERS ---
@st.cache_data(ttl=600)
def get_data(query):
    conn = sqlite3.connect('ecodrive.db', check_same_thread=False)
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

@st.cache_resource
def load_ml_suite():
    try:
        return {
            'risk_model': joblib.load('driver_risk_model.pkl'),
            'anomaly_model': joblib.load('anomaly_model.pkl'),
            'cluster_model': joblib.load('driver_clusters.pkl'),
            'scaler': joblib.load('scaler.pkl')
        }
    except:
        return None

# --- SIDEBAR ---
st.sidebar.title("🎛️ AI Telematics Control")
nav = st.sidebar.radio("Navigation", ["Fleet Intelligence", "Safety Diagnostics"])

if nav == "Fleet Intelligence":
    st.title("🏆 Fleet Performance & AI Analysis")
    
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
        HeatMap([[r['latitude'], r['longitude'], r['idle_minutes']] for i, r in heatmap_data.iterrows()]).add_to(h_map)
        st_folium(h_map, width=1400, height=500, key="fleet_heatmap")

else:
    # --- SAFETY DIAGNOSTICS ---
    st.sidebar.header("Vehicle Selection")
    taxis_df = get_data("SELECT DISTINCT tid FROM trajectories LIMIT 500")
    taxi_id = st.sidebar.selectbox("Select Vehicle ID", taxis_df['tid'].tolist())

    st.title(f"🛡️ Safety & AI Risk Report: Vehicle {taxi_id}")

    route_df = get_data(f"SELECT * FROM trajectories WHERE tid = {taxi_id} ORDER BY timestamp")
    # Fetch raw incidents for ML calculation
    incidents_raw = get_data(f"SELECT * FROM v_idle_events WHERE tid = {taxi_id} ORDER BY start_idle")

    # Metrics Calc
    total_idle = incidents_raw['idle_minutes'].sum() if not incidents_raw.empty else 0
    total_fuel = incidents_raw['estimated_fuel_waste_gal'].sum() if not incidents_raw.empty else 0
    num_violations = len(incidents_raw[incidents_raw['idle_minutes'] > 18]) if not incidents_raw.empty else 0
    curr_score = max(0, 100 - (total_idle * 0.3) - (num_violations * 10))

    # --- AI INTELLIGENCE LAYER ---
    st.subheader("🤖 AI Predictive Insights")
    ml = load_ml_suite()
    if ml and not incidents_raw.empty:
        avg_idle = total_idle / len(incidents_raw)
        feature_risk = np.array([[avg_idle, len(incidents_raw)]])
        feature_full = np.array([[avg_idle, len(incidents_raw), total_fuel]])
        scaled_full = ml['scaler'].transform(feature_full)
        
        # Predictions
        risk_proba = ml['risk_model'].predict_proba(feature_risk)[0][1]
        is_anomaly = ml['anomaly_model'].predict(scaled_full)[0] == -1
        cluster_id = ml['cluster_model'].predict(scaled_full)[0]
        
        personas = ["Eco-Efficient", "Moderate Idler", "High-Waste Outlier"]
        
        a1, a2, a3 = st.columns(3)
        # Force risk proba up if curr_score is trash
        display_risk = max(risk_proba, (100 - curr_score) / 100)
        with a1:
            st.metric("Risk Probability", f"{display_risk*100:.1f}%")
        with a2:
            if is_anomaly or curr_score < 40: st.error("🚨 ANOMALY DETECTED: Behavior deviates significantly from fleet norms.")
            else: st.success("✅ Normal behavior pattern.")
        with a3:
            # Shift persona if current trip is extreme
            p_idx = 2 if curr_score < 40 else cluster_id
            st.markdown(f"**Driver Persona:** <span class='persona-tag'>{personas[p_idx]}</span>", unsafe_allow_html=True)
            
        if display_risk > 0.6 or curr_score < 40:
            st.warning("⚠️ Warning: Predictive models suggest a high likelihood of future safety or cost incidents.")

    # --- TRADITIONAL METRICS ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Eco-Score", f"{curr_score:.0f}/100")
    col2.metric("Total Idle", f"{total_idle:.1f}m")
    col3.metric("Safety Violations", num_violations)
    with col4:
        color = "#2ecc71" if curr_score > 85 else "#f39c12" if curr_score > 60 else "#e74c3c"
        st.markdown(f'<div class="status-card" style="background-color: {color};">{"EXCELLENT" if curr_score > 85 else "CAUTION" if curr_score > 60 else "HIGH RISK"}</div>', unsafe_allow_html=True)

    # --- MAP ---
    st.subheader("📍 Geospatial Incident Map")
    if not route_df.empty:
        m = folium.Map(location=[route_df.iloc[0]['latitude'], route_df.iloc[0]['longitude']], zoom_start=13, tiles="OpenStreetMap")
        folium.PolyLine(route_df[['latitude', 'longitude']].values.tolist(), color="#3498db", weight=2, opacity=0.6).add_to(m)
        for _, row in incidents_raw.iterrows():
            folium.Marker([row['latitude'], row['longitude']], icon=folium.Icon(color='red' if float(row['idle_minutes']) > 18 else 'orange')).add_to(m)
        st_folium(m, width=1400, height=500, key=f"map_taxi_{taxi_id}")

    # --- LOG & EXPORT (Fixed formatting for CSV) ---
    incidents_display = incidents_raw.copy()
    if not incidents_display.empty:
        incidents_display['start_idle'] = pd.to_datetime(incidents_display['start_idle']).dt.strftime('%Y-%m-%d %H:%M:%S')
        incidents_display['end_idle'] = pd.to_datetime(incidents_display['end_idle']).dt.strftime('%Y-%m-%d %H:%M:%S')
    
    st.subheader("📝 Incident Detailed Log")
    st.dataframe(incidents_display, use_container_width=True)
    st.download_button("📥 Download Safety Report (CSV)", incidents_display.to_csv(index=False).encode('utf-8'), f"taxi_{taxi_id}_report.csv", "text/csv")