"""
do_sensor.py - Atlas Scientific Mini D.O. + Surveyor Analog Isolator.

The Surveyor Isolator converts the D.O. probe's analog voltage into a
10.6 kHz PWM signal. Pulse width encodes the oxygen level.

Math (from do_iso_surveyor.cpp reference):
    voltage_mv = (avg_pulse_width_us * 20.0) - 60.0

pigpio is required because standard GPIO interrupt libraries (RPi.GPIO)
do not have enough timing resolution for a 10.6 kHz signal.

Prerequisites:
    sudo apt install pigpio python3-pigpio
    sudo systemctl enable pigpiod
    sudo systemctl start pigpiod
"""

import time
import logging
import pigpio

from sensors.base_sensor import BaseSensor

log = logging.getLogger(__name__)


class DOSensor(BaseSensor):
    def __init__(
        self,
        pwm_pin: int = 17,
        avg_samples: int = 30,
        pulse_timeout_us: int = 400,
    ):
        """
        Args:
            pwm_pin: BCM GPIO pin connected to the Surveyor Isolator PWM output
            avg_samples: number of pulses to average (mirrors volt_avg_len*3 in C++)
            pulse_timeout_us: max wait for a pulse in microseconds
        """
        super().__init__(name="dissolved_oxygen")
        self.pwm_pin = pwm_pin
        self.avg_samples = avg_samples
        self.pulse_timeout_us = pulse_timeout_us
        self._pi = None
        self._pulse_widths = []
        self._cb = None

    def connect(self) -> None:
        try:
            self._pi = pigpio.pi()
            if not self._pi.connected:
                raise RuntimeError("pigpiod daemon is not running. Start with: sudo systemctl start pigpiod")
            self._pi.set_mode(self.pwm_pin, pigpio.INPUT)
            self._pi.set_pull_up_down(self.pwm_pin, pigpio.PUD_DOWN)
            self._connected = True
            log.info(f"[{self.name}] Connected via pigpio on GPIO{self.pwm_pin}.")
        except Exception as e:
            raise RuntimeError(f"[{self.name}] Failed to connect: {e}")

    def disconnect(self) -> None:
        self.stop()
        if self._pi and self._pi.connected:
            self._pi.stop()
        self._pi = None
        self._connected = False

    def start(self) -> None:
        if not self._connected:
            raise RuntimeError(f"[{self.name}] Call connect() first.")

        self._pulse_widths = []

        # Register a callback to measure HIGH pulse widths via pigpio ticks
        self._last_rise = None

        def _edge_cb(gpio, level, tick):
            if level == 1:
                self._last_rise = tick
            elif level == 0 and self._last_rise is not None:
                # pigpio tick is in microseconds, wraps at 2^32
                width = pigpio.tickDiff(self._last_rise, tick)
                if width < self.pulse_timeout_us:
                    self._pulse_widths.append(width)
                    if len(self._pulse_widths) > self.avg_samples * 2:
                        self._pulse_widths = self._pulse_widths[-self.avg_samples:]

        self._cb = self._pi.callback(self.pwm_pin, pigpio.EITHER_EDGE, _edge_cb)
        self._measuring = True
        # Allow callback to accumulate some samples before first read
        time.sleep(0.1)
        log.info(f"[{self.name}] Measurement started.")

    def stop(self) -> None:
        if self._cb:
            self._cb.cancel()
            self._cb = None
        self._measuring = False

    def read(self) -> dict:
        if not self._connected or not self._measuring:
            raise RuntimeError(f"[{self.name}] Sensor not ready.")

        samples = self._pulse_widths[-self.avg_samples:]

        if not samples:
            # No pulses received - check pin state to distinguish 0% vs 100% DO
            pin_high = self._pi.read(self.pwm_pin)
            avg = 80.0 if pin_high else 0.0
        else:
            avg = sum(samples) / len(samples)

        # Convert pulse width to voltage (from C++ reference)
        voltage_mv = (avg * 20.0) - 60.0
        voltage_mv = max(0.0, voltage_mv)  # clamp - can't be negative

        return {
            "avg_pulse_width_us": round(avg, 3),
            "voltage_mv": round(voltage_mv, 3),
            # Calibration to mg/L or % saturation is done post-flight
            # using the known voltage-to-DO curve for this probe.
        }
