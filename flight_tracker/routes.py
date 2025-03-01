# flight_tracker/routes.py
from flask import render_template, request, jsonify
from flight_tracker.utils import logger
from flight_tracker.models import db, MonitoredArea, FlightPath, Classification
from flight_tracker.monitoring import start_monitoring_thread
from flight_tracker.ml_model import train_model
from flight_tracker.analysis import analyze_flight
from sklearn.utils.validation import check_is_fitted

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
        start_monitoring_thread(app, socketio, area, app.config['selected_classifications'])
        logger.info(f"Started monitoring for area ID {area.id}")
        return jsonify({'message': 'Monitoring started', 'area_id': area.id}), 200

    @app.route('/start_monitoring_existing', methods=['POST'])
    def start_monitoring_existing():
        data = request.get_json()
        area_id = data.get('area_id')
        frequency = data.get('frequency')
        if not area_id or not frequency:
            return jsonify({'error': 'Missing area_id or frequency'}), 400
        area = MonitoredArea.query.get(area_id)
        if not area:
            return jsonify({'error': 'Area not found'}), 404
        if not area.is_monitoring:
            area.is_monitoring = True
            area.frequency = frequency
            db.session.commit()
            start_monitoring_thread(app, socketio, area, app.config['selected_classifications'])
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
            if area.is_monitoring:
                area.is_monitoring = False
                db.session.commit()
                logger.info(f"Stopped monitoring for area ID {area_id}")
            return jsonify({'message': 'Monitoring stopped', 'area_id': area_id}), 200
        logger.warning(f"Area ID {area_id} not found for stop_monitoring, possibly already deleted")
        return jsonify({'message': 'Monitoring stopped or area already deleted', 'area_id': area_id}), 200

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
                'is_monitoring': area.is_monitoring,
                'name': area.name
            }
            for area in areas
        ]
        return jsonify(area_data)

    @app.route('/flight_paths', methods=['GET'])
    def get_flight_paths():
        classifications = request.args.getlist('classifications')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 1000))  # Default to 1000 flights per page
        query = FlightPath.query
        if classifications:
            if 'N/A' in classifications:
                classifications.remove('N/A')
                query = query.filter(
                    (FlightPath.classification.in_(classifications)) | 
                    (FlightPath.classification.is_(None))
                )
            else:
                query = query.filter(FlightPath.classification.in_(classifications))
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
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
            for flight in paginated.items
        ]
        logger.debug(f"Returning {len(flight_data)} flights for classifications: {classifications}, page: {page}")
        return jsonify({
            'flights': flight_data,
            'total': paginated.total,
            'pages': paginated.pages,
            'page': page
        })

    @app.route('/flight_count', methods=['GET'])
    def get_flight_count():
        count = FlightPath.query.distinct(FlightPath.flight_id).count()
        logger.debug(f"Total tracked flights: {count}")
        return jsonify({'count': count})

    @app.route('/flight_path/<flight_id>', methods=['GET'])
    def get_flight_path(flight_id):
        flight = FlightPath.query.get(flight_id)
        if flight:
            return jsonify({
                'flight_id': flight.flight_id,
                'points': flight.points_list,
                'classification': flight.classification,
                'classification_source': flight.classification_source,
                'avg_altitude': flight.avg_altitude,
                'avg_velocity': flight.avg_velocity,
                'duration': flight.duration
            })
        return jsonify({'error': 'Flight not found'}), 404

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

    @app.route('/update_area_name', methods=['POST'])
    def update_area_name():
        data = request.get_json()
        area_id = data.get('area_id')
        name = data.get('name')
        if not area_id or not name:
            return jsonify({'error': 'Missing area_id or name'}), 400
        area = MonitoredArea.query.get(area_id)
        if area:
            area.name = name
            db.session.commit()
            logger.info(f"Area {area_id} renamed to {name}")
            return jsonify({'message': 'Area name updated'}), 200
        return jsonify({'error': 'Area not found'}), 404

    @app.route('/area_classifications', methods=['GET'])
    def get_area_classifications():
        area_id = request.args.get('area_id')
        if area_id == 'all':
            flights = FlightPath.query.all()
        else:
            area = MonitoredArea.query.get(area_id)
            if not area:
                return jsonify({'error': 'Area not found'}), 404
            flights = []
            all_flights = FlightPath.query.all()
            for flight in all_flights:
                points = flight.points_list
                if any(p[0] >= area.lamin and p[0] <= area.lamax and p[1] >= area.lomin and p[1] <= area.lomax for p in points):
                    flights.append(flight)
        classifications = {}
        for flight in flights:
            cls = flight.classification or 'N/A'
            classifications[cls] = classifications.get(cls, 0) + 1
        logger.debug(f"Area {area_id} classifications: {classifications}")
        return jsonify(classifications)

    @app.route('/classifications', methods=['GET'])
    def get_classifications():
        classifications = Classification.query.all()
        return jsonify([{'name': c.name, 'color': c.color} for c in classifications])

    @app.route('/add_classification', methods=['POST'])
    def add_classification():
        data = request.get_json()
        name = data.get('name')
        color = data.get('color')
        if not name or not color:
            return jsonify({'error': 'Missing name or color'}), 400
        if Classification.query.filter_by(name=name).first():
            return jsonify({'error': 'Classification already exists'}), 400
        classification = Classification(name=name, color=color)
        db.session.add(classification)
        db.session.commit()
        logger.info(f"Added classification {name} with color {color}")
        return jsonify({'message': 'Classification added'}), 200

    @app.route('/ml_stats', methods=['GET'])
    def get_ml_stats():
        flights = FlightPath.query.filter_by(auto_classified=False).filter(FlightPath.classification.isnot(None)).all()
        samples = len(flights)
        classes = len(set(f.classification for f in flights))
        retrainRecommended = samples >= 10 and classes > 1
        # Use check_is_fitted to determine if the model is trained
        status = 'Not loaded'
        if hasattr(analyze_flight, 'model') and analyze_flight.model is not None:
            try:
                check_is_fitted(analyze_flight.model)
                status = 'Trained'
            except:
                status = 'Loaded but not trained'
        return jsonify({
            'status': status,
            'samples': samples,
            'classes': classes,
            'retrainRecommended': retrainRecommended
        })