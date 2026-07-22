"""
main.py - MSW CAN-SBX 2025-2026 sensor collection entry point.

Supports two sensor modes (set SENSOR_MODE in config.py):

  "direct"  — Each sensor has its own Python driver and runs in its own
              thread on the Pi.  Original mode.

  "arduino" — An Arduino runs Combinedsensors.ino, reads all sensors, and
              streams the data over USB serial.  The Pi parses the serial
              output and logs to SQLite.  Use this when the Arduino can
              reach sensors the Pi cannot (e.g. SoftwareSerial RS-485 for
              the PAR sensor).

Both modes share the same DataLogger and heater controller.
"""

import os
import sys
import time
import signal
import logging
import threading

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("src/data/msw_sensor.log"),
    ],
)
log = logging.getLogger("main")

# ---------------------------------------------------------------------------
# Config and storage
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))
import config
from storage.data_logger import DataLogger

# ---------------------------------------------------------------------------
# Sensor imports — mode is resolved at startup:
#   SENSOR_MODE=arduino  →  ArduinoSerialReader (single USB serial stream)
#   USE_DUMMY_SENSORS=true → dummy drivers (no hardware)
#   otherwise             → real Pi-attached drivers (direct mode)
# ---------------------------------------------------------------------------
USE_DUMMY = os.getenv("USE_DUMMY_SENSORS", "false").lower() == "true"
SENSOR_MODE = os.getenv("SENSOR_MODE", config.SENSOR_MODE).lower()

if SENSOR_MODE == "arduino":
    log.info("--- ARDUINO MODE: reading sensors via USB serial ---")
    from sensors.real.arduino_serial_reader import ArduinoSerialReader
elif USE_DUMMY:
    log.info("--- DUMMY MODE: no real hardware will be accessed ---")
    from sensors.dummy.dummy_temperature_sensor import TemperatureSensor
    from sensors.dummy.dummy_current_sensor import CurrentSensor
    from sensors.dummy.dummy_do_sensor import DOSensor
    from sensors.dummy.dummy_par_sensor import PARSensor
    from sensors.dummy.dummy_uvc_sensor import UVCSensor
    from sensors.dummy.dummy_uvb_sensor import UVBSensor
else:
    from sensors.real.temperature_sensor import TemperatureSensor
    from sensors.real.current_sensor import CurrentSensor
    from sensors.real.do_sensor import DOSensor
    from sensors.real.par_sensor import PARSensor
    from sensors.real.uvc_sensor import UVCSensor
    from sensors.real.uvb_sensor import UVBSensor

# ---------------------------------------------------------------------------
# Heater controller
# ---------------------------------------------------------------------------
from actuators.heater_controller import (
    MOSFETHeaterController,
    PassiveHeaterController,
)


def build_heater_controller():
    """Instantiate the heater controller specified in config.py."""
    choice = config.HEATER_CONTROLLER.lower()

    if choice == "mosfet":
        return MOSFETHeaterController(
            target_c=config.TEMP_TARGET_C,
            hysteresis_c=config.HEATER_HYSTERESIS_C,
            warning_low_c=config.TEMP_WARNING_LOW_C,
            warning_high_c=config.TEMP_WARNING_HIGH_C,
            pwm_pin=config.HEATER_PWM_PIN,
            pwm_freq_hz=config.HEATER_PWM_FREQ_HZ,
        )
    elif choice == "passive":
        return PassiveHeaterController(
            target_c=config.TEMP_TARGET_C,
            warning_low_c=config.TEMP_WARNING_LOW_C,
            warning_high_c=config.TEMP_WARNING_HIGH_C,
        )
    else:
        raise ValueError(
            f"Unknown HEATER_CONTROLLER '{config.HEATER_CONTROLLER}'. "
            f"Choose 'mosfet' or 'passive'."
        )


# ---------------------------------------------------------------------------
# Graceful shutdown flag
# ---------------------------------------------------------------------------
_shutdown = threading.Event()


def _handle_signal(signum, frame):
    log.info(f"Signal {signum} received - shutting down.")
    _shutdown.set()


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


# ---------------------------------------------------------------------------
# Per-sensor collection loop
# ---------------------------------------------------------------------------

def sensor_loop(sensor, db: DataLogger, interval: float, heater=None) -> None:
    consecutive_failures = 0
    log.info(f"[{sensor.name}] Starting collection loop.")

    while not _shutdown.is_set():
        try:
            data = sensor.read()
            db.write(sensor.name, data)
            consecutive_failures = 0

            if heater is not None and "temperature_c" in data:
                try:
                    heater.update(data["temperature_c"])
                except Exception as e:
                    log.warning(f"[heater] update() failed: {e}")

        except Exception as e:
            consecutive_failures += 1
            log.warning(
                f"[{sensor.name}] Read failed ({consecutive_failures}): {e}"
            )
            if consecutive_failures >= config.MAX_CONSECUTIVE_FAILURES:
                log.error(
                    f"[{sensor.name}] {consecutive_failures} consecutive failures. "
                    f"Backing off for {config.FAILURE_BACKOFF_S}s."
                )
                for _ in range(int(config.FAILURE_BACKOFF_S)):
                    if _shutdown.is_set():
                        break
                    time.sleep(1)
                consecutive_failures = 0

        _shutdown.wait(timeout=interval)

    log.info(f"[{sensor.name}] Collection loop stopped.")


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

