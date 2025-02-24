import os
from flask import Flask
from flask_socketio import SocketIO
from flight_analyzer.routes import init_routes
from flight_analyzer.logging_config import init_logging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config['UPLOAD_FOLDER'] = 'uploads'
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize logging and routes
init_logging(socketio)
init_routes(app, socketio)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    socketio.run(app, debug=True, host='0.0.0.0')