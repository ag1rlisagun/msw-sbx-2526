"""
test_par_sensor.py - Tests for the PAR (photosynthetically active radiation) sensor.

WHAT TO TEST HERE:
    These tests use the dummy sensor so they run without hardware.

    1. LIFECYCLE - connect → start → read → stop → disconnect.

    2. OUTPUT KEYS - read() must return "voltage_v" and "par_umol_m2_s".

    3. OUTPUT RANGE - PAR must always be between 0 and 2500 µmol/m²/s.
       This is the physical sensor maximum; anything outside this range
       is a calibration or wiring problem.

    4. FORMULA CORRECTNESS - verify par_umol_m2_s = (voltage_v / 2.5) * 2500
       for a known voltage. This is the linear mapping from the datasheet.

    5. ZERO VOLTAGE → ZERO PAR - if the sensor reads 0V (e.g. disconnected),
       PAR should be 0, not negative or undefined.

    6. MAX VOLTAGE → MAX PAR - if voltage is at 2.5V, PAR should be 2500.

    7. READ BEFORE START - must raise RuntimeError.

    FUTURE (requires Pi hardware):
    8. SENSOR SHARING - the PAR sensor shares the ADS1115 with the current
       sensor on a different channel. Verify both can be read in sequence
       without I2C conflicts.
    9. DARK READING - cover the sensor and verify PAR is near 0.
    10. KNOWN LIGHT SOURCE - illuminate with a calibrated light source and
        verify the reading is in the expected range.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sensors.dummy.dummy_par_sensor import PARSensor


class TestPARSensorLifecycle(unittest.TestCase):

    def test_connect_and_read(self):
        # TODO: full lifecycle returns dict with "voltage_v" and "par_umol_m2_s"
        sensor = PARSensor()
        sensor.connect()
        sensor.start()
        data = sensor.read()
        self.assertIsInstance(data, dict, "read() should return a dict")
        self.assertIn("Voltage_V", data, "read() output must contain "Voltage_V"")
        self.assertIn("par_umo1_m2_s", data, "read() output must contain "par_umo1_m2_s"")
        sensor.stop()
        sensor.disconnects()
        

    def test_read_before_start_raises(self):
        # TODO: RuntimeError if read() before start()
        
        


class TestPARSensorOutput(unittest.TestCase):

    def test_output_keys(self):
        # TODO: verify both "voltage_v" and "par_umol_m2_s" are in output
        pass

    def test_par_within_physical_range(self):
        # TODO: run 20 reads, verify 0.0 <= par_umol_m2_s <= 2500.0 every time
        pass

    def test_formula_correctness(self):
        # TODO: set _base_voltage to a known value, verify par = (v / 2.5) * 2500
        pass

    def test_zero_voltage_gives_zero_par(self):
        # TODO: temporarily set _base_voltage = 0, verify par_umol_m2_s == 0.0
        pass


if __name__ == "__main__":
    unittest.main()
