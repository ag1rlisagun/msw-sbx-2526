# Monitoring Data on the Pi

## Watch the database and logs live

Start a tmux session:
```bash
tmux new -s monitor
```

In the first pane, watch the database refresh every 2 seconds:
```bash
watch -n 2 'sqlite3 src/data/sensor_data.db ".mode column" ".headers on" \
  "SELECT datetime(timestamp, '\''unixepoch'\'', '\''localtime'\'') AS time, temperature_c FROM temperature ORDER BY timestamp DESC LIMIT 10;"'
```

Split the screen - press `Ctrl+b` then `Shift+"`.

In the second pane, tail the log:
```bash
tail -f src/data/msw_sensor.log
```

Switch between panes with `Ctrl+b ↑` or `Ctrl+b ↓`.

Change the table/column names in the `watch` command to view a different sensor.

### If you disconnect

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
