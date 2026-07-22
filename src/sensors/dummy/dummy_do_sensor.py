"""
dummy_do_sensor.py - Dummy dissolved oxygen (D.O.) sensor.

PURPOSE:
    Stand-in for the Atlas Scientific Mini D.O. + Surveyor Analog Isolator
    read via ADS1015 ADC. Used when running the pipeline without hardware.

    The real sensor (sensors/real/do_sensor.py) requires:
      - ADS1015 wired to I2C
      - Surveyor Isolator analog output on AIN2
      - adafruit-circuitpython-ads1x15 library

    This dummy simulates a voltage near saturation (~1040mV), matching
    a healthy cyanobacteria culture.

    NOTE ON MODES: this dummy (and the direct-mode real driver) reports a
    raw "voltage_mv" value that is converted to % saturation / mg/L
    post-flight using tools/analyse_do.py and a pre-flight calibration
    voltage. Arduino mode instead logs "do_percent" directly from the
    Atlas Surveyor library, which calibrates on-device. See
    tools/analyse_do.py for how both are handled.

HOW TO USE:
    USE_DUMMY_SENSORS=true python3 src/main.py
    or: ./run.sh --dummy
"""

import random
from sensors.base_sensor import BaseSensor


class DOSensor(BaseSensor):
    def __init__(self, i2c_address=0x48, channel=2, sample_count=10):
        # All parameters mirror the real sensor - ignored in dummy mode
        super().__init__(name="dissolved_oxygen")
        self._base_voltage_mv = 1040.0  # ~full saturation

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
        voltage_mv = self._base_voltage_mv + random.uniform(-20.0, 20.0)
        voltage_mv = max(0.0, voltage_mv)
        return {
            "voltage_mv": round(voltage_mv, 3),
        }
