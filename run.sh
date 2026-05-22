#!/bin/bash

set -e

USE_DUMMY=false
USE_ARDUINO=false

for arg in "$@"; do
  case "$arg" in
    --dummy)   USE_DUMMY=true ;;
    --arduino) USE_ARDUINO=true ;;
    *)
      echo "[!] Unknown option: $arg"
      echo "Usage: ./run.sh [--dummy | --arduino]"
      exit 1
      ;;
  esac
done

# Setup virtual environment
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate

# Install the right requirements file.
# On a Raspberry Pi (Linux + ARM), install the full hardware requirements.
# On any other machine (Mac, Linux dev box), install the lightweight dev requirements.
echo "Installing requirements..."
pip install --upgrade pip --quiet

if [[ "$(uname -s)" == "Linux" ]] && [[ "$(uname -m)" == arm* || "$(uname -m)" == aarch64 ]]; then
  pip install -r requirements-pi.txt --quiet
else
  echo "(Non-Pi machine detected - installing dev requirements only)"
  echo "(Hardware libraries like RPi.GPIO, smbus2, minimalmodbus are skipped - use --dummy)"
  pip install -r requirements.txt --quiet
fi

mkdir -p src/data

echo "Starting MSW sensor collection..."
if $USE_DUMMY; then
  echo "(DUMMY MODE - no hardware required)"
  USE_DUMMY_SENSORS=true python3 src/main.py
elif $USE_ARDUINO; then
  echo "(ARDUINO MODE - reading sensors via USB serial)"
  SENSOR_MODE=arduino python3 src/main.py
else
  python3 src/main.py
fi