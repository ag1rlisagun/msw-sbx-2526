"""
test_data_logger.py - Unit tests for the DataLogger.

These tests use a temporary in-memory SQLite database so they never
touch the real data file and can run on any machine, including CI.
"""

import os
import sys
import time
import threading
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from storage.data_logger import DataLogger


class TestDataLogger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = DataLogger(self.tmp.name)
        self.db.connect()

    def tearDown(self):
        self.db.disconnect()
        os.unlink(self.tmp.name)

    def _fetch_all(self, table: str) -> list:
        import sqlite3
        conn = sqlite3.connect(self.tmp.name)
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        conn.close()
        return rows

    def test_write_creates_table_and_row(self):
        self.db.write("temperature", {"temperature_c": 25.1})
        rows = self._fetch_all("temperature")
        self.assertEqual(len(rows), 1)

    def test_write_stores_correct_value(self):
        self.db.write("temperature", {"temperature_c": 22.5})
        rows = self._fetch_all("temperature")
        # row: (id, timestamp, temperature_c)
        self.assertAlmostEqual(rows[0][2], 22.5, places=4)

    def test_multiple_sensors_create_separate_tables(self):
        self.db.write("temperature", {"temperature_c": 25.0})
        self.db.write("current", {"voltage_v": 2.5, "current_a": 0.05})
        temp_rows = self._fetch_all("temperature")
        curr_rows = self._fetch_all("current")
        self.assertEqual(len(temp_rows), 1)
        self.assertEqual(len(curr_rows), 1)

    def test_timestamp_is_written(self):
        before = time.time()
        self.db.write("par", {"par_umol_m2_s": 1200.0})
        after = time.time()
        rows = self._fetch_all("par")
        ts = rows[0][1]  # timestamp column
        self.assertGreaterEqual(ts, before)
        self.assertLessEqual(ts, after)

    def test_concurrent_writes_do_not_corrupt(self):
        """Multiple threads writing simultaneously should all succeed."""
        errors = []

        def write_many(sensor_name, value_key, value):
            for _ in range(20):
                try:
                    self.db.write(sensor_name, {value_key: value})
                except Exception as e:
                    errors.append(e)
                time.sleep(0.005)

        threads = [
            threading.Thread(target=write_many, args=("temperature", "temperature_c", 25.0)),
            threading.Thread(target=write_many, args=("current", "current_a", 0.05)),
            threading.Thread(target=write_many, args=("uvc", "intensity_mw_cm2", 1.5)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Concurrent write errors: {errors}")
        self.assertEqual(len(self._fetch_all("temperature")), 20)
        self.assertEqual(len(self._fetch_all("current")), 20)

    def test_write_before_connect_does_not_raise(self):
        """Logger should log an error but never raise to the caller."""
        db2 = DataLogger(self.tmp.name)  # not connected
        try:
            db2.write("temperature", {"temperature_c": 1.0})  # should not raise
        except Exception as e:
            self.fail(f"write() raised unexpectedly: {e}")


class TestDataLoggerTableNameSanitization(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = DataLogger(self.tmp.name)
        self.db.connect()

    def tearDown(self):
        self.db.disconnect()
        os.unlink(self.tmp.name)

    def test_special_chars_in_sensor_name_are_sanitized(self):
        """Sensor names with spaces or dashes should not crash the logger."""
        try:
            self.db.write("dissolved-oxygen sensor", {"voltage_mv": 500.0})
        except Exception as e:
            self.fail(f"Raised unexpectedly: {e}")


if __name__ == "__main__":
    unittest.main()
