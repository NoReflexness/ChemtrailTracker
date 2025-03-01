# flight_tracker/analysis.py
from sklearn.ensemble import RandomForestClassifier
from sklearn.utils.validation import check_is_fitted
import threading
import time
from flight_tracker.features import extract_features
from flight_tracker.utils import logger
from flight_tracker.ml_model import load_model, save_model

classification_log_buffer = []
ml_failure_buffer = []
buffer_lock = threading.Lock()
first_ml_failure_logged = False

def flush_log_buffers(socketio):
    global first_ml_failure_logged
    while True:
        time.sleep(5)
        with buffer_lock:
            if classification_log_buffer:
                socketio.emit('log', {'message': '\n'.join(classification_log_buffer)})
                classification_log_buffer.clear()
            if ml_failure_buffer:
                count = len(ml_failure_buffer)
                if not first_ml_failure_logged:
                    socketio.emit('log', {'message': f"ML model not fitted or failed: {ml_failure_buffer[0]}"})
                    first_ml_failure_logged = True
                socketio.emit('log', {'message': f"ML not fitted for {count} flights, using rule-based fallback"})
                ml_failure_buffer.clear()

def start_buffer_thread(socketio):
    thread = threading.Thread(target=flush_log_buffers, args=(socketio,), daemon=True)
    thread.start()

def analyze_flight(flight):
    if not hasattr(analyze_flight, 'model'):
        analyze_flight.model = load_model()
        if analyze_flight.model is None:
            logger.info("No pre-trained model found, initializing new RandomForestClassifier")
            analyze_flight.model = RandomForestClassifier(n_estimators=100, random_state=42)

    logger.debug(f"Analyzing flight {flight.flight_id} with points: {flight.points_list}")
    features = extract_features(flight.points_list)
    if features is None:  # This should no longer happen with the updated features.py
        logger.error(f"Unexpected None from extract_features for flight {flight.flight_id}")
        flight.classification = None
        flight.classification_source = None
        flight.auto_classified = False
        return

    if features['avg_altitude'] > 5000 and features['avg_velocity'] > 100:
        flight.classification = 'commercial'
        flight.classification_source = 'rule'
        flight.auto_classified = False
        logger.debug(f"Classified flight {flight.flight_id} as 'commercial' (rule-based)")
    elif features['avg_altitude'] < 1000 and features['turns_per_point'] > 0.1:
        flight.classification = 'survey'
        flight.classification_source = 'rule'
        flight.auto_classified = False
        logger.debug(f"Classified flight {flight.flight_id} as 'survey' (rule-based)")
    elif features['avg_altitude'] < 2000 and features['avg_velocity'] < 50 and features['parallelism_score'] > 0.2:
        flight.classification = 'cloud seeding'
        flight.classification_source = 'rule'
        flight.auto_classified = False
        logger.debug(f"Classified flight {flight.flight_id} as 'cloud seeding' (rule-based)")
    elif features['avg_altitude'] < 1000 and features['zig_zag_count'] > 0.3:
        flight.classification = 'crop dusting'
        flight.classification_source = 'rule'
        flight.auto_classified = False
        logger.debug(f"Classified flight {flight.flight_id} as 'crop dusting' (rule-based)")
    elif features['avg_altitude'] < 2000 and features['circularity'] > 0.7:
        flight.classification = 'rescue'
        flight.classification_source = 'rule'
        flight.auto_classified = False
        logger.debug(f"Classified flight {flight.flight_id} as 'rescue' (rule-based)")
    else:
        try:
            check_is_fitted(analyze_flight.model)
            feature_vector = list(features.values())
            prediction = analyze_flight.model.predict([feature_vector])[0]
            flight.classification = prediction
            flight.classification_source = 'ml'
            flight.auto_classified = True
            with buffer_lock:
                classification_log_buffer.append(f"Classified flight {flight.flight_id} as {prediction} (ML)")
            logger.debug(f"Classified flight {flight.flight_id} as {prediction} (ML)")
        except Exception as e:
            with buffer_lock:
                ml_failure_buffer.append(str(e))
            flight.classification = None
            flight.classification_source = None
            flight.auto_classified = False
            logger.debug(f"ML classification failed for {flight.flight_id}: {e}, using fallback (None)")