import pandas as pd
import sqlite3
import glob
import os
from tqdm import tqdm

def setup_database():
    conn = sqlite3.connect('ecodrive.db')
    cursor = conn.cursor()
    # Create the table with an index on tid (Taxi ID) for fast lookups
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trajectories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tid INTEGER,
            timestamp DATETIME,
            longitude REAL,
            latitude REAL
        )
    ''')
    conn.commit()
    return conn

def ingest_files(data_path):
    conn = setup_database()
    # Get all .txt files in the directory
    all_files = glob.glob(os.path.join(data_path, "*.txt"))
    
    print(f"Found {len(all_files)} files. Starting ingestion...")
    
    for file_path in tqdm(all_files):
        try:
            # Read the file (comma separated)
            df = pd.read_csv(file_path, header=None, 
                             names=['tid', 'timestamp', 'longitude', 'latitude'])
            
            # Convert timestamp to datetime objects
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            df.to_sql('trajectories', conn, if_exists='append', index=False)
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            
    print("Optimizing database...")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tid_time ON trajectories (tid, timestamp)")
    conn.close()
    print("Ingestion Complete!")

if __name__ == "__main__":
    PATH_TO_DATA = "data/taxi_log_2008_by_id" 
    ingest_files(PATH_TO_DATA)