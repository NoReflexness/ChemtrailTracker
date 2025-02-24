import logging
from logging.handlers import QueueHandler
import queue

log_queue = queue.Queue()
logger = logging.getLogger('FlightAnalyzer')

def init_logging(socketio):
    logging.basicConfig(level=logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    queue_handler = QueueHandler(log_queue)
    queue_handler.setFormatter(formatter)
    logger.addHandler(queue_handler)

    def log_emitter():
        while True:
            try:
                record = log_queue.get()
                # Use the fully formatted message from the QueueHandler
                socketio.emit('log_message', {'message': record.message})
            except Exception as e:
                logger.error("Error in log emitter: %s", str(e))

    socketio.start_background_task(log_emitter)
    logger.info("Logging initialized")