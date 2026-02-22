"""
main.py - MSW CAN-SBX 2025-2026 sensor collection entry point.

Design:
- Each sensor runs in its own thread. A failure in one sensor thread
  does not affect any other sensor - this is the primary lesson from
  the previous experiment.
- Every reading is written to SQLite immediately after it is taken.
- The logger is shared across threads but is internally thread-safe.
- On startup, sensors are initialized one by one. If a sensor fails
  to connect, it is skipped with a warning - the others still run.
- The temperature sensor thread passes each reading to the heater
  controller so it can act on it (warn, toggle relay, or send serial
  command - depending on which controller is configured in config.py).
- The main thread does nothing except keep the process alive and
  respond to Ctrl-C / SIGTERM cleanly.
"""

import os
import sys
import time
import signal
import logging
import threading

# ---------------------------------------------------------------------------
# Logging setup - goes to stdout (captured by systemd journal) and a file
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
# Sensor imports - real vs dummy selected by environment variable
# ---------------------------------------------------------------------------
USE_DUMMY = os.getenv("USE_DUMMY_SENSORS", "false").lower() == "true"

if USE_DUMMY:
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
# Heater controller - selected by HEATER_CONTROLLER in config.py
# ---------------------------------------------------------------------------
from actuators.heater_controller import (
    SSRHeaterController,
    PassiveHeaterController,
)

def build_heater_controller():
    """Instantiate the heater controller specified in config.py."""
    choice = config.HEATER_CONTROLLER.lower()

    if choice == "ssr":
        return SSRHeaterController(
            target_c=config.TEMP_TARGET_C,
            hysteresis_c=config.HEATER_HYSTERESIS_C,
            warning_low_c=config.TEMP_WARNING_LOW_C,
            warning_high_c=config.TEMP_WARNING_HIGH_C,
            ssr_pin=config.HEATER_SSR_PIN,
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
            f"Choose 'ssr' or 'passive'."
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
    """
    Runs in its own thread. Collects one reading per interval and writes
    it to the database. Handles failures independently - a sensor that
    keeps failing backs off and retries, but never kills other sensors.

    If heater is provided (temperature sensor only), each reading is
    passed to heater.update() so the controller can act on it.
    """
    consecutive_failures = 0

    log.info(f"[{sensor.name}] Starting collection loop.")

    while not _shutdown.is_set():
        try:
            data = sensor.read()
            db.write(sensor.name, data)
            consecutive_failures = 0  # reset on success

            # Pass temperature to heater controller
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
    """
    Instantiate and connect each sensor. If a sensor fails to connect,
    it is skipped - the program continues without it.
    """
    sensor_factories = [
        lambda: TemperatureSensor(
            sensor_id=config.TEMPERATURE_SENSOR_ID
        ),
        lambda: CurrentSensor(
            i2c_address=config.ADS1115_I2C_ADDRESS,
            channel=config.ADS1115_CHANNEL_CURRENT,
            sensitivity=config.ACS723_SENSITIVITY_V_PER_A,
            vcc=config.ACS723_VCC,
            sample_count=config.CURRENT_SAMPLE_COUNT,
        ),
        lambda: DOSensor(
            pwm_pin=config.DO_PWM_PIN,
            avg_samples=config.DO_AVG_SAMPLES,
            pulse_timeout_us=config.DO_PULSE_TIMEOUT_US,
        ),
        lambda: PARSensor(
            i2c_address=config.ADS1115_I2C_ADDRESS,
            channel=config.ADS1115_CHANNEL_PAR,
            max_voltage=config.PAR_MAX_VOLTAGE_V,
            max_umol=config.PAR_MAX_UMOL,
            sample_count=config.PAR_SAMPLE_COUNT,
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

    os.makedirs("src/data", exist_ok=True)

    # Open database
    db = DataLogger(config.DB_PATH)
    db.connect()

    # Connect heater controller
    heater = None
    try:
        heater = build_heater_controller()
        heater.connect()
        log.info(f"[heater] Controller active: {config.HEATER_CONTROLLER}")
    except Exception as e:
        log.error(f"[heater] Failed to connect - temperature warnings disabled. Error: {e}")
        heater = None

    # Connect sensors
    sensors = build_sensors()

    if not sensors:
        log.critical("No sensors connected. Exiting.")
        db.disconnect()
        sys.exit(1)

    log.info(f"{len(sensors)} sensor(s) active: {[s.name for s in sensors]}")

    # Start one thread per sensor.
    # The temperature sensor thread gets the heater controller passed in.
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

    log.info("Collection running. Send SIGTERM or Ctrl-C to stop.")
    _shutdown.wait()

    log.info("Shutdown signal received - stopping sensors.")

    for sensor in sensors:
        try:
            sensor.stop()
            sensor.disconnect()
        except Exception as e:
            log.warning(f"[{sensor.name}] Error during shutdown: {e}")

    if heater is not None:
        try:
            heater.disconnect()
        except Exception as e:
            log.warning(f"[heater] Error during shutdown: {e}")

    for t in threads:
        t.join(timeout=10)

    db.disconnect()
    log.info("=== MSW CAN-SBX 2025-2026 Shutdown complete ===")


if __name__ == "__main__":
    main()
