from flask import Flask
from flask_socketio import SocketIO
import logging
from flight_tracker.models import db, init_db

app = Flask(__name__)
socketio = SocketIO(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SocketIOHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        socketio.emit('log', {'message': log_entry})

logger.addHandler(SocketIOHandler())

from flight_tracker.routes import *
from flight_tracker.monitoring import start_monitoring

init_db(app)

@socketio.on('connect')
def handle_connect():
    logger.info("Client connected")
    start_monitoring()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)