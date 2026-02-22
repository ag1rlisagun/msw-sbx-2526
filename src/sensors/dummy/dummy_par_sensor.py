"""
dummy_par_sensor.py - Dummy PAR (photosynthetically active radiation) sensor.

PURPOSE:
    Stand-in for the SenseCAP S-PAR-02 PAR sensor read via ADS1115 ADC.
    Used when running the pipeline without hardware.

    The real sensor (sensors/real/par_sensor.py) requires:
      - ADS1115 wired to I2C (shared with current sensor - different channel)
      - PAR sensor analog output wired to ADS1115 input
      - adafruit-circuitpython-ads1x15 library

    This dummy simulates moderate indoor light (~1200 µmol/m²/s) with
    small noise, representing a cyanobacteria culture under grow lights.

HOW TO USE:
    USE_DUMMY_SENSORS=true python3 src/main.py
    or: ./run.sh --dummy
"""

import random
from sensors.base_sensor import BaseSensor


class PARSensor(BaseSensor):
    def __init__(self, i2c_address=0x48, channel=1, max_voltage=2.5, max_umol=2500.0, sample_count=10):
        # All parameters mirror the real sensor - ignored in dummy mode
        super().__init__(name="par")
        self._base_voltage = 1.2  # 1.2V → ~1200 µmol/m²/s

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
        voltage = self._base_voltage + random.uniform(-0.05, 0.05)
        voltage = max(0.0, min(voltage, 2.5))  # clamp to valid range
        par = (voltage / 2.5) * 2500.0
        return {
            "voltage_v": round(voltage, 5),
            "par_umol_m2_s": round(par, 2),
        }
