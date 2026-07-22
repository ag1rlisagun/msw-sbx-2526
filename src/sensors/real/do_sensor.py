"""
do_sensor.py - Atlas Scientific Mini D.O. + Surveyor Analog Isolator via ADS1015.

UPDATED (FRR schematic, Figure 10):
    The electrical team routes the Surveyor Analog Isolator's analog output
    through an ADS1015 ADC, then to the Pi over I2C.  This replaces the
    previous PWM/pigpio approach.

Wiring (from schematic):
    D.O. probe  → Surveyor Analog Isolator
    Isolator analog output (+) → ADS1015 AIN2 (via R7 1kΩ + C5 1µF filter)
    ADS1015 SDA/SCL → Pi I2C bus (GPIO2/GPIO3)

The isolator outputs a voltage proportional to dissolved oxygen.
Raw voltage_mv is logged; conversion to mg/L is done post-flight
using the pre-flight calibration curve (see tools/analyse_do.py).

NOTE ON MODES: this "voltage_mv" schema is specific to direct mode (this
file) and the dummy sensor. Arduino mode instead uses the Atlas Surveyor
Arduino library's read_do_percentage() and logs "do_percent" directly,
since that library already calibrates on-device. tools/analyse_do.py
detects which schema a given database has and handles both — see that
file if you're doing post-flight analysis.

IMPORTANT - I2C ADDRESS:
    The ADS1015 may be shared with the current sensor (AIN0).
    If so, they use the same I2C address (default 0x48).
    If the D.O. uses a separate ADS1015, confirm the address with
    the electrical team.

Prerequisites:
    pip install adafruit-blinka adafruit-circuitpython-ads1x15
    Enable I2C: sudo raspi-config → Interface Options → I2C
"""

import time
import logging
from sensors.base_sensor import BaseSensor

log = logging.getLogger(__name__)


class DOSensor(BaseSensor):
    def __init__(
        self,
        i2c_address: int = 0x48,
        channel: int = 2,
        sample_count: int = 10,
    ):
        """
        Args:
            i2c_address: ADS1015 I2C address (default 0x48, may be shared
                         with current sensor on a different channel)
            channel:     ADS1015 analog input channel (2 = AIN2 from schematic)
            sample_count: readings to average per call to read()
        """
        super().__init__(name="dissolved_oxygen")
        self.i2c_address = i2c_address
        self.channel = channel
        self.sample_count = sample_count
        self._chan = None

    def connect(self) -> None:
        try:
            import board
            import busio
            import adafruit_ads1x15.ads1015 as ADS
            from adafruit_ads1x15.analog_in import AnalogIn

            i2c = busio.I2C(board.SCL, board.SDA)
            ads = ADS.ADS1015(i2c, address=self.i2c_address)
            channel_map = [ADS.P0, ADS.P1, ADS.P2, ADS.P3]
            self._chan = AnalogIn(ads, channel_map[self.channel])
            self._connected = True
            log.info(
                f"[{self.name}] ADS1015 connected at 0x{self.i2c_address:02X}, "
                f"channel {self.channel}."
            )
        except Exception as e:
            raise RuntimeError(f"[{self.name}] Failed to connect: {e}")

    def disconnect(self) -> None:
        self._chan = None
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
            voltages = []
            for _ in range(self.sample_count):
                voltages.append(self._chan.voltage)
                time.sleep(0.05)

            avg_voltage = sum(voltages) / len(voltages)
            # Convert to millivolts for consistency with post-flight analysis
            voltage_mv = avg_voltage * 1000.0
            voltage_mv = max(0.0, voltage_mv)  # clamp

            return {
                "voltage_mv": round(voltage_mv, 3),
            }
        except Exception as e:
            raise RuntimeError(f"[{self.name}] Read failed: {e}")
