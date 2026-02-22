"""
uvb_sensor.py - DFRobot SEN0636 Gravity UV Index Sensor.

SENSOR: DFRobot SEN0636 Gravity: UV Index Sensor (240-370nm, UVA/UVB/UVC)
INTERFACE: I2C at address 0x23
SUPPLY: 3.3V-5V (set switch to I2C mode before use)
OUTPUTS (directly from onboard MCU - no conversion needed):
    - uv_voltage_mv  : raw UV sensor voltage in millivolts
    - uv_index       : UV index (0-11)
    - uv_risk_level  : risk level (0=Low, 1=Moderate, 2=High, 3=Very High, 4=Extreme)

IMPORTANT - HARDWARE SETUP:
    The SEN0636 has a physical switch for I2C/UART mode selection.
    Flip it to the I2C side before wiring.
    Verify it appears on the bus: sudo i2cdetect -y 1
    Expected address: 0x23

I2C REGISTER MAP (from DFRobot Arduino library source):
    0x10 - UV voltage raw data (2 bytes, little-endian, units: mV)
    0x11 - UV index (2 bytes, little-endian, 0-11)
    0x12 - UV risk level (2 bytes, little-endian, 0-4)

READ PROTOCOL:
    Write the register address, then read 2 bytes.
    Combine as: value = (byte[1] << 8) | byte[0]  (little-endian)

Prerequisites:
    pip install smbus2
    Enable I2C: sudo raspi-config → Interface Options → I2C
"""

import time
import logging
from sensors.base_sensor import BaseSensor

log = logging.getLogger(__name__)

# I2C register addresses (from DFRobot_UVIndex240370Sensor library)
_REG_UV_VOLTAGE  = 0x10   # raw UV voltage, 2 bytes, mV
_REG_UV_INDEX    = 0x11   # UV index, 2 bytes, 0-11
_REG_UV_RISK     = 0x12   # risk level, 2 bytes, 0-4

# Human-readable risk level labels for logging
_RISK_LABELS = {
    0: "Low",
    1: "Moderate",
    2: "High",
    3: "Very High",
    4: "Extreme",
}


class UVBSensor(BaseSensor):
    def __init__(
        self,
        i2c_address: int = 0x23,
        sample_count: int = 5,
        i2c_bus: int = 1,
    ):
        """
        Args:
            i2c_address: I2C address of the SEN0636 (default 0x23)
            sample_count: number of readings to average per call to read()
            i2c_bus: I2C bus number (1 on all modern Pi models)
        """
        super().__init__(name="uvb")
        self.i2c_address = i2c_address
        self.sample_count = sample_count
        self.i2c_bus = i2c_bus
        self._bus = None

    def connect(self) -> None:
        try:
            import smbus2
            self._bus = smbus2.SMBus(self.i2c_bus)
            # Verify the device responds by reading the voltage register
            self._read_register(_REG_UV_VOLTAGE)
            self._connected = True
            log.info(f"[{self.name}] SEN0636 connected at 0x{self.i2c_address:02X} on bus {self.i2c_bus}.")
        except Exception as e:
            raise RuntimeError(f"[{self.name}] Failed to connect to SEN0636: {e}")

    def disconnect(self) -> None:
        if self._bus:
            self._bus.close()
            self._bus = None
        self._connected = False
        self._measuring = False

    def start(self) -> None:
        if not self._connected:
            raise RuntimeError(f"[{self.name}] Call connect() first.")
        self._measuring = True

    def stop(self) -> None:
        self._measuring = False

    def _read_register(self, register: int) -> int:
        """
        Read a 2-byte little-endian unsigned value from the given register.
        Write the register address, then read 2 bytes.
        """
        data = self._bus.read_i2c_block_data(self.i2c_address, register, 2)
        return (data[1] << 8) | data[0]

    def read(self) -> dict:
        if not self._connected or not self._measuring:
            raise RuntimeError(f"[{self.name}] Sensor not ready.")
        try:
            voltages = []
            indices = []
            risks = []

            for _ in range(self.sample_count):
                voltages.append(self._read_register(_REG_UV_VOLTAGE))
                indices.append(self._read_register(_REG_UV_INDEX))
                risks.append(self._read_register(_REG_UV_RISK))
                time.sleep(0.05)

            avg_voltage = sum(voltages) / len(voltages)
            avg_index   = sum(indices)  / len(indices)
            # Risk level is discrete - take the most frequent value
            risk_level = max(set(risks), key=risks.count)

            return {
                "uv_voltage_mv": round(avg_voltage, 2),
                "uv_index":      round(avg_index, 2),
                "uv_risk_level": risk_level,
            }
        except Exception as e:
            raise RuntimeError(f"[{self.name}] Read failed: {e}")
