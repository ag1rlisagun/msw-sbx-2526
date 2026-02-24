# Mission SpaceWalker - CAN-SBX 2025-2026

Repository for the 2025–2026 CAN-SBX stratospheric balloon experiment. The payload is a capillary-driven bioreactor cultivating cyanobacteria under near-space conditions. The experiment evaluates radiation-induced changes in the organism's ability to generate bioelectricity in real time through a photosynthetic air-cathode microbial fuel cell system, by continuously measuring current output and oxygen evolution throughout the stratospheric profile.

A Raspberry Pi 4 collects data from six sensors across the full flight. All data is stored locally to an SD card in a SQLite database - no telemetry, no external dependencies.

## Software Team

**Lead:** Aaliyah Wusu  
Shaira Zareen Islam
Nsikan Akpan  


---

## Sensors

| Sensor | Hardware | Measurement | Interface |
|---|---|---|---|
| Temperature | DFRobot Waterproof DS18B20 | Temperature (°C) | 1-Wire |
| Current | Allegro ACS723 + ADS1115 | Current (A), Voltage (V) | I2C |
| Dissolved Oxygen | Atlas Scientific Mini D.O. + Surveyor Isolator | Voltage (mV) → mg/L post-flight | PWM (pigpio) |
| PAR | SenseCAP S-PAR-02 + ADS1115 | PAR (µmol/m²/s) | I2C |
| UV-C | MikroE UVC Click (GUVC-T21GH) | Intensity (mW/cm²) | I2C |
| UV-B/Index | DFRobot SEN0636 Gravity UV Index | UV index (0–11), Risk level (0–4) | I2C |

---

## Repository Structure

See [`STRUCTURE.md`](STRUCTURE.md) for the full annotated file tree.

The short version:

```
src/
  main.py               - entry point, one thread per sensor
  config.py             - all pins, addresses, thresholds (edit here, not in sensor files)
  sensors/real/         - hardware drivers (run on Pi)
  sensors/dummy/        - software stand-ins (run anywhere, no hardware needed)
  actuators/            - heater controller interface
  storage/              - SQLite data logger
  tools/                - benchmark for SAMPLE_INTERVAL_S (run when ADS1115 arrives)
  data/                 - sensor_data.db and log file written here at runtime
tests/                  - unit tests
```

---

## Hardware Requirements

- Raspberry Pi 4
- microSD card - 16–32 GB, Class 10 recommended
- SD card reader
- Power supply appropriate for Pi 4

---

## Wiring

### I2C devices (shared bus, SDA/SCL)

| Device | I2C Address | Supply | Notes |
|---|---|---|---|
| ADS1115 (ADC) | 0x48 | **5V** | Shared by current sensor (AIN0) and PAR sensor (AIN1) |
| MikroE UVC Click | 0x4D | 3.3V | Check VCC SEL jumper - left position = 3.3V |
| DFRobot SEN0636 | 0x23 | 3.3–5V | **Set physical switch to I2C side before wiring** |

⚠️ **Logic level shifter required:** The ADS1115 must be powered at 5V for the ACS723 current sensor to work correctly. The Pi's I2C lines are 3.3V logic. A bidirectional logic level shifter is needed between the Pi's SDA/SCL pins and the ADS1115 to protect the Pi's GPIO.

Verify all I2C devices after wiring:
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

### PWM input (dissolved oxygen)

| Device | GPIO Pin (BCM) | Supply | Notes |
|---|---|---|---|
| Atlas Surveyor Isolator PWM out | GPIO17 | 3.3V | pigpiod daemon must be running |

The Surveyor Analog Isolator converts the D.O. probe's analog voltage to a 10.6 kHz PWM signal. The Pi reads pulse width to determine oxygen level. Raw voltage (mV) is logged; conversion to mg/L is done post-flight using the calibration curve from the pre-flight calibration procedure.

### Analog inputs via ADS1115

| Device | ADS1115 Channel | Notes |
|---|---|---|
| ACS723 current sensor output | AIN0 | Zero-current output = VCC/2 = 2.5V |
| PAR sensor output | AIN1 | 0–2.5V maps to 0–2500 µmol/m²/s |

### Heater - Solid State Relay (SSR)

The Pi controls the heater via a Solid State Relay on a single GPIO pin. The SSR switches the heater circuit silently with no moving parts and handles the mains load cleanly.

| Connection | Notes |
|---|---|
| Pi GPIO pin (HEATER_SSR_PIN) → SSR DC+ | 3.3V GPIO is sufficient to trigger most SSRs |
| Pi GND → SSR DC- | Common ground |
| Heater live → SSR AC Load terminal 1 | |
| Mains live → SSR AC Load terminal 2 | |
| Heater neutral / mains neutral → direct | Bypass the SSR on the neutral side |

⚠️ **The SSR load side carries mains voltage.** Have the mains wiring inspected before connecting power.

To activate: set `HEATER_CONTROLLER = "ssr"` and `HEATER_SSR_PIN = <pin>` in `config.py`. Verify switching with a multimeter across the SSR load terminals before connecting the heater - GPIO HIGH should give near-zero resistance.

The controller uses hysteresis: heater turns ON below `TEMP_TARGET_C - HEATER_HYSTERESIS_C` and OFF above `TEMP_TARGET_C + HEATER_HYSTERESIS_C`. If the SSR is switching too rapidly during testing, increase `HEATER_HYSTERESIS_C` in `config.py`.

