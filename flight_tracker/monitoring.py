# flight_tracker/monitoring.py
import threading
import time
from flight_tracker.utils import logger
from flight_tracker.models import db, MonitoredArea
from flight_tracker.fetch import fetch_flight_data
from flight_tracker.processing import process_states, cleanup_old_flights

def monitor_area(app, socketio, area, frequency, selected_classifications):
    last_update_time = 0
    update_interval = 10  # Send updates every 10 seconds
    while True:
        with app.app_context():
            session = db.session
            try:
                current_area = session.get(MonitoredArea, area.id)
                if not current_area or not current_area.is_monitoring:
                    logger.info(f"Area ID {area.id} no longer exists or stopped, stopping thread")
                    if area.id in app.config['monitoring_threads']:
                        del app.config['monitoring_threads'][area.id]
                    break
                states = fetch_flight_data(current_area)
                if states:
                    current_time = time.time()
                    if current_time - last_update_time >= update_interval:
                        process_states(states, socketio, selected_classifications)
                        last_update_time = current_time
                cleanup_old_flights(session, socketio)
            except Exception as e:
                logger.error(f"Error in monitoring area {area.id}: {e}")
            finally:
                session.close()
        time.sleep(frequency)

def start_monitoring_thread(app, socketio, area, selected_classifications):
    freq_map = {'30s': 30, '1m': 60, '5m': 300}
    frequency = freq_map.get(area.frequency, 30)
    thread = threading.Thread(
        target=monitor_area,
        args=(app, socketio, area, frequency, selected_classifications),
        daemon=True,
        name=f"monitor_area_{area.id}"
    )
    thread.start()
    logger.info(f"Started monitoring thread for area {area.id} with frequency {area.frequency}")
    return thread

def start_monitoring(app, socketio, selected_classifications):
    with app.app_context():
        session = db.session
        try:
            areas = session.query(MonitoredArea).filter_by(is_monitoring=True).all()
            for area in areas:
                if area.id not in app.config['monitoring_threads']:
                    thread = start_monitoring_thread(app, socketio, area, selected_classifications)
                    app.config['monitoring_threads'][area.id] = thread
            logger.info(f"Started monitoring for {len(areas)} areas")
        except Exception as e:
            logger.error(f"Error starting monitoring: {e}")
        finally:
            session.close()

def init_indexes():
    with db.session() as session:
        try:
            session.execute("CREATE INDEX IF NOT EXISTS idx_flight_id ON flight_path (flight_id)")
            session.execute("CREATE INDEX IF NOT EXISTS idx_last_updated ON flight_path (last_updated)")
            session.commit()
            logger.info("Database indexes created")
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            session.rollback()