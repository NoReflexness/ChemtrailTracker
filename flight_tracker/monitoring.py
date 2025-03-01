import requests
import time
import threading
import configparser
import json
from flight_tracker.utils import logger
from flight_tracker.models import db, MonitoredArea, FlightPath
from flight_tracker.analysis import analyze_flight
from sqlalchemy.orm import attributes, scoped_session, sessionmaker
from sqlalchemy import text
import sqlalchemy.exc

BASE_URL = "https://opensky-network.org/api/states/all"
config = configparser.ConfigParser()
config.read('/root/.config/pyopensky/settings.conf')
USERNAME = config['opensky']['username']
PASSWORD = config['opensky']['password']

credits_used = 0
MAX_CREDITS = 4000
batch_lock = threading.Lock()

def get_session():
    """Create a thread-local scoped session."""
    if not hasattr(threading.current_thread(), '_session_factory'):
        threading.current_thread()._session_factory = sessionmaker(bind=db.engine)
    return scoped_session(threading.current_thread()._session_factory)

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
        response = requests.get(BASE_URL, params=params, auth=(USERNAME, PASSWORD), timeout=30)
        response.raise_for_status()
        states = response.json()
        if not states or 'states' not in states or states['states'] is None:
            logger.warning(f"Invalid API response for area {area.id}: {states}")
            return None
        states_count = len(states['states'])
        logger.info(f"Fetched {states_count} states for area {area.id}")
        for state in states['states']:
            if not all(isinstance(state[i], (int, float, str, type(None))) for i in [0, 5, 6, 7, 9]):
                logger.warning(f"Invalid state data for flight {state[0]}: {state}")
                states['states'] = [s for s in states['states'] if all(isinstance(s[i], (int, float, str, type(None))) for i in [0, 5, 6, 7, 9])]
                break
        credits_used += cost
        logger.info(f"Fetched data for area {area.id}. Credits used: {credits_used}/{MAX_CREDITS}")
        return states
    except requests.RequestException as e:
        logger.error(f"Failed to fetch data for area {area.id}: {e}")
        return None

def cleanup_old_flights(session, socketio):  # Add socketio param
    cutoff = int(time.time()) - (24 * 3600)
    try:
        result = session.execute(
            text("DELETE FROM flight_path WHERE last_updated < :cutoff RETURNING flight_id"),
            {"cutoff": cutoff}
        )
        deleted_flight_ids = [row[0] for row in result]
        session.commit()
        logger.debug("Cleaned up old flights")
        if deleted_flight_ids:
            socketio.emit('flight_cleanup', {'flight_ids': deleted_flight_ids})
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        session.rollback()

