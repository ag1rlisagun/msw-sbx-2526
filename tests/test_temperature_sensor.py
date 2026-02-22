"""
test_temperature_sensor.py - Tests for the DS18B20 temperature sensor.

WHAT TO TEST HERE:
    These tests use the dummy sensor so they run without hardware.
    The goal is to verify the sensor satisfies the BaseSensor contract
    and that its output values are physically reasonable.

    When you are ready to expand:

    1. LIFECYCLE - already covered in test_sensors_dummy.py but worth
       having sensor-specific versions here for clarity.

    2. OUTPUT RANGE - temperature should always be a float and, for our
       experiment, should never be wildly outside -10°C to 60°C.

    3. READ BEFORE START - calling read() without start() must raise
       RuntimeError, not return garbage data.

    4. CONNECT REQUIRED - calling start() without connect() must raise
       RuntimeError.

    5. CONTEXT MANAGER - the 'with TemperatureSensor() as s:' pattern
       must call connect() on entry and disconnect() on exit, even if
       an exception is raised inside the block.

    6. MULTIPLE READS - read() should succeed when called many times
       in a row without reconnecting.

    FUTURE (requires Pi hardware):
    7. REAL SENSOR INTEGRATION - confirm a reading is returned within
       the expected range when a physical DS18B20 is connected.
    8. WRONG SENSOR ID - passing a nonexistent sensor_id to the real
       sensor should raise RuntimeError, not hang.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sensors.dummy.dummy_temperature_sensor import TemperatureSensor


class TestTemperatureSensorLifecycle(unittest.TestCase):

    def test_connect_and_read(self):
        # TODO: verify connect → start → read → stop → disconnect completes
        # without error and returns a dict containing "temperature_c"
        pass

    def test_read_before_start_raises(self):
        # TODO: verify RuntimeError is raised if read() is called before start()
        pass

    def test_start_before_connect_raises(self):
        # TODO: verify RuntimeError is raised if start() is called before connect()
        pass

    def test_context_manager(self):
        # TODO: verify the 'with' statement calls connect() and disconnect()
        # correctly, and that the sensor reads inside the block
        pass


class TestTemperatureSensorOutput(unittest.TestCase):

    def test_output_contains_temperature_key(self):
        # TODO: verify read() returns a dict with key "temperature_c"
        pass

    def test_temperature_is_float(self):
        # TODO: verify the returned temperature_c value is a float (not int, not None)
        pass

    def test_temperature_within_reasonable_range(self):
        # TODO: verify temperature_c is between -10.0 and 60.0 over many reads
        # (the dummy won't drift far, but this catches formula bugs in the real sensor)
        pass

    def test_multiple_reads_succeed(self):
        # TODO: verify read() can be called 10+ times without error or state corruption
        pass


if __name__ == "__main__":
    unittest.main()
