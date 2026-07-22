"""
analyse_do.py - Post-flight dissolved oxygen analysis.

PURPOSE:
    Converts raw dissolved_oxygen readings into % saturation and mg/L.

    IMPORTANT — TWO POSSIBLE SCHEMAS:
        Direct mode / dummy mode log a raw "voltage_mv" column. This is an
        uncalibrated ADS1015 ADC reading and requires a --cal argument
        (the pre-flight air calibration voltage) to convert to % saturation.

        Arduino mode logs a "do_percent" column instead. This comes from
        the Atlas Scientific Surveyor Arduino library's
        read_do_percentage(), which is already calibrated on-device via
        its own EEPROM-stored calibration (see the "CAL" / "CAL,CLEAR"
        serial commands in arduino/Combinedsensors.ino). No --cal value
        is needed or used for this schema.

    This script auto-detects which schema a given database has (by
    checking the dissolved_oxygen table's columns) and processes it
    accordingly. Do not assume a hardcoded "voltage_mv" column - it may
    not exist, depending on which mode collected the data.

    A pre-flight air calibration voltage (recorded in your lab notebook)
    - Concurrent temperature readings from the temperature table
    - Optional pressure correction for stratospheric altitude

USAGE:
    # Direct-mode / dummy-mode data (voltage_mv) - calibration required:
    python3 tools/analyse_do.py --db src/data/sensor_data.db --cal 440.0

    # Arduino-mode data (do_percent) - already calibrated, no --cal needed:
    python3 tools/analyse_do.py --db src/data/sensor_data.db

    # With pressure correction using estimated altitude data:
    python3 tools/analyse_do.py --db src/data/sensor_data.db --cal 440.0 --pressure-csv altitude.csv

    # Save output to CSV:
    python3 tools/analyse_do.py --db src/data/sensor_data.db --cal 440.0 --out results/do_analysis.csv

PRE-FLIGHT CALIBRATION PROCEDURE (direct/dummy mode only):
    Before launch, expose the probe to open air for 5+ minutes until the
    voltage reading stabilises. Record:
        1. The stable voltage_mv value  ← this is your --cal value
        2. The temperature at that moment (from DS18B20)
        3. Atmospheric pressure if available
        4. Time of calibration

    Example: if the probe reads 438.2 mV in open air at 22°C before launch,
    run this script with --cal 438.2

    Arduino mode does NOT need this procedure - calibrate the probe using
    the "CAL" serial command (see Combinedsensors.ino) before flight instead,
    and read_do_percentage() will already reflect that calibration.

WHAT GETS CALCULATED:
    % saturation (voltage_mv schema):
        saturation_pct = (voltage_mv / calibration_voltage_mv) * 100.0

    % saturation (do_percent schema):
        saturation_pct = do_percent   (already computed on-device)

    mg/L (requires temperature, both schemas):
        do_mg_L = (saturation_pct / 100.0) * solubility_at_temp(temp_c)

        Solubility values come from the Standard Methods table (APHA 4500-O)
        for freshwater at 1 atm. Interpolated for temperatures between
        table entries.

    Pressure-corrected mg/L (optional, recommended for stratosphere data):
        do_corrected = do_mg_L * (pressure_kpa / 101.325)

        At ~30 km altitude, pressure is ~1-2% of sea level. The DO readings
        during float represent genuine off-gassing as ambient O2 partial
        pressure drops. This correction contextualises those readings.

OUTPUT COLUMNS:
    timestamp           - Unix epoch (from database)
    datetime            - Human-readable UTC
    voltage_mv OR do_percent - Raw logged value (whichever schema applies)
    temperature_c       - From DS18B20 (matched by nearest timestamp)
    saturation_pct       - % dissolved oxygen saturation
    do_mg_L              - Dissolved oxygen in mg/L
    do_mg_L_corrected    - Pressure-corrected mg/L (only if --pressure-csv provided)
    temp_source          - "measured" or "interpolated" or "default_25C"
"""

import argparse
import csv
import os
import sqlite3
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# DO solubility table - Standard Methods (APHA 4500-O), freshwater, 1 atm
# Temperature in °C → max dissolved oxygen in mg/L
# ---------------------------------------------------------------------------

