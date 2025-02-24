import pytest
import sqlite3
import os
from flight_analyzer.database import Database

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    yield db
    db.conn.close()
    if os.path.exists(db_path):
        os.remove(db_path)

@pytest.fixture
def sample_coords():
    return [
        [40.0, -70.0],
        [40.0, -69.0],
        [41.0, -69.0],
        [41.0, -70.0],
        [40.0, -70.0]
    ]