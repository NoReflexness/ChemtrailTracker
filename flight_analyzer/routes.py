import logging
from datetime import datetime
from flask import jsonify, send_file, request, render_template
from flask_socketio import emit
import json
import sqlite3
import os
import pandas as pd
from flight_analyzer.analyzer import FlightPatternAnalyzer
from flight_analyzer.database import Database
from flight_analyzer.ml_model import retrain_model
from flight_analyzer.utils import generate_individual_svg

logger = logging.getLogger('FlightAnalyzer')
CREDITS_PER_DAY = 4000
DAY_SECONDS = 24 * 60 * 60

def calculate_credit_cost(lamin, lamax, lomin, lomax):
    lat_range = lamax - lamin
    lon_range = lomax - lomin
    area_sq_deg = lat_range * lon_range
    if area_sq_deg <= 25:
        return 1
    elif area_sq_deg <= 100:
        return 2
    elif area_sq_deg <= 400:
        return 3
    else:
        return 4

def init_routes(app, socketio):
    analyzer = None
    refresh_rate = None
    last_refresh = None
    credits_used = 0
    monitoring_active = False
    monitoring_paused = False
    bounds = None

    bounds_db = sqlite3.connect('/data/bounds_data.db', check_same_thread=False)
    bounds_db.execute('CREATE TABLE IF NOT EXISTS last_bounds (id INTEGER PRIMARY KEY, lamin REAL, lamax REAL, lomin REAL, lomax REAL, refresh_rate INTEGER, credits_used INTEGER)')
    bounds_db.commit()

    def save_bounds(lamin, lamax, lomin, lomax, refresh_rate_val, credits_val):
        nonlocal bounds
        bounds = {'lamin': lamin, 'lamax': lamax, 'lomin': lomin, 'lomax': lomax, 'refresh_rate': refresh_rate_val, 'credits_used': credits_val}
        cursor = bounds_db.cursor()
        cursor.execute('DELETE FROM last_bounds')
        cursor.execute('INSERT INTO last_bounds (lamin, lamax, lomin, lomax, refresh_rate, credits_used) VALUES (?, ?, ?, ?, ?, ?)', 
                       (lamin, lamax, lomin, lomax, refresh_rate_val, credits_val))
        bounds_db.commit()

    def load_bounds():
        cursor = bounds_db.cursor()
        cursor.execute('SELECT lamin, lamax, lomin, lomax, refresh_rate, credits_used FROM last_bounds LIMIT 1')
        result = cursor.fetchone()
        return {'lamin': result[0], 'lamax': result[1], 'lomin': result[2], 'lomax': result[3], 'refresh_rate': result[4], 'credits_used': result[5]} if result else None

    @app.route('/')
    def index():
        saved_bounds = load_bounds()
        credits_used = saved_bounds['credits_used'] if saved_bounds else 0
        return render_template('index.html', saved_bounds=saved_bounds, initial_credits_used=credits_used, CREDITS_PER_DAY=CREDITS_PER_DAY)

    @app.route('/begin_monitoring', methods=['POST'])
    def begin_monitoring():
        nonlocal analyzer, refresh_rate, last_refresh, credits_used, monitoring_active, monitoring_paused, bounds
        data = request.get_json()
        lamin, lamax, lomin, lomax = data.get('lamin'), data.get('lamax'), data.get('lomin'), data.get('lomax')
        refresh_rate = int(data.get('refresh_rate', 30))
        if not all([lamin, lamax, lomin, lomax]):
            logger.error("Missing bounds for monitoring: lamin=%s, lamax=%s, lomin=%s, lomax=%s", lamin, lamax, lomin, lomax)
            emit('log_message', {'message': 'Monitoring failed: Please select an area on the map.'}, broadcast=True)
            return jsonify({'error': 'Please select an area on the map'}), 400

        logger.info("Received bounds: lamin=%s, lamax=%s, lomin=%s, lomax=%s", lamin, lamax, lomin, lomax)
        credit_cost = calculate_credit_cost(lamin, lamax, lomin, lomax)
        logger.info("Starting monitoring for area: lamin=%s, lamax=%s, lomin=%s, lomax=%s, credit cost=%d, refresh rate=%d seconds", 
                    lamin, lamax, lomin, lomax, credit_cost, refresh_rate)
        save_bounds(lamin, lamax, lomin, lomax, refresh_rate, credits_used)

        def monitoring_task():
            nonlocal analyzer, last_refresh, credits_used, monitoring_active, monitoring_paused
            analyzer = FlightPatternAnalyzer()
            last_refresh = datetime.now().timestamp()
            socketio.emit('log_message', {'message': f'Monitoring started for area: {lamin}-{lamax}, {lomin}-{lomax}. Refresh rate: {refresh_rate} seconds.'})
            while monitoring_active:
                if not monitoring_paused:
                    now = datetime.now().timestamp()
                    if (now - last_refresh) >= refresh_rate:
                        flight_data = analyzer.fetch_data(lamin, lamax, lomin, lomax)
                        if flight_data is not None:
                            analyzer.analyze_flights(flight_data)
                            credits_used += credit_cost
                            remaining_credits = CREDITS_PER_DAY - credits_used
                            logger.info("Credits used: %d, Remaining credits: %d", credits_used, remaining_credits)
                            socketio.emit('credit_update', {'credits_used': credits_used, 'remaining_credits': remaining_credits})
                            socketio.emit('refresh_timer', {'next_refresh': refresh_rate - (now - last_refresh)})
                            socketio.emit('update_paths', get_flight_paths_data())  # Emit updated paths
                            save_bounds(lamin, lamax, lomin, lomax, refresh_rate, credits_used)
                            last_refresh = now
                        else:
                            logger.warning("No new data fetched")
                socketio.sleep(1)
            logger.info("Monitoring stopped")

        if not monitoring_active:
            monitoring_active = True
            monitoring_paused = False
            socketio.start_background_task(monitoring_task)
        else:
            monitoring_paused = False
        return jsonify({'message': 'Monitoring started', 'refresh_rate': refresh_rate})

    @app.route('/pause_monitoring', methods=['POST'])
    def pause_monitoring():
        nonlocal monitoring_paused
        if monitoring_active:
            monitoring_paused = True
            logger.info("Monitoring paused")
            socketio.emit('log_message', {'message': 'Monitoring paused'})
            return jsonify({'message': 'Monitoring paused'})
        return jsonify({'error': 'Monitoring not active'}), 400

    @app.route('/stop_monitoring', methods=['POST'])
    def stop_monitoring():
        nonlocal monitoring_active, monitoring_paused, analyzer, last_refresh
        if monitoring_active:
            monitoring_active = False
            monitoring_paused = False
            analyzer = None
            last_refresh = None
            logger.info("Monitoring stopped")
            socketio.emit('log_message', {'message': 'Monitoring stopped'})
            socketio.emit('refresh_timer', {'next_refresh': 'N/A'})
            return jsonify({'message': 'Monitoring stopped'})
        return jsonify({'error': 'Monitoring not active'}), 400

    @app.route('/get_flight_paths', methods=['GET'])
    def get_flight_paths():
        return jsonify(get_flight_paths_data())

    def get_flight_paths_data():
        conn = sqlite3.connect('/data/states_data.db')
        df = pd.read_sql_query("SELECT icao24, latitude, longitude, true_track, timestamp FROM states ORDER BY timestamp ASC", conn)
        conn.close()
        if df.empty:
            return {'paths': []}

        paths = {}
        for _, row in df.iterrows():
            icao24 = row['icao24']
            if icao24 not in paths:
                paths[icao24] = {'coords': [], 'latest': None}
            coord = [row['latitude'], row['longitude']]
            paths[icao24]['coords'].append(coord)
            paths[icao24]['latest'] = {'lat': row['latitude'], 'lon': row['longitude'], 'true_track': row['true_track'], 'timestamp': row['timestamp']}

        return {'paths': [{'icao24': key, 'coords': val['coords'], 'latest': val['latest']} for key, val in paths.items()]}

    @app.route('/analyze', methods=['POST'])
    def analyze_data():
        conn = sqlite3.connect('/data/states_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM states")
        count = cursor.fetchone()[0]
        if count == 0:
            conn.close()
            logger.warning("No stored data available for analysis")
            return jsonify({'error': 'No stored data available for analysis'}), 404

        flight_data = pd.read_sql_query("SELECT icao24, latitude, longitude FROM states", conn)
        conn.close()
        if flight_data.empty:
            logger.warning("No stored data available for analysis")
            return jsonify({'error': 'No stored data available for analysis'}), 404

        analyzer = FlightPatternAnalyzer()
        analyzer.analyze_flights(flight_data)
        report_df = analyzer.generate_report()
        report_path = os.path.join(app.config['UPLOAD_FOLDER'], 'unusual_flights.csv')
        report_df.to_csv(report_path, index=False)
        logger.info("Report saved to %s", report_path)

        report_data = []
        for flight in analyzer.unusual_flights:
            svg_path = f"static/flight_{flight['icao24']}.svg"
            generate_individual_svg(flight['coords'], flight['pattern_type'], svg_path)
            report_data.append({
                'icao24': flight['icao24'],
                'coords': flight['coords'],
                'pattern_type': flight['pattern_type'],
                'svg_path': f"/{svg_path}"
            })

        logger.info("Analysis completed")
        return jsonify({'report': report_data})

    @app.route('/update_pattern', methods=['POST'])
    def update_pattern():
        logger.info("Updating pattern classification")
        icao24 = request.form.get('icao24')
        new_pattern = request.form.get('pattern_type')
        coords_str = request.form.get('coords')

        analyzer = FlightPatternAnalyzer()
        coords = json.loads(coords_str)
        features = analyzer.extract_features(coords)

        db = Database('flight_patterns.db')
        db.update_pattern(icao24, new_pattern)

        training_db = Database('training_data.db')
        training_db.insert_training_data(icao24, features, new_pattern)

        return jsonify({'status': 'success'})

    @app.route('/retrain', methods=['POST'])
    def retrain():
        logger.info("Retraining requested")
        retrain_model()
        return jsonify({'status': 'Model retrained'})

    @app.route('/download_report')
    def download_report():
        logger.info("Downloading report")
        report_path = os.path.join(app.config['UPLOAD_FOLDER'], 'unusual_flights.csv')
        if os.path.exists(report_path):
            return send_file(report_path, as_attachment=True)
        logger.error("Report file not found")
        return "Report not found", 404