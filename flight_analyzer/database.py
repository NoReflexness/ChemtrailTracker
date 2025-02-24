import sqlite3
import logging

# Dedicated logger for the database module
logger = logging.getLogger('FlightAnalyzer.Database')

class Database:
    def __init__(self, db_path):
        """
        Initialize the database connection.

        Args:
            db_path (str): Path to the SQLite database file.
        """
        self.db_path = db_path
        try:
            self.conn = sqlite3.connect(db_path)
            logger.info("Database connection established to %s", db_path)
            self.init_db()
        except sqlite3.Error as e:
            logger.error("Failed to connect to database %s: %s", db_path, str(e))
            raise

    def get_cursor(self):
        """Return a cursor for database operations."""
        return self.conn.cursor()

    def commit(self):
        """Commit changes to the database."""
        try:
            self.conn.commit()
            logger.debug("Database changes committed")
        except sqlite3.Error as e:
            logger.error("Failed to commit changes: %s", str(e))
            raise

    def init_db(self):
        """Initialize the database with appropriate tables based on file name."""
        cursor = self.get_cursor()
        try:
            # Check if any tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            logger.debug("Existing tables: %s", existing_tables)

            # Determine table name based on database path
            if 'patterns' in self.db_path:
                table_name = 'patterns'
                create_sql = '''
                    CREATE TABLE IF NOT EXISTS patterns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        icao24 TEXT,
                        coords TEXT,
                        pattern_type TEXT
                    )
                '''
            elif 'training_data' in self.db_path:
                table_name = 'training_data'
                create_sql = '''
                    CREATE TABLE IF NOT EXISTS training_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        icao24 TEXT,
                        avg_distance REAL,
                        distance_var REAL,
                        turn_count INTEGER,
                        path_length INTEGER,
                        pattern_type TEXT
                    )
                '''
            else:
                logger.error("Unknown database path: %s", self.db_path)
                raise ValueError(f"Unsupported database path: {self.db_path}")

            # Create table if it doesn’t exist
            if table_name not in existing_tables:
                cursor.execute(create_sql)
                logger.info("Created table '%s' in %s", table_name, self.db_path)
            else:
                logger.debug("Table '%s' already exists in %s", table_name, self.db_path)

            self.commit()
        except sqlite3.Error as e:
            logger.error("Failed to initialize database %s: %s", self.db_path, str(e))
            raise

    def update_pattern(self, icao24, new_pattern):
        """Update the pattern type for a given ICAO24."""
        logger.info("Updating pattern_type for %s to %s", icao24, new_pattern)
        try:
            cursor = self.get_cursor()
            cursor.execute('UPDATE patterns SET pattern_type = ? WHERE icao24 = ?', (new_pattern, icao24))
            if cursor.rowcount == 0:
                logger.warning("No rows updated for icao24=%s", icao24)
            self.commit()
        except sqlite3.Error as e:
            logger.error("Failed to update pattern for %s: %s", icao24, str(e))
            raise

    def insert_training_data(self, icao24, features, pattern_type):
        """Insert training data into the training_data table."""
        logger.info("Adding training data for %s", icao24)
        try:
            cursor = self.get_cursor()
            cursor.execute('INSERT INTO training_data (icao24, avg_distance, distance_var, turn_count, path_length, pattern_type) VALUES (?, ?, ?, ?, ?, ?)',
                           (icao24, features['avg_distance'], features['distance_var'], features['turn_count'], features['path_length'], pattern_type))
            self.commit()
        except sqlite3.Error as e:
            logger.error("Failed to insert training data for %s: %s", icao24, str(e))
            raise

    def fetch_training_data(self):
        """Fetch all training data for model retraining."""
        logger.info("Fetching training data from %s", self.db_path)
        try:
            cursor = self.get_cursor()
            cursor.execute('SELECT avg_distance, distance_var, turn_count, path_length, pattern_type FROM training_data')
            data = cursor.fetchall()
            logger.debug("Fetched %d rows of training data", len(data))
            return data
        except sqlite3.Error as e:
            logger.error("Failed to fetch training data: %s", str(e))
            raise