"""
config.py - Central configuration for MSW CAN-SBX 2025-2026.

All hardware pin assignments, sensor parameters, and tunable constants
live here. Change values here rather than touching sensor driver code.

UPDATED 2026-05-14 based on FRR presentation schematics:
    - Current sensor: ADS1015 (12-bit) replaces ADS1115 (16-bit)
    - D.O. sensor: ADS1015 analog read replaces PWM/pigpio
    - PAR sensor: RS-485 MODBUS via MAX485E replaces ADS1115 I2C
    - Heater: MOSFET PWM replaces SSR on/off
    - UVB sensor: unchanged (direct I2C @ 0x23)
    - UVC sensor: unchanged (MCP3221 @ 0x4D)
    - Temperature sensor: unchanged (1-Wire)

UPDATED (Arduino/Pi integration pass):
    - Combinedsensors.ino reads all six sensors and streams over USB serial.
    - Current sensor on the Arduino is an INA226 (I2C), not an ACS723.
    - tools/analyse_do.py handles both DO schemas (voltage_mv from direct
      mode / dummy, do_percent from Arduino mode).

UPDATED (heater enablement pass):
    - Heater control is Pi-side on GPIO12, acting on the temperature the
      Arduino streams. There is no Arduino-side heater code.
    - Sentinel handling added to both heater controllers - see
      src/actuators/heater_controller.py.
"""

# ---------------------------------------------------------------------------
# Sensor mode: "direct" (Pi reads hardware) or "arduino" (Arduino over USB)
# ---------------------------------------------------------------------------
# "direct"  - original mode. Each sensor has its own Python driver and thread.
# "arduino" - Arduino runs Combinedsensors.ino and streams readings over USB
#             serial. The Pi parses the serial output and logs to SQLite.
#
# Note run.sh --arduino sets SENSOR_MODE=arduino in the environment, which
# overrides this value. The systemd unit passes --arduino.

SENSOR_MODE = "arduino"

# ---------------------------------------------------------------------------
# Arduino serial settings (only used when SENSOR_MODE = "arduino")
# ---------------------------------------------------------------------------
# Port: /dev/ttyACM0 on Linux, /dev/cu.usbmodem* on Mac, COM3 on Windows.
# Baud must match Serial.begin() in the .ino sketch (115200).

ARDUINO_SERIAL_PORT = "/dev/ttyACM0"
ARDUINO_BAUD_RATE = 115200
ARDUINO_RECONNECT_DELAY_S = 5.0

# ---------------------------------------------------------------------------
# Data storage
# ---------------------------------------------------------------------------

DB_PATH = "src/data/sensor_data.db"

SAMPLE_INTERVAL_S = 1.0

MAX_CONSECUTIVE_FAILURES = 5

FAILURE_BACKOFF_S = 5.0

# ---------------------------------------------------------------------------
# ADS1015 (direct mode only - Arduino mode does not use this)
# ---------------------------------------------------------------------------

ADS1015_I2C_ADDRESS = 0x48
ADS1015_CHANNEL_CURRENT = 0   # AIN0 - current sensor output
ADS1015_CHANNEL_DO = 2        # AIN2 - Surveyor Isolator analog output

# ---------------------------------------------------------------------------
# Current sensor (direct mode only)
# ---------------------------------------------------------------------------
# In Arduino mode the current sensor is an INA226 read over I2C by the
# sketch. Its shunt value and address live in Combinedsensors.ino, not here.
#
# !! OPEN ITEM: the INA226 shunt resistor value is unverified. A wrong value
#    scales every current reading by a fixed factor while looking plausible,
#    and current output is the primary science measurement.

ACS723_SENSITIVITY_V_PER_A = 0.400
ACS723_VCC = 5.0
CURRENT_SAMPLE_COUNT = 10

# ---------------------------------------------------------------------------
# Dissolved Oxygen sensor
# ---------------------------------------------------------------------------
# Direct mode logs "voltage_mv" (raw, needs post-flight calibration).
# Arduino mode logs "do_percent" (Atlas Surveyor library, calibrated
# on-device via the CAL serial command). tools/analyse_do.py handles both.

DO_SAMPLE_COUNT = 10

# ---------------------------------------------------------------------------
# PAR sensor (direct mode only)
# ---------------------------------------------------------------------------
# In Arduino mode the PAR sensor is read via SoftwareSerial on the Arduino.

