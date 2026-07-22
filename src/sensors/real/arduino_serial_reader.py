"""
arduino_serial_reader.py - Read all sensor data from an Arduino over USB serial.

The Arduino runs Combinedsensors.ino and prints one block of readings per
second, separated by "---" lines.  This class parses those blocks and writes
each sensor's data to the shared DataLogger, exactly as the per-sensor
threads would in direct mode.

Reconnection: if the serial connection drops (USB glitch, Arduino reset),
the reader waits and retries automatically.

NOTE: this class reads and aggregates six sensors' worth of data from a
single serial stream — it is not itself a BaseSensor implementation (it
doesn't have a single connect/start/read cycle per sensor). It's kept in
sensors/real/ because it's a hardware-facing "real mode" data source, but
conceptually it plays the role of main.py's per-sensor threads for the
whole Arduino, not the role of an individual sensor driver.
"""

import re
import time
import logging
import threading

log = logging.getLogger(__name__)

# Maps a literal prefix printed by Combinedsensors.ino to (table, column).
# IMPORTANT: this is a text match against the exact strings the .ino prints
# via Serial.print(F("...")). If the wording in the sketch changes, the
# corresponding entry here must be updated too, or that field will silently
# stop being logged (no error is raised — the line just won't match).
_PARSERS = {
    "Temp:":           ("temperature",      "temperature_c"),
    "PAR:":            ("par",              "par_umol_m2_s"),
    "Current:":        ("current",          "current_a"),
    "DO:":             ("dissolved_oxygen", "do_percent"),
    "UV Voltage:":     ("uv",              "uv_voltage_mv"),
    "UV Index:":       ("uv",              "uv_index"),
    "UV Irradiance:":  ("uv",              "uv_irradiance_w_m2"),
    "Risk Level:":     ("uv",              "uv_risk_level"),
    # UV-C (MikroE UVC Click / MCP3221) — added alongside readUVC() in
    # Combinedsensors.ino. Column names match sensors/real/uvc_sensor.py
    # and sensors/dummy/dummy_uvc_sensor.py so the "uvc" table has the
    # same schema regardless of which mode wrote it.
    "UVC Voltage:":    ("uvc",             "voltage_v"),
    "UVC Intensity:":  ("uvc",             "intensity_mw_cm2"),
}

_RISK_LEVEL_MAP = {
    "low": 0,
    "moderate": 1,
    "high": 2,
    "very high": 3,
    "extreme": 4,
}

_NUMBER_RE = re.compile(r"[-+]?\d*\.?\d+")


class ArduinoSerialReader:
    """
    Reads sensor blocks from an Arduino over USB serial and writes them
    to a DataLogger.  Designed to replace the per-sensor thread model
    when the Arduino handles all hardware reads.

    Usage:
        reader = ArduinoSerialReader(port, baud, db, heater, shutdown_event)
        # runs until shutdown_event is set:
        reader.run()
    """

    def __init__(
        self,
        port: str,
        baud: int,
        db,
        heater=None,
        shutdown_event: threading.Event = None,
        reconnect_delay: float = 5.0,
    ):
        self.port = port
        self.baud = baud
        self.db = db
        self.heater = heater
        self._shutdown = shutdown_event or threading.Event()
        self.reconnect_delay = reconnect_delay

    def run(self) -> None:
        """Block until shutdown.  Reconnects automatically on serial errors."""
        import serial as pyserial

        while not self._shutdown.is_set():
            try:
                self._read_loop(pyserial)
            except pyserial.SerialException as e:
                log.error(
                    f"[arduino] Serial error: {e} — "
                    f"retrying in {self.reconnect_delay}s."
                )
                self._shutdown.wait(timeout=self.reconnect_delay)
            except Exception as e:
                log.error(f"[arduino] Unexpected error: {e}")
                self._shutdown.wait(timeout=self.reconnect_delay)

        log.info("[arduino] Reader shut down.")

    def _read_loop(self, pyserial) -> None:
        log.info(f"[arduino] Opening {self.port} at {self.baud} baud...")
        with pyserial.Serial(self.port, self.baud, timeout=2) as ser:
            time.sleep(2)
            log.info("[arduino] Connected. Listening for sensor data...")

            current_block: dict[str, dict[str, float]] = {}

            while not self._shutdown.is_set():
                raw = ser.readline()
                if not raw:
                    continue

                try:
                    line = raw.decode("utf-8", errors="replace").strip()
                except Exception:
                    continue

                if not line:
                    continue

                if line == "---":
                    if current_block:
                        self._flush_block(current_block)
                    current_block = {}
                    continue

                self._parse_line(line, current_block)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_line(line: str, block: dict) -> None:
        for prefix, (table, column) in _PARSERS.items():
            if line.startswith(prefix):
                if column == "uv_risk_level":
                    value = ArduinoSerialReader._parse_risk_level(line)
                else:
                    value = ArduinoSerialReader._parse_number(line, prefix)
                if value is not None:
                    if table not in block:
                        block[table] = {}
                    block[table][column] = value
                break

    @staticmethod
    def _parse_number(line: str, prefix: str) -> float | None:
        after = line[len(prefix):].strip()
        match = _NUMBER_RE.search(after)
        return float(match.group()) if match else None

    @staticmethod
    def _parse_risk_level(line: str) -> float | None:
        after = line.split(":", 1)[1].strip().lower()
        return float(_RISK_LEVEL_MAP.get(after, -1))

    # ------------------------------------------------------------------
    # Write to DB + heater
    # ------------------------------------------------------------------

    def _flush_block(self, block: dict) -> None:
        count = 0
        for table_name, columns in block.items():
            self.db.write(table_name, columns)
            count += len(columns)

        log.debug(
            f"[arduino] Logged {count} values across "
            f"{len(block)} table(s)."
        )

        if self.heater is not None and "temperature" in block:
            temp = block["temperature"].get("temperature_c")
            if temp is not None:
                try:
                    self.heater.update(temp)
                except Exception as e:
                    log.warning(f"[heater] update() failed: {e}")