def process_states(states, socketio):
    if not states or 'states' not in states or states['states'] is None:
        logger.warning(f"No valid states data to process: {states}")
        return
    
    timestamp = states['time']
    flight_updates = []
    new_flights = []
    processed_flight_ids = set()
    batch_size = 500
    update_buffer = []

    session = get_session()
    try:
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
            if flight_id in processed_flight_ids:
                continue

            flight = session.get(FlightPath, flight_id)
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
                    update_buffer.append({
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
                new_flight = FlightPath(flight_id=flight_id, points=[new_point], last_updated=timestamp)
                new_flight.update_stats()
                analyze_flight(new_flight)
                new_flights.append(new_flight)
                processed_flight_ids.add(flight_id)
                update_buffer.append({
                    'flight_id': new_flight.flight_id,
                    'points': new_flight.points_list,
                    'classification': new_flight.classification,
                    'classification_source': new_flight.classification_source,
                    'avg_altitude': new_flight.avg_altitude,
                    'avg_velocity': new_flight.avg_velocity,
                    'duration': new_flight.duration
                })
                logger.debug(f"Queued new flight {flight_id}")

            if len(new_flights) >= batch_size or len(update_buffer) >= batch_size:
                with batch_lock:
                    try:
                        if new_flights:
                            session.execute(
                                text("""
                                    INSERT INTO flight_path (flight_id, points, last_updated, auto_classified, avg_altitude, avg_velocity, duration)
                                    VALUES (:flight_id, :points, :last_updated, :auto_classified, :avg_altitude, :avg_velocity, :duration)
                                    ON CONFLICT (flight_id) DO UPDATE
                                    SET points = EXCLUDED.points,
                                        last_updated = EXCLUDED.last_updated,
                                        auto_classified = EXCLUDED.auto_classified,
                                        avg_altitude = EXCLUDED.avg_altitude,
                                        avg_velocity = EXCLUDED.avg_velocity,
                                        duration = EXCLUDED.duration
                                """),
                                [{
                                    'flight_id': nf.flight_id,
                                    'points': nf.points,
                                    'last_updated': nf.last_updated,
                                    'auto_classified': nf.auto_classified,
                                    'avg_altitude': nf.avg_altitude,
                                    'avg_velocity': nf.avg_velocity,
                                    'duration': nf.duration
                                } for nf in new_flights]
                            )
                            session.commit()
                            logger.info(f"Upserted {len(new_flights)} new flights")
                            new_flights.clear()

                        if update_buffer:
                            flight_updates.extend(update_buffer)
                            logger.debug(f"Emitting {len(flight_updates)} flights in batch")
                            while flight_updates:
                                batch = flight_updates[:100]
                                socketio.emit('flight_batch_update', {'flights': batch})
                                flight_updates = flight_updates[100:]
                                logger.debug(f"Sent batch of {len(batch)} flights")
                            session.commit()
                            update_buffer.clear()
                            socketio.sleep(0.1)
                    except Exception as e:
                        logger.error(f"Error during batch processing: {e}")
                        session.rollback()
                        new_flights.clear()
                        update_buffer.clear()
                        flight_updates.clear()

        with batch_lock:
            try:
                if new_flights:
                    session.execute(
                        text("""
                            INSERT INTO flight_path (flight_id, points, last_updated, auto_classified, avg_altitude, avg_velocity, duration)
                            VALUES (:flight_id, :points, :last_updated, :auto_classified, :avg_altitude, :avg_velocity, :duration)
                            ON CONFLICT (flight_id) DO UPDATE
                            SET points = EXCLUDED.points,
                                last_updated = EXCLUDED.last_updated,
                                auto_classified = EXCLUDED.auto_classified,
                                avg_altitude = EXCLUDED.avg_altitude,
                                avg_velocity = EXCLUDED.avg_velocity,
                                duration = EXCLUDED.duration
                        """),
                        [{
                            'flight_id': nf.flight_id,
                            'points': nf.points,
                            'last_updated': nf.last_updated,
                            'auto_classified': nf.auto_classified,
                            'avg_altitude': nf.avg_altitude,
                            'avg_velocity': nf.avg_velocity,
                            'duration': nf.duration
                        } for nf in new_flights]
                    )
                    session.commit()
                    logger.info(f"Upserted {len(new_flights)} new flights")
                    new_flights.clear()

                if update_buffer:
                    flight_updates.extend(update_buffer)
                    logger.debug(f"Emitting final {len(flight_updates)} flights")
                    while flight_updates:
                        batch = flight_updates[:100]
                        socketio.emit('flight_batch_update', {'flights': batch})
                        flight_updates = flight_updates[100:]
                        logger.debug(f"Sent final batch of {len(batch)} flights")
                    session.commit()
                    update_buffer.clear()
            except Exception as e:
                logger.error(f"Error during final batch processing: {e}")
                session.rollback()
    finally:
        session.remove()



def monitor_area(app, socketio, area, frequency):
    while True:
        with app.app_context():
            session = get_session()
            try:
                current_area = session.get(MonitoredArea, area.id)
                if not current_area or not current_area.is_monitoring:
                    logger.info(f"Area ID {area.id} no longer exists or stopped, stopping thread")
                    break
                states = fetch_flight_data(area)
                if states:
                    process_states(states, socketio)
                cleanup_old_flights(session, socketio)  # Pass socketio
            finally:
                session.remove()
        time.sleep(frequency)

def start_monitoring_thread(app, socketio, area):
    freq = {'30s': 30, '1m': 60, '5m': 300}[area.frequency]
    thread = threading.Thread(target=monitor_area, args=(app, socketio, area, freq))
    thread.daemon = True
    thread.start()

def start_monitoring(app, socketio):
    with app.app_context():
        session = get_session()
        try:
            areas = session.query(MonitoredArea).all()
            for area in areas:
                if area.is_monitoring:
                    start_monitoring_thread(app, socketio, area)
        finally:
            session.remove()

def init_indexes():
    with app.app_context():
        session = get_session()
        try:
            session.execute(text("CREATE INDEX IF NOT EXISTS idx_flight_id ON flight_path (flight_id)"))
            session.execute(text("CREATE INDEX IF NOT EXISTS idx_last_updated ON flight_path (last_updated)"))
            session.commit()
            logger.info("Database indexes created")
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            session.rollback()
        finally:
            session.remove()

