# MSW CAN-SBX 2025-2026 - Repository Structure

## Overview

Each sensor runs in its own thread. A failure in one sensor never stops the others
from collecting data. All readings are written to SQLite immediately - no batching,
no telemetry, no dashboard. If power cuts mid-flight, every committed row is safe.

```
msw-sbx-2526/
│
├── .github/
│   └── workflows/
│       └── formatting.yaml          # Runs black --check on every pull request
│
├── src/
│   ├── main.py                      # Entry point. Boots all sensors, one thread each.
│   │                                # A sensor that crashes does not affect the others.
│   │                                # Passes each temperature reading to the heater
│   │                                # controller so it can act on it.
│   │
│   ├── config.py                    # ALL tunable constants live here:
│   │                                # GPIO pins, I2C addresses, thresholds,
│   │                                # sample rates, calibration values.
│   │                                # Change values here - not in sensor files.
│   │
│   ├── storage/
│   │   └── data_logger.py           # Thread-safe SQLite writer.
│   │                                # One table per sensor, created automatically.
│   │                                # Every read is committed immediately.
│   │                                # Named 'storage/' (not 'logging/') to avoid
│   │                                # shadowing Python's stdlib logging module.
│   │
│   ├── sensors/
│   │   ├── base_sensor.py           # Abstract base class all sensors must implement:
│   │   │                            # connect(), disconnect(), start(), stop(), read().
│   │   │                            # read() returns a dict - logger adds timestamp.
│   │   │
│   │   ├── real/                    # Hardware drivers (run on the Pi)
│   │   │   ├── temperature_sensor.py    # DS18B20 via 1-Wire (w1thermsensor)
│   │   │   │                            # Returns: temperature_c
│   │   │   ├── current_sensor.py        # ACS723 via ADS1015 ADC (I2C 0x48, AIN0)
│   │   │   │                            # Returns: voltage_v, current_a
│   │   │   ├── do_sensor.py             # Atlas Scientific D.O. via ADS1015 ADC (I2C 0x48, AIN2)
│   │   │   │                            # Returns: voltage_mv (direct-mode schema)
│   │   │   │                            # voltage_mv → mg/L conversion done post-flight
│   │   │   ├── par_sensor.py            # SenseCAP PAR via RS-485 MODBUS RTU (MAX485E, UART)
│   │   │   │                            # Returns: par_umol_m2_s
│   │   │   │                            # DE/RE on GPIO22, TXD=GPIO14, RXD=GPIO15
│   │   │   ├── uvc_sensor.py            # MikroE UVC Click via MCP3221 ADC (I2C 0x4D)
│   │   │   │                            # Returns: voltage_v, intensity_mw_cm2
│   │   │   ├── uvb_sensor.py            # DFRobot SEN0636 UV Index Sensor (I2C 0x23)
│   │   │   │                            # Returns: uv_voltage_mv, uv_index, uv_risk_level
│   │   │   │                            # ⚠ Set physical switch to I2C before wiring
│   │   │   └── arduino_serial_reader.py # NOT a BaseSensor - reads and parses the
│   │   │                                # combined serial stream from Combinedsensors.ino
│   │   │                                # (all 6 sensors) and writes each block to the
│   │   │                                # DataLogger. Used only in Arduino mode.
│   │   │                                # See its module docstring for the text-match
│   │   │                                # parsing caveat: if the .ino's print wording
│   │   │                                # changes, the corresponding entry in
│   │   │                                # _PARSERS must be updated too.
│   │   │
│   │   └── dummy/                   # Software stand-ins - no hardware required
│   │       ├── dummy_temperature_sensor.py  # Returns ~25°C ± noise
│   │       ├── dummy_current_sensor.py      # Returns ~50mA ± noise
│   │       ├── dummy_do_sensor.py           # Returns ~1040mV ± noise (voltage_mv schema)
│   │       ├── dummy_par_sensor.py          # Returns ~1200 µmol/m²/s ± noise
│   │       ├── dummy_uvc_sensor.py          # Returns ~2.3 mW/cm² ± noise
│   │       └── dummy_uvb_sensor.py          # Returns ~300mV, index ~3 (Moderate)
│   │
│   ├── actuators/
│   │   └── heater_controller.py     # Heater control interface + two implementations:
│   │                                #
│   │                                #   MOSFETHeaterController - Pi GPIO12/PWM0 →
│   │                                #     MOSFET gate. PWM duty cycle control.
│   │                                #     28V CSA supply via buck converter.
│   │                                #     Mechanical thermostat safety cutoff at 25°C.
│   │                                #     To activate: set HEATER_CONTROLLER = "mosfet"
│   │                                #     in config.py.
│   │                                #
│   │                                #   PassiveHeaterController - logs warnings only,
│   │                                #     no commands sent. Current default.
│   │                                #
│   │                                # Active controller set by HEATER_CONTROLLER
│   │                                # in config.py. Currently: "passive".
│   │
│   └── data/
│       └── .gitkeep                 # Keeps the directory in git.
│                                    # sensor_data.db and *.log are gitignored.
│                                    # Written here at runtime.
│
├── tests/
│   ├── test_data_logger.py          # ✅ Complete - SQLite writes, thread safety,
│   │                                #    table auto-creation, timestamp correctness,
│   │                                #    concurrent write stress test.
│   │
│   ├── test_sensors_dummy.py        # ✅ Complete - BaseSensor contract across all
│   │                                #    dummy sensors: lifecycle, output keys,
│   │                                #    range checks, read-before-start.
│   │
│   ├── test_heater_controller.py    # 🔲 Stub - PassiveHeaterController tests can be
│   │                                #    filled in now (no hardware). MOSFET tests
│   │                                #    require mocking RPi.GPIO.
│   │
│   ├── test_temperature_sensor.py   # 🔲 Stub. See file for what to implement.
│   ├── test_current_sensor.py       # 🔲 Stub. See file for what to implement.
│   ├── test_do_sensor.py            # 🔲 Stub. Updated to describe the current
│   │                                #    ADS1015 voltage_mv hardware (no longer the
│   │                                #    old PWM pulse-width formula). Covers only
│   │                                #    the voltage_mv (direct/dummy) schema — see
│   │                                #    the file's docstring for the Arduino-mode
│   │                                #    (do_percent) schema note.
│   ├── test_par_sensor.py           # 🔲 Stub. Updated to describe the current RS-485
│   │                                #    MODBUS hardware (no longer the old voltage-
│   │                                #    based formula).
│   ├── test_uvc_sensor.py           # 🔲 Stub. Includes MCP3221 byte-parsing tests
│   │                                #    (no hardware needed). Same schema applies
│   │                                #    to the Arduino-mode UVC read.
│   └── test_uvb_sensor.py           # 🔲 Stub. Includes SEN0636 register byte-parsing
│                                    #    tests (no hardware needed).
│
├── tools/
│   ├── benchmark_adc.py             # Measures real ADS1015 sample rate on the Pi.
│   │                                # ⚠ Needs ADS1115→ADS1015 import update before running.
│   │                                # Run once when hardware arrives.
│   │                                # Usage: python3 tools/benchmark_adc.py
│   │
│   └── analyse_do.py                # Post-flight DO analysis script.
│                                    # Auto-detects the dissolved_oxygen table's schema:
│                                    #   "voltage_mv" (direct/dummy mode) → requires --cal
│                                    #   "do_percent" (Arduino mode) → already calibrated,
│                                    #     --cal is ignored (with a printed note if given)
│                                    # Converts to % saturation and mg/L accordingly, with
│                                    # optional pressure correction for stratosphere data.
│                                    # Usage: python3 tools/analyse_do.py --db src/data/sensor_data.db [--cal <mV>]
│
├── msw-sensors.service              # systemd unit - auto-starts on Pi power-on.
│                                    # Install: sudo cp msw-sensors.service
│                                    #   /etc/systemd/system/ && sudo systemctl
│                                    #   enable msw-sensors
│
├── run.sh                           # Start the program.
│                                    #   ./run.sh            → real hardware (Pi only)
│                                    #   ./run.sh --dummy    → dummy sensors (any machine)
│                                    #   ./run.sh --arduino  → Arduino mode (all 6 sensors)
│                                    # Auto-detects Pi vs dev machine and installs
│                                    # the correct requirements file.
│
├── requirements.txt                 # Dev dependencies (Mac / Linux dev machine).
│                                    # Only black. No Pi hardware libraries.
├── requirements-pi.txt              # Full dependencies for the Raspberry Pi.
│                                    # Includes RPi.GPIO, minimalmodbus, smbus2, etc.
│                                    # pigpio is no longer a hard dependency.
├── .gitignore
└── README.md
```

