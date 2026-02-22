"""
benchmark_adc.py - Measure the real ADS1115 sample rate on this Pi.

PURPOSE:
    The ADS1115 has a configurable data rate up to 860 SPS, but the actual
    achievable rate is limited by I2C bus speed and Python overhead. This
    script measures the true sample rate so you can confirm SAMPLE_INTERVAL_S
    in config.py is set appropriately and not polling faster than the hardware
    can deliver.

    Run this once when the hardware arrives, before flight.

HARDWARE REQUIRED:
    - Raspberry Pi 4
    - ADS1115 wired to I2C (SDA/SCL) at address 0x48
    - At least one sensor connected to AIN0 (or just leave it floating for
      the purpose of this benchmark - measuring speed, not accuracy)

USAGE:
    python3 tools/benchmark_adc.py

EXPECTED OUTPUT:
    Taking 500 samples on AIN0...
    Elapsed:     2.341s
    Sample rate: 213.6 samples/sec
    Min safe SAMPLE_INTERVAL_S: 0.0047s

    Taking 500 samples on AIN1...
    Elapsed:     2.338s
    Sample rate: 213.9 samples/sec

    Recommended SAMPLE_INTERVAL_S: >= 0.005s
    Current config value:          1.0s  ← well within safe range

INTERPRETING RESULTS:
    SAMPLE_INTERVAL_S in config.py is currently 1.0 second. As long as the
    measured sample rate is above ~2 SPS (worst case
    is ~50 SPS on a loaded I2C bus), the current config is conservative and
    safe. The benchmark is to confirm this.

"""

import sys
import time

try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
except ImportError:
    print("ERROR: Required libraries not installed.")
    print("Run: pip install -r requirements-pi.txt")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SAMPLES = 500          # number of samples per channel
CHANNELS = [0, 1]      # AIN channels to benchmark (0 = current, 1 = PAR)

# Current config value - update this if SAMPLE_INTERVAL_S changes in config.py
CURRENT_INTERVAL_S = 1.0

# ---------------------------------------------------------------------------
# Run benchmark
# ---------------------------------------------------------------------------

def benchmark_channel(ads, channel_num: int, n_samples: int) -> float:
    """Read n_samples from the given AIN channel. Return samples/sec."""
    channel_map = {
        0: AnalogIn(ads, ADS.P0),
        1: AnalogIn(ads, ADS.P1),
        2: AnalogIn(ads, ADS.P2),
        3: AnalogIn(ads, ADS.P3),
    }
    ch = channel_map[channel_num]

    # Warm up - first read is sometimes slower
    _ = ch.value

    start = time.perf_counter()
    for _ in range(n_samples):
        _ = ch.value
    elapsed = time.perf_counter() - start

    rate = n_samples / elapsed
    print(f"  AIN{channel_num}: {n_samples} samples in {elapsed:.3f}s  →  {rate:.1f} SPS")
    return rate


def main():
    print("=" * 60)
    print("ADS1115 Sample Rate Benchmark")
    print("=" * 60)
    print()

    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c)
    except Exception as e:
        print(f"ERROR: Could not connect to ADS1115: {e}")
        print("Check wiring and confirm 0x48 appears in: sudo i2cdetect -y 1")
        sys.exit(1)

    print(f"Taking {SAMPLES} samples per channel...\n")

    rates = []
    for ch in CHANNELS:
        rate = benchmark_channel(ads, ch, SAMPLES)
        rates.append(rate)

    min_rate = min(rates)
    min_interval = 1.0 / min_rate

    print()
    print("-" * 60)
    print(f"Slowest channel:               {min_rate:.1f} SPS")
    print(f"Min safe SAMPLE_INTERVAL_S:    {min_interval:.4f}s")
    print(f"Current config value:          {CURRENT_INTERVAL_S}s", end="")

    if CURRENT_INTERVAL_S >= min_interval * 2:
        print("  ✅ well within safe range")
    elif CURRENT_INTERVAL_S >= min_interval:
        print("  ⚠  close to limit - consider increasing")
    else:
        print("  ❌ too fast - increase SAMPLE_INTERVAL_S in config.py")

    print()
    print("Record this result.")
    print("=" * 60)


if __name__ == "__main__":
    main()
