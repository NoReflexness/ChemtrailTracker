# flight_tracker/__main__.py
from flight_tracker import create_app

app, socketio = create_app()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)  # For local dev only