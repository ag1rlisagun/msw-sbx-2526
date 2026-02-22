"""
current_sensor.py - ACS723 current sensor read via ADS1115 ADC over I2C.

The ACS723 outputs a voltage proportional to current:
    current = (V_out - V_cc/2) / sensitivity

IMPORTANT HARDWARE NOTE from datasheet reference:
    The ACS723 requires 4.5-5.5V. If powered at 5V, the ADS1115 must
    also be on the 5V rail. The Pi's I2C lines are 3.3V logic - you
    need a logic level shifter between the Pi and ADS1115 to avoid
    damaging the Pi's GPIO pins.

Prerequisites:
    pip install adafruit-blinka adafruit-circuitpython-ads1x15
"""

import time
import logging
from sensors.base_sensor import BaseSensor

log = logging.getLogger(__name__)


class CurrentSensor(BaseSensor):
    def __init__(
        self,
        i2c_address: int = 0x48,
        channel: int = 0,
        sensitivity: float = 0.400,
        vcc: float = 5.0,
        sample_count: int = 10,
    ):
        """
        Args:
            i2c_address: ADS1115 I2C address (default 0x48)
            channel: ADS1115 channel connected to ACS723 output (0–3)
            sensitivity: V/A for your specific ACS723 part.
                         5A version  → 0.400 V/A
                         10A version → 0.264 V/A
            vcc: supply voltage to ACS723 (used to compute zero-current midpoint)
            sample_count: number of ADC readings to average per call to read()
        """
        super().__init__(name="current")
        self.i2c_address = i2c_address
        self.channel = channel
        self.sensitivity = sensitivity
        self.vcc = vcc
        self.sample_count = sample_count
        self._chan = None

    def connect(self) -> None:
        try:
            import board
            import busio
            import adafruit_ads1x15.ads1115 as ADS
            from adafruit_ads1x15.analog_in import AnalogIn

            i2c = busio.I2C(board.SCL, board.SDA)
            ads = ADS.ADS1115(i2c, address=self.i2c_address)
            channel_map = [ADS.P0, ADS.P1, ADS.P2, ADS.P3]
            self._chan = AnalogIn(ads, channel_map[self.channel])
            self._connected = True
            log.info(f"[{self.name}] ADS1115 connected at 0x{self.i2c_address:02X}, channel {self.channel}.")
        except Exception as e:
            raise RuntimeError(f"[{self.name}] Failed to connect to ADS1115: {e}")

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
            # Zero-current output is at VCC/2
            current_a = (avg_voltage - (self.vcc / 2.0)) / self.sensitivity

            return {
                "voltage_v": round(avg_voltage, 5),
                "current_a": round(current_a, 5),
            }
        except Exception as e:
            raise RuntimeError(f"[{self.name}] Read failed: {e}")
