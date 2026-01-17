import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import sqlite3
import joblib  # To save the model

def train_and_save_model():
    conn = sqlite3.connect('ecodrive.db')
    query = """
        SELECT tid, 
               AVG(idle_minutes) as avg_idle, 
               COUNT(*) as incident_count
        FROM v_idle_events GROUP BY tid
    """
    df = pd.read_sql(query, conn)
    conn.close()
    
    # Target: High Risk (1) if avg_idle > 15 mins
    df['risk_label'] = (df['avg_idle'] > 15).astype(int)
    
    X = df[['avg_idle', 'incident_count']]
    y = df['risk_label']
    
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)
    
    # Save the model to a file
    joblib.dump(model, 'driver_risk_model.pkl')
    print("Model saved as driver_risk_model.pkl")

if __name__ == "__main__":
    train_and_save_model()