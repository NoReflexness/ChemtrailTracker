# flight_tracker/features.py
import numpy as np
from flight_tracker.utils import logger

def extract_features(points):
    if not points:
        logger.debug("No points provided, returning default features")
        return {
            'avg_altitude': -1,
            'avg_velocity': -1,
            'turns_per_point': 0,
            'parallelism_score': 0,
            'circularity': 0,
            'zig_zag_count': 0,
            'segment_length_std': 0,
            'altitude_variability': 0
        }

    valid_points = [p for p in points if isinstance(p, list) and len(p) >= 3]
    if len(valid_points) < 1:
        logger.debug(f"Invalid points data: {points}, returning default features")
        return {
            'avg_altitude': -1,
            'avg_velocity': -1,
            'turns_per_point': 0,
            'parallelism_score': 0,
            'circularity': 0,
            'zig_zag_count': 0,
            'segment_length_std': 0,
            'altitude_variability': 0
        }

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
                if cos_angle < 0.7:
                    turns += 1

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

    circularity = 0
    if len(lat_lons) > 5:
        x = [p[1] for p in lat_lons]
        y = [p[0] for p in lat_lons]
        x_m, y_m = np.mean(x), np.mean(y)
        u = [xi - x_m for xi in x]
        v = [yi - y_m for yi in y]
        Suu = sum(ui * ui for ui in u)
        Svv = sum(vi * vi for vi in v)
        Suv = sum(ui * vi for ui, vi in zip(u, v))
        radius = np.sqrt((Suu + Svv) / len(lat_lons)) if (Suu + Svv) > 0 else 0
        residuals = [abs(np.sqrt((xi - x_m)**2 + (yi - y_m)**2) - radius) for xi, yi in zip(x, y)]
        circularity = 1 - (np.mean(residuals) / radius) if radius > 0 else 0

    zig_zag_count = 0
    if len(angles) > 2:
        for i in range(len(angles) - 1):
            angle_diff = abs((angles[i+1] - angles[i] + 180) % 360 - 180)
            if angle_diff > 45 and angle_diff < 135:
                zig_zag_count += 1
        zig_zag_count /= len(lat_lons)

    segment_lengths = []
    for i in range(len(lat_lons) - 1):
        dx = (lat_lons[i+1][1] - lat_lons[i][1]) * 111.32 * np.cos(lat_lons[i][0] * np.pi / 180)
        dy = (lat_lons[i+1][0] - lat_lons[i][0]) * 111.32
        segment_lengths.append(np.sqrt(dx**2 + dy**2))

    features = {
        'avg_altitude': np.mean(altitudes) if any(a != -1 for a in altitudes) else -1,
        'avg_velocity': np.mean(velocities) if any(v != -1 for v in velocities) else -1,
        'turns_per_point': turns / len(valid_points) if len(valid_points) > 1 else 0,
        'parallelism_score': parallelism_score,
        'circularity': circularity,
        'zig_zag_count': zig_zag_count,
        'segment_length_std': np.std(segment_lengths) if segment_lengths else 0,
        'altitude_variability': np.std([a for a in altitudes if a != -1]) if any(a != -1 for a in altitudes) else 0
    }
    logger.debug(f"Extracted features for points {len(valid_points)}: {features}")
    return features