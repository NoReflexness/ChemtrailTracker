import os
import logging
import pickle
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from flight_analyzer.database import Database

logger = logging.getLogger('FlightAnalyzer')
MODEL_PATH = 'flight_classifier.pkl'

def train_initial_model():
    logger.info("Training initial model with dummy data")
    X = [
        [50, 5, 0, 20],  # Commercial
        [10, 2, 6, 50],  # Survey
        [5, 1, 8, 30],   # Agricultural
        [20, 10, 4, 40]  # Firefighting
    ]
    y = ['Commercial', 'Survey', 'Agricultural', 'Firefighting']
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    clf = RandomForestClassifier(n_estimators=10, random_state=42)
    clf.fit(X_scaled, y)
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump((clf, scaler), f)
    logger.info("Initial model trained and saved")

def classify_pattern(features):
    logger.info("Classifying pattern")
    if not os.path.exists(MODEL_PATH):
        train_initial_model()
    with open(MODEL_PATH, 'rb') as f:
        clf, scaler = pickle.load(f)
    X = scaler.transform([[features['avg_distance'], features['distance_var'], features['turn_count'], features['path_length']]])
    pattern = clf.predict(X)[0]
    logger.info(f"Pattern classified as: {pattern}")
    return pattern

def retrain_model():
    logger.info("Retraining model with training data")
    training_db = Database('training_data.db')
    data = training_db.fetch_training_data()
    if not data:
        train_initial_model()
        logger.warning("No training data found; using initial model")
        return
    X = [[row[0], row[1], row[2], row[3]] for row in data]
    y = [row[4] for row in data]
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    clf = RandomForestClassifier(n_estimators=50, random_state=42)
    clf.fit(X_scaled, y)
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump((clf, scaler), f)
    logger.info("Model retrained successfully")