"""
dummy_uvb_sensor.py - Dummy DFRobot SEN0636 UV Index Sensor.

PURPOSE:
    Stand-in for the real SEN0636 UV Index Sensor. Used when running
    the pipeline on a laptop or any machine without hardware attached.

    The real sensor (sensors/real/uvb_sensor.py) requires:
      - SEN0636 physical switch set to I2C side
      - smbus2 library
      - Sensor wired to I2C at address 0x23
      - Verified with: sudo i2cdetect -y 1

    This dummy returns values typical of moderate ambient UV with small
    noise: UV index around 3 (moderate), risk level 1 (moderate).

HOW TO USE:
    USE_DUMMY_SENSORS=true python3 src/main.py
    or: ./run.sh --dummy
"""

import random
from sensors.base_sensor import BaseSensor


class UVBSensor(BaseSensor):
    def __init__(self, i2c_address=0x23, sample_count=5, i2c_bus=1):
        # All parameters mirror the real sensor - ignored in dummy mode
        super().__init__(name="uvb")
        self._base_voltage_mv = 300.0  # mV - moderate UV
        self._base_index = 3.0         # UV index 0–11

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
        voltage = self._base_voltage_mv + random.uniform(-10.0, 10.0)
        index = self._base_index + random.uniform(-0.2, 0.2)
        index = max(0.0, min(index, 11.0))  # clamp to valid range
        # Risk level derived from UV index (matches SEN0636 logic)
        if index < 3:
            risk = 0   # Low
        elif index < 6:
            risk = 1   # Moderate
        elif index < 8:
            risk = 2   # High
        elif index < 11:
            risk = 3   # Very High
        else:
            risk = 4   # Extreme
        return {
            "uv_voltage_mv": round(voltage, 2),
            "uv_index":      round(index, 2),
            "uv_risk_level": risk,
        }
