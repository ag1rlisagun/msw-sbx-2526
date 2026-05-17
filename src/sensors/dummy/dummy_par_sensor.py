"""
dummy_par_sensor.py - Dummy PAR (photosynthetically active radiation) sensor.

PURPOSE:
    Stand-in for the SenseCAP S-PAR-02 PAR sensor via RS-485 MODBUS.
    Used when running the pipeline without hardware.

    The real sensor (sensors/real/par_sensor.py) requires:
      - MAX485E transceiver wired to UART (GPIO14/GPIO15)
      - DE/RE pin on GPIO22
      - minimalmodbus + pyserial libraries

    This dummy simulates moderate indoor light (~1200 µmol/m²/s) with
    small noise, representing a cyanobacteria culture under grow lights.

HOW TO USE:
    USE_DUMMY_SENSORS=true python3 src/main.py
    or: ./run.sh --dummy
"""

import random
from sensors.base_sensor import BaseSensor


class PARSensor(BaseSensor):
    def __init__(
        self,
        serial_port="/dev/serial0",
        slave_address=0x01,
        de_pin=22,
        baudrate=9600,
        sample_count=3,
        max_umol=2500.0,
    ):
        # All parameters mirror the real sensor - ignored in dummy mode
        super().__init__(name="par")
        self.max_umol = max_umol

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
        par = 1200.0 + random.uniform(-50.0, 50.0)
        par = max(0.0, min(par, self.max_umol))
        return {
            "par_umol_m2_s": round(par, 2),
        }