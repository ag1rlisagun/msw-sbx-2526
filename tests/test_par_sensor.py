"""
test_par_sensor.py - Tests for the PAR (photosynthetically active radiation) sensor.

WHAT TO TEST HERE:
    These tests use the dummy sensor so they run without hardware.

    NOTE: this file was updated to match the current (post-FRR) hardware.
    The PAR sensor is now the RS-485 MODBUS version (SenseCAP S-PAR-02
    via MAX485E), which returns par_umol_m2_s directly from a MODBUS
    register — there is no analog voltage stage and no voltage-based
    formula involved (that described the earlier ADS1115 analog version,
    which this replaced — see src/config.py's 2026-05-14 changelog).
    If you're picking up an older version of this file, ignore any
    references to "voltage_v" or a voltage-to-PAR formula for this sensor.

    1. LIFECYCLE - connect → start → read → stop → disconnect.

    2. OUTPUT KEYS - read() must return "par_umol_m2_s".

    3. OUTPUT RANGE - par_umol_m2_s must always be between 0 and 2500.
       This is the physical sensor maximum (config.PAR_MAX_UMOL); anything
       outside this range is a calibration or wiring problem.

    4. NO VOLTAGE FIELD - the RS-485 MODBUS sensor returns PAR as an
       integer µmol/m²/s value directly from register 0x0000 — there is
       no analog voltage stage and no voltage-to-PAR formula involved
       (unlike the earlier ADS1115 analog version this replaced).

    5. PAR IS NUMERIC - par_umol_m2_s should always be a float/int, never
       None or a string, even after averaging sample_count readings.

    6. READ BEFORE START - must raise RuntimeError.

    FUTURE (requires Pi hardware):
    7. SENSOR SHARING - in Arduino mode the PAR sensor shares the
       SoftwareSerial bus and DE/RE pin with no other sensor, so no I2C-
       style conflict is expected — but confirm timing doesn't interfere
       with the UV Index or UVC I2C reads happening in the same loop.
    8. DARK READING - cover the sensor and verify PAR is near 0.
    9. KNOWN LIGHT SOURCE - illuminate with a calibrated light source and
       verify the reading is in the expected range.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sensors.dummy.dummy_par_sensor import PARSensor


class TestPARSensorLifecycle(unittest.TestCase):

    def test_connect_and_read(self):
        # TODO: full lifecycle returns dict with "par_umol_m2_s"
        pass

    def test_read_before_start_raises(self):
        # TODO: RuntimeError if read() before start()
        pass


class TestPARSensorOutput(unittest.TestCase):

    def test_output_keys(self):
        # TODO: verify "par_umol_m2_s" is in output, and "voltage_v" is NOT
        # (this sensor has no analog voltage stage)
        pass

    def test_par_within_physical_range(self):
        # TODO: run 20 reads, verify 0.0 <= par_umol_m2_s <= 2500.0 every time
        pass

    def test_par_is_integer_valued(self):
        # TODO: the MODBUS register returns a 16-bit unsigned int — verify
        # par_umol_m2_s has no fractional component from the raw register
        # read itself (averaging across sample_count may introduce
        # decimals — that's expected and fine, this just checks the
        # underlying register value logic is sound, e.g. by inspecting a
        # single unaveraged sample if the sensor exposes one)
        pass

    def test_multiple_reads_succeed(self):
        # TODO: 10+ consecutive reads without error
        pass


if __name__ == "__main__":
    unittest.main()
