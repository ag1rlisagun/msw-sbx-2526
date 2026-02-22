"""
test_current_sensor.py - Tests for the ACS723 current sensor.

WHAT TO TEST HERE:
    These tests use the dummy sensor so they run without hardware.

    1. LIFECYCLE - connect → start → read → stop → disconnect.

    2. OUTPUT KEYS - read() must return "voltage_v" and "current_a".

    3. CURRENT SIGN - for our experiment the cyanobacteria should only
       produce positive current. Negative current_a would indicate a
       wiring or calibration error. Test that dummy never goes below 0.

    4. VOLTAGE MIDPOINT - when current is 0A, ACS723 outputs exactly
       VCC/2 (2.5V at 5V). Test that voltage_v is near 2.5 at zero current.

    5. FORMULA CONSISTENCY - verify that current_a and voltage_v are
       mathematically consistent: current = (voltage - 2.5) / sensitivity
       This catches copy-paste errors where the two values disagree.

    6. READ BEFORE START - must raise RuntimeError.

    FUTURE (requires Pi hardware):
    7. ZERO CURRENT CALIBRATION - with nothing connected to the ACS723,
       current_a should be ~0A and voltage_v should be ~2.5V.
    8. KNOWN LOAD - attach a known resistor + power supply and verify
       the reported current matches the expected value (V/R = I).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sensors.dummy.dummy_current_sensor import CurrentSensor


class TestCurrentSensorLifecycle(unittest.TestCase):

    def test_connect_and_read(self):
        # TODO: full lifecycle returns dict with "voltage_v" and "current_a"
        pass

    def test_read_before_start_raises(self):
        # TODO: RuntimeError if read() before start()
        pass


class TestCurrentSensorOutput(unittest.TestCase):

    def test_output_keys(self):
        # TODO: verify both "voltage_v" and "current_a" are present in output
        pass

    def test_current_is_non_negative(self):
        # TODO: verify current_a >= 0 over many reads (negative = wiring error)
        pass

    def test_voltage_and_current_are_consistent(self):
        # TODO: verify (voltage_v - 2.5) / 0.4 ≈ current_a within a small tolerance
        # This catches cases where the two fields disagree with each other
        pass

    def test_multiple_reads_succeed(self):
        # TODO: 10+ consecutive reads without error
        pass


if __name__ == "__main__":
    unittest.main()