---

## Operating System

**Raspberry Pi OS Lite (64-bit)** - fully supports GPIO, I²C, 1-Wire, Python, and Blinka.

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

Then reboot when prompted.

Enable and start the pigpio daemon (required for D.O. sensor):
```bash
sudo apt install pigpio python3-pigpio -y
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
```

Verify interfaces:
```bash
# I2C
ls /dev/i2c-*          # expected: /dev/i2c-1

# 1-Wire (after connecting DS18B20)
ls /sys/bus/w1/devices/ # expected: 28-xxxxxxxxxxxx

# pigpio
sudo systemctl status pigpiod  # expected: active (running)
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

### Start data collection

```bash
./run.sh
```

This activates the virtual environment, installs dependencies if needed, and starts `src/main.py`. Each sensor runs in its own thread. If one sensor fails, the others keep collecting.

### Dummy mode (no hardware required)

```bash
./run.sh --dummy
```

Runs the full pipeline with simulated sensor values. Useful for testing on a laptop or verifying the database and logging work correctly before connecting hardware.

### Auto-start on boot  

Install the systemd service so data collection starts automatically when the Pi receives power, with no manual intervention:

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

-- See current and DO readings together by time
SELECT
  datetime(c.timestamp, 'unixepoch') AS time,
  c.current_a,
  d.voltage_mv
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

Tests run without hardware using dummy sensors. Completed tests cover the data logger (thread safety, SQLite correctness) and the full sensor lifecycle contract. Per-sensor test stubs in `tests/test_*.py` are ready to be filled in - each file has comments describing exactly what to implement.

---

## Pre-Flight Tools

### ADC Sample Rate Benchmark

The ADS1115 is shared between the current sensor (AIN0) and PAR sensor (AIN1). Its theoretical maximum is 860 SPS but the real achievable rate on the Pi is limited by I2C bus speed and Python overhead. Run this benchmark once when hardware arrives to confirm `SAMPLE_INTERVAL_S` in `config.py` is appropriate.  

```bash
python3 tools/benchmark_adc.py
```

The script reads 500 samples from each active ADC channel, reports the sample rate in SPS, and tells you whether the current `SAMPLE_INTERVAL_S = 1.0` setting is within a safe margin. At 1 second per sample the bar is very low - this is mainly to have the number on record.

---

## Configuration

All tunable values are in `src/config.py`. Key settings:

| Setting | Default | Description |
|---|---|---|
| `SAMPLE_INTERVAL_S` | `1.0` | Seconds between readings |
| `DO_PWM_PIN` | `17` | BCM GPIO pin for D.O. PWM input |
| `ACS723_SENSITIVITY_V_PER_A` | `0.400` | **Verify against exact ACS723 part number** |
| `TEMP_TARGET_C` | `25.0` | Target temperature (used by heater controller) |
| `TEMP_WARNING_LOW_C` | `18.0` | Log warning below this temperature |
| `TEMP_WARNING_HIGH_C` | `30.0` | Log warning above this temperature |
| `HEATER_CONTROLLER` | `"passive"` | `"ssr"`, `"passive"`, or `"serial"` - set to `"ssr"` once `HEATER_SSR_PIN` is assigned |

---

## Pre-Flight Checklist

- [ ] Physical switch on SEN0636 set to **I2C** side
- [ ] VCC SEL jumper on UVC Click set to correct voltage (left = 3.3V)
- [ ] Logic level shifter in place between Pi I2C and ADS1115
- [ ] DS18B20 pull-up resistor (4.7kΩ) wired between DATA and 3.3V
- [ ] `sudo i2cdetect -y 1` shows `0x23`, `0x48`, `0x4D`
- [ ] `ls /sys/bus/w1/devices/` shows `28-xxxxxxxxxxxx`
- [ ] `sudo systemctl status pigpiod` shows active
- [ ] ACS723 part number confirmed → correct sensitivity set in `config.py`
- [ ] D.O. sensor calibration completed → calibration curve recorded
- [ ] `./run.sh --dummy` runs clean with no errors
- [ ] `./run.sh` runs on Pi with real hardware - all 6 sensors appear in startup log
- [ ] Systemd service enabled (`sudo systemctl enable msw-sensors`)
- [ ] SSR wired: GPIO pin → SSR DC+, GND → SSR DC-, load side wired to heater circuit
- [ ] `HEATER_SSR_PIN` set in `config.py` to the correct BCM pin number
- [ ] `HEATER_CONTROLLER = "ssr"` set in `config.py`
- [ ] SSR switching verified with multimeter before connecting heater to load terminals
- [ ] SD card formatted and has sufficient space (16 GB+ recommended)
- [ ] `python3 tools/benchmark_adc.py` run. 

---

## Known Gaps

| Item | Status |
|---|---|
| Heater controller GPIO pin | `HEATER_SSR_PIN` not yet set in `config.py` - assign a free BCM pin and set `HEATER_CONTROLLER = "ssr"` |
| D.O. calibration to mg/L | Raw voltage (mV) is logged; conversion done post-flight using pre-flight calibration curve |
| ADS1115 max sample rate | Run `tools/benchmark_adc.py` when hardware arrives |
| Per-sensor unit tests | Stubs written, implementation pending - see `tests/test_*.py` |
