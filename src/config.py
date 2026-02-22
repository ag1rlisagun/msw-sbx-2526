"""
config.py - Central configuration for MSW CAN-SBX 2025-2026.

All hardware pin assignments, sensor parameters, and tunable constants
live here. Change values here rather than touching sensor driver code.
"""

# ---------------------------------------------------------------------------
# Data storage
# ---------------------------------------------------------------------------

DB_PATH = "src/data/sensor_data.db"

# How often each sensor is polled (seconds).
# Increase if a sensor is too slow to keep up.
SAMPLE_INTERVAL_S = 1.0

# How many consecutive read failures before the main loop logs a WARNING
# and backs off (instead of spamming the log every second).
MAX_CONSECUTIVE_FAILURES = 5

# Seconds to wait before retrying after a sensor failure.
FAILURE_BACKOFF_S = 5.0

# ---------------------------------------------------------------------------
# ADS1115 (ADC for current sensor and PAR sensor)
# ---------------------------------------------------------------------------

# I2C address - default is 0x48. Check with: sudo i2cdetect -y 1
ADS1115_I2C_ADDRESS = 0x48

# ADS1115 channel assignments
ADS1115_CHANNEL_CURRENT = 0  # AIN0 - ACS723 output
ADS1115_CHANNEL_PAR = 1      # AIN1 - PAR sensor output

# ---------------------------------------------------------------------------
# Current sensor - Allegro ACS723
# ---------------------------------------------------------------------------

# CRITICAL: Verify your exact part number from the bag/reel.
# ACS723LLCTR-05AB-T (5A version)  → sensitivity = 0.400 V/A
# ACS723LLCTR-10AB-T (10A version) → sensitivity = 0.264 V/A
ACS723_SENSITIVITY_V_PER_A = 0.400

# Supply voltage to the ACS723. Must be 4.5–5.5V.
# The ADS1115 MUST also be on 5V if this is 5V (see README hardware warning).
ACS723_VCC = 5.0

# Number of samples to average per reading (at 0.1s delay each = ~1s total)
CURRENT_SAMPLE_COUNT = 10

# ---------------------------------------------------------------------------
# PAR sensor - SenseCAP S-PAR-02 / PAR-2.5V
# ---------------------------------------------------------------------------

# Sensor output range: 0–2.5V maps to 0–2500 µmol/m²/s
PAR_MAX_VOLTAGE_V = 2.5
PAR_MAX_UMOL = 2500.0

PAR_SAMPLE_COUNT = 10

# ---------------------------------------------------------------------------
# UV-C sensor - MikroE UVC Click (GUVC-T21GH via MCP3221 ADC)
# ---------------------------------------------------------------------------

# I2C address of the MCP3221 on the UVC Click board (usually 0x4D)
UVC_I2C_ADDRESS = 0x4D

# VCC supplied to the UVC Click board (3.3V or 5V - check jumper setting)
UVC_VCC = 3.3

# Calibration factor for converting voltage to mW/cm²
# Typical range is 2.8–3.0 - verify against your sensor's calibration sheet
UVC_CALIBRATION_FACTOR = 2.9

UVC_SAMPLE_COUNT = 10

# ---------------------------------------------------------------------------
# UV sensor - DFRobot SEN0636 Gravity UV Index Sensor (240–370nm)
# ---------------------------------------------------------------------------

# I2C address - fixed at 0x23 (not configurable on this board)
# Verify with: sudo i2cdetect -y 1
# IMPORTANT: Set the physical switch on the board to I2C before wiring.
UVB_I2C_ADDRESS = 0x23
UVB_SAMPLE_COUNT = 5

# ---------------------------------------------------------------------------
# Dissolved Oxygen sensor - Atlas Scientific Mini D.O. + Surveyor Isolator
# ---------------------------------------------------------------------------

# GPIO pin (BCM numbering) connected to the PWM output of the Surveyor Isolator
DO_PWM_PIN = 17

# Number of pulse measurements to average (mirrors volt_avg_len * 3 from C++ reference)
# At 10.6 kHz this gives ~8ms of averaging per reading
DO_AVG_SAMPLES = 30

# Maximum pulse width timeout in microseconds (pigpio pulseIn equivalent)
DO_PULSE_TIMEOUT_US = 400

# ---------------------------------------------------------------------------
# Temperature sensor - DFRobot Waterproof DS18B20 (1-Wire)
# ---------------------------------------------------------------------------

# 1-Wire devices appear at /sys/bus/w1/devices/28-xxxxxxxxxxxx
# Set to None to auto-detect the first DS18B20 found.
# Set to a specific ID string if you have multiple sensors on the bus.
TEMPERATURE_SENSOR_ID = None

# ---------------------------------------------------------------------------
# Heater controller
# ---------------------------------------------------------------------------

# Which controller class to use. Options:
#   "ssr"      - Solid State Relay on a Pi GPIO pin (RECOMMENDED - fully implemented)
#   "passive"  - log warnings only, no commands sent (safe default)
HEATER_CONTROLLER = "passive"   # change to "ssr" once HEATER_SSR_PIN is set

# Target operating temperature
TEMP_TARGET_C = 25.0

# Warning thresholds - logged regardless of controller type
TEMP_WARNING_LOW_C = 18.0
TEMP_WARNING_HIGH_C = 30.0

# ---------------------------------------------------------------------------
# SSR controller settings - only used if HEATER_CONTROLLER = "ssr"
# ---------------------------------------------------------------------------

# BCM GPIO pin number wired to the SSR control input (DC+).
# TODO: set this to whichever GPIO pin you wire up.
# Common safe choices: 27, 22, 5, 6, 13, 26 (avoid pins used by other sensors).
# Current pin assignments:
#   GPIO4  - DS18B20 1-Wire
#   GPIO17 - Atlas D.O. PWM input
#   GPIO2/3 - I2C SDA/SCL (reserved)
HEATER_SSR_PIN = None          # e.g. 27

# Dead band around the target temperature.
# Heater turns ON  when temp < (TEMP_TARGET_C - HEATER_HYSTERESIS_C)
# Heater turns OFF when temp > (TEMP_TARGET_C + HEATER_HYSTERESIS_C)
# Keep >= 1.0 to prevent rapid SSR switching. Increase if chattering occurs.
HEATER_HYSTERESIS_C = 1.0



# ---------------------------------------------------------------------------
# Dummy mode
# ---------------------------------------------------------------------------

# Set via environment variable: USE_DUMMY_SENSORS=true ./run.sh
# Do not change this value here - use the environment variable instead.
USE_DUMMY_DEFAULT = False
