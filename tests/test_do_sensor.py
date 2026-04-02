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

def _lifecycle():
    """Helper: full connect → start → read → stop → disconnect cycle."""
    # Pattern from test_sensors_dummy.py

    s = DOSensor()
    s.connect()
    s.start()
    data = s.read()
    s.stop()
    s.disconnect()
    return data


def start_sensor_for_read() -> DOSensor:
    """Helper, to start sensor without read"""

    sensor = DOSensor()
    sensor.connect()
    sensor.start()
    return sensor

def end_sensor(sensor):
    """Helper to end sensor after read"""

    sensor.stop()
    sensor.disconnect



class TestDOSensorLifecycle(unittest.TestCase):

    
    def test_connect_and_read(self):

         #full lifecycle returns dict with "avg_pulse_width_us" and "voltage_mv"
        """Done"""

        sensor = start_sensor_for_read()     

        main_dict = sensor.read()

        self.assertIsInstance(main_dict,dict)
        self.assertIn("avg_pulse_width_us", main_dict)
        self.assertIn("voltage_mv", main_dict)

        end_sensor(sensor)
   
    def test_read_before_start_raises(self):
        #RuntimeError if read() before start()
        """Done"""

        sensor = DOSensor()
        sensor.connect()
        with self.assertRaises(RuntimeError):
            sensor.read()
        sensor.stop()
        sensor.disconnect()


        

    def test_start_without_connect_raises(self):
        #testing if start raises an exception
        #additional test
        sensor = DOSensor()
        with self.assertRaises(RuntimeError):
            sensor.start()


        


class TestDOSensorOutput(unittest.TestCase):

    def test_output_keys(self):
        #verify both "avg_pulse_width_us" and "voltage_mv" are in output
        """Done"""
        
        data = _lifecycle(DOSensor)
        self.assertIn("avg_pulse_width_us", data)
        self.assertIn("voltage_mv", data)

    def test_voltage_never_negative(self):
        # run 20 reads, assert voltage_mv >= 0.0 every time
        # This is critical - the clamp in the formula must always hold
        """Done"""

        sensor = start_sensor_for_read()

        for i in range(20):
            main_dict = sensor.read()
            self.assertTrue(main_dict["voltage_mv"] >= 0.0)

        end_sensor(sensor)

    def test_formula_correctness(self):
        #for a known avg_pulse_width_us, verify voltage_mv = (pulse * 20) - 60
        # You can temporarily set _base_pulse to a fixed value and check the math
        """Done"""

        sensor = start_sensor_for_read()
        
        main_dict = sensor.read()
        calculated = (main_dict["avg_pulse_width_us"]*20)-60
        self.assertAlmostEqual(main_dict["voltage_mv"], round(max(0.0, calculated), 4), places=1)

        end_sensor(sensor)

    def test_pulse_width_in_realistic_range(self):
        #verifies that avg_pulse_width_us stays between 0 and 100µs over many reads
        """Done"""
        
        
        sensor = start_sensor_for_read()
        
        for i in range(20):
            main_dict = sensor.read()
            
            self.assertGreaterEqual(main_dict["avg_pulse_width_us"], 0)
            self.assertLessEqual(main_dict["avg_pulse_width_us"], 100)

        end_sensor(sensor)


if __name__ == "__main__":
    unittest.main()
