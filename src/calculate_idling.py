import sqlite3
import pandas as pd

def detect_idling():
    conn = sqlite3.connect('ecodrive.db')
    
    print("Running Window Function Analysis on 17.5M rows...")
    
    # This CTE calculates the gap between pings
    query = """
    WITH Gaps AS (
        SELECT 
            tid,
            timestamp,
            longitude,
            latitude,
            LEAD(timestamp) OVER (PARTITION BY tid ORDER BY timestamp) as next_time,
            LEAD(longitude) OVER (PARTITION BY tid ORDER BY timestamp) as next_lon,
            LEAD(latitude) OVER (PARTITION BY tid ORDER BY timestamp) as next_lat
        FROM trajectories
    )
    SELECT 
        tid,
        timestamp as start_idle,
        next_time as end_idle,
        (strftime('%s', next_time) - strftime('%s', timestamp)) / 60.0 as idle_minutes
    FROM Gaps
    WHERE longitude = next_lon 
      AND latitude = next_lat
      AND idle_minutes > 2 -- Only capture stops longer than 2 mins
      AND idle_minutes < 120 -- Ignore gaps > 2 hours (likely end of shift)
    LIMIT 10000;
    """
    
    df_idle = pd.read_sql_query(query, conn)
    
    print(f"Detected {len(df_idle)} significant idling events in sample.")
    print(df_idle.head())
    
    # Calculate Total Waste (Industry Avg: 0.6 gallons/hour of idling)
    total_minutes = df_idle['idle_minutes'].sum()
    gallons_wasted = (total_minutes / 60.0) * 0.6
    
    print(f"\n--- Initial Insight ---")
    print(f"Total Idle Time in Sample: {total_minutes:.2f} minutes")
    print(f"Estimated Fuel Wasted: {gallons_wasted:.2f} gallons")
    
    conn.close()

if __name__ == "__main__":
    detect_idling()