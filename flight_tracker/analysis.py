from sklearn.ensemble import RandomForestClassifier
from sklearn.utils.validation import check_is_fitted
import numpy as np
from flight_tracker.utils import logger
from flight_tracker.ml_model import load_model, save_model
import threading
import time

# Buffers for logs
classification_log_buffer = []
ml_failure_buffer = []
buffer_lock = threading.Lock()
first_ml_failure_logged = False  # Track if we've logged the detailed message once

def flush_log_buffers(socketio):
    """Emit buffered logs every 5 seconds."""
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
                    # Log detailed message once
                    socketio.emit('log', {'message': f"ML model not fitted or failed: {ml_failure_buffer[0]}"})
                    first_ml_failure_logged = True
                # Summarize subsequent failures
                socketio.emit('log', {'message': f"ML not fitted for {count} flights, using rule-based fallback"})
                ml_failure_buffer.clear()

def start_buffer_thread(socketio):
    """Start the buffer flush thread."""
    thread = threading.Thread(target=flush_log_buffers, args=(socketio,), daemon=True)
    thread.start()

def analyze_flight(flight):
    if not hasattr(analyze_flight, 'model'):
        analyze_flight.model = load_model() or RandomForestClassifier(n_estimators=100, random_state=42)

    points = flight.points_list or []
    if not points or len(points) < 2:
        flight.classification = None
        flight.classification_source = None
        flight.auto_classified = False
        return

    valid_points = [p for p in points if isinstance(p, list) and len(p) >= 3]
    if len(valid_points) < 2:
        logger.warning(f"Invalid points data for flight {flight.flight_id}: {points}")
        flight.classification = None
        flight.classification_source = None
        flight.auto_classified = False
        return

    altitudes = [p[3] if len(p) > 3 and p[3] != -1 else -1 for p in valid_points]
    velocities = [p[4] if len(p) > 4 and p[4] != -1 else -1 for p in valid_points]
    lat_lons = [(p[0], p[1]) for p in valid_points]
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
                if cos_angle < 0.7:  # ~45° turn
                    turns += 1

    features = [
        np.mean(altitudes) if any(a != -1 for a in altitudes) else -1,
        np.mean(velocities) if any(v != -1 for v in velocities) else -1,
        turns / len(valid_points) if valid_points else 0
    ]

    if features[0] > 5000 and features[1] > 100:
        flight.classification = 'commercial'
        flight.classification_source = 'rule'
        flight.auto_classified = False
    elif features[0] < 1000 and features[2] > 0.1:
        flight.classification = 'survey'
        flight.classification_source = 'rule'
        flight.auto_classified = False
    elif features[0] < 2000 and features[1] < 50:
        flight.classification = 'cloud seeding'
        flight.classification_source = 'rule'
        flight.auto_classified = False
    else:
        try:
            check_is_fitted(analyze_flight.model)
            prediction = analyze_flight.model.predict([features])[0]
            flight.classification = prediction
            flight.classification_source = 'ml'
            flight.auto_classified = True
            with buffer_lock:
                classification_log_buffer.append(f"Classified flight {flight.flight_id} as {prediction} (ML)")
        except Exception as e:
            with buffer_lock:
                ml_failure_buffer.append(str(e))
            flight.classification = None
            flight.classification_source = None
            flight.auto_classified = False