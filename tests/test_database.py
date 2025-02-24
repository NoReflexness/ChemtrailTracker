import pytest
from flight_analyzer.database import Database

def test_init_db(temp_db):
    cursor = temp_db.get_cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    assert len(tables) > 0  # Table created

def test_update_pattern(temp_db):
    cursor = temp_db.get_cursor()
    cursor.execute("INSERT INTO patterns (icao24, coords, pattern_type) VALUES (?, ?, ?)", 
                   ('abc123', '[]', 'Commercial'))
    temp_db.commit()
    temp_db.update_pattern('abc123', 'Survey')
    cursor.execute("SELECT pattern_type FROM patterns WHERE icao24 = ?", ('abc123',))
    assert cursor.fetchone()[0] == 'Survey'

def test_insert_training_data(temp_db):
    features = {'avg_distance': 50, 'distance_var': 5, 'turn_count': 0, 'path_length': 20}
    temp_db.insert_training_data('abc123', features, 'Commercial')
    cursor = temp_db.get_cursor()
    cursor.execute("SELECT * FROM training_data WHERE icao24 = ?", ('abc123',))
    row = cursor.fetchone()
    assert row[1] == 'abc123'
    assert row[6] == 'Commercial'