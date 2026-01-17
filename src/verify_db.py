import sqlite3
import pandas as pd

def verify_data():
    conn = sqlite3.connect('ecodrive.db')
    
    # 1. Check Total Row Count
    total_rows = conn.execute("SELECT COUNT(*) FROM trajectories").fetchone()[0]
    
    # 2. Check Unique Taxis
    unique_taxis = conn.execute("SELECT COUNT(DISTINCT tid) FROM trajectories").fetchone()[0]
    
    # 3. Preview Data
    df_preview = pd.read_sql_query("SELECT * FROM trajectories LIMIT 5", conn)
    
    print("--- Database Sanity Check ---")
    print(f"Total Records Ingested: {total_rows:,}")
    print(f"Unique Taxis Identified: {unique_taxis}")
    print("\nData Preview:")
    print(df_preview)
    
    conn.close()

if __name__ == "__main__":
    verify_data()