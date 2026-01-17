import sqlite3

def create_idling_view():
    conn = sqlite3.connect('ecodrive.db')
    cursor = conn.cursor()
    
    print("Creating 'v_idle_events' View...")
    
    cursor.execute("DROP VIEW IF EXISTS v_idle_events")
    
    # strftime('%s') converts to Unix timestamp for easy math
    view_query = """
    CREATE VIEW v_idle_events AS
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
        (strftime('%s', next_time) - strftime('%s', timestamp)) / 60.0 as idle_minutes,
        0.01 * ((strftime('%s', next_time) - strftime('%s', timestamp)) / 60.0) as estimated_fuel_waste_gal,
        latitude,
        longitude
    FROM Gaps
    WHERE longitude = next_lon 
      AND latitude = next_lat
      AND idle_minutes BETWEEN 2 AND 120;
    """
    
    try:
        cursor.execute(view_query)
        conn.commit()
        print("Success! 'v_idle_events' view created.")
    except Exception as e:
        print(f"Error creating view: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    create_idling_view()