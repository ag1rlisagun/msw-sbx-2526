"""
par_sensor.py - SenseCAP S-PAR-02 PAR sensor via RS-485 MODBUS RTU.

UPDATED (FRR schematic, Figure 8):
    The electrical team wired the RS-485 version of the PAR sensor through
    a MAX485E transceiver connected to the Pi's UART:
        - MAX485E RO  → GPIO15 (UART RXD, physical pin 10)
        - MAX485E DI  → GPIO14 (UART TXD, physical pin 8)
        - MAX485E RE/DE → GPIO22 (confirmed by GPIO scan test)

    The sensor speaks standard MODBUS RTU at 9600 baud, 8N1.
    Default slave address is 0x01.  Register 0x0000 holds the PAR value
    in µmol/m²/s as a 16-bit unsigned integer.

IMPORTANT - UART setup on the Pi:
    1. Disable the serial console:
         sudo raspi-config → Interface Options → Serial Port
         → Login shell over serial: NO
         → Serial port hardware enabled: YES
    2. Reboot.
    3. The serial port will be available as /dev/serial0.

Prerequisites:
    pip install minimalmodbus pyserial RPi.GPIO
"""

import time
import logging

import minimalmodbus
import serial

from sensors.base_sensor import BaseSensor

log = logging.getLogger(__name__)

_PAR_REGISTER = 0x0000
_PAR_FUNCTION_CODE = 3


class PARSensor(BaseSensor):
    def __init__(
        self,
        serial_port: str = "/dev/serial0",
        slave_address: int = 0x01,
        de_pin: int = 22,
        baudrate: int = 9600,
        sample_count: int = 3,
        max_umol: float = 2500.0,
    ):
        super().__init__(name="par")
        self.serial_port = serial_port
        self.slave_address = slave_address
        self.de_pin = de_pin
        self.baudrate = baudrate
        self.sample_count = sample_count
        self.max_umol = max_umol
        self._instrument = None
        self._gpio = None

    def _setup_de_pin(self) -> None:
        import RPi.GPIO as GPIO
        self._gpio = GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.de_pin, GPIO.OUT, initial=GPIO.LOW)

    def _set_tx_mode(self) -> None:
        self._gpio.output(self.de_pin, self._gpio.HIGH)

    def _set_rx_mode(self) -> None:
        self._gpio.output(self.de_pin, self._gpio.LOW)

    def connect(self) -> None:
        try:
            self._setup_de_pin()
            instrument = minimalmodbus.Instrument(
                self.serial_port, self.slave_address, mode=minimalmodbus.MODE_RTU,
            )
            instrument.serial.baudrate = self.baudrate
            instrument.serial.bytesize = serial.EIGHTBITS
            instrument.serial.parity = serial.PARITY_NONE
            instrument.serial.stopbits = serial.STOPBITS_ONE
            instrument.serial.timeout = 1.0
            instrument.close_port_after_each_call = False
            self._instrument = instrument
            self._modbus_read()
            self._connected = True
            log.info(
                f"[{self.name}] Connected via MODBUS RTU on {self.serial_port} "
                f"(slave {self.slave_address}, DE pin GPIO{self.de_pin})."
            )
        except Exception as e:
            raise RuntimeError(f"[{self.name}] Failed to connect: {e}")

    def disconnect(self) -> None:
        if self._instrument is not None:
            try:
                self._instrument.serial.close()
            except Exception:
                pass
            self._instrument = None
        if self._gpio is not None:
            try:
                self._gpio.cleanup(self.de_pin)
            except Exception:
                pass
            self._gpio = None
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
            readings = []
            for _ in range(self.sample_count):
                readings.append(self._modbus_read())
                time.sleep(0.2)
            avg_par = sum(readings) / len(readings)
            avg_par = max(0.0, min(avg_par, self.max_umol))
            return {"par_umol_m2_s": round(avg_par, 2)}
        except Exception as e:
            raise RuntimeError(f"[{self.name}] Read failed: {e}")

    def _modbus_read(self) -> float:
        self._set_tx_mode()
        time.sleep(0.001)
        try:
            orig_write = self._instrument.serial.write

            def _write_then_rx(data):
                result = orig_write(data)
                self._instrument.serial.flush()
                time.sleep(0.005)
                self._set_rx_mode()
                return result

            self._instrument.serial.write = _write_then_rx
            value = self._instrument.read_register(
                _PAR_REGISTER, number_of_decimals=0, functioncode=_PAR_FUNCTION_CODE,
            )
            self._instrument.serial.write = orig_write
            return float(value)
        finally:
            self._set_rx_mode()
