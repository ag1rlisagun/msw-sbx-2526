# Mission SpaceWalker - CAN-SBX 2025-2026

Repository for the 2025–2026 CAN-SBX stratospheric balloon experiment. The payload is a capillary-driven bioreactor cultivating cyanobacteria under near-space conditions. The experiment evaluates radiation-induced changes in the organism's ability to generate bioelectricity in real time through a photosynthetic air-cathode microbial fuel cell system, by continuously measuring current output and oxygen evolution throughout the stratospheric profile.

A Raspberry Pi 4 collects data from six sensors across the full flight. All data is stored locally to an SD card in a SQLite database - no telemetry, no external dependencies.

The system supports two sensor modes:
- **Direct mode** — the Pi reads all sensors directly through its own GPIO, I2C, and UART interfaces.
- **Arduino mode** — an Arduino Uno reads all sensors and streams the data to the Pi over USB serial. The Pi parses the serial output and logs to SQLite. Use this mode when the Arduino can reach sensors the Pi cannot (e.g. the PAR sensor via SoftwareSerial RS-485). As of the current sketch, Arduino mode covers all six sensors, including UV-C.

## Software Team

**Lead:** Aaliyah Wusu  
Shaira Zareen Islam  
Nsikan Akpan  
Uchenna Ibeziako    


---

## Sensors

| Sensor | Hardware | Measurement | Interface |
|---|---|---|---|
| Temperature | DFRobot Waterproof DS18B20 | Temperature (°C) | 1-Wire |
| Current | Allegro ACS723 + ADS1015 | Current (A), Voltage (V) | I2C |
| Dissolved Oxygen | Atlas Scientific Mini D.O. + Surveyor Isolator + ADS1015 | Voltage (mV) → mg/L post-flight (direct mode); % saturation on-device (Arduino mode) | I2C (direct) / analog via Arduino (Arduino mode) |
| PAR | SenseCAP S-PAR-02 + MAX485E transceiver | PAR (µmol/m²/s) | RS-485 MODBUS RTU via UART |
| UV-C | MikroE UVC Click (GUVC-T21GH) | Intensity (mW/cm²) | I2C |
| UV-B/Index | DFRobot SEN0636 Gravity UV Index | UV index (0–11), Risk level (0–4) | I2C |

**Note on Dissolved Oxygen:** direct mode logs a raw `voltage_mv` value that needs post-flight calibration (see `tools/analyse_do.py`). Arduino mode logs `do_percent` from the Atlas Surveyor Arduino library, which calibrates on-device via its own "CAL" serial command — no post-flight calibration voltage is needed for that schema. `tools/analyse_do.py` auto-detects which schema a given database uses.

---

## Repository Structure

See [`STRUCTURE.md`](STRUCTURE.md) for the full annotated file tree.

The short version:

```
src/
  main.py               - entry point, selects direct or Arduino mode at startup
  config.py             - all pins, addresses, thresholds (edit here, not in sensor files)
  sensors/real/         - hardware drivers (run on Pi) + arduino_serial_reader.py
  sensors/dummy/        - software stand-ins (run anywhere, no hardware needed)
  actuators/            - heater controller interface
  storage/              - SQLite data logger
  tools/                - post-flight DO analysis, ADC benchmark
  data/                 - sensor_data.db and log file written here at runtime
arduino/
  Combinedsensors.ino   - Arduino sketch (upload via Arduino IDE) - reads all 6 sensors
tests/                  - unit tests
```

---

## Hardware Requirements

**Both modes:**
- Raspberry Pi 4
- microSD card - 16–32 GB, Class 10 recommended
- SD card reader
- Power supply appropriate for Pi 4

**Arduino mode (additional):**
- Arduino Uno (or compatible board)
- USB-A to USB-B cable (connects Arduino to Pi)
- All sensors wired to the Arduino instead of the Pi (same sensors, different host)

---

## Wiring

### I2C devices (shared bus, SDA/SCL)

