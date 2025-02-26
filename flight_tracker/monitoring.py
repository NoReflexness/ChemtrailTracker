import requests
import time
import threading
import configparser
import json
from flight_tracker.utils import logger
from flight_tracker.models import db, MonitoredArea, FlightPath
from flight_tracker.analysis import analyze_flight
from sqlalchemy.orm import attributes
from sqlalchemy import text

BASE_URL = "https://opensky-network.org/api/states/all"
config = configparser.ConfigParser()
config.read('/root/.config/pyopensky/settings.conf')
USERNAME = config['opensky']['username']
PASSWORD = config['opensky']['password']

credits_used = 0
MAX_CREDITS = 4000

def calculate_credit_cost(lamin, lamax, lomin, lomax):
    area = (lamax - lamin) * (lomax - lomin)
    if area <= 25:
        return 1
    elif area <= 100:
        return 2
    elif area <= 400:
        return 3
    else:
        return 4

def fetch_flight_data(area):
    global credits_used
    cost = calculate_credit_cost(area.lamin, area.lamax, area.lomin, area.lomax)
    if credits_used + cost > MAX_CREDITS:
        logger.warning("Credit limit reached for today.")
        return None
    
    params = {"lamin": area.lamin, "lamax": area.lamax, "lomin": area.lomin, "lomax": area.lomax}
    try:
        response = requests.get(BASE_URL, params=params, auth=(USERNAME, PASSWORD))
        response.raise_for_status()
        states = response.json()
        credits_used += cost
        logger.info(f"Fetched data for area {area.id}. Credits used: {credits_used}/{MAX_CREDITS}")
        return states
    except requests.RequestException as e:
        logger.error(f"Failed to fetch data: {e}")
        return None

def cleanup_old_flights():
    cutoff = int(time.time()) - (24 * 3600)
    db.session.execute(text("DELETE FROM flight_path WHERE last_updated < :cutoff"), {"cutoff": cutoff})
    db.session.commit()
    logger.info("Cleaned up old flights")

def process_states(states, socketio):
    if not states or 'states' not in states:
        logger.warning("No states data to process")
        return
    
    timestamp = states['time']
    flight_updates = []
    new_flights = []
    processed_flight_ids = set()  # Track processed IDs in this cycle
    existing_flights = {f.flight_id: f for f in FlightPath.query.all()}
    batch_size = 500

    for state in states['states']:
        flight_id = state[0]
        lon = state[5]
        lat = state[6]
        alt = state[7] if state[7] is not None else -1
        vel = state[9] if state[9] is not None else -1
        if lat is None or lon is None:
            logger.debug(f"Skipping flight {flight_id} due to missing lat/lon")
            continue

        new_point = [lat, lon, timestamp, alt, vel]
        flight = existing_flights.get(flight_id)

        if flight:
            current_points = flight.points_list
            current_coords = [[p[0], p[1]] for p in current_points]
            if [lat, lon] not in current_coords:
                current_points.append(new_point)
                current_points.sort(key=lambda p: p[2])
                flight.points = json.dumps(current_points)
                attributes.flag_modified(flight, "points")
                flight.last_updated = timestamp
                flight.update_stats()
                analyze_flight(flight)
                flight_updates.append({
                    'flight_id': flight_id,
                    'points': flight.points_list,
                    'classification': flight.classification,
                    'classification_source': flight.classification_source,
                    'avg_altitude': flight.avg_altitude,
                    'avg_velocity': flight.avg_velocity,
                    'duration': flight.duration
                })
                logger.debug(f"Updated flight {flight_id} with new point: {new_point}")
            else:
                logger.debug(f"Duplicate point for {flight_id}, skipping update")
        elif flight_id not in processed_flight_ids:  # Check against processed IDs in this cycle
            new_flight = FlightPath(flight_id=flight_id, points=[new_point], last_updated=timestamp)
            new_flight.update_stats()
            analyze_flight(new_flight)
            flight_updates.append({
                'flight_id': flight_id,
                'points': new_flight.points_list,
                'classification': new_flight.classification,
                'classification_source': new_flight.classification_source,
                'avg_altitude': new_flight.avg_altitude,
                'avg_velocity': new_flight.avg_velocity,
                'duration': new_flight.duration
            })
            new_flights.append(new_flight)
            processed_flight_ids.add(flight_id)  # Add to processed set
            logger.debug(f"Added new flight {flight_id}")
        else:
            logger.debug(f"Flight {flight_id} already processed in this cycle, skipping")

        if len(new_flights) >= batch_size or len(flight_updates) >= batch_size:
            if new_flights:
                db.session.bulk_save_objects(new_flights)
                db.session.commit()
                logger.info(f"Added {len(new_flights)} new flights")
                for nf in new_flights:
                    existing_flights[nf.flight_id] = nf
                new_flights.clear()
            if flight_updates:
                db.session.commit()
                socketio.emit('flight_batch_update', {'flights': flight_updates})
                logger.info(f"Updated {len(flight_updates)} flights")
                flight_updates.clear()

    if new_flights:
        db.session.bulk_save_objects(new_flights)
        db.session.commit()
        logger.info(f"Added {len(new_flights)} new flights")
    if flight_updates:
        db.session.commit()
        socketio.emit('flight_batch_update', {'flights': flight_updates})
        logger.info(f"Updated {len(flight_updates)} flights")
    elif not new_flights:
        logger.debug("No flight updates to emit")

def monitor_area(app, socketio, area, frequency):
    while True:
        with app.app_context():
            current_area = MonitoredArea.query.get(area.id)
            if not current_area or not current_area.is_monitoring:
                logger.info(f"Area ID {area.id} no longer exists or stopped, stopping thread")
                break
            states = fetch_flight_data(area)
            if states:
                process_states(states, socketio)
            cleanup_old_flights()
        time.sleep(frequency)

def start_monitoring_thread(app, socketio, area):
    freq = {'30s': 30, '1m': 60, '5m': 300}[area.frequency]
    thread = threading.Thread(target=monitor_area, args=(app, socketio, area, freq))
    thread.daemon = True
    thread.start()

def start_monitoring(app, socketio):
    with app.app_context():
        areas = MonitoredArea.query.all()
        for area in areas:
            if area.is_monitoring:
                start_monitoring_thread(app, socketio, area)

def init_indexes():
    db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_flight_id ON flight_path (flight_id)"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_last_updated ON flight_path (last_updated)"))
    db.session.commit()
    logger.info("Database indexes created")