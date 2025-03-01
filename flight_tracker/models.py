from flask_sqlalchemy import SQLAlchemy
import json
from flight_tracker.utils import logger

db = SQLAlchemy()

def init_db(app):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////data/flights.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()

class MonitoredArea(db.Model):
    __tablename__ = 'monitored_area'  
    id = db.Column(db.Integer, primary_key=True)
    lamin = db.Column(db.Float, nullable=False)
    lamax = db.Column(db.Float, nullable=False)
    lomin = db.Column(db.Float, nullable=False)
    lomax = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.String(10), nullable=False)
    is_monitoring = db.Column(db.Boolean, default=False)

class FlightPath(db.Model):
    __tablename__ = 'flight_path'
    flight_id = db.Column(db.String(20), primary_key=True)
    points = db.Column(db.Text, nullable=True)  
    last_updated = db.Column(db.Integer, nullable=False)
    classification = db.Column(db.String(20))
    classification_source = db.Column(db.String(20))
    auto_classified = db.Column(db.Boolean, default=True)
    avg_altitude = db.Column(db.Float, default=-1)
    avg_velocity = db.Column(db.Float, default=-1)
    duration = db.Column(db.Integer, default=0)

    def __init__(self, flight_id, points=None, last_updated=0):
        self.flight_id = flight_id
        self.points = json.dumps(points) if points else None
        self.last_updated = last_updated
        self.update_stats()

    def update_stats(self):
        try:
            points = json.loads(self.points) if isinstance(self.points, str) else self.points
            if not isinstance(points, list):
                raise ValueError("Points must be a list")
            normalized_points = []
            for p in points:
                if not isinstance(p, list):
                    logger.warning(f"Invalid point format for {self.flight_id}: {p}")
                    continue
                while len(p) < 5:
                    p.append(-1)
                normalized_points.append(p)
            self.points = json.dumps(normalized_points)
            altitudes = [p[3] for p in normalized_points if p[3] != -1]
            velocities = [p[4] for p in normalized_points if p[4] != -1]
            timestamps = [p[2] for p in normalized_points]
            self.avg_altitude = sum(altitudes) / len(altitudes) if altitudes else -1
            self.avg_velocity = sum(velocities) / len(velocities) if velocities else -1
            self.duration = max(timestamps) - min(timestamps) if len(timestamps) > 1 else 0
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error updating stats for {self.flight_id}: {e}")
            self.points = json.dumps([])
            self.avg_altitude = -1
            self.avg_velocity = -1
            self.duration = 0

    @property
    def points_list(self):
        if self.points:
            points = json.loads(self.points) if isinstance(self.points, str) else self.points
            normalized_points = []
            for p in points:
                if not isinstance(p, list):
                    logger.warning(f"Invalid point format on read for {self.flight_id}: {p}")
                    continue
                while len(p) < 5:
                    p.append(-1)
                normalized_points.append(p)
            return normalized_points
        return []