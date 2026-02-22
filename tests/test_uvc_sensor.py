"""
test_uvc_sensor.py - Tests for the MikroE UVC Click UV-C sensor.

WHAT TO TEST HERE:
    These tests use the dummy sensor so they run without hardware.
    The real sensor reads 2 raw bytes from the MCP3221 over I2C and
    converts them to a voltage and intensity - verify that math here.

    1. LIFECYCLE - connect → start → read → stop → disconnect.

    2. OUTPUT KEYS - read() must return "voltage_v" and "intensity_mw_cm2".

    3. FORMULA CORRECTNESS - verify intensity_mw_cm2 = voltage_v * calibration_factor.
       The calibration_factor is set in config.py (default 2.9).

    4. INTENSITY NON-NEGATIVE - intensity must never be negative.

    5. ADC BIT MATH (real sensor only) - the MCP3221 returns 12-bit data
       in 2 bytes: adc = ((byte[0] & 0x0F) << 8) | byte[1].
       Test this parsing with known byte inputs and expected adc values.
       This is easy to unit test without hardware by calling _read_raw()
       with mocked I2C data.

    6. READ BEFORE START - must raise RuntimeError.

    FUTURE (requires Pi hardware):
    7. I2C ADDRESS DETECTION - verify MCP3221 appears at 0x4D using
       i2cdetect before running.
    8. DARK READING - block all UV-C light and verify intensity is near 0.
    9. KNOWN SOURCE - expose to a calibrated UV-C source and verify reading.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sensors.dummy.dummy_uvc_sensor import UVCSensor


class TestUVCSensorLifecycle(unittest.TestCase):

    def test_connect_and_read(self):
        # TODO: full lifecycle returns dict with "voltage_v" and "intensity_mw_cm2"
        pass

    def test_read_before_start_raises(self):
        # TODO: RuntimeError if read() before start()
        pass


class TestUVCSensorOutput(unittest.TestCase):

    def test_output_keys(self):
        # TODO: verify both "voltage_v" and "intensity_mw_cm2" are in output
        pass

    def test_intensity_non_negative(self):
        # TODO: run 20 reads, verify intensity_mw_cm2 >= 0 every time
        pass

    def test_formula_correctness(self):
        # TODO: verify intensity_mw_cm2 ≈ voltage_v * 2.9 within a small tolerance
        pass


class TestMCP3221ADCParsing(unittest.TestCase):
    """
    Tests for the raw byte → ADC value parsing used in the real sensor.
    These can run without hardware because they only test the bit math.
    """

    def test_known_byte_values(self):
        # TODO: import the real UVCSensor and call _read_raw() with mocked smbus2
        # Example: bytes [0x01, 0xFF] should give adc = (0x01 << 8) | 0xFF = 511
        # Then voltage = (511 / 4096) * vcc
        # Use unittest.mock.patch to mock the smbus2.SMBus.read_i2c_block_data call
        pass

    def test_max_adc_value(self):
        # TODO: bytes [0x0F, 0xFF] → adc = 4095 → voltage ≈ vcc
        pass

    def test_zero_adc_value(self):
        # TODO: bytes [0x00, 0x00] → adc = 0 → voltage = 0 → intensity = 0
        pass


if __name__ == "__main__":
    unittest.main()
