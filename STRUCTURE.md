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
│   │   │   ├── current_sensor.py        # ACS723 via ADS1115 ADC (I2C 0x48, AIN0)
│   │   │   │                            # Returns: voltage_v, current_a
│   │   │   ├── do_sensor.py             # Atlas Scientific D.O. via PWM (pigpio, GPIO17)
│   │   │   │                            # Returns: avg_pulse_width_us, voltage_mv
│   │   │   │                            # voltage_mv → mg/L conversion done post-flight
│   │   │   ├── par_sensor.py            # SenseCAP PAR via ADS1115 ADC (I2C 0x48, AIN1)
│   │   │   │                            # Returns: voltage_v, par_umol_m2_s
│   │   │   ├── uvc_sensor.py            # MikroE UVC Click via MCP3221 ADC (I2C 0x4D)
│   │   │   │                            # Returns: voltage_v, intensity_mw_cm2
│   │   │   └── uvb_sensor.py            # DFRobot SEN0636 UV Index Sensor (I2C 0x23)
│   │   │                                # Returns: uv_voltage_mv, uv_index, uv_risk_level
│   │   │                                # ⚠ Set physical switch to I2C before wiring
│   │   │
│   │   └── dummy/                   # Software stand-ins - no hardware required
│   │       ├── dummy_temperature_sensor.py  # Returns ~25°C ± noise
│   │       ├── dummy_current_sensor.py      # Returns ~50mA ± noise
│   │       ├── dummy_do_sensor.py           # Returns ~1040µs pulse / ~20760mV
│   │       ├── dummy_par_sensor.py          # Returns ~1200 µmol/m²/s ± noise
│   │       ├── dummy_uvc_sensor.py          # Returns ~2.3 mW/cm² ± noise
│   │       └── dummy_uvb_sensor.py          # Returns ~300mV, index ~3 (Moderate)
│   │
│   ├── actuators/
│   │   └── heater_controller.py     # Heater control interface + two implementations:
│   │                                #
│   │                                #   SSRHeaterController - Pi GPIO → SSR control
│   │                                #     input. On/off hysteresis. Fully implemented.
│   │                                #     To activate: set HEATER_CONTROLLER = "ssr"
│   │                                #     and HEATER_SSR_PIN = <pin> in config.py.
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
│   │                                #    filled in now (no hardware). SSR tests require
│   │                                #    mocking RPi.GPIO.
│   │
│   ├── test_temperature_sensor.py   # 🔲 Stub. See file for what to implement.
│   ├── test_current_sensor.py       # 🔲 Stub. See file for what to implement.
│   ├── test_do_sensor.py            # 🔲 Stub. See file for what to implement.
│   ├── test_par_sensor.py           # 🔲 Stub. See file for what to implement.
│   ├── test_uvc_sensor.py           # 🔲 Stub. Includes MCP3221 byte-parsing tests
│   │                                #    (no hardware needed).
│   └── test_uvb_sensor.py           # 🔲 Stub. Includes SEN0636 register byte-parsing
│                                    #    tests (no hardware needed).
│
├── tools/
│   ├── benchmark_adc.py             # Measures real ADS1115 sample rate on the Pi.
│   │                                # Run once when hardware arrives - result needed
│   │                                # to confirm SAMPLE_INTERVAL_S is appropriate
│   │                                # and to report max SPS to Megan.
│   │                                # Usage: python3 tools/benchmark_adc.py
│   │
│   └── analyse_do.py                # Post-flight DO analysis script.
│                                    # Converts raw voltage_mv → % saturation and mg/L
│                                    # using pre-flight calibration voltage + temperature.
│                                    # Optional pressure correction for stratosphere data.
│                                    # Usage: python3 tools/analyse_do.py --db src/data/sensor_data.db --cal <mV>
│                                    # Run once when hardware arrives - result needed
│                                    # to confirm SAMPLE_INTERVAL_S is appropriate
│                                    # and to report max SPS to Megan.
│                                    # Usage: python3 tools/benchmark_adc.py
│
│                                    
│
├── msw-sensors.service              # systemd unit - auto-starts on Pi power-on.
│                                    # Install: sudo cp msw-sensors.service
│                                    #   /etc/systemd/system/ && sudo systemctl
│                                    #   enable msw-sensors
│
├── run.sh                           # Start the program.
│                                    #   ./run.sh          → real hardware (Pi only)
│                                    #   ./run.sh --dummy  → dummy sensors (any machine)
│                                    # Auto-detects Pi vs dev machine and installs
│                                    # the correct requirements file.
│
├── requirements.txt                 # Dev dependencies (Mac / Linux dev machine).
│                                    # Only black. No Pi hardware libraries.
├── requirements-pi.txt              # Full dependencies for the Raspberry Pi.
│                                    # Includes RPi.GPIO, pigpio, smbus2, etc.
├── .gitignore
└── README.md
```

---

## Sensor → File Quick Reference

| Sensor | Interface | Real driver | Dummy | Test stub |
|---|---|---|---|---|
| DS18B20 Temperature | 1-Wire, GPIO4 | `real/temperature_sensor.py` | `dummy/dummy_temperature_sensor.py` | `test_temperature_sensor.py` |
| ACS723 Current | I2C 0x48, AIN0 | `real/current_sensor.py` | `dummy/dummy_current_sensor.py` | `test_current_sensor.py` |
| Atlas D.O. | PWM, GPIO17 | `real/do_sensor.py` | `dummy/dummy_do_sensor.py` | `test_do_sensor.py` |
| SenseCAP PAR | I2C 0x48, AIN1 | `real/par_sensor.py` | `dummy/dummy_par_sensor.py` | `test_par_sensor.py` |
| MikroE UVC Click | I2C 0x4D | `real/uvc_sensor.py` | `dummy/dummy_uvc_sensor.py` | `test_uvc_sensor.py` |
| DFRobot SEN0636 UV | I2C 0x23 | `real/uvb_sensor.py` | `dummy/dummy_uvb_sensor.py` | `test_uvb_sensor.py` |

---

## Heater Controller Quick Reference

| Option | Class | Status | How to activate |
|---|---|---|---|
| Solid State Relay | `SSRHeaterController` | ✅ Fully implemented | `HEATER_CONTROLLER = "ssr"`, set `HEATER_SSR_PIN` |
| Passive monitor | `PassiveHeaterController` | ✅ Fully implemented | `HEATER_CONTROLLER = "passive"` (current default) |

---

## Running Tests

```bash
# From the repo root:
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_*.py" -v
```

Completed tests (`test_data_logger.py`, `test_sensors_dummy.py`) pass fully.
Stub test files run but all methods are `pass` - no failures, just no coverage yet.

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
5. Create `tests/test_your_sensor.py`
6. Add any new Pi library to `requirements-pi.txt`
7. Update the wiring section in `README.md` and the tables above

---

## Known Gaps

| Item | Status |
|---|---|
| `HEATER_SSR_PIN` | Not yet assigned - set in `config.py` once wiring is confirmed, then switch `HEATER_CONTROLLER` to `"ssr"` |
| D.O. calibration | `voltage_mv` is logged; conversion to mg/L is done post-flight using the pre-flight calibration curve |
| Per-sensor unit test stubs | Written and documented - implementation pending |
| ADS1115 max sample rate | Run `tools/benchmark_adc.py` when hardware arrives and report result to Megan |

---

## Pre-Flight Tools

| Script | Purpose | When to run |
|---|---|---|
| `tools/benchmark_adc.py` | Measures real ADS1115 sample rate - confirms `SAMPLE_INTERVAL_S` is safe and provides max SPS figure | Once, when Pi and ADS1115 arrive |
| `tools/analyse_do.py` | Converts raw `voltage_mv` → % saturation and mg/L using pre-flight calibration voltage and temperature data | Post-flight, after recovery |


