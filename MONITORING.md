# Monitoring Data on the Pi

## Watch all sensors and logs live

```bash
./monitor.sh
```

This opens a tmux session with all sensor tables updating every 2 seconds on top and the log streaming on the bottom. New sensors show up automatically - no script changes needed.

Switch between panes with `Ctrl+b ↑` or `Ctrl+b ↓`.

Detach: `Ctrl+b d`
Reattach: `tmux attach -t monitor`
Kill: `tmux kill-session -t monitor`

---

## Query the database directly

```bash
sqlite3 src/data/sensor_data.db
```

```sql
.mode column
.headers on

-- List all sensor tables
.tables

-- See columns in a table
.schema temperature

-- Last 10 readings from any sensor
SELECT datetime(timestamp, 'unixepoch', 'localtime') AS time, temperature_c
FROM temperature ORDER BY timestamp DESC LIMIT 10;

-- Total readings per sensor
SELECT 'temperature' AS sensor, COUNT(*) AS rows FROM temperature
UNION SELECT 'current',           COUNT(*) FROM current
UNION SELECT 'dissolved_oxygen',  COUNT(*) FROM dissolved_oxygen
UNION SELECT 'par',               COUNT(*) FROM par
UNION SELECT 'uvc',               COUNT(*) FROM uvc
UNION SELECT 'uvb',               COUNT(*) FROM uvb;

.quit
```

---

## Sensor tables

| Table               | Columns                              |
|---------------------|--------------------------------------|
| `temperature`       | `temperature_c`                      |
| `current`           | `voltage_v`, `current_a`             |
| `dissolved_oxygen`  | `voltage_mv`                         |
| `par`               | `par_umol_m2_s`                      |
| `uvc`               | `intensity_mw_cm2`                   |
| `uvb`               | `uv_index`, `risk_level`             |

All tables also have `id` and `timestamp`.