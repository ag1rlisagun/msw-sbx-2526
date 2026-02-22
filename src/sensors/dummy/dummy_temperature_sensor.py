"""
dummy_temperature_sensor.py - Dummy DS18B20 temperature sensor.

PURPOSE:
    Stand-in for the real DS18B20 1-Wire sensor. Used when running
    the pipeline on a laptop or any machine without hardware attached.

    The real sensor (sensors/real/temperature_sensor.py) requires:
      - 1-Wire enabled via raspi-config
      - w1thermsensor library
      - A physical DS18B20 wired to GPIO

    This dummy returns a slowly drifting value around 25°C so logged
    data looks plausible during pipeline and integration testing.

HOW TO USE:
    USE_DUMMY_SENSORS=true python3 src/main.py
    or: ./run.sh --dummy
"""

import random
from sensors.base_sensor import BaseSensor


class TemperatureSensor(BaseSensor):
    def __init__(self, sensor_id=None):
        # sensor_id mirrors the real sensor's parameter - ignored in dummy mode
        super().__init__(name="temperature")
        self._base_temp = 25.0

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
        temp = self._base_temp + random.uniform(-0.5, 0.5)
        return {"temperature_c": round(temp, 3)}