| Device | I2C Address | Supply | Notes |
|---|---|---|---|
| ADS1015 (ADC) | 0x48 | **5V** | Shared by current sensor (AIN0) and D.O. sensor (AIN2). Direct mode only. |
| MikroE UVC Click | 0x4D | 3.3V | Check VCC SEL jumper - left position = 3.3V. Read by the Pi in direct mode, or by the Arduino (same address, same Wire bus as the UV Index sensor) in Arduino mode. |
| DFRobot SEN0636 | 0x23 | 3.3–5V | **Set physical switch to I2C side before wiring** |

⚠️ **Logic level shifter required (direct mode only):** The ADS1015 must be powered at 5V for the ACS723 current sensor to work correctly. The Pi's I2C lines are 3.3V logic. A bidirectional logic level shifter is needed between the Pi's SDA/SCL pins and the ADS1015 to protect the Pi's GPIO.

Verify all I2C devices after wiring (direct mode):
```
sudo i2cdetect -y 1
```
Expected addresses: `0x23`, `0x48`, `0x4D`

### 1-Wire (temperature)

| Device | GPIO Pin (BCM) | Supply | Notes |
|---|---|---|---|
| DS18B20 | GPIO4 (default) | 3.3V | Requires 4.7kΩ pull-up resistor between DATA and 3.3V |

Verify after wiring:
```
ls /sys/bus/w1/devices/
```
Expected: `28-xxxxxxxxxxxx`

### UART / RS-485 (PAR sensor)

| Connection | GPIO Pin (BCM) | Physical Pin | Notes |
|---|---|---|---|
| MAX485E RO → Pi RXD | GPIO15 | Pin 10 | Data FROM sensor |
| MAX485E DI → Pi TXD | GPIO14 | Pin 8 | Data TO sensor |
| MAX485E RE+DE | GPIO22 | Pin 15 | Direction control (TX/RX toggle) |

The MAX485E transceiver converts RS-485 from the SenseCAP S-PAR-02 sensor to UART for the Pi. The sensor speaks MODBUS RTU at 9600 baud, 8N1.

⚠️ **The Pi serial console must be disabled for UART to work:**
```bash
sudo raspi-config
# Interface Options → Serial Port → Login shell over serial: NO → Serial port hardware enabled: YES
sudo reboot
```

Verify after reboot:
```bash
ls -l /dev/serial0    # should point to ttyS0 or ttyAMA0
```

### Analog inputs via ADS1015 (direct mode)

| Device | ADS1015 Channel | Notes |
|---|---|---|
| ACS723 current sensor output | AIN0 | Zero-current output = VCC/2 = 2.5V |
| Surveyor Isolator D.O. output | AIN2 | Via R7 1kΩ + C5 1µF low-pass filter |

### Heater - MOSFET + PWM (cartridge heater)

The Pi controls the heater via a MOSFET gate driven by PWM. Power comes from the 28V CSA supply through a buck converter (LM2576HVS) regulated to ~20-24V. A mechanical thermostat provides hardware safety cutoff at 25°C.

| Connection | Notes |
|---|---|
| Pi GPIO12/PWM0 (pin 32) → MOSFET gate | Via gate resistor |
| 28V CSA supply → Buck converter → MOSFET drain | Regulated ~20-24V |
| MOSFET source → Cartridge heater → GND | Immersible in water, ~10W |
| Mechanical thermostat in series | Hardware cutoff at 25°C |

To activate: set `HEATER_CONTROLLER = "mosfet"` in `config.py`. The controller uses hysteresis: heater turns ON below 20°C and OFF above 25°C.

### GPIO pin assignments (Pi, direct mode)

| GPIO (BCM) | Physical Pin | Function |
|---|---|---|
| GPIO2 | Pin 3 | I2C SDA (shared bus) |
| GPIO3 | Pin 5 | I2C SCL (shared bus) |
| GPIO4 | Pin 7 | DS18B20 1-Wire |
| GPIO12 | Pin 32 | Heater MOSFET PWM (PWM0) |
| GPIO14 | Pin 8 | UART TXD (PAR MAX485E DI) |
| GPIO15 | Pin 10 | UART RXD (PAR MAX485E RO) |
| GPIO22 | Pin 15 | PAR MAX485E DE/RE |

### Arduino pin assignments (Arduino mode)

See `arduino/Combinedsensors.ino` for the authoritative pin list. Summary:

