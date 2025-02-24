import sqlite3
import pandas as pd
from datetime import datetime

# Unusual flight paths: tight turns and loops
test_data = [
    # Flight 1: Tight zigzag pattern (Survey-like)
    {'icao24': 'abc123', 'latitude': 54.20, 'longitude': 7.10, 'timestamp': 1740417409},
    {'icao24': 'abc123', 'latitude': 54.21, 'longitude': 7.15, 'timestamp': 1740417410},
    {'icao24': 'abc123', 'latitude': 54.20, 'longitude': 7.20, 'timestamp': 1740417411},
    {'icao24': 'abc123', 'latitude': 54.21, 'longitude': 7.25, 'timestamp': 1740417412},
    {'icao24': 'abc123', 'latitude': 54.20, 'longitude': 7.30, 'timestamp': 1740417413},
    {'icao24': 'abc123', 'latitude': 54.21, 'longitude': 7.35, 'timestamp': 1740417414},
    # Flight 2: Circular pattern (Agricultural-like)
    {'icao24': 'def456', 'latitude': 54.30, 'longitude': 7.40, 'timestamp': 1740417409},
    {'icao24': 'def456', 'latitude': 54.32, 'longitude': 7.42, 'timestamp': 1740417410},
    {'icao24': 'def456', 'latitude': 54.34, 'longitude': 7.40, 'timestamp': 1740417411},
    {'icao24': 'def456', 'latitude': 54.32, 'longitude': 7.38, 'timestamp': 1740417412},
    {'icao24': 'def456', 'latitude': 54.30, 'longitude': 7.40, 'timestamp': 1740417413},
]

df = pd.DataFrame(test_data)

# Connect to the external database
conn = sqlite3.connect('/path/to/flightAnalyzerData/states_data.db')
cursor = conn.cursor()

# Ensure the table exists
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

# Insert test data
df.to_sql('states', conn, if_exists='append', index=False)
conn.commit()
conn.close()

print("Test data loaded into states_data.db")