"""
dummy_do_sensor.py - Dummy dissolved oxygen (D.O.) sensor.

PURPOSE:
    Stand-in for the Atlas Scientific Mini D.O. + Surveyor Analog Isolator.
    Used when running the pipeline without hardware.

    The real sensor (sensors/real/do_sensor.py) requires:
      - pigpio daemon running (sudo systemctl start pigpiod)
      - Surveyor Isolator PWM output wired to a GPIO pin
      - Physical Atlas Scientific Mini D.O. probe

    This dummy simulates the PWM pulse width output as if oxygen levels
    are near saturation (~55µs pulse → ~1040mV), matching a healthy
    cyanobacteria culture.

HOW TO USE:
    USE_DUMMY_SENSORS=true python3 src/main.py
    or: ./run.sh --dummy
"""

import random
from sensors.base_sensor import BaseSensor


class DOSensor(BaseSensor):
    def __init__(self, pwm_pin=17, avg_samples=30, pulse_timeout_us=400):
        # All parameters mirror the real sensor - ignored in dummy mode
        super().__init__(name="dissolved_oxygen")
        self._base_pulse = 55.0  # µs - maps to ~1040mV via (pulse * 20) - 60

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
        avg_pulse = self._base_pulse + random.uniform(-2.0, 2.0)
        voltage_mv = (avg_pulse * 20.0) - 60.0
        return {
            "avg_pulse_width_us": round(avg_pulse, 3),
            "voltage_mv": round(max(0.0, voltage_mv), 3),
        }
