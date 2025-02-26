import pickle
import os
from sklearn.ensemble import RandomForestClassifier
from flight_tracker.utils import logger
from flight_tracker.models import db, FlightPath

MODEL_PATH = '/data/flight_model.pkl'

def load_model():
    """Load the saved model from disk."""
    if os.path.exists(MODEL_PATH):
        try:
            with open(MODEL_PATH, 'rb') as f:
                model = pickle.load(f)
                logger.info("Model loaded from disk")
                return model
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return None
    logger.info("No saved model found, returning None")
    return None

def save_model(model):
    """Save the model to disk."""
    try:
        with open(MODEL_PATH, 'wb') as f:
            pickle.dump(model, f)
        logger.info("Model saved to disk")
    except Exception as e:
        logger.error(f"Failed to save model: {e}")

def train_model():
    """Train the model using manual classifications from the database."""
    # Filter for manually classified flights with valid classifications
    flights = FlightPath.query.filter_by(auto_classified=False).filter(FlightPath.classification.isnot(None)).all()
    if len(flights) < 10:
        logger.warning(f"Insufficient manually classified flights to train model: {len(flights)} found")
        return False

    X = []
    y = []
    for flight in flights:
        points = flight.points_list
        if len(points) < 2:
            continue
        altitudes = [p[3] for p in points if p[3] != -1]
        velocities = [p[4] for p in points if p[4] != -1]
        lat_lons = [(p[0], p[1]) for p in points]
        turns = 0
        if len(lat_lons) > 2:
            for i in range(len(lat_lons) - 2):
                v1 = (lat_lons[i+1][0] - lat_lons[i][0], lat_lons[i+1][1] - lat_lons[i][1])
                v2 = (lat_lons[i+2][0] - lat_lons[i+1][0], lat_lons[i+2][1] - lat_lons[i+1][1])
                dot = v1[0] * v2[0] + v1[1] * v2[1]
                mag1 = (v1[0]**2 + v1[1]**2)**0.5
                mag2 = (v2[0]**2 + v2[1]**2)**0.5
                if mag1 * mag2 > 0:
                    cos_angle = dot / (mag1 * mag2)
                    if cos_angle < 0.7:
                        turns += 1
        features = [
            sum(altitudes) / len(altitudes) if altitudes else -1,
            sum(velocities) / len(velocities) if velocities else -1,
            turns / len(points) if points else 0
        ]
        X.append(features)
        y.append(flight.classification)

    if len(X) < 2 or len(set(y)) < 2:
        logger.warning(f"Insufficient data variety to train model: {len(X)} samples, {len(set(y))} unique classes")
        return False

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    if model.fit(X, y):
        save_model(model)
        logger.info("Model trained successfully with %d samples and %d classes", len(X), len(set(y)))
        return True
    return False