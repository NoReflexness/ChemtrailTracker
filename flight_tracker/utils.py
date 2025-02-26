import logging
from flask_socketio import SocketIO

logger = logging.getLogger(__name__)

class SocketIOHandler(logging.Handler):
    def __init__(self, socketio):
        super().__init__()
        self.socketio = socketio

    def emit(self, record):
        log_entry = self.format(record)
        self.socketio.emit('log', {'message': log_entry})

def setup_logging(socketio):
    logging.basicConfig(level=logging.INFO)
    logger.addHandler(SocketIOHandler(socketio))