---

## Sensor → File Quick Reference

| Sensor | Interface | Real driver | Dummy | Test stub |
|---|---|---|---|---|
| DS18B20 Temperature | 1-Wire, GPIO4 (Pi) / digital pin 5 (Arduino) | `real/temperature_sensor.py` | `dummy/dummy_temperature_sensor.py` | `test_temperature_sensor.py` |
| ACS723 Current | I2C 0x48, ADS1015 AIN0 (Pi) / A2 (Arduino) | `real/current_sensor.py` | `dummy/dummy_current_sensor.py` | `test_current_sensor.py` |
| Atlas D.O. | I2C 0x48, ADS1015 AIN2 (Pi) / A0 (Arduino) | `real/do_sensor.py` | `dummy/dummy_do_sensor.py` | `test_do_sensor.py` |
| SenseCAP PAR | RS-485 MODBUS via UART, DE=GPIO22 (Pi) / SoftwareSerial pins 2/3, DE=pin 4 (Arduino) | `real/par_sensor.py` | `dummy/dummy_par_sensor.py` | `test_par_sensor.py` |
| MikroE UVC Click | I2C 0x4D (both Pi and Arduino, shares Wire bus with UV Index on Arduino) | `real/uvc_sensor.py` | `dummy/dummy_uvc_sensor.py` | `test_uvc_sensor.py` |
| DFRobot SEN0636 UV | I2C 0x23 (both Pi and Arduino) | `real/uvb_sensor.py` | `dummy/dummy_uvb_sensor.py` | `test_uvb_sensor.py` |

