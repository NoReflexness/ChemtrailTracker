# flight_tracker/processing.py
import json
import time
import threading
from sqlalchemy.orm import attributes
from flight_tracker.utils import logger
from flight_tracker.models import db, FlightPath
from flight_tracker.analysis import analyze_flight
from sqlalchemy import text

batch_lock = threading.Lock()

def cleanup_old_flights(session, socketio):
    cutoff = int(time.time()) - (24 * 3600)
    try:
        result = session.execute(
            text("DELETE FROM flight_path WHERE last_updated < :cutoff RETURNING flight_id"),
            {"cutoff": cutoff}
        )
        deleted_flight_ids = [row[0] for row in result]
        session.commit()
        logger.debug(f"Cleaned up {len(deleted_flight_ids)} old flights")
        if deleted_flight_ids:
            socketio.emit('flight_cleanup', {'flight_ids': deleted_flight_ids})
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        session.rollback()

def process_states(states, socketio, selected_classifications=None):
    if not states or 'states' not in states or states['states'] is None:
        logger.warning(f"No valid states data to process: {states}")
        return
    
    timestamp = states['time']
    flight_updates = []
    new_flights = []
    processed_flight_ids = set()
    batch_size = 500
    update_buffer = []
    
    session = db.session
    
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
                    if not selected_classifications or flight.classification in selected_classifications:
                        update_buffer.append({
                            'flight_id': flight.flight_id,
                            'points': flight.points_list,
                            'classification': flight.classification,
                            'classification_source': flight.classification_source,
                            'avg_altitude': flight.avg_altitude,
                            'avg_velocity': flight.avg_velocity,
                            'duration': flight.duration
                        })
                    logger.debug(f"Updated flight {flight_id} with new point")
            else:
                new_flight = FlightPath(flight_id=flight_id, points=[new_point], last_updated=timestamp)
                new_flight.update_stats()
                analyze_flight(new_flight)
                new_flights.append(new_flight)
                processed_flight_ids.add(flight_id)
                if not selected_classifications or new_flight.classification in selected_classifications:
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
                            session.bulk_save_objects(new_flights)
                            session.commit()
                            logger.info(f"Inserted {len(new_flights)} new flights")
                            new_flights.clear()
                        
                        if update_buffer:
                            flight_updates.extend(update_buffer)
                            while flight_updates:
                                batch = flight_updates[:100]
                                socketio.emit('flight_batch_update', {'flights': batch})
                                flight_updates = flight_updates[100:]
                                logger.debug(f"Sent batch of {len(batch)} flights")
                            session.commit()
                            update_buffer.clear()
                            socketio.sleep(0.1)
                    except Exception as e:
                        logger.error(f"Batch processing error: {e}")
                        session.rollback()
                        new_flights.clear()
                        update_buffer.clear()
                        flight_updates.clear()
        
        with batch_lock:
            try:
                if new_flights:
                    session.bulk_save_objects(new_flights)
                    session.commit()
                    logger.info(f"Inserted {len(new_flights)} new flights")
                    new_flights.clear()
                
                if update_buffer:
                    flight_updates.extend(update_buffer)
                    while flight_updates:
                        batch = flight_updates[:100]
                        socketio.emit('flight_batch_update', {'flights': batch})
                        flight_updates = flight_updates[100:]
                        logger.debug(f"Sent final batch of {len(batch)} flights")
                    session.commit()
                    update_buffer.clear()
            except Exception as e:
                logger.error(f"Final batch processing error: {e}")
                session.rollback()
    finally:
        session.close()