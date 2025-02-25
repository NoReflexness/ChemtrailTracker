# Flight Tracker Dashboard

A modern, real-time flight tracking application built with Python, Flask, SocketIO, and Leaflet.js. This project fetches flight data from the [OpenSky Network API](https://opensky-network.org/), tracks flight paths over configurable areas.

Developed as a pure AI developed application based on conversations with xAI Grok. 

## Features

- **Real-Time Tracking**: Fetches flight data from OpenSky Network API and updates paths dynamically via SocketIO.
- **Interactive Map**: Displays flight paths on a Leaflet.js map with color-coded classifications (green for A-to-B, red for survey, grey for other).
- **Custom Areas**: Define multiple monitoring areas with shift-click on the map; overlapping areas are replaced by the latest.
- **Flight Classification**:
  - Rule-based: Uses direction changes, distance, speed, and point density.
  - ML-based: Trains a Random Forest model on manually labeled data for improved accuracy.
- **Dashboard UI**: Modern layout with stats (tracked flights, active areas), controls, flight list, and logs.
- **Manual Overrides**: Adjust flight classifications via dropdowns, feeding data back into ML training.
- **Data Persistence**: Stores flight paths in SQLite and training data in CSV for ML model retraining.
- **Optimization**: Handles many flights with cleanup of stale data to prevent crashes.

## Tech Stack

- **Backend**: Flask, Flask-SocketIO, Flask-SQLAlchemy, SQLite, `requests`, scikit-learn
- **Frontend**: Leaflet.js, HTML/CSS/JavaScript, SocketIO
- **Container**: Docker (python:3.12-slim)
- **Dependencies**: See `requirements.txt`

## Prerequisites

- Docker installed
- OpenSky Network API credentials (username and password)
- Python 3.12 (if running locally without Docker)

## Setup

### Using Docker (Recommended)

1. **Clone the Repository**
    ```bash
    git clone https://github.com/yourusername/flight-tracker.git
    cd flight-tracker
    ```
2. **Configure OpenSky Credentials**
    - Edit settings.conf with your OpenSky credentials:
    ```
    [opensky]
    username=your_username
    password=your_password
    ```
    - Place it in the project root (it will be copied to /root/.config/pyopensky/settings.conf in the container).
3. **Build and Run**
    ```bash
    docker build -t flight_tracker .
    docker run -it -p 5000:5000 -p 5678:5678 -v $(pwd)/data:/data flight_tracker
    ```
    -p 5000:5000: Exposes the Flask app.
    -p 5678:5678: Exposes debugpy for VSCode debugging.
    -v $(pwd)/data:/data: Mounts the data directory for persistent SQLite DB and CSV files.

4. **Access the Dashboard**  
    Open your browser to http://localhost:5000.

## Local Setup (Alternative)
1. Clone and Install Dependencies
    ```bash
    git clone https://github.com/yourusername/flight-tracker.git
    cd flight-tracker
    pip install -r requirements.txt
    ```
1. Configure OpenSky Credentials  
    - Place settings.conf in ~/.config/pyopensky/ with your credentials.
1. Run the App
    ```bash
    python -m flight_tracker
    ```
    - Access at http://localhost:5000.
## Usage
1. Define Monitoring Areas
    - Shift-click on the map to start an area, shift-click again to complete it.
    - Areas are shown with dotted grey borders; overlapping areas replace older ones.
1. Start Monitoring
    - Select a frequency (30s, 1m, 5m) and click "Start Monitoring" to begin tracking flights in all defined areas.
1. View Flights
    - Flights appear on the map as lines (multi-point) or markers (single-point), color-coded by classification.
    - Hover over paths for details (flight ID, class, source: ML/rule/manual).
    - The flight list shows active flights with dropdowns to override classifications.
1. Train the ML Model
    - Manually classify flights to populate /data/flight_training_data.csv.
    - The "Retrain Model" button enables when there are ≥10 flights with >1 unique classification.
    - Click to train a Random Forest model; check logs for accuracy.
1. Monitor Logs
    - Real-time logs appear at the bottom, including data fetches, classifications, and training results.
## Project Structure
```
flight-tracker/
├── Dockerfile
├── README.md
├── requirements.txt
├── settings.conf.sample  # Rename to settings.conf with credentials
├── data/                 # Mounted volume for SQLite DB and CSV
│   ├── flight_data.db
│   └── flight_training_data.csv
├── flight_tracker/
│   ├── __init__.py
│   ├── __main__.py
│   ├── analysis.py
│   ├── ml_model.py
│   ├── models.py
│   ├── monitoring.py
│   ├── routes.py
│   ├── static/
│   │   └── style.css
│   └── templates/
│       └── index.html
```

## License
    This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments
- OpenSky Network for flight data.
- Leaflet.js for interactive maps.
- xAI for inspiration via Grok (used in development).