"""
test_do_sensor.py - Tests for the Atlas Scientific D.O. sensor.

WHAT TO TEST HERE:
    These tests use the dummy sensor so they run without hardware.

    NOTE: this file was updated to match the current (post-FRR) hardware.
    The D.O. sensor no longer uses a PWM pulse-width read via pigpio — it
    now reads a raw analog voltage through the ADS1015 ADC (see
    src/config.py's 2026-05-14 changelog and sensors/real/do_sensor.py).
    If you're picking up an older version of this file, ignore any
    references to "avg_pulse_width_us" or a pulse-width formula — those
    describe hardware that is no longer in use.

    1. LIFECYCLE - connect → start → read → stop → disconnect.

    2. OUTPUT KEYS - read() must return "voltage_mv" (dummy/direct mode)
       — this is a raw ADS1015 ADC reading, NOT yet converted to % saturation
       or mg/L. That conversion happens post-flight in tools/analyse_do.py
       using a pre-flight calibration voltage recorded in the lab notebook.

    3. VOLTAGE NEVER NEGATIVE - voltage_mv must be clamped to >= 0.0.
       Test this over many reads.

    4. PLAUSIBLE RANGE - voltage_mv should stay within a realistic range for
       the Surveyor Isolator output (roughly 0–1200mV). Values far outside
       this suggest a wiring or ADC channel error, not real DO data.

    5. READ BEFORE START - must raise RuntimeError.

    6. NO HARDCODED CONVERSION - the sensor driver itself must not attempt
       any DO% or mg/L conversion. That belongs in tools/analyse_do.py,
       which is run post-flight once a calibration voltage is known.

    FUTURE (requires Pi hardware):
    7. ZERO CURRENT / OPEN AIR CALIBRATION - with the probe in open air at
       a known temperature, voltage_mv should stabilise and match the
       value later used as the --cal argument to tools/analyse_do.py.
    8. KNOWN CALIBRATION POINT - with the probe in air-saturated water at
       known temperature and pressure, verify voltage_mv matches expected value.

    ARDUINO MODE NOTE:
        In Arduino mode, the dissolved_oxygen table instead has a
        "do_percent" column (from the Atlas Surveyor Arduino library's
        read_do_percentage(), which calibrates on-device). These tests
        only cover the dummy/direct-mode "voltage_mv" schema. See
        tools/analyse_do.py for how both schemas are handled.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sensors.dummy.dummy_do_sensor import DOSensor


class TestDOSensorLifecycle(unittest.TestCase):

    def test_connect_and_read(self):
        # TODO: full lifecycle returns dict with "voltage_mv"
        pass

    def test_read_before_start_raises(self):
        # TODO: RuntimeError if read() before start()
        pass


class TestDOSensorOutput(unittest.TestCase):

    def test_output_keys(self):
        # TODO: verify "voltage_mv" is present in output
        pass

    def test_voltage_never_negative(self):
        # TODO: run 20 reads, assert voltage_mv >= 0.0 every time
        # This is critical - the clamp in dummy/real read() must always hold
        pass

    def test_voltage_in_plausible_range(self):
        # TODO: run 20 reads, verify voltage_mv stays roughly within
        # 0-1200mV (typical Surveyor Isolator output range)
        pass

    def test_no_hardcoded_conversion(self):
        # TODO: verify read() does NOT attempt any DO% or mg/L conversion —
        # that belongs in tools/analyse_do.py post-flight, not in the sensor
        # driver. (I.e. the returned dict should only contain voltage_mv,
        # nothing derived from it.)
        pass

    def test_multiple_reads_succeed(self):
        # TODO: 10+ consecutive reads without error
        pass


if __name__ == "__main__":
    unittest.main()
