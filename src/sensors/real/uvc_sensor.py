"""
uvc_sensor.py — MikroE UVC Click (GUVC-T21GH) via MCP3221 12-bit ADC over I2C.

Reading protocol (no library needed — raw I2C):
    1. Read 2 bytes from the MCP3221 at its I2C address.
    2. Combine: adc_val = (byte[0] << 8) | byte[1]  (12-bit value, top 4 bits ignored)
    3. voltage = (adc_val / 4096.0) * VCC
    4. intensity_mW_cm2 = voltage * calibration_factor

Prerequisites:
    pip install smbus2
    Enable I2C: sudo raspi-config → Interface Options → I2C
"""

import time
import logging
from sensors.base_sensor import BaseSensor

log = logging.getLogger(__name__)

# MCP3221 only has one channel — just read 2 bytes
_MCP3221_READ_BYTES = 2
_MCP3221_ADC_MAX = 4096.0


class UVCSensor(BaseSensor):
    def __init__(
        self,
        i2c_address: int = 0x4D,
        vcc: float = 3.3,
        calibration_factor: float = 2.9,
        sample_count: int = 10,
        i2c_bus: int = 1,
    ):
        """
        Args:
            i2c_address: MCP3221 I2C address (default 0x4D for MCP3221A5T)
            vcc: voltage supplied to the UVC Click board (check jumper)
            calibration_factor: converts voltage to mW/cm² — verify against
                                your sensor's calibration sheet (typical 2.8–3.0)
            sample_count: readings to average per call to read()
            i2c_bus: I2C bus number (1 on all modern Pi models)
        """
        super().__init__(name="uvc")
        self.i2c_address = i2c_address
        self.vcc = vcc
        self.calibration_factor = calibration_factor
        self.sample_count = sample_count
        self.i2c_bus = i2c_bus
        self._bus = None

    def connect(self) -> None:
        try:
            import smbus2
            self._bus = smbus2.SMBus(self.i2c_bus)
            # Verify the device responds
            self._bus.read_i2c_block_data(self.i2c_address, 0, _MCP3221_READ_BYTES)
            self._connected = True
            log.info(f"[{self.name}] MCP3221 connected at 0x{self.i2c_address:02X} on bus {self.i2c_bus}.")
        except Exception as e:
            raise RuntimeError(f"[{self.name}] Failed to connect to MCP3221: {e}")

    def disconnect(self) -> None:
        if self._bus:
            self._bus.close()
            self._bus = None
        self._connected = False
        self._measuring = False

    def start(self) -> None:
        if not self._connected:
            raise RuntimeError(f"[{self.name}] Call connect() first.")
        self._measuring = True

    def stop(self) -> None:
        self._measuring = False

    def _read_raw(self) -> float:
        """Read one raw ADC value and convert to voltage."""
        data = self._bus.read_i2c_block_data(self.i2c_address, 0, _MCP3221_READ_BYTES)
        adc_val = ((data[0] & 0x0F) << 8) | data[1]  # 12-bit, mask top nibble
        return (adc_val / _MCP3221_ADC_MAX) * self.vcc

    def read(self) -> dict:
        if not self._connected or not self._measuring:
            raise RuntimeError(f"[{self.name}] Sensor not ready.")
        try:
            voltages = []
            for _ in range(self.sample_count):
                voltages.append(self._read_raw())
                time.sleep(0.05)

            avg_voltage = sum(voltages) / len(voltages)
            intensity_mw_cm2 = avg_voltage * self.calibration_factor

            return {
                "voltage_v": round(avg_voltage, 5),
                "intensity_mw_cm2": round(intensity_mw_cm2, 5),
            }
        except Exception as e:
            raise RuntimeError(f"[{self.name}] Read failed: {e}")
