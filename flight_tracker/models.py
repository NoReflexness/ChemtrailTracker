from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class MonitoredArea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lamin = db.Column(db.Float, nullable=False)
    lamax = db.Column(db.Float, nullable=False)
    lomin = db.Column(db.Float, nullable=False)
    lomax = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.String(10), nullable=False)

class FlightPath(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    flight_id = db.Column(db.String(50), nullable=False)
    points = db.Column(db.JSON, nullable=False)
    classification = db.Column(db.String(50), nullable=True)
    auto_classified = db.Column(db.Boolean, default=False)
    classification_source = db.Column(db.String(20), nullable=True)  # 'ml' or 'rule'
    last_updated = db.Column(db.Integer, nullable=False)

def init_db(app):
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////data/flight_data.db'
    db.init_app(app)
    with app.app_context():
        db.create_all()