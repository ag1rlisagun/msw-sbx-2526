"""
dummy_uvc_sensor.py - Dummy UV-C sensor.

PURPOSE:
    Stand-in for the MikroE UVC Click board (GUVC-T21GH photodiode via
    MCP3221 I2C ADC). Used when running the pipeline without hardware.

    The real sensor (sensors/real/uvc_sensor.py) requires:
      - smbus2 library
      - MCP3221 wired to I2C at address 0x4D
      - UVC Click board powered at correct voltage (check jumper)

    This dummy returns a stable low UV-C intensity value with small
    noise, representing background radiation during stratospheric flight.

HOW TO USE:
    USE_DUMMY_SENSORS=true python3 src/main.py
    or: ./run.sh --dummy
"""

import random
from sensors.base_sensor import BaseSensor


class UVCSensor(BaseSensor):
    def __init__(self, i2c_address=0x4D, vcc=3.3, calibration_factor=2.9, sample_count=10, i2c_bus=1):
        # All parameters mirror the real sensor - ignored in dummy mode
        super().__init__(name="uvc")
        self._base_voltage = 0.8

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False
        self._measuring = False

    def start(self) -> None:
        if not self._connected:
            raise RuntimeError(f"[{self.name}] Call connect() first.")
        self._measuring = True

    def stop(self) -> None:
        self._measuring = False

    def read(self) -> dict:
        if not self._measuring:
            raise RuntimeError(f"[{self.name}] Sensor not measuring.")
        voltage = self._base_voltage + random.uniform(-0.02, 0.02)
        intensity = voltage * 2.9  # calibration_factor from config
        return {
            "voltage_v": round(voltage, 5),
            "intensity_mw_cm2": round(intensity, 5),
        }