PAR_SERIAL_PORT = "/dev/serial0"
PAR_SLAVE_ADDRESS = 0x01
PAR_BAUDRATE = 9600
PAR_RS485_DE_PIN = 22
PAR_MAX_UMOL = 2500.0
PAR_SAMPLE_COUNT = 3

# ---------------------------------------------------------------------------
# UV-C sensor (direct mode only)
# ---------------------------------------------------------------------------

UVC_I2C_ADDRESS = 0x4D
UVC_VCC = 3.3
UVC_CALIBRATION_FACTOR = 2.9
UVC_SAMPLE_COUNT = 10

# ---------------------------------------------------------------------------
# UV sensor (direct mode only)
# ---------------------------------------------------------------------------

UVB_I2C_ADDRESS = 0x23
UVB_SAMPLE_COUNT = 5

# ---------------------------------------------------------------------------
# Temperature sensor (direct mode only)
# ---------------------------------------------------------------------------

TEMPERATURE_SENSOR_ID = None

# ---------------------------------------------------------------------------
# Heater controller - MOSFET + PWM, Pi-side
# ---------------------------------------------------------------------------
# WIRING (FRR schematic, Figure 5):
#   Pi GPIO12/PWM0 (physical pin 32) -> MOSFET gate (via gate resistor)
#   Pi GND (physical pin 6)          -> heater circuit ground
#   28V CSA supply -> buck converter (LM2576HVS) -> ~20-24V regulated
#   Buck output -> MOSFET drain -> cartridge heater (immersible) -> GND
#   Mechanical thermostat in series -> hardware safety cutoff at 25 C
#
# FRR presentation states:
#   Heater ON when temperature < 20 C
#   Heater OFF when temperature > 25 C
#   Target ~10 W, regulated via PWM duty cycle
#
# ---------------------------------------------------------------------------
# BEFORE SETTING THIS TO "mosfet" - complete all four steps in order:
#
#   1. Confirm a pulldown resistor (10k typical) exists from GPIO12 to
#      ground. Without it the MOSFET gate floats whenever the Pi is off or
#      mid-boot, and can drift to a partially-on state.
#
#   2. Flash the revised Combinedsensors.ino, which maps a missing DS18B20
#      to the -1.0 sentinel instead of reporting 0.00 C.
#
#   3. With the HEATER LOAD DISCONNECTED, set this to "mosfet" and verify
#      with a multimeter that GPIO12 goes high when the DS18B20 is cooled
#      below 20 C and low when warmed above 25 C.
#
#   4. Only after that switching is confirmed, connect the heater load.
#
# Leave this as "passive" until all four are done. Passive mode logs
# temperature warnings and sends no commands to any hardware.
# ---------------------------------------------------------------------------

HEATER_CONTROLLER = "passive"   # change to "mosfet" after the steps above

# Temperature thresholds (per FRR)
TEMP_TARGET_C = 22.5            # midpoint of the 20-25 C operating range
TEMP_WARNING_LOW_C = 20.0
TEMP_WARNING_HIGH_C = 25.0

# MOSFET controller settings
HEATER_PWM_PIN = 12             # GPIO12/PWM0 from FRR schematic
HEATER_PWM_FREQ_HZ = 1000       # 1 kHz switching frequency
HEATER_HYSTERESIS_C = 2.5       # ON below 20 C (22.5-2.5), OFF above 25 C (22.5+2.5)

# ---------------------------------------------------------------------------
# GPIO pin assignments summary
# ---------------------------------------------------------------------------
# Arduino mode - the Pi uses only these:
#   GPIO12 - Heater MOSFET PWM (PWM0), physical pin 32
#   GND    - heater circuit ground, physical pin 6
#   USB    - serial link to the Arduino
#
# Direct mode additionally uses:
#   GPIO2  - I2C SDA (shared bus)
#   GPIO3  - I2C SCL (shared bus)
#   GPIO4  - DS18B20 1-Wire
#   GPIO14 - UART TXD (PAR sensor MAX485E DI)
#   GPIO15 - UART RXD (PAR sensor MAX485E RO)
#   GPIO22 - PAR sensor MAX485E DE/RE

# ---------------------------------------------------------------------------
# Dummy mode
# ---------------------------------------------------------------------------

USE_DUMMY_DEFAULT = False