DO_SOLUBILITY_TABLE = {
    0:  14.62,
    1:  14.23,
    2:  13.84,
    3:  13.48,
    4:  13.13,
    5:  12.80,
    6:  12.48,
    7:  12.17,
    8:  11.87,
    9:  11.59,
    10: 11.33,
    11: 11.08,
    12: 10.77,
    13: 10.60,
    14: 10.37,
    15: 10.15,
    16:  9.95,
    17:  9.74,
    18:  9.54,
    19:  9.35,
    20:  9.17,
    21:  8.99,
    22:  8.83,
    23:  8.68,
    24:  8.53,
    25:  8.26,
    26:  8.11,
    27:  7.99,
    28:  7.83,
    29:  7.69,
    30:  7.56,
    35:  7.05,
    40:  6.59,
}


def solubility_at_temp(temp_c: float) -> float:
    """
    Interpolate DO solubility (mg/L) at a given temperature from the
    Standard Methods table. Clamps to table bounds if out of range.
    """
    temps = sorted(DO_SOLUBILITY_TABLE.keys())

    if temp_c <= temps[0]:
        return DO_SOLUBILITY_TABLE[temps[0]]
    if temp_c >= temps[-1]:
        return DO_SOLUBILITY_TABLE[temps[-1]]

    # Find surrounding table entries and interpolate linearly
    for i in range(len(temps) - 1):
        t_low, t_high = temps[i], temps[i + 1]
        if t_low <= temp_c <= t_high:
            s_low = DO_SOLUBILITY_TABLE[t_low]
            s_high = DO_SOLUBILITY_TABLE[t_high]
            fraction = (temp_c - t_low) / (t_high - t_low)
            return s_low + fraction * (s_high - s_low)

    return DO_SOLUBILITY_TABLE[25]  # fallback - should never reach here


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def load_do_readings(db_path: str) -> tuple[list[dict], str]:
    """
    Load all rows from the dissolved_oxygen table.

    Returns:
        (rows, mode) where mode is:
            "voltage" - table has a "voltage_mv" column (direct/dummy mode).
                        Needs --cal to compute saturation_pct.
            "percent" - table has a "do_percent" column (Arduino mode).
                        Already calibrated on-device; --cal is ignored.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(dissolved_oxygen)")]

        if "voltage_mv" in cols:
            mode = "voltage"
            rows = conn.execute(
                "SELECT timestamp, voltage_mv "
                "FROM dissolved_oxygen ORDER BY timestamp ASC"
            ).fetchall()
        elif "do_percent" in cols:
            mode = "percent"
            rows = conn.execute(
                "SELECT timestamp, do_percent "
                "FROM dissolved_oxygen ORDER BY timestamp ASC"
            ).fetchall()
        else:
            print(
                f"ERROR: dissolved_oxygen table has neither 'voltage_mv' nor "
                f"'do_percent' column. Found columns: {cols}"
            )
            print(
                "This usually means the table is empty (no schema yet) or "
                "was written by an unexpected sensor version."
            )
            sys.exit(1)

        return [dict(r) for r in rows], mode
    except sqlite3.OperationalError as e:
        print(f"ERROR: Could not read dissolved_oxygen table: {e}")
        print("Has the sensor run and written data to this database?")
        sys.exit(1)
    finally:
        conn.close()


def load_temperature_readings(db_path: str) -> list[dict]:
    """Load all rows from the temperature table."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT timestamp, temperature_c "
            "FROM temperature ORDER BY timestamp ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        print("WARNING: No temperature table found. Will use default 25°C for all calculations.")
        return []
    finally:
        conn.close()


def match_temperature(do_ts: float, temp_rows: list[dict]) -> tuple[float, str]:
    """
    Find the temperature reading closest in time to a given DO timestamp.
    Returns (temperature_c, source_label).
    """
    if not temp_rows:
        return 25.0, "default_25C"

    closest = min(temp_rows, key=lambda r: abs(r["timestamp"] - do_ts))
    gap = abs(closest["timestamp"] - do_ts)

    if gap > 60:
        # More than 60 seconds away - flag it
        return closest["temperature_c"], "interpolated"
    return closest["temperature_c"], "measured"


# ---------------------------------------------------------------------------
# Pressure CSV loader (optional)
# ---------------------------------------------------------------------------

