
## Prerequisites
- **Python**: 3.8 or higher (3.12 recommended for Docker).
- **Docker**: Optional, for containerized deployment.
- **Input Data**: CSV files with columns `icao24`, `lat`, `lon` (e.g., OpenSky Network format).

## Setup Instructions

### Local Development Environment

1. **Clone or Create the Project**:
   - If cloning from a repository:
     ```bash
     git clone <repository-url>
     cd flight_analyzer
     ```
   - Or manually create the folder structure and copy files as described.

2. **Install Dependencies**:
   - Ensure Python is installed (`python --version`).
   - Install required packages:
     ```bash
     pip install -r requirements.txt
     ```
   - `requirements.txt` includes:
     ```
     Flask==2.3.3
     pandas==2.2.0
     numpy==1.26.4
     matplotlib==3.8.3
     svgwrite==1.4.3
     ```

3. **Run the Application**:
   - Start the Flask server:
     ```bash
     python app.py
     ```
   - Open a browser to `http://127.0.0.1:5000`.

4. **Test the App**:
   - Drag and drop a CSV file with `icao24`, `lat`, and `lon` columns.
   - Example CSV:
     ```
     icao24,time,lat,lon
     abc123,2025-01-01 00:00:00,40.0,-70.0
     abc123,2025-01-01 00:01:00,40.0,-69.0
     abc123,2025-01-01 00:02:00,41.0,-69.0
     abc123,2025-01-01 00:03:00,41.0,-70.0
     abc123,2025-01-01 00:04:00,40.0,-70.0
     ```

### Docker Setup

1. **Install Docker**:
   - Download and install Docker from [docker.com](https://www.docker.com/get-started).

2. **Build the Docker Image**:
   - In the `flight_analyzer/` directory:
     ```bash
     docker build -t flight-analyzer .
     ```

3. **Run the Container**:
   - Start the app:
     ```bash
     docker run -p 5000:5000 flight-analyzer
     ```
   - Access it at `http://localhost:5000`.

4. **Optional: Persistent Uploads**:
   - To save uploaded files/reports outside the container:
     ```bash
     docker run -p 5000:5000 -v $(pwd)/uploads:/app/uploads flight-analyzer
     ```

## Usage
1. Visit the web interface (`http://localhost:5000`).
2. Drag and drop a flight data CSV file into the drop zone.
3. View the analysis results:
   - A table of unusual flights (ICAO24 and coordinates).
   - An SVG graphic of flight paths.
   - A link to download the report CSV.

## Development Notes
- **Data Source**: Designed for OpenSky Network CSV format (`icao24`, `lat`, `lon`). Adjust `app.py` if your data differs.
- **Pattern Detection**: Identifies grid-like paths with ≥4 significant (~90°) turns and consistent segment lengths. Tune parameters in `analyze_path_pattern` as needed.
- **Ownership**: Currently excludes ownership data; add an external lookup (e.g., FAA registry) to `FlightPatternAnalyzer` if required.
- **Performance**: Large CSVs may slow processing; consider chunking for production use.

## Troubleshooting
- **ModuleNotFoundError**: Ensure all dependencies are installed (`pip install -r requirements.txt`).
- **Port Conflict**: Change the port in `docker run -p <new-port>:5000` if 5000 is in use.
- **No Results**: Verify CSV format matches expected columns; check console logs (`debug=True` in `app.py`).

## Future Enhancements
- Add ownership lookup via an API or database.
- Optimize for large datasets with streaming or multiprocessing.
- Deploy to a cloud service (e.g., AWS, Heroku) for broader access.

## License
This project is unlicensed by default. Add a license file (e.g., MIT) if distributing.

---
Generated on February 22, 2025