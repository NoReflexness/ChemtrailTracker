import pytest
import os
from flight_analyzer.ml_model import train_initial_model, classify_pattern, retrain_model, MODEL_PATH

def test_train_initial_model(tmp_path):
    global MODEL_PATH
    MODEL_PATH = str(tmp_path / "test_model.pkl")  # Override for test
    train_initial_model()
    assert os.path.exists(MODEL_PATH)

def test_classify_pattern(tmp_path):
    global MODEL_PATH
    MODEL_PATH = str(tmp_path / "test_model.pkl")
    train_initial_model()
    features = {'avg_distance': 50, 'distance_var': 5, 'turn_count': 0, 'path_length': 20}
    pattern = classify_pattern(features)
    assert pattern in ['Commercial', 'Survey', 'Agricultural', 'Firefighting']

def test_retrain_model(temp_db, tmp_path):
    global MODEL_PATH
    MODEL_PATH = str(tmp_path / "test_model.pkl")
    features = {'avg_distance': 50, 'distance_var': 5, 'turn_count': 0, 'path_length': 20}
    temp_db.insert_training_data('abc123', features, 'Commercial')
    retrain_model()
    assert os.path.exists(MODEL_PATH)