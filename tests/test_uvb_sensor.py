"""
test_uvb_sensor.py - Tests for the DFRobot SEN0636 UV Index Sensor.

SENSOR: DFRobot SEN0636 Gravity UV Index Sensor (240-370nm)
INTERFACE: I2C at address 0x23 (set physical switch to I2C side)
OUTPUTS:
    - uv_voltage_mv  : raw UV sensor voltage in millivolts
    - uv_index       : UV index 0-11
    - uv_risk_level  : risk level 0 (Low) through 4 (Extreme)

WHAT TO TEST HERE:
    These tests use the dummy sensor so they run without hardware.

    1. LIFECYCLE - connect → start → read → stop → disconnect.

    2. OUTPUT KEYS - read() must return "uv_voltage_mv", "uv_index",
       and "uv_risk_level".

    3. UV INDEX RANGE - uv_index must always be between 0 and 11 (WHO scale).

    4. RISK LEVEL RANGE - uv_risk_level must be an integer 0-4.

    5. RISK LEVEL CONSISTENCY - risk level must be consistent with UV index:
        0 (Low)       → index < 3
        1 (Moderate)  → 3 ≤ index < 6
        2 (High)      → 6 ≤ index < 8
        3 (Very High) → 8 ≤ index < 11
        4 (Extreme)   → index = 11

    6. VOLTAGE NON-NEGATIVE - uv_voltage_mv must never be negative.

    7. READ BEFORE START - must raise RuntimeError.

    8. I2C REGISTER PARSING (real sensor only):
       The SEN0636 returns 2-byte little-endian values.
       Formula: value = (byte[1] << 8) | byte[0]
       Test _read_register() with mocked smbus2 data:
           bytes [0x2C, 0x01] → value = (0x01 << 8) | 0x2C = 300
       Use unittest.mock.patch to mock smbus2.SMBus.read_i2c_block_data.

    FUTURE (requires Pi hardware):
    9.  SWITCH POSITION - verify 0x23 appears on i2cdetect after setting
        the physical switch to I2C side.
    10. DARK READING - cover sensor, verify uv_index is near 0.
    11. OUTDOOR READING - verify values change meaningfully in sunlight.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sensors.dummy.dummy_uvb_sensor import UVBSensor
from sensors.real.uvb_sensor import UVBSensor as RealUVBsensor

def lifecycle() -> dict:
    sensor = UVBSensor()
    sensor.connect()
    sensor.start()
    data = sensor.read()
    sensor.stop()
    sensor.disconnect()
    return data

def sensor_for_read() -> UVBSensor:
    sensor = UVBSensor()
    sensor.connect()
    sensor.start()
    return sensor

def end_for_read(sensor):
    sensor.stop()
    sensor.disconnect()
    


class TestUVBSensorLifecycle(unittest.TestCase):

    def test_connect_and_read(self):
        #full lifecycle completes without error and returns expected keys
        data = lifecycle()
        self.assertIsInstance(data, dict)
        self.assertIn("uv_voltage_mv", data)
        self.assertIn("uv_index", data)
        self.assertIn("uv_risk_level", data)

    def test_read_before_start_raises(self):
        #RuntimeError if read() is called before start()

        sensor = UVBSensor()
        sensor.connect()
        with self.assertRaises(RuntimeError):
            sensor.read()
        end_for_read(sensor)
        

    def test_start_before_connect_raises(self):
        #RuntimeError if start() is called before connect()
        sensor = UVBSensor()
        with self.assertRaises(RuntimeError):
            sensor.start()


class TestUVBSensorOutput(unittest.TestCase):

    def _make_and_start(self):
        s = UVBSensor()
        s.connect()
        s.start()
        return s

    def test_output_keys(self):
        #verify "uv_voltage_mv", "uv_index", "uv_risk_level" all present
        data = lifecycle()
        self.assertIsInstance(data, dict)
        self.assertIn("uv_voltage_mv", data)
        self.assertIn("uv_index", data)
        self.assertIn("uv_risk_level", data)

    def test_uv_index_within_who_range(self):
        #run 20 reads, verify 0.0 <= uv_index <= 11.0 every time
       
        sensor = self._make_and_start()

        for i in range(20):
            data = sensor.read()
            self.assertGreaterEqual(data["uv_index"], 0.0)
            self.assertLessEqual(data["uv_index"], 11.0)
        
        end_for_read(sensor)


    def test_risk_level_within_range(self):
        #run 20 reads, verify uv_risk_level is an int in {0, 1, 2, 3, 4}
        
        check = [0,1,2,3,4]
        
        sensor = self._make_and_start()
        for i in range(20):
            data = sensor.read()
            self.assertIn("uv_risk_level", data)
            self.assertIsInstance(data["uv_risk_level"], int)
            self.assertIn(data["uv_risk_level"], check)

        end_for_read(sensor)

    def test_voltage_non_negative(self):
        #run 20 reads, verify uv_voltage_mv >= 0 every time

        sensor = self._make_and_start()
        for i in range(20):
            data = sensor.read()
            self.assertGreaterEqual(data["uv_voltage_mv"], 0)

        end_for_read(sensor)


    def test_risk_level_consistent_with_index(self):
        # TODO: for each read, verify risk_level matches index using this table:
        #   index < 3   → risk 0
        #   3 <= index < 6  → risk 1
        #   6 <= index < 8  → risk 2
        #   8 <= index < 11 → risk 3
        #   index >= 11 → risk 4
        # This is the most important test - catches calibration errors.
       
        sensor = self._make_and_start()
        for i in range(20):
            data = sensor.read()
            if data["uv_index"] < 3:
                self.assertEqual(data["uv_risk_level"], 0)
            elif 3 <= data["uv_index"] < 6:
                self.assertEqual(data["uv_risk_level"], 1)
            elif 6 <= data["uv_index"] < 8:
                self.assertEqual(data["uv_risk_level"], 2)
            elif 8 <= data["uv_index"] < 11:
                self.assertEqual(data["uv_risk_level"], 3)
            elif data["uv_index"] >= 11:
                self.assertEqual(data["uv_risk_level"], 4)

        end_for_read(sensor)
            
            


       


class TestSEN0636RegisterParsing(unittest.TestCase):
    """
    Tests for the 2-byte little-endian register parsing used in the real sensor.
    These can run without hardware because they only test the byte math.
    """

    def test_little_endian_parsing(self):
        # TODO: mock smbus2.SMBus.read_i2c_block_data to return [0x2C, 0x01]
        # import the real UVBSensor, call _read_register(0x10)
        # verify result = (0x01 << 8) | 0x2C = 300
        # Example mock pattern:
        #   from unittest.mock import patch, MagicMock
        #   with patch("smbus2.SMBus") as MockSMBus:
        #       instance = MockSMBus.return_value
        #       instance.read_i2c_block_data.return_value = [0x2C, 0x01]
        #       from sensors.real.uvb_sensor import UVBSensor as RealUVBSensor
        #       s = RealUVBSensor()
        #       s.connect()
        #       result = s._read_register(0x10)
        #       self.assertEqual(result, 300)
        """sensor = RealUVBsensor()
        sensor.connect()
        result = sensor. _read_register(0x10)
        self.assertEqual(result, 300) """


    def test_zero_bytes_give_zero(self):
        # TODO: [0x00, 0x00] → value = 0
        pass

    def test_max_bytes_give_max(self):
        # TODO: [0xFF, 0xFF] → value = 65535
        pass


if __name__ == "__main__":
    unittest.main()
