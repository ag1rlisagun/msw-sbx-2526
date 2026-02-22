"""
temperature_sensor.py - DS18B20 waterproof temperature sensor via 1-Wire.

Prerequisites:
    - 1-Wire must be enabled: sudo raspi-config → Interface Options → 1-Wire
    - pip install w1thermsensor
    - After wiring, verify: ls /sys/bus/w1/devices/  (expect 28-xxxxxxxxxxxx)
"""

import logging
from sensors.base_sensor import BaseSensor

log = logging.getLogger(__name__)


class TemperatureSensor(BaseSensor):
    def __init__(self, sensor_id: str = None):
        """
        Args:
            sensor_id: specific 1-Wire device ID (e.g. "28-abc123def456").
                       If None, auto-detects the first DS18B20 on the bus.
        """
        super().__init__(name="temperature")
        self.sensor_id = sensor_id
        self._sensor = None

    def connect(self) -> None:
        from w1thermsensor import W1ThermSensor, Sensor

        try:
            if self.sensor_id:
                self._sensor = W1ThermSensor(sensor_type=Sensor.DS18B20, sensor_id=self.sensor_id)
            else:
                self._sensor = W1ThermSensor()
            self._connected = True
            log.info(f"[{self.name}] Connected. Device ID: {self._sensor.id}")
        except Exception as e:
            raise RuntimeError(f"[{self.name}] Could not connect to DS18B20: {e}")

    def disconnect(self) -> None:
        self._sensor = None
        self._connected = False
        self._measuring = False

    def start(self) -> None:
        if not self._connected:
            raise RuntimeError(f"[{self.name}] Call connect() first.")
        self._measuring = True

    def stop(self) -> None:
        self._measuring = False

    def read(self) -> dict:
        if not self._connected or not self._measuring:
            raise RuntimeError(f"[{self.name}] Sensor not ready.")
        try:
            temp_c = self._sensor.get_temperature()
            return {"temperature_c": round(temp_c, 3)}
        except Exception as e:
            raise RuntimeError(f"[{self.name}] Read failed: {e}")
