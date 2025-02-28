from flask import render_template, request, jsonify
from flight_tracker.utils import logger
from flight_tracker.models import db, MonitoredArea, FlightPath
from flight_tracker.monitoring import start_monitoring_thread
from flight_tracker.ml_model import train_model

def register_routes(app, socketio):
    @app.route('/add_area', methods=['POST'])
    def add_area():
        data = request.get_json()
        area = MonitoredArea(
            lamin=data['lamin'],
            lamax=data['lamax'],
            lomin=data['lomin'],
            lomax=data['lomax'],
            frequency=data['frequency'],
            is_monitoring=False
        )
        db.session.add(area)
        db.session.commit()
        return jsonify({'message': f'Area {area.id} added', 'area_id': area.id})
    
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/start_monitoring', methods=['POST'])
    def start_monitoring():
        data = request.get_json()
        lamin = data.get('lamin')
        lamax = data.get('lamax')
        lomin = data.get('lomin')
        lomax = data.get('lomax')
        frequency = data.get('frequency')

        if not all([lamin, lamax, lomin, lomax, frequency]):
            return jsonify({'error': 'Missing parameters'}), 400

        area = MonitoredArea(lamin=lamin, lamax=lamax, lomin=lomin, lomax=lomax, frequency=frequency, is_monitoring=True)
        db.session.add(area)
        db.session.commit()
        start_monitoring_thread(app, socketio, area)
        logger.info(f"Started monitoring for area ID {area.id}")
        return jsonify({'message': 'Monitoring started', 'area_id': area.id}), 200

    @app.route('/stop_monitoring', methods=['POST'])
    def stop_monitoring():
        data = request.get_json()
        area_id = data.get('area_id')
        if not area_id:
            logger.error("No area_id provided in stop_monitoring request")
            return jsonify({'error': 'Missing area_id'}), 400

        area = MonitoredArea.query.get(area_id)
        if area:
            area.is_monitoring = False
            db.session.commit()
            logger.info(f"Stopped monitoring for area ID {area_id}")
            return jsonify({'message': 'Monitoring stopped', 'area_id': area_id}), 200
        logger.warning(f"Area ID {area_id} not found for stop_monitoring")
        return jsonify({'error': 'Area not found'}), 404

    @app.route('/areas', methods=['GET'])
    def get_areas():
        areas = MonitoredArea.query.all()
        area_data = [
            {
                'id': area.id,
                'lamin': area.lamin,
                'lamax': area.lamax,
                'lomin': area.lomin,
                'lomax': area.lomax,
                'frequency': area.frequency,
                'is_monitoring': area.is_monitoring
            }
            for area in areas
        ]
        return jsonify(area_data)

    @app.route('/flight_paths', methods=['GET'])
    def get_flight_paths():
        flights = FlightPath.query.all()
        flight_data = [
            {
                'flight_id': flight.flight_id,
                'points': flight.points_list,
                'classification': flight.classification,
                'classification_source': flight.classification_source,
                'avg_altitude': flight.avg_altitude,
                'avg_velocity': flight.avg_velocity,
                'duration': flight.duration
            }
            for flight in flights
        ]
        return jsonify(flight_data)

    @app.route('/update_classification', methods=['POST'])
    def update_classification():
        data = request.get_json()
        flight_id = data.get('flight_id')
        classification = data.get('classification')
        
        if not flight_id or not classification:
            return jsonify({'error': 'Missing flight_id or classification'}), 400

        flight = FlightPath.query.filter_by(flight_id=flight_id).first()
        if flight:
            flight.classification = classification
            flight.auto_classified = False
            flight.classification_source = 'manual'
            db.session.commit()
            socketio.emit('flight_update', {
                'flight_id': flight.flight_id,
                'points': flight.points_list,
                'classification': flight.classification,
                'classification_source': flight.classification_source,
                'avg_altitude': flight.avg_altitude,
                'avg_velocity': flight.avg_velocity,
                'duration': flight.duration
            })
            return jsonify({'message': f'Classification updated for {flight_id}'}), 200
        return jsonify({'error': 'Flight not found'}), 404

    @app.route('/retrain_model', methods=['POST'])
    def retrain_model_endpoint():
        success = train_model()
        if success:
            return jsonify({'message': 'Model retrained successfully'}), 200
        return jsonify({'error': 'Failed to retrain model (insufficient data or error)'}), 400

    @app.route('/delete_area', methods=['POST'])
    def delete_area():
        data = request.get_json()
        area_id = data.get('area_id')
        if not area_id:
            logger.error("No area_id provided in delete_area request")
            return jsonify({'error': 'Missing area_id'}), 400

        area = MonitoredArea.query.get(area_id)
        if area:
            db.session.delete(area)
            db.session.commit()
            logger.info(f"Deleted area ID {area_id}")
            return jsonify({'message': 'Area deleted', 'area_id': area_id}), 200
        logger.warning(f"Area ID {area_id} not found for deletion")
        return jsonify({'error': 'Area not found'}), 404