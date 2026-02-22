"""
dummy_current_sensor.py - Dummy ACS723 current sensor.

PURPOSE:
    Stand-in for the real ACS723 current sensor read via ADS1115 ADC.
    Used when running the pipeline without hardware.

    The real sensor (sensors/real/current_sensor.py) requires:
      - ADS1115 wired to I2C
      - ACS723 wired to the ADS1115 input channel
      - adafruit-circuitpython-ads1x15 library
      - IMPORTANT: logic level shifter if ACS723 is on 5V rail

    This dummy simulates a small positive current (~50mA) with noise,
    representing baseline power draw from the bioreactor electronics.

HOW TO USE:
    USE_DUMMY_SENSORS=true python3 src/main.py
    or: ./run.sh --dummy
"""

import random
from sensors.base_sensor import BaseSensor


class CurrentSensor(BaseSensor):
    def __init__(self, i2c_address=0x48, channel=0, sensitivity=0.4, vcc=5.0, sample_count=10):
        # All parameters mirror the real sensor - ignored in dummy mode
        super().__init__(name="current")
        self._base_current = 0.05  # ~50mA baseline

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
        current = self._base_current + random.uniform(-0.01, 0.01)
        # Reverse of the ACS723 formula so voltage is consistent with current
        voltage = (current * 0.4) + 2.5
        return {
            "voltage_v": round(voltage, 5),
            "current_a": round(current, 5),
        }
