"""
data_logger.py - Thread-safe SQLite data logger.

Design principles:
- One table per sensor, created automatically on first write.
- All writes go through a single threading.Lock so concurrent sensor
  threads never corrupt the database.
- Every reading is committed immediately. We prefer many small commits
  over batching - if power is cut mid-flight, we lose at most one sample.
- The logger never raises to the caller on write failure; it prints the
  error and moves on so sensor collection is never interrupted by a DB issue.
"""

import sqlite3
import threading
import time
import os
import logging

logger = logging.getLogger(__name__)


class DataLogger:
    def __init__(self, db_path: str):
        """
        Args:
            db_path: path to the SQLite database file.
                     The directory must exist (created by main.py at startup).
        """
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = None
        self._known_tables: set[str] = set()

    def connect(self) -> None:
        """Open the database connection. Call once at startup."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        # check_same_thread=False is safe here because we guard all
        # access with self._lock ourselves.
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")  # safer for concurrent access
        self._conn.commit()
        logger.info(f"Database opened at {self.db_path}")

    def disconnect(self) -> None:
        """Close the database connection cleanly."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Database closed.")

    def write(self, sensor_name: str, data: dict) -> None:
        """
        Write one sensor reading to the database.

        The table for this sensor is created automatically if it does not exist.
        A "timestamp" column (Unix epoch float) and "sensor_name" column are
        added automatically — do not include them in the data dict.

        Args:
            sensor_name: used as the table name (e.g. "temperature", "do_sensor")
            data: dict of column_name -> numeric value from sensor.read()
        """
        if self._conn is None:
            logger.error("DataLogger.write() called before connect()")
            return

        # Sanitize table name — only allow alphanumeric and underscores
        table = "".join(c if c.isalnum() or c == "_" else "_" for c in sensor_name)

        timestamp = time.time()

        with self._lock:
            try:
                self._ensure_table(table, data)
                columns = ["timestamp"] + list(data.keys())
                values = [timestamp] + list(data.values())
                placeholders = ", ".join("?" for _ in values)
                col_str = ", ".join(columns)
                self._conn.execute(
                    f"INSERT INTO {table} ({col_str}) VALUES ({placeholders})",
                    values,
                )
                self._conn.commit()
            except Exception as e:
                logger.error(f"Failed to write data for sensor '{sensor_name}': {e}")

    def _ensure_table(self, table: str, data: dict) -> None:
        """
        Create the table if it doesn't exist yet.
        Called inside the lock — do not call from outside.
        """
        if table in self._known_tables:
            return

        # Build column definitions from the first reading's keys.
        # All sensor values are stored as REAL.
        col_defs = "timestamp REAL NOT NULL"
        for key in data.keys():
            safe_key = "".join(c if c.isalnum() or c == "_" else "_" for c in key)
            col_defs += f", {safe_key} REAL"

        self._conn.execute(
            f"CREATE TABLE IF NOT EXISTS {table} (id INTEGER PRIMARY KEY AUTOINCREMENT, {col_defs})"
        )
        self._conn.commit()
        self._known_tables.add(table)
        logger.info(f"Table '{table}' ready in database.")
