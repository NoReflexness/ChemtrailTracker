import logging
import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime
import requests
import json
import sqlite3
from flight_analyzer.database import Database
from flight_analyzer.ml_model import classify_pattern, MODEL_PATH

logger = logging.getLogger('FlightAnalyzer')

class FlightPatternAnalyzer:
    def __init__(self):
        logger.info("Initializing FlightPatternAnalyzer")
        self.unusual_flights = []
        self.db = Database('flight_patterns.db')
        self.training_db = Database('training_data.db')
        self.states_db = sqlite3.connect('states_data.db')
        self.init_states_db()

    def init_states_db(self):
        logger.info("Initializing states database")
        cursor = self.states_db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                icao24 TEXT,
                callsign TEXT,
                origin_country TEXT,
                time_position INTEGER,
                last_contact INTEGER,
                longitude REAL,
                latitude REAL,
                baro_altitude REAL,
                on_ground BOOLEAN,
                velocity REAL,
                true_track REAL,
                vertical_rate REAL,
                sensors TEXT,
                geo_altitude REAL,
                squawk TEXT,
                spi BOOLEAN,
                position_source INTEGER,
                timestamp INTEGER
            )
        ''')
        self.states_db.commit()

    def fetch_data(self, lamin, lamax, lomin, lomax):
        logger.info("Fetching data from OpenSky for area: lamin=%s, lamax=%s, lomin=%s, lomax=%s", lamin, lamax, lomin, lomax)
        try:
            url = f"https://opensky-network.org/api/states/all?lamin={lamin}&lamax={lamax}&lomin={lomin}&lomax={lomax}"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            states = data.get('states', [])
            if not states:
                logger.warning("No states retrieved for the specified area")
                return None
            df = pd.DataFrame(states, columns=[
                'icao24', 'callsign', 'origin_country', 'time_position', 'last_contact',
                'longitude', 'latitude', 'baro_altitude', 'on_ground', 'velocity',
                'true_track', 'vertical_rate', 'sensors', 'geo_altitude', 'squawk',
                'spi', 'position_source'
            ])
            df['timestamp'] = data['time']  # Use API's time instead of local time
            self.store_states(df)
            logger.info("Data fetched successfully with %d rows", len(df))
            return df[['icao24', 'latitude', 'longitude']].dropna()
        except Exception as e:
            logger.error("Error fetching data: %s", str(e))
            return None

    def store_states(self, df):
        cursor = self.states_db.cursor()
        df.to_sql('states', self.states_db, if_exists='append', index=False)
        self.states_db.commit()

    def extract_features(self, coords):
        logger.debug("Extracting features from coordinates")
        coords = np.array(coords)
        if len(coords) < 2:
            return None
        distances = []
        angles = []
        for i in range(len(coords)-1):
            lat1, lon1 = radians(coords[i][0]), radians(coords[i][1])
            lat2, lon2 = radians(coords[i+1][0]), radians(coords[i+1][1])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            distance = 6371 * 2 * atan2(sqrt(a), sqrt(1-a))
            distances.append(distance)
            y = sin(dlon) * cos(lat2)
            x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
            angles.append(atan2(y, x))
        
        angle_changes = np.abs(np.diff(angles)) if angles else [0]
        features = {
            'avg_distance': np.mean(distances) if distances else 0,
            'distance_var': np.var(distances) if distances else 0,
            'turn_count': sum(1 for change in angle_changes if 1.3 < change < 1.8),
            'path_length': len(coords)
        }
        logger.debug("Features extracted: %s", features)
        return features

    def analyze_path_pattern(self, df_group):
        logger.debug("Analyzing path pattern")
        coords = df_group[['latitude', 'longitude']].values
        features = self.extract_features(coords)
        if not features or features['path_length'] < 10:
            return False
        return features['turn_count'] >= 4 and features['distance_var'] < (features['avg_distance'] * 0.3)

    def analyze_flights(self, flight_data):
        logger.info("Analyzing flights")
        self.unusual_flights = []
        cursor = self.db.get_cursor()
        for icao, group in flight_data.groupby('icao24'):
            if self.analyze_path_pattern(group):
                coords = group[['latitude', 'longitude']].values.tolist()
                features = self.extract_features(coords)
                pattern_type = classify_pattern(features)
                self.unusual_flights.append({
                    'icao24': icao,
                    'coords': coords,
                    'pattern_type': pattern_type
                })
                coords_str = json.dumps(coords)
                cursor.execute('INSERT INTO patterns (icao24, coords, pattern_type) VALUES (?, ?, ?)',
                               (icao, coords_str, pattern_type))
                logger.info("Flight %s identified as %s", icao, pattern_type)
        self.db.commit()
        logger.info("Flight analysis completed")

    def generate_report(self):
        logger.info("Generating report")
        return pd.DataFrame(self.unusual_flights)

    def get_stored_states(self, start_date, end_date):
        logger.info("Retrieving stored states for %s to %s", start_date, end_date)
        start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp())
        end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp())
        query = "SELECT icao24, latitude, longitude FROM states WHERE timestamp BETWEEN ? AND ?"
        df = pd.read_sql_query(query, self.states_db, params=(start_ts, end_ts))
        return df.dropna()