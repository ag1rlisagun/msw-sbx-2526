"""
test_do_sensor.py - Tests for the Atlas Scientific D.O. sensor.

WHAT TO TEST HERE:
    These tests use the dummy sensor so they run without hardware.
    The real sensor requires pigpio and a PWM signal - these tests
    verify the math and interface contract without any of that.

    1. LIFECYCLE - connect → start → read → stop → disconnect.

    2. OUTPUT KEYS - read() must return "avg_pulse_width_us" and "voltage_mv".

    3. VOLTAGE NEVER NEGATIVE - the formula (pulse * 20) - 60 can produce
       a negative result for very short pulses. The sensor must clamp to 0.
       Test this boundary explicitly.

    4. FORMULA CORRECTNESS - verify that voltage_mv = (avg_pulse_width_us * 20) - 60
       for a known pulse width. This is the most important math in the system.

    5. PULSE WIDTH RANGE - realistic pulse widths from the Surveyor Isolator
       are between ~10µs (near 0% saturation) and ~80µs (near 100%).
       Test that dummy output stays in a plausible range.

    6. READ BEFORE START - must raise RuntimeError.

    FUTURE (requires Pi hardware):
    7. PIGPIOD RUNNING - connect() on the real sensor should raise a clear
       RuntimeError with instructions if pigpiod is not running.
    8. KNOWN CALIBRATION POINT - with the probe in air-saturated water at
       known temperature and pressure, verify voltage_mv matches expected value.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sensors.dummy.dummy_do_sensor import DOSensor


class TestDOSensorLifecycle(unittest.TestCase):

    def test_connect_and_read(self):
        # TODO: full lifecycle returns dict with "avg_pulse_width_us" and "voltage_mv"
        pass

    def test_read_before_start_raises(self):
        # TODO: RuntimeError if read() before start()
        pass


class TestDOSensorOutput(unittest.TestCase):

    def test_output_keys(self):
        # TODO: verify both "avg_pulse_width_us" and "voltage_mv" are in output
        pass

    def test_voltage_never_negative(self):
        # TODO: run 20 reads, assert voltage_mv >= 0.0 every time
        # This is critical - the clamp in the formula must always hold
        pass

    def test_formula_correctness(self):
        # TODO: for a known avg_pulse_width_us, verify voltage_mv = (pulse * 20) - 60
        # You can temporarily set _base_pulse to a fixed value and check the math
        pass

    def test_pulse_width_in_realistic_range(self):
        # TODO: verify avg_pulse_width_us stays between 0 and 100µs over many reads
        pass


if __name__ == "__main__":
    unittest.main()