| Device | Arduino Pin | Notes |
|---|---|---|
| DS18B20 temperature | Digital pin 5 | 1-Wire |
| ACS723 current sensor | A2 | Analog read |
| DO probe (Surveyor Isolator) | A0 | Analog read |
| PAR sensor (RS-485) | SoftwareSerial pins 2/3, DE/RE on pin 4 | MODBUS RTU |
| UV Index (SEN0636) | I2C (Wire) | Address 0x23 |
| UV-C (MCP3221) | I2C (Wire), shares bus with UV Index | Address 0x4D |

---

## Operating System

**Raspberry Pi OS Lite (64-bit)** - fully supports GPIO, I²C, 1-Wire, UART, Python, and Blinka.

### Write OS to microSD

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Choose OS: **Raspberry Pi OS (other) → Raspberry Pi OS Lite (64-bit)**
3. Before writing, open Advanced Options (gear icon) and configure:
   - Hostname (e.g. `msw-sensor-node`)
   - Enable SSH with password authentication
   - Username and password (do not use defaults)
   - Wi-Fi SSID, password, and country code
   - Locale and timezone
4. Write to SD card, insert into Pi, connect power
5. Wait ~60–90 seconds for first boot

Connect via SSH:
```bash
ssh <username>@<hostname>.local
```

### Initial system setup

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

Enable required interfaces:
```bash
sudo raspi-config
```

Enable all of the following:
- **I2C** - Interface Options → I2C → Enable
- **1-Wire** - Interface Options → 1-Wire → Enable
- **Serial Port** - Interface Options → Serial Port → Login shell: **NO** → Hardware: **YES**

Then reboot when prompted.

Verify interfaces:
```bash
# I2C
ls /dev/i2c-*          # expected: /dev/i2c-1

# 1-Wire (after connecting DS18B20)
ls /sys/bus/w1/devices/ # expected: 28-xxxxxxxxxxxx

# UART (for PAR sensor)
ls -l /dev/serial0      # expected: symlink to ttyS0 or ttyAMA0
```

### Install core tools

```bash
sudo apt install -y python3 python3-pip python3-venv git i2c-tools build-essential
```

---

## Installation

```bash
cd ~
git clone https://github.com/ag1rlisagun/msw-sbx-2526.git
cd msw-sbx-2526
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

On the **Raspberry Pi**:
```bash
pip install -r requirements-pi.txt
```

On a **Mac or Linux dev machine** (dummy mode only - no hardware libraries):
```bash
pip install -r requirements.txt
```

`run.sh` detects which machine it's on and installs the right file automatically.

---

## Running

### Direct mode (Pi reads sensors)

```bash
./run.sh
```

This activates the virtual environment, installs dependencies if needed, and starts `src/main.py`. Each sensor runs in its own thread. If one sensor fails, the others keep collecting.

### Arduino mode (Arduino reads sensors, Pi logs data)

```bash
./run.sh --arduino
```

The Arduino must be connected to the Pi via USB and have `arduino/Combinedsensors.ino` uploaded. On startup the Pi waits for the Arduino to finish initializing its sensors and send `READY`, then sends `START` to begin data collection. No data is lost during boot — the Arduino does not print sensor readings until the Pi is listening.

If the USB connection drops (glitch, Arduino reset), the reader automatically reconnects and re-handshakes.

The serial port defaults to `/dev/ttyACM0`. To check or change it:
```bash
ls /dev/ttyACM*                      # find the port
# edit ARDUINO_SERIAL_PORT in src/config.py if different
```

If you get a permission error on the serial port:
```bash
sudo usermod -aG dialout $USER
# then log out and back in
```

### Dummy mode (no hardware required)

```bash
./run.sh --dummy
```

Runs the full pipeline with simulated sensor values. Useful for testing on a laptop or verifying the database and logging work correctly before connecting hardware.

### Auto-start on boot  

Install the systemd service so data collection starts automatically when the Pi receives power, with no manual intervention.

For **Arduino mode**, edit `msw-sensors.service` before copying — change the `ExecStart` line to:
```
ExecStart=/home/pi/msw-sbx-2526/run.sh --arduino
```

Then install the service:
```bash
sudo cp msw-sensors.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable msw-sensors
sudo systemctl start msw-sensors
```

Check status and view live logs:
```bash
sudo systemctl status msw-sensors
sudo journalctl -u msw-sensors -f
```

---

## Data

All sensor readings are written to:
```
src/data/sensor_data.db       - SQLite database
src/data/msw_sensor.log       - runtime log (warnings, errors, startup messages)
```

Each sensor has its own table, created automatically. Every reading is committed immediately - if power cuts mid-flight, all previously committed rows are safe.

**Note:** In Arduino mode, the dissolved oxygen sensor logs `do_percent` (from the Atlas Surveyor's `read_do_percentage()`, calibrated on-device), while direct mode logs raw `voltage_mv` (needs post-flight calibration — see `tools/analyse_do.py`). The UV Index sensor data is grouped into a single `uv` table with columns for voltage, index, irradiance, and risk level. The UV-C sensor writes to its own `uvc` table with `voltage_v` and `intensity_mw_cm2` columns, identical in both direct and Arduino modes.

### Reading the database

Copy the SD card after flight and open the database:

```bash
sqlite3 src/data/sensor_data.db
```

Useful queries:

```sql
-- See all tables (one per sensor)
.tables