Arduino-mode data for all six sensors is parsed by `real/arduino_serial_reader.py` from the combined serial stream printed by `arduino/Combinedsensors.ino`; there are no separate per-sensor Arduino-mode driver files.

---

## Heater Controller Quick Reference

| Option | Class | Status | How to activate |
|---|---|---|---|
| MOSFET + PWM | `MOSFETHeaterController` | ✅ Fully implemented | `HEATER_CONTROLLER = "mosfet"` in config.py |
| Passive monitor | `PassiveHeaterController` | ✅ Fully implemented | `HEATER_CONTROLLER = "passive"` (current default) |

---

## Running Tests

```bash
# From the repo root:
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v
```

Completed tests (`test_data_logger.py`, `test_sensors_dummy.py`) pass fully.
Stub test files run but all methods are `pass` - no failures, just no coverage yet.
`test_do_sensor.py` and `test_par_sensor.py` were updated to match the current
(post-FRR) hardware — see their docstrings if you're used to the older
pulse-width DO / voltage-based PAR descriptions.

---

## Dummy Mode

Dummy sensors simulate realistic output without any hardware. Use this when:
- Developing or testing on a Mac or non-Pi machine
- Verifying the data pipeline (main.py → sensor → SQLite) end-to-end
- Checking the systemd service starts correctly before flight

```bash
./run.sh --dummy
# or
USE_DUMMY_SENSORS=true python3 src/main.py
```

---

## Adding a New Sensor

1. Create `src/sensors/real/your_sensor.py` - extend `BaseSensor`
2. Create `src/sensors/dummy/dummy_your_sensor.py` - same interface, fake data
3. Add constants to `src/config.py`
4. Import and add to the sensor list in `src/main.py`
5. If it should also be read in Arduino mode: add the read function and
   `Serial.print` lines to `arduino/Combinedsensors.ino`, then add the
   matching prefix → (table, column) entries to `_PARSERS` in
   `src/sensors/real/arduino_serial_reader.py`. Use the same output key
   names as the direct-mode driver so both modes produce the same schema.
6. Create `tests/test_your_sensor.py`
7. Add any new Pi library to `requirements-pi.txt`
8. Update the wiring section in `README.md` and the tables above

---

## Known Gaps

| Item | Status |
|---|---|
| PAR sensor MODBUS | Hardware wiring not fully verified — GPIO22 gets partial response, RO/DI needs confirmation |
| D.O. calibration | Direct/dummy mode: `voltage_mv` logged, converted post-flight. Arduino mode: `do_percent` already calibrated on-device. `tools/analyse_do.py` handles both. |
| `benchmark_adc.py` | Needs ADS1115 → ADS1015 import update before running |
| Per-sensor unit test stubs | Written and documented - implementation pending. `test_do_sensor.py`/`test_par_sensor.py` updated to match current hardware. |
| Heater testing | MOSFET + buck converter + thermostat integration test pending (scheduled May 18th) |
| Arduino serial parsing | Text-match against literal `Serial.print` strings in the `.ino` — no error is raised if the wording drifts out of sync with `_PARSERS` in `arduino_serial_reader.py`, it just silently stops logging that field |
| Surveyor vendor library | Only `do_surveyor.*`/`do_iso_surveyor.*` are used (DO sensor). ORP/pH/RTD Surveyor variants at the repo root appear to be unused leftovers from the vendor library drop-in and are candidates for removal or relocation into `arduino/libraries/` |