def load_pressure_data(csv_path: str) -> list[dict]:
    """
    Load pressure data from a CSV file with columns: timestamp, pressure_kpa
    OR: timestamp, altitude_m  (will convert altitude to pressure)

    The CSV can be generated from GPS altitude data using the standard
    atmosphere model, or from a barometric sensor if one is available.
    """
    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = float(row["timestamp"])
            if "pressure_kpa" in row:
                pressure = float(row["pressure_kpa"])
            elif "altitude_m" in row:
                # International Standard Atmosphere approximation
                alt = float(row["altitude_m"])
                pressure = 101.325 * ((1 - (alt / 44330.0)) ** 5.255)
            else:
                print("ERROR: Pressure CSV must have 'pressure_kpa' or 'altitude_m' column")
                sys.exit(1)
            rows.append({"timestamp": ts, "pressure_kpa": pressure})
    return sorted(rows, key=lambda r: r["timestamp"])


def match_pressure(do_ts: float, pressure_rows: list[dict]) -> float | None:
    """Find the pressure reading closest in time to a given DO timestamp."""
    if not pressure_rows:
        return None
    closest = min(pressure_rows, key=lambda r: abs(r["timestamp"] - do_ts))
    return closest["pressure_kpa"]


# ---------------------------------------------------------------------------
# Core conversion
# ---------------------------------------------------------------------------

