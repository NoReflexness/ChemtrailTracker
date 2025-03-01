import pickle
import os
from sklearn.ensemble import RandomForestClassifier
from flight_tracker.utils import logger
from flight_tracker.models import db, FlightPath
from flight_tracker.features import extract_features

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
    flights = FlightPath.query.filter_by(auto_classified=False).filter(FlightPath.classification.isnot(None)).all()
    if len(flights) < 10:
        logger.warning(f"Insufficient data: {len(flights)} flights")
        return False

    X, y = [], []
    for flight in flights:
        features = extract_features(flight.points_list)
        if features:
            X.append(list(features.values()))
            y.append(flight.classification)

    if len(X) < 2 or len(set(y)) < 2:
        logger.warning(f"Insufficient variety: {len(X)} samples, {len(set(y))} classes")
        return False

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)
    save_model(model)
    logger.info(f"Model trained with {len(X)} samples, {len(set(y))} classes")
    return True