---

## Change Log

### Arduino/Pi integration pass (current)

| Component | Old | New | Reason |
|---|---|---|---|
| Arduino sketch sensor coverage | 5 sensors (no UV-C) | 6 sensors (UV-C added via `readUVC()`, same I2C bus as UV Index) | Arduino mode was missing UV-C entirely — direct mode reads it but the `.ino` never did |
| `arduino_serial_reader.py` `_PARSERS` | No UVC entries | `"UVC Voltage:"` / `"UVC Intensity:"` mapped to a `uvc` table with `voltage_v`/`intensity_mw_cm2` — same schema as direct-mode `uvc_sensor.py` | Keep the `uvc` table schema identical regardless of collection mode |
| `tools/analyse_do.py` | Assumed `voltage_mv` column unconditionally; crashed or silently mis-processed Arduino-mode (`do_percent`) databases | Auto-detects `voltage_mv` vs `do_percent` schema via `PRAGMA table_info`, processes each correctly, `--cal` now optional/conditional | Direct mode and Arduino mode log genuinely different DO quantities (raw ADC vs. on-device calibrated %); analysis tooling needs to handle both instead of assuming one |
| `tests/test_do_sensor.py` | Docstring described `avg_pulse_width_us` / old PWM formula | Rewritten to describe the current `voltage_mv` (ADS1015) schema | Old hardware (pigpio PWM) was already replaced per the 2026-05-14 FRR update; test stub had not been updated to match |
| `tests/test_par_sensor.py` | Docstring described a voltage-to-PAR formula and a `voltage_v` field | Rewritten to describe the current RS-485 MODBUS integer register read, with no voltage stage | Old hardware (ADS1115 analog PAR) was already replaced per the 2026-05-14 FRR update; test stub had not been updated to match |

### 2026-05-14 (FRR schematic updates)

| Component | Old | New | Reason |
|---|---|---|---|
| Current sensor ADC | ADS1115 (16-bit) | ADS1015 (12-bit) | Electrical team schematic (Figure 6) |
| D.O. sensor interface | PWM via pigpio on GPIO17 | ADS1015 AIN2 via I2C | Electrical team schematic (Figure 10) — analog isolator output routed through ADC |
| PAR sensor interface | ADS1115 AIN1 via I2C | RS-485 MODBUS RTU via UART + MAX485E | Electrical team wired RS-485 version (S-PAR-1) instead of voltage version |
| PAR DE/RE pin | GPIO17 (assumed) | GPIO22 (confirmed by GPIO scan) | Schematic ambiguous; GPIO scan test confirmed GPIO22 |
| Heater controller | SSR on/off (GPIO HIGH/LOW) | MOSFET + PWM on GPIO12 | FRR schematic (Figure 5) — cartridge heater via buck converter from 28V |
| Heater thresholds | ON < 24°C, OFF > 26°C | ON < 20°C, OFF > 25°C | FRR presentation explicitly states 20-25°C operating range |
| pigpio dependency | Required (D.O. PWM) | Optional (no longer needed) | D.O. now reads analog via ADS1015 |
| UVB sensor | Unchanged | Unchanged | FRR data table + Arduino code both confirm direct I2C @ 0x23 |
| UVC sensor | Unchanged | Unchanged | No change in FRR schematics |
| Temperature sensor | Unchanged | Unchanged | No change in FRR schematics |

---

## Pre-Flight Tools

| Script | Purpose | When to run |
|---|---|---|
| `tools/benchmark_adc.py` | Measures real ADS1015 sample rate — confirms `SAMPLE_INTERVAL_S` is safe | Once, when Pi and ADS1015 arrive |
| `tools/analyse_do.py` | Converts raw DO readings (`voltage_mv` or `do_percent`, auto-detected) → % saturation and mg/L | Post-flight, after recovery |