-- See all temperature readings
SELECT datetime(timestamp, 'unixepoch'), temperature_c
FROM temperature
ORDER BY timestamp;

-- Check which DO schema this database uses
.schema dissolved_oxygen

-- See current and DO readings together by time
SELECT
  datetime(c.timestamp, 'unixepoch') AS time,
  c.current_a,
  d.*
FROM current c
JOIN dissolved_oxygen d ON ABS(c.timestamp - d.timestamp) < 2
ORDER BY c.timestamp;

-- Count readings per sensor (check for gaps)
SELECT 'temperature',      COUNT(*) FROM temperature
UNION SELECT 'current',    COUNT(*) FROM current
UNION SELECT 'dissolved_oxygen', COUNT(*) FROM dissolved_oxygen
UNION SELECT 'par',        COUNT(*) FROM par
UNION SELECT 'uvc',        COUNT(*) FROM uvc
UNION SELECT 'uvb',        COUNT(*) FROM uvb;

-- Find time range of collected data
SELECT
  datetime(MIN(timestamp), 'unixepoch') AS start,
  datetime(MAX(timestamp), 'unixepoch') AS end,
  COUNT(*) AS readings
FROM temperature;
```

Export to CSV for analysis:
```bash
sqlite3 -header -csv src/data/sensor_data.db \
  "SELECT datetime(timestamp,'unixepoch'), current_a FROM current;" \
  > current_readings.csv
```

---

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v
```

Tests run without hardware using dummy sensors. Completed tests cover the data logger (thread safety, SQLite correctness) and the full sensor lifecycle contract. Per-sensor test stubs in `tests/test_*.py` are ready to be filled in - each file has comments describing exactly what to implement, and each has been checked against the current (post-FRR) hardware, so the described formulas/schemas match what the drivers actually do.

---

## Pre-Flight Tools

### ADC Sample Rate Benchmark

The ADS1015 is shared between the current sensor (AIN0) and D.O. sensor (AIN2). Run this benchmark once when hardware arrives to confirm `SAMPLE_INTERVAL_S` in `config.py` is appropriate.

```bash
python3 tools/benchmark_adc.py
```

Note: `benchmark_adc.py` currently references ADS1115 — update the import to `ads1015` before running.

### D.O. Pre-Flight Calibration Procedure

**Direct / dummy mode:** the dissolved oxygen sensor logs raw `voltage_mv` during flight. To convert those voltages to mg/L after recovery, you need a single reference point recorded before launch.

**Steps (do this at the launch site, after all sensors are connected and running):**

1. Ensure `./run.sh` is running and the DO sensor is logging
2. Leave the probe exposed to open air - do not submerge it
3. Watch the `voltage_mv` readings stabilise (allow at least 5 minutes)
4. Once stable, record in your lab notebook:
   - The `voltage_mv` value ← this is your `--cal` value
   - The temperature reading from the DS18B20 at that moment
   - The time of calibration
5. This is the only number that cannot be recovered after the fact - do not skip it

