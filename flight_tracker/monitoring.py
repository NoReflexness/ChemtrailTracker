import requests
import time
import threading
import configparser
from flight_tracker import app, logger, socketio
from flight_tracker.models import db, MonitoredArea, FlightPath
from flight_tracker.analysis import analyze_flight
from sqlalchemy.orm import attributes

BASE_URL = "https://opensky-network.org/api/states/all"
config = configparser.ConfigParser()
config.read('/root/.config/pyopensky/settings.conf')
USERNAME = config['opensky']['username']
PASSWORD = config['opensky']['password']

credits_used = 0
MAX_CREDITS = 4000

def cleanup_old_flights():
    with app.app_context():
        cutoff = int(time.time()) - (24 * 3600)  # 24 hours ago
        old_flights = FlightPath.query.filter(FlightPath.last_updated < cutoff).all()
        for flight in old_flights:
            db.session.delete(flight)
            logger.info(f"Removed old flight {flight.flight_id}")
        db.session.commit()

def monitor_area(area, frequency):
    while True:
        states = fetch_flight_data(area)
        if states:
            process_states(states)
        cleanup_old_flights()  # Run cleanup each cycle
        time.sleep(frequency)
        
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

def process_states(states):
    if not states or 'states' not in states:
        logger.warning("No states data to process")
        return
    with app.app_context():
        for state in states['states']:
            flight_id = state[0]
            lon = state[5]
            lat = state[6]
            timestamp = states['time']

            if lat is None or lon is None:
                continue

            flight = FlightPath.query.filter_by(flight_id=flight_id).first()
            new_point = [lat, lon, timestamp]
            if flight:
                current_points = flight.points or []
                current_coords = [[p[0], p[1]] for p in current_points]
                if [lat, lon] not in current_coords:
                    current_points.append(new_point)
                    flight.points = current_points
                    attributes.flag_modified(flight, "points")
            else:
                flight = FlightPath(flight_id=flight_id, points=[new_point], last_updated=timestamp)
                db.session.add(flight)
                logger.info(f"New flight {flight_id} added")
            flight.last_updated = timestamp
            analyze_flight(flight)  # Classify after update
            db.session.commit()
            socketio.emit('flight_update', {
                'flight_id': flight_id,
                'points': flight.points,
                'classification': flight.classification
            })

def monitor_area(area, frequency):
    while True:
        states = fetch_flight_data(area)
        if states:
            process_states(states)
        time.sleep(frequency)

def start_monitoring_thread(area):
    freq = {'30s': 30, '1m': 60, '5m': 300}[area.frequency]
    thread = threading.Thread(target=monitor_area, args=(area, freq))
    thread.daemon = True
    thread.start()

def start_monitoring():
    areas = MonitoredArea.query.all()
    for area in areas:
        start_monitoring_thread(area)