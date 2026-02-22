"""
par_sensor.py - SenseCAP S-PAR-02 PAR sensor via ADS1115 ADC.

The PAR sensor outputs 0-2.5V linearly mapped to 0-2500 µmol/m²/s.
It shares the ADS1115 with the current sensor - make sure the channel
in config.py is different from the current sensor channel.

Prerequisites:
    pip install adafruit-blinka adafruit-circuitpython-ads1x15
"""

import time
import logging
from sensors.base_sensor import BaseSensor

log = logging.getLogger(__name__)


class PARSensor(BaseSensor):
    def __init__(
        self,
        i2c_address: int = 0x48,
        channel: int = 1,
        max_voltage: float = 2.5,
        max_umol: float = 2500.0,
        sample_count: int = 10,
    ):
        super().__init__(name="par")
        self.i2c_address = i2c_address
        self.channel = channel
        self.max_voltage = max_voltage
        self.max_umol = max_umol
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
            # Linear mapping: 0V → 0 µmol/m²/s, max_voltage → max_umol
            par_umol = (avg_voltage / self.max_voltage) * self.max_umol
            par_umol = max(0.0, min(par_umol, self.max_umol))  # clamp

            return {
                "voltage_v": round(avg_voltage, 5),
                "par_umol_m2_s": round(par_umol, 2),
            }
        except Exception as e:
            raise RuntimeError(f"[{self.name}] Read failed: {e}")
