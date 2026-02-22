#!/bin/bash

set -e

USE_DUMMY=false

if [[ "$1" == "--dummy" ]]; then
  USE_DUMMY=true
elif [[ -n "$1" ]]; then
  echo "[!] Unknown option: $1"
  echo "Usage: ./run.sh [--dummy]"
  exit 1
fi

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
  echo "(Hardware libraries like RPi.GPIO, pigpio, smbus2 are skipped - use --dummy)"
  pip install -r requirements.txt --quiet
fi

mkdir -p src/data

echo "Starting MSW sensor collection..."
if $USE_DUMMY; then
  echo "(DUMMY MODE - no hardware required)"
  USE_DUMMY_SENSORS=true python3 src/main.py
else
  python3 src/main.py
fi