def convert_row(
    do_row: dict,
    mode: str,
    cal_voltage_mv: float | None,
    temp_rows: list[dict],
    pressure_rows: list[dict],
) -> dict:
    """
    Convert a single DO row to all derived values.

    Args:
        do_row: one row from load_do_readings(), containing "timestamp" and
                either "voltage_mv" or "do_percent" depending on mode.
        mode: "voltage" or "percent" - see load_do_readings().
        cal_voltage_mv: required (and used) only when mode == "voltage".
    """
    ts = do_row["timestamp"]
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if mode == "voltage":
        voltage_mv = do_row["voltage_mv"]
        if cal_voltage_mv and cal_voltage_mv > 0:
            saturation_pct = (voltage_mv / cal_voltage_mv) * 100.0
        else:
            saturation_pct = 0.0
        raw_field = {"voltage_mv": round(voltage_mv, 3)}
    else:  # mode == "percent" — already calibrated on-device (Arduino/Atlas library)
        saturation_pct = do_row["do_percent"]
        raw_field = {"do_percent": round(saturation_pct, 3)}

    # mg/L using temperature (same for both schemas)
    temp_c, temp_source = match_temperature(ts, temp_rows)
    solubility = solubility_at_temp(temp_c)
    do_mg_L = (saturation_pct / 100.0) * solubility

    # Pressure-corrected mg/L
    pressure_kpa = match_pressure(ts, pressure_rows)
    if pressure_kpa is not None:
        do_mg_L_corrected = do_mg_L * (pressure_kpa / 101.325)
    else:
        do_mg_L_corrected = None

    return {
        "timestamp":          round(ts, 3),
        "datetime":           dt,
        **raw_field,
        "temperature_c":      round(temp_c, 2),
        "temp_source":        temp_source,
        "saturation_pct":     round(saturation_pct, 2),
        "do_mg_L":            round(do_mg_L, 3),
        "do_mg_L_corrected":  round(do_mg_L_corrected, 3) if do_mg_L_corrected is not None else "",
        "solubility_ref_mg_L": round(solubility, 3),
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_summary(results: list[dict], mode: str, has_pressure: bool) -> None:
    """Print a human-readable summary to stdout."""
    if not results:
        print("No data to summarise.")
        return

    sats        = [r["saturation_pct"] for r in results]
    do_vals     = [r["do_mg_L"] for r in results]
    temps       = [r["temperature_c"] for r in results]

    print()
    print("=" * 60)
    print("POST-FLIGHT DO ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"  Data schema:          {'voltage_mv (direct/dummy mode)' if mode == 'voltage' else 'do_percent (Arduino mode, pre-calibrated)'}")
    print(f"  Total readings:       {len(results)}")
    print(f"  Time range:           {results[0]['datetime']} → {results[-1]['datetime']}")
    print()

    if mode == "voltage":
        voltages = [r["voltage_mv"] for r in results]
        print(f"  Voltage (mV):         min {min(voltages):.1f}  max {max(voltages):.1f}  mean {sum(voltages)/len(voltages):.1f}")

    print(f"  Temperature (°C):     min {min(temps):.1f}  max {max(temps):.1f}  mean {sum(temps)/len(temps):.1f}")
    print(f"  DO saturation (%):    min {min(sats):.1f}  max {max(sats):.1f}  mean {sum(sats)/len(sats):.1f}")
    print(f"  DO (mg/L):            min {min(do_vals):.2f}  max {max(do_vals):.2f}  mean {sum(do_vals)/len(do_vals):.2f}")

    if has_pressure:
        corrected = [r["do_mg_L_corrected"] for r in results if r["do_mg_L_corrected"] != ""]
        if corrected:
            print(f"  DO corrected (mg/L):  min {min(corrected):.2f}  max {max(corrected):.2f}  mean {sum(corrected)/len(corrected):.2f}")

    print("=" * 60)
    print()


def write_csv(results: list[dict], out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"Results written to: {out_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Post-flight dissolved oxygen analysis for MSW CAN-SBX 2025-2026"
    )
    parser.add_argument(
        "--db",
        required=True,
        help="Path to sensor_data.db (e.g. src/data/sensor_data.db)"
    )
    parser.add_argument(
        "--cal",
        type=float,
        default=None,
        help="Pre-flight air calibration voltage in mV. REQUIRED for "
             "direct-mode/dummy-mode data (voltage_mv schema). IGNORED for "
             "Arduino-mode data (do_percent schema), which is already "
             "calibrated on-device via the Atlas Surveyor library."
    )
    parser.add_argument(
        "--pressure-csv",
        default=None,
        help="Optional CSV with columns: timestamp, pressure_kpa OR timestamp, altitude_m"
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional output CSV path (e.g. results/do_analysis.csv)"
    )
    args = parser.parse_args()

    # Validate inputs
    if not os.path.exists(args.db):
        print(f"ERROR: Database not found: {args.db}")
        sys.exit(1)

    print(f"Loading data from:       {args.db}")

    # Load data — this also tells us which schema (mode) the DB uses
    do_rows, mode = load_do_readings(args.db)

    if not do_rows:
        print("No dissolved oxygen readings found in database.")
        sys.exit(0)

    # --cal is required only for the voltage schema; ignored (with a note)
    # for the percent schema, since that's already calibrated on-device.
    if mode == "voltage":
        if args.cal is None or args.cal <= 0:
            print(
                "ERROR: This database uses the voltage_mv schema (direct/dummy mode). "
                "--cal (a positive number, in mV) is required to compute saturation_pct."
            )
            sys.exit(1)
        print(f"Data schema:              voltage_mv (direct/dummy mode)")
        print(f"Calibration voltage:      {args.cal} mV")
    else:
        if args.cal is not None:
            print(
                "NOTE: This database uses the do_percent schema (Arduino mode), "
                "which is already calibrated on-device — ignoring --cal."
            )
        print(f"Data schema:              do_percent (Arduino mode, pre-calibrated)")

    temp_rows    = load_temperature_readings(args.db)
    pressure_rows = load_pressure_data(args.pressure_csv) if args.pressure_csv else []

    print(f"DO readings loaded:      {len(do_rows)}")
    print(f"Temperature readings:    {len(temp_rows)}")
    if pressure_rows:
        print(f"Pressure readings:       {len(pressure_rows)}")

    # Convert all rows
    results = [
        convert_row(row, mode, args.cal, temp_rows, pressure_rows)
        for row in do_rows
    ]

    # Print summary
    print_summary(results, mode, has_pressure=bool(pressure_rows))

    # Write CSV if requested
    if args.out:
        write_csv(results, args.out)
    else:
        # Print first few rows as a preview
        print("Preview (first 5 rows):")
        print("-" * 60)
        for r in results[:5]:
            raw_display = (
                f"{r['voltage_mv']} mV" if mode == "voltage" else f"{r['do_percent']}% (on-device)"
            )
            print(
                f"  {r['datetime']}  "
                f"{raw_display}  "
                f"{r['saturation_pct']}%  "
                f"{r['do_mg_L']} mg/L  "
                f"({r['temperature_c']}°C)"
            )
        if len(results) > 5:
            print(f"  ... and {len(results) - 5} more rows. Use --out to save full results.")


if __name__ == "__main__":
    main()
