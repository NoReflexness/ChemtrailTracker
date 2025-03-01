# flight_tracker/analysis.py (updated)
from sklearn.ensemble import RandomForestClassifier
from sklearn.utils.validation import check_is_fitted
import numpy as np
from flight_tracker.utils import logger
from flight_tracker.ml_model import load_model, save_model
import threading
import time

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

    # Turns
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

    # Parallelism (grid-like)
    parallelism_score = 0
    angles = []
    if len(lat_lons) > 3:
        for i in range(len(lat_lons) - 1):
            dx = lat_lons[i+1][1] - lat_lons[i][1]
            dy = lat_lons[i+1][0] - lat_lons[i][0]
            angle = np.arctan2(dy, dx) * 180 / np.pi
            angles.append(angle)
        for i in range(len(angles) - 2):
            if abs((angles[i] - angles[i+2] + 180) % 360 - 180) < 10:
                parallelism_score += 1
        parallelism_score /= len(lat_lons)

    # Circularity
    circularity = 0
    if len(lat_lons) > 5:
        x = [p[1] for p in lat_lons]
        y = [p[0] for p in lat_lons]
        x_m = np.mean(x)
        y_m = np.mean(y)
        u = [xi - x_m for xi in x]
        v = [yi - y_m for yi in y]
        Suu = sum(ui * ui for ui in u)
        Svv = sum(vi * vi for vi in v)
        Suv = sum(ui * vi for ui, vi in zip(u, v))
        radius = np.sqrt((Suu + Svv) / len(lat_lons)) if (Suu + Svv) > 0 else 0
        residuals = [abs(np.sqrt((xi - x_m)**2 + (yi - y_m)**2) - radius) for xi, yi in zip(x, y)]
        circularity = 1 - (np.mean(residuals) / radius) if radius > 0 else 0

    # Zig-zag
    zig_zag_count = 0
    if len(angles) > 2:
        for i in range(len(angles) - 1):
            angle_diff = abs((angles[i+1] - angles[i] + 180) % 360 - 180)
            if angle_diff > 45 and angle_diff < 135:
                zig_zag_count += 1
        zig_zag_count /= len(lat_lons)

    # Additional features (Suggestion 1)
    segment_lengths = []
    for i in range(len(lat_lons) - 1):
        dx = (lat_lons[i+1][1] - lat_lons[i][1]) * 111.32 * np.cos(lat_lons[i][0] * np.pi / 180)
        dy = (lat_lons[i+1][0] - lat_lons[i][0]) * 111.32
        segment_lengths.append(np.sqrt(dx**2 + dy**2))
    segment_length_std = np.std(segment_lengths) if segment_lengths else 0
    altitude_variability = np.std([a for a in altitudes if a != -1]) if any(a != -1 for a in altitudes) else 0

    features = [
        np.mean(altitudes) if any(a != -1 for a in altitudes) else -1,
        np.mean(velocities) if any(v != -1 for v in velocities) else -1,
        turns / len(valid_points) if valid_points else 0,
        parallelism_score,
        circularity,
        zig_zag_count,
        segment_length_std,
        altitude_variability
    ]

    # Rule-based classification
    if features[0] > 5000 and features[1] > 100:
        flight.classification = 'commercial'
        flight.classification_source = 'rule'
        flight.auto_classified = False
    elif features[0] < 1000 and features[2] > 0.1:
        flight.classification = 'survey'
        flight.classification_source = 'rule'
        flight.auto_classified = False
    elif features[0] < 2000 and features[1] < 50 and features[3] > 0.2:
        flight.classification = 'cloud seeding'
        flight.classification_source = 'rule'
        flight.auto_classified = False
    elif features[0] < 1000 and features[5] > 0.3:
        flight.classification = 'crop dusting'
        flight.classification_source = 'rule'
        flight.auto_classified = False
    elif features[0] < 2000 and features[4] > 0.7:
        flight.classification = 'rescue'
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