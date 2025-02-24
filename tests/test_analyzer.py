import pytest
import pandas as pd
from flight_analyzer.analyzer import FlightPatternAnalyzer

def test_extract_features(sample_coords):
    analyzer = FlightPatternAnalyzer("", "")  # Dummy credentials
    features = analyzer.extract_features(sample_coords)
    assert features is not None
    assert 'avg_distance' in features
    assert 'distance_var' in features
    assert 'turn_count' in features
    assert 'path_length' in features
    assert features['path_length'] == 5

def test_analyze_path_pattern(temp_db):
    analyzer = FlightPatternAnalyzer("", "")
    df = pd.DataFrame({
        'icao24': ['abc123'] * 11,
        'lat': [40.0] * 11,
        'lon': list(range(-70, -60))
    })
    assert analyzer.analyze_path_pattern(df) == False  # Not enough turns

# Mock pyopensky.Trino.history for fetch_data test if needed