**Arduino mode:** the Atlas Surveyor Arduino library calibrates on-device. Instead of the above, send the `CAL` command over serial (see `arduino/Combinedsensors.ino`) with the probe in open air before launch. `tools/analyse_do.py` does not need a `--cal` value for Arduino-mode data.

---

## Post-Flight Analysis

### Step 1 - Retrieve the database

Put the SD card in a card reader. The Pi's main partition is ext4 (Linux only). On a Mac, retrieve the database over SSH instead:

```bash
scp <username>@msw2026.local:~/msw-sbx-2526/src/data/sensor_data.db ./sensor_data.db
```

### Step 2 - Verify data integrity

```bash
sqlite3 sensor_data.db

-- Check all tables exist and have data
SELECT 'temperature',      COUNT(*) FROM temperature
UNION SELECT 'current',    COUNT(*) FROM current
UNION SELECT 'dissolved_oxygen', COUNT(*) FROM dissolved_oxygen
UNION SELECT 'par',        COUNT(*) FROM par
UNION SELECT 'uvc',        COUNT(*) FROM uvc
UNION SELECT 'uvb',        COUNT(*) FROM uvb;

-- Check time range
SELECT
  datetime(MIN(timestamp), 'unixepoch') AS start,
  datetime(MAX(timestamp), 'unixepoch') AS end,
  COUNT(*) AS readings
FROM temperature;
```

### Step 3 - Convert D.O. voltage to mg/L

`tools/analyse_do.py` auto-detects whether the database has a `voltage_mv` column (direct/dummy mode — needs `--cal`) or a `do_percent` column (Arduino mode — already calibrated, `--cal` is ignored).

```bash
# Direct / dummy mode - calibration required
python3 tools/analyse_do.py --db sensor_data.db --cal <your_calibration_mV>

# Arduino mode - no --cal needed (already calibrated on-device)
python3 tools/analyse_do.py --db sensor_data.db

# With altitude/pressure correction (recommended - accounts for stratospheric conditions)
python3 tools/analyse_do.py --db sensor_data.db --cal <your_calibration_mV> --pressure-csv altitude.csv

# Save full results to CSV for reporting
python3 tools/analyse_do.py --db sensor_data.db --cal <your_calibration_mV> --out results/do_analysis.csv
```

**What the script calculates:**

| Output column | Formula | Notes |
|---|---|---|
| `saturation_pct` | `(voltage_mv / cal_voltage) × 100` (direct mode) **or** `do_percent` directly (Arduino mode) | Direct mode: simple ratio against calibration reference. Arduino mode: already computed on-device. |
| `do_mg_L` | `saturation_pct × solubility_at_temp(temp_c)` | Uses Standard Methods (APHA 4500-O) solubility table, interpolated per temperature reading. Same for both modes. |
| `do_mg_L_corrected` | `do_mg_L × (pressure_kpa / 101.325)` | Pressure correction - important for float altitude where ambient O₂ partial pressure is ~1–2% of sea level. |

The pressure correction is what makes the stratosphere data scientifically meaningful - without it, the mg/L values during float would assume sea-level oxygen partial pressure, which is not the environment the cyanobacteria were experiencing.

---

## Configuration

All tunable values are in `src/config.py`. Key settings:

