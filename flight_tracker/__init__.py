from flask import Flask
from flask_socketio import SocketIO
from sqlalchemy import text
from flight_tracker.utils import logger, setup_logging
from flight_tracker.models import db, init_db, FlightPath
from flight_tracker.monitoring import init_indexes
from flight_tracker.analysis import start_buffer_thread  # Import this
import json
import os

def create_app():
    app = Flask(__name__)
    socketio = SocketIO(app)

    setup_logging(socketio)

    from flight_tracker.routes import register_routes
    from flight_tracker.monitoring import start_monitoring

    init_db(app)
    
    with app.app_context():
        # Enable WAL mode
        db.session.execute(text("PRAGMA journal_mode=WAL"))
        db.session.commit()
        
        init_indexes()
        for flight in FlightPath.query.all():
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

        if not FlightPath.query.first() and os.path.exists('initial_data.json'):
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

    register_routes(app, socketio)
    start_buffer_thread(socketio)

    @socketio.on('connect')
    def handle_connect():
        logger.info("Client connected")
        start_monitoring(app, socketio)

    return app, socketio