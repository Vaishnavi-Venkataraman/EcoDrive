import sqlite3
import pandas as pd
import numpy as np

def haversine_distance(lon1, lat1, lon2, lat2):
    # Earth radius in km
    R = 6371.0
    # Convert to radians
    lon1, lat1, lon2, lat2 = map(np.radians, [lon1, lat1, lon2, lat2])
    
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c

def detect_harsh_events(taxi_id):
    conn = sqlite3.connect('ecodrive.db')
    query = f"SELECT * FROM trajectories WHERE tid = {taxi_id} ORDER BY timestamp"
    df = pd.read_sql_query(query, conn)
    conn.close()

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    # Time diff in seconds
    df['time_gap'] = df['timestamp'].diff().dt.total_seconds()
    
    # Distance diff in km
    df['dist_km'] = haversine_distance(
        df['longitude'].shift(), df['latitude'].shift(),
        df['longitude'], df['latitude']
    )

    # Speed = km/h
    df['speed_kmh'] = (df['dist_km'] / df['time_gap']) * 3600
    
    # Acceleration = Change in speed (m/s^2)
    # (Speed_diff / 3.6) converts km/h to m/s
    df['accel_mss'] = (df['speed_kmh'].diff() / 3.6) / df['time_gap']

    # Filter for Harsh Braking (Industry standard: < -3.0 m/s^2)
    harsh_braking = df[df['accel_mss'] < -3.0]
    
    print(f"--- Safety Report for Taxi {taxi_id} ---")
    print(f"Max Speed: {df['speed_kmh'].max():.2f} km/h")
    print(f"Harsh Braking Events: {len(harsh_braking)}")
    
    return harsh_braking

if __name__ == "__main__":
    detect_harsh_events(10078)