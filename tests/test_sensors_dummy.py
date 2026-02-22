"""
test_sensors_dummy.py - Verifies that all dummy sensors satisfy the BaseSensor contract.

These tests run without any hardware and should pass in CI.
They check:
  - connect/start/read/stop/disconnect lifecycle
  - read() returns a dict with expected keys
  - read() raises RuntimeError if called before start()
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sensors.dummy.dummy_temperature_sensor import TemperatureSensor
from sensors.dummy.dummy_current_sensor import CurrentSensor
from sensors.dummy.dummy_do_sensor import DOSensor
from sensors.dummy.dummy_par_sensor import PARSensor
from sensors.dummy.dummy_uvc_sensor import UVCSensor


def _lifecycle(sensor_class, **kwargs):
    """Helper: full connect → start → read → stop → disconnect cycle."""
    s = sensor_class(**kwargs)
    s.connect()
    s.start()
    data = s.read()
    s.stop()
    s.disconnect()
    return data


class TestTemperatureSensor(unittest.TestCase):
    def test_lifecycle(self):
        data = _lifecycle(TemperatureSensor)
        self.assertIn("temperature_c", data)
        self.assertIsInstance(data["temperature_c"], float)

    def test_read_before_start_raises(self):
        s = TemperatureSensor()
        s.connect()
        with self.assertRaises(RuntimeError):
            s.read()
        s.disconnect()

    def test_context_manager(self):
        with TemperatureSensor() as s:
            s.start()
            data = s.read()
        self.assertIn("temperature_c", data)


class TestCurrentSensor(unittest.TestCase):
    def test_lifecycle(self):
        data = _lifecycle(CurrentSensor)
        self.assertIn("voltage_v", data)
        self.assertIn("current_a", data)

    def test_values_are_numeric(self):
        data = _lifecycle(CurrentSensor)
        self.assertIsInstance(data["current_a"], float)


class TestDOSensor(unittest.TestCase):
    def test_lifecycle(self):
        data = _lifecycle(DOSensor)
        self.assertIn("avg_pulse_width_us", data)
        self.assertIn("voltage_mv", data)

    def test_voltage_mv_never_negative(self):
        s = DOSensor()
        s.connect()
        s.start()
        for _ in range(20):
            data = s.read()
            self.assertGreaterEqual(data["voltage_mv"], 0.0)
        s.stop()
        s.disconnect()


class TestPARSensor(unittest.TestCase):
    def test_lifecycle(self):
        data = _lifecycle(PARSensor)
        self.assertIn("par_umol_m2_s", data)

    def test_par_within_range(self):
        s = PARSensor()
        s.connect()
        s.start()
        for _ in range(20):
            data = s.read()
            self.assertGreaterEqual(data["par_umol_m2_s"], 0.0)
            self.assertLessEqual(data["par_umol_m2_s"], 2500.0)
        s.stop()
        s.disconnect()


class TestUVCSensor(unittest.TestCase):
    def test_lifecycle(self):
        data = _lifecycle(UVCSensor)
        self.assertIn("voltage_v", data)
        self.assertIn("intensity_mw_cm2", data)


if __name__ == "__main__":
    unittest.main()