| Setting | Default | Description |
|---|---|---|
| `SENSOR_MODE` | `"direct"` | `"direct"` (Pi reads sensors) or `"arduino"` (Arduino over USB) |
| `ARDUINO_SERIAL_PORT` | `"/dev/ttyACM0"` | USB serial port for Arduino (only used in Arduino mode) |
| `ARDUINO_BAUD_RATE` | `115200` | Must match `Serial.begin()` in the `.ino` sketch |
| `SAMPLE_INTERVAL_S` | `1.0` | Seconds between readings (direct mode only — Arduino mode uses the sketch's `delay()`) |
| `ADS1015_I2C_ADDRESS` | `0x48` | I2C address for the ADS1015 (current + D.O., direct mode) |
| `ADS1015_CHANNEL_CURRENT` | `0` | ADS1015 AIN0 for current sensor |
| `ADS1015_CHANNEL_DO` | `2` | ADS1015 AIN2 for D.O. sensor |
| `PAR_RS485_DE_PIN` | `22` | BCM GPIO for MAX485E DE/RE direction control |
| `ACS723_SENSITIVITY_V_PER_A` | `0.400` | **Verify against exact ACS723 part number** |
| `UVC_I2C_ADDRESS` | `0x4D` | I2C address for the UVC Click (direct mode; also used by the Arduino sketch) |
| `TEMP_TARGET_C` | `22.5` | Target temperature (midpoint of 20–25°C range) |
| `TEMP_WARNING_LOW_C` | `20.0` | Heater ON below this temperature |
| `TEMP_WARNING_HIGH_C` | `25.0` | Heater OFF above this temperature |
| `HEATER_CONTROLLER` | `"passive"` | `"mosfet"` or `"passive"` |
| `HEATER_PWM_PIN` | `12` | GPIO12/PWM0 for MOSFET gate |

---

## Pre-Flight Checklist

### Both modes

- [ ] Physical switch on SEN0636 set to **I2C** side
- [ ] VCC SEL jumper on UVC Click set to correct voltage (left = 3.3V)
- [ ] DS18B20 pull-up resistor (4.7kΩ) wired between DATA and 3.3V
- [ ] ACS723 part number confirmed → correct sensitivity set in `config.py`
- [ ] D.O. pre-flight calibration completed (see mode-specific procedure above)
- [ ] `./run.sh --dummy` runs clean with no errors
- [ ] Systemd service enabled (`sudo systemctl enable msw-sensors`)
- [ ] MOSFET heater wired: GPIO12 → gate, buck converter output → drain, heater → source
- [ ] Mechanical thermostat in series with heater (hardware cutoff at 25°C)
- [ ] `HEATER_CONTROLLER = "mosfet"` set in `config.py`
- [ ] Heater PWM verified: GPIO12 HIGH heats, LOW stops
- [ ] SD card formatted and has sufficient space (16 GB+ recommended)

### Direct mode only

- [ ] Logic level shifter in place between Pi I2C and ADS1015
- [ ] `sudo i2cdetect -y 1` shows `0x23`, `0x48`, `0x4D`
- [ ] `ls /sys/bus/w1/devices/` shows `28-xxxxxxxxxxxx`
- [ ] `ls -l /dev/serial0` shows symlink (UART enabled, serial console disabled)
- [ ] PAR sensor responds to MODBUS test query
- [ ] `./run.sh` runs on Pi with real hardware - all 6 sensors appear in startup log

### Arduino mode only

- [ ] `arduino/Combinedsensors.ino` uploaded to Arduino via Arduino IDE
- [ ] Arduino connected to Pi via USB cable
- [ ] `ls /dev/ttyACM*` shows the Arduino serial port
- [ ] `ARDUINO_SERIAL_PORT` in `config.py` matches the port from the step above
- [ ] All sensors wired to Arduino pins (not to the Pi — see pin assignments above and in the `.ino`)
- [ ] `./run.sh --arduino` shows `READY` → `START` → sensor data in the log, including `UVC Voltage:` / `UVC Intensity:` lines
- [ ] Arduino DO probe calibrated via the `CAL` serial command before flight

---

## Known Gaps

| Item | Status |
|---|---|
| PAR sensor MODBUS communication | Works in Arduino mode (SoftwareSerial RS-485). Direct Pi mode not yet fully verified — GPIO22 gets partial response, RO/DI wiring needs confirmation |
| D.O. calibration | Direct/dummy mode: raw voltage (mV) is logged; conversion done post-flight using pre-flight calibration curve. Arduino mode: calibrated on-device via the Atlas Surveyor library. `tools/analyse_do.py` handles both. |
| ADS1015 max sample rate | Run `tools/benchmark_adc.py` (update import to ads1015 first) when hardware arrives |
| Per-sensor unit tests | Stubs written, implementation pending - see `tests/test_*.py` (updated to match current hardware) |
| `benchmark_adc.py` | Needs ADS1115 → ADS1015 import update |
| Surveyor vendor library files | `do_surveyor.*`/`do_iso_surveyor.*` are used by the DO sensor; ORP/pH/RTD Surveyor variants at the repo root are unused leftovers from the vendor library and are candidates for removal |
