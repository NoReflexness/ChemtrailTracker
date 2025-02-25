from flight_tracker import app, socketio
from flask import render_template, request, jsonify
from flight_tracker.models import db, MonitoredArea, FlightPath
from flight_tracker.monitoring import start_monitoring_thread
from flight_tracker.ml_model import train_model

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

    # Remove overlapping areas
    existing_areas = MonitoredArea.query.all()
    for area in existing_areas:
        if (lamin < area.lamax and lamax > area.lamin and 
            lomin < area.lomax and lomax > area.lomin):
            db.session.delete(area)

    area = MonitoredArea(lamin=lamin, lamax=lamax, lomin=lomin, lomax=lomax, frequency=frequency)
    db.session.add(area)
    db.session.commit()
    start_monitoring_thread(area)
    return jsonify({'message': 'Monitoring started', 'area_id': area.id}), 200

@app.route('/flight_paths', methods=['GET'])
def get_flight_paths():
    flights = FlightPath.query.all()
    flight_data = [
        {
            'flight_id': flight.flight_id,
            'points': flight.points,
            'classification': flight.classification,
            'classification_source': flight.classification_source
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
            'points': flight.points,
            'classification': flight.classification,
            'classification_source': flight.classification_source
        })
        return jsonify({'message': f'Classification updated for {flight_id}'}), 200
    return jsonify({'error': 'Flight not found'}), 404

@app.route('/retrain_model', methods=['POST'])
def retrain_model_endpoint():
    success = train_model()
    if success:
        return jsonify({'message': 'Model retrained successfully'}), 200
    return jsonify({'error': 'Failed to retrain model (insufficient data or error)'}), 400