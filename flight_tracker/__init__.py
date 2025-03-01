# flight_tracker/__init__.py
from flask import Flask
from flask_socketio import SocketIO
from flight_tracker.utils import logger, setup_logging
from flight_tracker.models import db, FlightPath, MonitoredArea
from flight_tracker.monitoring import init_indexes, start_monitoring_thread
from flight_tracker.analysis import start_buffer_thread
import json
import os
import threading

init_lock = threading.Lock()

socketio = SocketIO()

def initialize_db(app):
    with app.app_context():
        db.create_all()
        for flight in db.session.query(FlightPath).all():
            try:
                points = json.loads(flight.points) if flight.points else []
                if not isinstance(points, list) or (points and not all(isinstance(p, list) for p in points)):
                    logger.warning(f"Fixing corrupt points for {flight.flight_id}: {flight.points}")
                    flight.points = json.dumps([])
                    db.session.commit()
                flight.update_stats()
            except json.JSONDecodeError:
                logger.warning(f"Resetting corrupt JSON for {flight.flight_id}")
                flight.points = json.dumps([])
                db.session.commit()

        if not db.session.query(FlightPath).first() and os.path.exists('initial_data.json'):
            try:
                with open('initial_data.json', 'r') as f:
                    data = json.load(f)
                    for item in data:
                        flight = FlightPath(
                            flight_id=item['flight_id'],
                            points=item['points'],
                            last_updated=item['points'][-1][2]
                        )
                        flight.classification = item['classification']
                        flight.auto_classified = item['auto_classified']
                        flight.update_stats()
                        db.session.add(flight)
                    db.session.commit()
                    from flight_tracker.ml_model import train_model
                    train_model()
                    logger.info("Initial data loaded and model trained")
            except FileNotFoundError:
                logger.warning("initial_data.json not found, skipping initial data load")
            except Exception as e:
                logger.error(f"Failed to load initial data: {e}")
                db.session.rollback()

def create_app():
    app = Flask(__name__)

    uri = 'postgresql://user:password@postgres:5432/flight_tracker'
    logger.info(f"Using database URI: {uri}")
    app.config['SQLALCHEMY_DATABASE_URI'] = uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['selected_classifications'] = set()
    app.config['monitoring_threads'] = {}
    db.init_app(app)
    
    setup_logging(socketio)
    socketio.init_app(app, manage_session=False, async_mode='gevent', ping_timeout=60, ping_interval=25)

    from flight_tracker.routes import register_routes
    register_routes(app, socketio)
    start_buffer_thread(socketio)

    # Move DB initialization to a background thread
    threading.Thread(target=initialize_db, args=(app,), daemon=True).start()

    @socketio.on('connect')
    def handle_connect():
        logger.info("Client connected")
        with app.app_context():
            with init_lock:  # Prevent concurrent thread starts
                areas = MonitoredArea.query.filter_by(is_monitoring=True).all()
                for area in areas:
                    if area.id not in app.config['monitoring_threads']:
                        thread = start_monitoring_thread(app, socketio, area, app.config['selected_classifications'])
                        app.config['monitoring_threads'][area.id] = thread
                logger.info(f"Started monitoring for {len(areas)} areas")

    @socketio.on('disconnect')
    def handle_disconnect(sid=None):
        logger.info("Client disconnected")

    @socketio.on('update_classifications')
    def handle_classifications(data):
        app.config['selected_classifications'] = set(data['classifications'])
        logger.info(f"Updated selected classifications: {app.config['selected_classifications']}")

    @socketio.on_error_default
    def handle_error(e):
        logger.error(f"Socket.IO error: {e}")

    return app

if __name__ == '__main__':
    app = create_app()
    socketio.run(app, host='0.0.0.0', port=5000)