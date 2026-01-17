import pandas as pd
import sqlite3
import joblib
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

def train_advanced_ml():
    conn = sqlite3.connect('ecodrive.db')
    query = """
        SELECT tid, 
               AVG(idle_minutes) as avg_idle, 
               COUNT(*) as incident_count,
               SUM(estimated_fuel_waste_gal) as total_fuel_waste
        FROM v_idle_events GROUP BY tid
    """
    df = pd.read_sql(query, conn)
    conn.close()

    # Features for ML
    features = ['avg_idle', 'incident_count', 'total_fuel_waste']
    X = df[features]
    
    # Scale data for better Clustering/Anomaly performance
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # FEATURE 1: Driver Risk Classifier (Supervised)
    df['risk_label'] = (df['avg_idle'] > 15).astype(int)
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X[['avg_idle', 'incident_count']], df['risk_label'])
    joblib.dump(clf, 'driver_risk_model.pkl')

    # FEATURE 2: Anomaly Detection (Unsupervised)
    # Detects "Outlier" drivers who behave completely differently from the 10,000 others
    iso_forest = IsolationForest(contamination=0.05, random_state=42)
    iso_forest.fit(X_scaled)
    joblib.dump(iso_forest, 'anomaly_model.pkl')

    # FEATURE 3: Trajectory Clustering (Unsupervised)
    # Groups drivers into 3 Personas: Efficient, Moderate, and High-Waste
    kmeans = KMeans(n_clusters=3, random_state=42)
    kmeans.fit(X_scaled)
    joblib.dump(kmeans, 'driver_clusters.pkl')
    joblib.dump(scaler, 'scaler.pkl')

    print("All ML models trained and saved: Risk Classifier, Anomaly Detector, and Clustering.")

if __name__ == "__main__":
    train_advanced_ml()