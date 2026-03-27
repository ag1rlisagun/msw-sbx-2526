#!/bin/bash
# monitor.sh — Live sensor dashboard
# Discovers all tables in the database automatically.
# Usage: ./monitor.sh

DB="src/data/sensor_data.db"
LOG="src/data/msw_sensor.log"
SESSION="monitor"

if ! command -v tmux &> /dev/null; then
  echo "tmux is not installed. Run: sudo apt install tmux"
  exit 1
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Session '$SESSION' already exists. Attaching..."
  tmux attach -t "$SESSION"
  exit 0
fi

# Top pane: cycle through every table in the database
tmux new-session -d -s "$SESSION" \
  "watch -n 2 'for table in \$(sqlite3 $DB \"SELECT name FROM sqlite_master WHERE type=\\\"table\\\" ORDER BY name;\"); do
    echo \"========== \$table ==========\"
    sqlite3 -column -header $DB \"SELECT datetime(timestamp, \\\"unixepoch\\\", \\\"localtime\\\") AS time, * FROM \$table ORDER BY timestamp DESC LIMIT 5;\"
    echo \"\"
  done'"

# Bottom pane: live log
tmux split-window -v -t "$SESSION" "tail -f $LOG"

# Give the DB pane more space
tmux resize-pane -t "$SESSION:0.0" -y 75%

tmux attach -t "$SESSION"