def build_sensors() -> list:
    sensor_factories = [
        lambda: TemperatureSensor(
            sensor_id=config.TEMPERATURE_SENSOR_ID,
        ),
        lambda: CurrentSensor(
            i2c_address=config.ADS1015_I2C_ADDRESS,
            channel=config.ADS1015_CHANNEL_CURRENT,
            sensitivity=config.ACS723_SENSITIVITY_V_PER_A,
            vcc=config.ACS723_VCC,
            sample_count=config.CURRENT_SAMPLE_COUNT,
        ),
        lambda: DOSensor(
            i2c_address=config.ADS1015_I2C_ADDRESS,
            channel=config.ADS1015_CHANNEL_DO,
            sample_count=config.DO_SAMPLE_COUNT,
        ),
        lambda: PARSensor(
            serial_port=config.PAR_SERIAL_PORT,
            slave_address=config.PAR_SLAVE_ADDRESS,
            de_pin=config.PAR_RS485_DE_PIN,
            baudrate=config.PAR_BAUDRATE,
            sample_count=config.PAR_SAMPLE_COUNT,
            max_umol=config.PAR_MAX_UMOL,
        ),
        lambda: UVCSensor(
            i2c_address=config.UVC_I2C_ADDRESS,
            vcc=config.UVC_VCC,
            calibration_factor=config.UVC_CALIBRATION_FACTOR,
            sample_count=config.UVC_SAMPLE_COUNT,
        ),
        lambda: UVBSensor(
            i2c_address=config.UVB_I2C_ADDRESS,
            sample_count=config.UVB_SAMPLE_COUNT,
        ),
    ]

    connected_sensors = []
    for factory in sensor_factories:
        sensor = None
        try:
            sensor = factory()
            sensor.connect()
            sensor.start()
            log.info(f"[{sensor.name}] Connected and started.")
            connected_sensors.append(sensor)
        except Exception as e:
            name = sensor.name if sensor else "unknown"
            log.error(f"[{name}] Failed to connect - skipping. Error: {e}")

    return connected_sensors


def main():
    log.info("=== MSW CAN-SBX 2025-2026 Starting ===")
    log.info(f"Sensor mode: {SENSOR_MODE}")

    os.makedirs("src/data", exist_ok=True)

    db = DataLogger(config.DB_PATH)
    db.connect()

    heater = None
    try:
        heater = build_heater_controller()
        heater.connect()
        log.info(f"[heater] Controller active: {config.HEATER_CONTROLLER}")
    except Exception as e:
        log.error(f"[heater] Failed to connect - temperature warnings disabled. Error: {e}")
        heater = None

    if SENSOR_MODE == "arduino":
        _run_arduino_mode(db, heater)
    else:
        _run_direct_mode(db, heater)

    if heater is not None:
        try:
            heater.disconnect()
        except Exception as e:
            log.warning(f"[heater] Error during shutdown: {e}")

    db.disconnect()
    log.info("=== MSW CAN-SBX 2025-2026 Shutdown complete ===")


# ---------------------------------------------------------------------------
# Arduino mode — single serial reader thread
# ---------------------------------------------------------------------------

def _run_arduino_mode(db: DataLogger, heater) -> None:
    reader = ArduinoSerialReader(
        port=config.ARDUINO_SERIAL_PORT,
        baud=config.ARDUINO_BAUD_RATE,
        db=db,
        heater=heater,
        shutdown_event=_shutdown,
        reconnect_delay=config.ARDUINO_RECONNECT_DELAY_S,
    )

    t = threading.Thread(
        target=reader.run,
        name="thread-arduino",
        daemon=True,
    )
    t.start()

    log.info("Collection running (Arduino mode). Send SIGTERM or Ctrl-C to stop.")
    _shutdown.wait()

    log.info("Shutdown signal received.")
    t.join(timeout=10)


# ---------------------------------------------------------------------------
# Direct mode — one thread per sensor (original behaviour)
# ---------------------------------------------------------------------------

def _run_direct_mode(db: DataLogger, heater) -> None:
    sensors = build_sensors()

    if not sensors:
        log.critical("No sensors connected. Exiting.")
        db.disconnect()
        sys.exit(1)

    log.info(f"{len(sensors)} sensor(s) active: {[s.name for s in sensors]}")

    threads = []
    for sensor in sensors:
        t = threading.Thread(
            target=sensor_loop,
            args=(sensor, db, config.SAMPLE_INTERVAL_S),
            kwargs={"heater": heater if sensor.name == "temperature" else None},
            name=f"thread-{sensor.name}",
            daemon=True,
        )
        t.start()
        threads.append(t)

    log.info("Collection running (direct mode). Send SIGTERM or Ctrl-C to stop.")
    _shutdown.wait()

    log.info("Shutdown signal received - stopping sensors.")

    for sensor in sensors:
        try:
            sensor.stop()
            sensor.disconnect()
        except Exception as e:
            log.warning(f"[{sensor.name}] Error during shutdown: {e}")

    for t in threads:
        t.join(timeout=10)


if __name__ == "__main__":
    main()
