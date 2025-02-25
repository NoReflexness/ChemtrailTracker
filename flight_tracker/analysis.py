from flight_tracker import logger
import math
import json
import csv
from flight_tracker.ml_model import predict_classification

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance between two points in degrees."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return math.degrees(c)

def classify_path(points):
    """Rule-based classification as fallback."""
    if len(points) < 3:
        return None

    direction_changes = 0
    total_distance = 0
    prev_angle = None
    time_delta = points[-1][2] - points[0][2] if points[-1][2] and points[0][2] else 1
    
    for i in range(len(points) - 1):
        lat1, lon1 = points[i][0], points[i][1]
        lat2, lon2 = points[i + 1][0], points[i + 1][1]
        distance = calculate_distance(lat1, lon1, lat2, lon2)
        total_distance += distance

        delta_lon = math.radians(lon2 - lon1)
        lat1, lat2 = math.radians(lat1), math.radians(lat2)
        y = math.sin(delta_lon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(delta_lon)
        angle = math.degrees(math.atan2(y, x))

        if prev_angle is not None:
            angle_diff = min(abs(angle - prev_angle), 360 - abs(angle - prev_angle))
            if angle_diff > 30:
                direction_changes += 1
        prev_angle = angle

    avg_speed = total_distance / (time_delta / 3600) if time_delta > 0 else 0
    point_density = len(points) / total_distance if total_distance > 0 else 0

    if direction_changes > len(points) / 3 and point_density > 5:
        return "survey"
    elif total_distance > 0.3 and direction_changes < 2 and avg_speed > 0.1:
        return "a_to_b"
    else:
        return "other"

def analyze_flight(flight):
    """Classify flight using ML if available, otherwise use rule-based."""
    classification = predict_classification(flight.points)
    source = "ml" if classification else "rule"
    
    if classification is None:
        logger.debug(f"No ML prediction for {flight.flight_id}, using rule-based classification")
        classification = classify_path(flight.points)

    if classification:
        flight.classification = classification
        flight.classification_source = source
        flight.auto_classified = True
        logger.info(f"Classified flight {flight.flight_id} as {classification} ({source})")
        latitudes = json.dumps([p[0] for p in flight.points])
        longitudes = json.dumps([p[1] for p in flight.points])
        with open('/data/flight_training_data.csv', 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([flight.flight_id, latitudes, longitudes, classification])
    return classification