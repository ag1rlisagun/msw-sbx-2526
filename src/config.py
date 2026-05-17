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
"""

# ---------------------------------------------------------------------------
# Data storage
# ---------------------------------------------------------------------------

DB_PATH = "src/data/sensor_data.db"

SAMPLE_INTERVAL_S = 1.0

MAX_CONSECUTIVE_FAILURES = 5

FAILURE_BACKOFF_S = 5.0

# ---------------------------------------------------------------------------
# ADS1015 (12-bit ADC, shared by current sensor and D.O. sensor)
# ---------------------------------------------------------------------------
# FRR schematics show ADS1015 (not ADS1115).
# I2C address default is 0x48. Check with: sudo i2cdetect -y 1

ADS1015_I2C_ADDRESS = 0x48

# ADS1015 channel assignments
ADS1015_CHANNEL_CURRENT = 0   # AIN0 - ACS723 output
ADS1015_CHANNEL_DO = 2        # AIN2 - Surveyor Isolator analog output

# ---------------------------------------------------------------------------
# Current sensor - Allegro ACS723 via ADS1015
# ---------------------------------------------------------------------------
# FRR schematic Figure 6: ACS723LLCTR-05AB-T → ADS1015 AIN0

ACS723_SENSITIVITY_V_PER_A = 0.400

ACS723_VCC = 5.0

CURRENT_SAMPLE_COUNT = 10

# ---------------------------------------------------------------------------
# Dissolved Oxygen sensor - Atlas Scientific Mini D.O. + Surveyor Isolator
#                           via ADS1015 (REPLACES PWM/pigpio)
# ---------------------------------------------------------------------------
# FRR schematic Figure 10: Surveyor analog output → ADS1015 AIN2
# via R7 (1kΩ) + C5 (1µF) low-pass filter.
#
# pigpiod is NO LONGER required for D.O.

DO_SAMPLE_COUNT = 10

# ---------------------------------------------------------------------------
# PAR sensor - SenseCAP S-PAR-02 via RS-485 MODBUS RTU + MAX485E
# ---------------------------------------------------------------------------
# FRR schematic Figure 8:
#   PAR sensor RS-485 A/B → MAX485E A/B
#   MAX485E RO  → GPIO15 / UART RXD (physical pin 10)
#   MAX485E DI  → GPIO14 / UART TXD (physical pin 8)
#   MAX485E RE + DE → GPIO22 (confirmed by GPIO scan test)
#
# IMPORTANT: The Pi serial console must be DISABLED for UART to work.
#   sudo raspi-config → Interface Options → Serial Port
#   → Login shell over serial: NO → Serial port hardware enabled: YES

PAR_SERIAL_PORT = "/dev/serial0"
PAR_SLAVE_ADDRESS = 0x01
PAR_BAUDRATE = 9600
PAR_RS485_DE_PIN = 22          # GPIO22 — confirmed by GPIO scan
PAR_MAX_UMOL = 2500.0
PAR_SAMPLE_COUNT = 3

# ---------------------------------------------------------------------------
# UV-C sensor - MikroE UVC Click (GUVC-T21GH via MCP3221 ADC)
# ---------------------------------------------------------------------------
# NO CHANGE from original design.

UVC_I2C_ADDRESS = 0x4D
UVC_VCC = 3.3
UVC_CALIBRATION_FACTOR = 2.9
UVC_SAMPLE_COUNT = 10

# ---------------------------------------------------------------------------
# UV sensor - DFRobot SEN0636 Gravity UV Index Sensor (240–370nm)
# ---------------------------------------------------------------------------
# NO CHANGE from original design. FRR data acquisition table confirms
# direct I2C @ 0x23. The Arduino code also uses direct I2C.
# IMPORTANT: Set the physical switch on the board to I2C before wiring.

UVB_I2C_ADDRESS = 0x23
UVB_SAMPLE_COUNT = 5

# ---------------------------------------------------------------------------
# Temperature sensor - DFRobot Waterproof DS18B20 (1-Wire)
# ---------------------------------------------------------------------------
# NO CHANGE from original design.

TEMPERATURE_SENSOR_ID = None

# ---------------------------------------------------------------------------
# Heater controller - MOSFET + PWM (REPLACES SSR)
# ---------------------------------------------------------------------------
# FRR schematic Figure 5:
#   Pi GPIO12/PWM0 → MOSFET gate (via gate resistor)
#   28V CSA supply → Buck converter (LM2576HVS) → ~20-24V regulated
#   Buck output → MOSFET drain → Cartridge heater (immersible) → GND
#   Mechanical thermostat in series → hardware safety cutoff at 25°C
#
# FRR presentation explicitly states:
#   Heater ON when temperature < 20°C
#   Heater OFF when temperature > 25°C
#   Target ~10W power, regulated via PWM duty cycle

HEATER_CONTROLLER = "passive"   # change to "mosfet" once wiring is confirmed

# Temperature thresholds (updated per FRR)
TEMP_TARGET_C = 22.5            # midpoint of 20-25°C operating range
TEMP_WARNING_LOW_C = 20.0
TEMP_WARNING_HIGH_C = 25.0

# MOSFET controller settings
HEATER_PWM_PIN = 12             # GPIO12/PWM0 from FRR schematic
HEATER_PWM_FREQ_HZ = 1000      # 1 kHz switching frequency
HEATER_HYSTERESIS_C = 2.5      # ON below 20°C (22.5-2.5), OFF above 25°C (22.5+2.5)

# ---------------------------------------------------------------------------
# GPIO pin assignments summary
# ---------------------------------------------------------------------------
# GPIO2  - I2C SDA (reserved, shared bus)
# GPIO3  - I2C SCL (reserved, shared bus)
# GPIO4  - DS18B20 1-Wire
# GPIO12 - Heater MOSFET PWM (PWM0)
# GPIO14 - UART TXD (PAR sensor MAX485E DI)
# GPIO15 - UART RXD (PAR sensor MAX485E RO)
# GPIO22 - PAR sensor MAX485E DE/RE

# ---------------------------------------------------------------------------
# Dummy mode
# ---------------------------------------------------------------------------

USE_DUMMY_DEFAULT = False