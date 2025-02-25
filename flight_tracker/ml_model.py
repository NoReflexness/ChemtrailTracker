import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib
import os
import json
from flight_tracker import logger

MODEL_PATH = '/data/flight_classifier.pkl'
DATA_PATH = '/data/flight_training_data.csv'

def extract_features(points):
    """Extract features from flight points for ML."""
    if len(points) < 2:
        return None
    
    total_distance = 0
    direction_changes = 0
    prev_angle = None
    time_delta = points[-1][2] - points[0][2] if points[-1][2] and points[0][2] else 1
    
    for i in range(len(points) - 1):
        lat1, lon1 = points[i][0], points[i][1]
        lat2, lon2 = points[i + 1][0], points[i + 1][1]
        distance = np.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2)
        total_distance += distance

        delta_lon = np.radians(lon2 - lon1)
        lat1, lat2 = np.radians(lat1), np.radians(lat2)
        y = np.sin(delta_lon) * np.cos(lat2)
        x = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(delta_lon)
        angle = np.degrees(np.atan2(y, x))

        if prev_angle is not None:
            angle_diff = min(abs(angle - prev_angle), 360 - abs(angle - prev_angle))
            if angle_diff > 30:
                direction_changes += 1
        prev_angle = angle

    avg_speed = total_distance / (time_delta / 3600) if time_delta > 0 else 0
    point_density = len(points) / total_distance if total_distance > 0 else 0
    
    return {
        'total_distance': total_distance,
        'direction_changes': direction_changes,
        'avg_speed': avg_speed,
        'point_density': point_density
    }

def train_model():
    if not os.path.exists(DATA_PATH):
        logger.warning("No training data available at {}".format(DATA_PATH))
        return False

    try:
        df = pd.read_csv(DATA_PATH, header=None, names=['flight_id', 'latitudes', 'longitudes', 'label'], quotechar='"')
    except pd.errors.ParserError as e:
        logger.error(f"Failed to parse CSV: {e}")
        df = pd.read_csv(DATA_PATH, header=None, names=['flight_id', 'latitudes', 'longitudes', 'label'], 
                         quotechar='"', engine='python', on_bad_lines='skip')
        logger.warning("Skipped malformed lines in CSV")

    def parse_json_safe(x):
        try:
            return json.loads(x)
        except (json.JSONDecodeError, TypeError):
            logger.debug(f"Failed to parse JSON: {x}")
            return []

    df['latitudes'] = df['latitudes'].apply(parse_json_safe)
    df['longitudes'] = df['longitudes'].apply(parse_json_safe)
    df['points'] = df.apply(lambda row: list(zip(row['latitudes'], row['longitudes'], [0]*len(row['latitudes']))), axis=1)

    features = df['points'].apply(extract_features)
    mask = features.notna()
    X = pd.DataFrame(features[mask].tolist())
    y = df['label'][mask]

    if len(X) < 10:
        logger.warning("Insufficient data for training (<10 samples)")
        return False

    # Log class distribution
    class_counts = y.value_counts().to_dict()
    logger.info(f"Training data distribution: {class_counts}")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    logger.info(f"Model trained with accuracy: {accuracy:.2f}")

    joblib.dump(model, MODEL_PATH)
    return True

def load_model():
    """Load the trained model."""
    if os.path.exists(MODEL_PATH):
        return joblib.load(MODEL_PATH)
    return None

def predict_classification(points):
    """Predict classification using the trained model."""
    model = load_model()
    if model is None:
        logger.debug("No trained model available for prediction")
        return None

    features = extract_features(points)
    if features is None:
        return None

    X = pd.DataFrame([features])
    prediction = model.predict(X)[0]
    return prediction