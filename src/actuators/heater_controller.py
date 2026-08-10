"""
heater_controller.py - Heater control interface.

HOW IT FITS INTO THE SYSTEM:
    - The Arduino reads temperature via the DS18B20 (digital pin 5) and
      streams it to the Pi over USB serial.
    - arduino_serial_reader.py parses each block and calls
      HeaterController.update(temp_c).
    - The controller decides whether to drive the MOSFET gate on GPIO12
      based on the target temperature and hysteresis band from config.py.

    Note the split: the temperature sensor is on the Arduino, the MOSFET
    gate is on the Pi. Control therefore has to be Pi-side, acting on the
    temperature the Arduino reports. There is no Arduino-side heater code.

CONTROLLER OPTIONS - set HEATER_CONTROLLER in config.py:

    "mosfet"   - MOSFET + PWM controlled by the Pi on GPIO12.
                 Power comes from the 28V CSA supply via a buck converter.
                 A mechanical thermostat provides a hardware safety cutoff
                 at 25 C. Uses on/off hysteresis (duty = 100% or 0%).

    "passive"  - Log temperature warnings only, send no commands to
                 hardware. Safe with any setup. Current default.

HYSTERESIS (MOSFET):
    Heater turns ON  when temp drops below (target - hysteresis).
    Heater turns OFF when temp rises above (target + hysteresis).

MOSFET WIRING (from FRR schematic, Figure 5):
    Pi GPIO12/PWM0 (physical pin 32) -> MOSFET gate (via gate resistor)
    Pi GND (physical pin 6)          -> heater circuit ground
    28V CSA supply -> buck converter (LM2576HVS) -> regulated ~20-24V
    Buck output -> MOSFET drain -> cartridge heater -> GND
    Mechanical thermostat in series -> hardware cutoff at 25 C

    !! Before powering the heater circuit, confirm a pulldown resistor
       (10k typical) is present from GPIO12 to ground. An unconfigured Pi
       GPIO is a high-impedance input, and a floating MOSFET gate can
       drift to a partially-on state - uncontrolled heating that software
       is unaware of. The mechanical thermostat is a slow backstop, not a
       substitute.

CHANGES IN THIS REVISION:
    1. MOSFETHeaterController.update() now rejects the -1.0 sentinel that
       the Arduino sends when the DS18B20 is absent or reads implausibly.
       Previously -1.0 would have been read as "far below 20 C" and driven
       the heater to 100% duty on a phantom reading.
    2. Added a staleness watchdog. If no valid temperature arrives within
       STALE_TIMEOUT_S, the heater is forced off. Covers the case where the
       serial link drops or the Arduino wedges while the heater is on.
"""

import time
import logging

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class BaseHeaterController:
    def connect(self) -> None:
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError

    def update(self, temp_c: float) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Shared sentinel handling
# ---------------------------------------------------------------------------

# The Arduino sends -1.0 for "no valid reading" (see readTemperature() in
# arduino/Combinedsensors.ino). Anything at or below this threshold is not a
# real bioreactor temperature and must never drive a control decision.
SENTINEL_THRESHOLD_C = -0.5


def _is_sentinel(temp_c) -> bool:
    """True if this value is a no-data sentinel rather than a real reading."""
    if temp_c is None:
        return True
    try:
        t = float(temp_c)
    except (TypeError, ValueError):
        return True
    if t != t:  # NaN
        return True
    return t <= SENTINEL_THRESHOLD_C


# ---------------------------------------------------------------------------
# MOSFET PWM controller
# ---------------------------------------------------------------------------

class MOSFETHeaterController(BaseHeaterController):
    """
    Controls a cartridge heater via MOSFET + PWM from a single Pi GPIO pin.
    Uses on/off hysteresis. PWM duty is 100% (full on) or 0% (off).

    To activate (config.py):
        HEATER_CONTROLLER    = "mosfet"
        HEATER_PWM_PIN       = 12       # GPIO12/PWM0 from schematic
        HEATER_PWM_FREQ_HZ   = 1000     # 1 kHz switching frequency
        HEATER_HYSTERESIS_C  = 2.5      # ON below 20 C, OFF above 25 C
    """

    # If no valid temperature arrives within this window, force the heater
    # off. Nominal Arduino block cadence is ~2-3 s, so 30 s means roughly
    # ten missed blocks before the failsafe trips - long enough to ride out
    # a brief serial hiccup, short enough to matter.
    STALE_TIMEOUT_S = 30.0

    def __init__(
        self,
        target_c: float,
        hysteresis_c: float,
        warning_low_c: float,
        warning_high_c: float,
        pwm_pin: int = None,
        pwm_freq_hz: int = 1000,
    ):
        self.target_c = target_c
        self.hysteresis_c = hysteresis_c
        self.warning_low_c = warning_low_c
        self.warning_high_c = warning_high_c
        self.pwm_pin = pwm_pin
        self.pwm_freq_hz = pwm_freq_hz
        self._heater_on = False
        self._gpio = None
        self._pwm = None
        self._last_valid_reading = None
        self._sentinel_logged = False

    def connect(self) -> None:
        if self.pwm_pin is None:
            raise RuntimeError(
                "[heater] HEATER_PWM_PIN is not set in config.py. "
                "Set it to the BCM GPIO pin number wired to the MOSFET gate."
            )
        import RPi.GPIO as GPIO
        self._gpio = GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pwm_pin, GPIO.OUT, initial=GPIO.LOW)
        self._pwm = GPIO.PWM(self.pwm_pin, self.pwm_freq_hz)
        self._pwm.start(0)  # 0% duty - heater off
        self._last_valid_reading = None
        log.info(
            f"[heater] MOSFET PWM controller ready on GPIO{self.pwm_pin} "
            f"at {self.pwm_freq_hz} Hz. "
            f"Target: {self.target_c}°C  |  "
            f"ON below {self.target_c - self.hysteresis_c:.1f}°C  |  "
            f"OFF above {self.target_c + self.hysteresis_c:.1f}°C"
        )

    def disconnect(self) -> None:
        if self._pwm is not None:
            self._pwm.ChangeDutyCycle(0)
            self._pwm.stop()
            self._pwm = None
        if self._gpio is not None:
            self._gpio.cleanup(self.pwm_pin)
            self._gpio = None
        self._heater_on = False
        log.info("[heater] MOSFET PWM controller disconnected. Heater off.")

    def update(self, temp_c: float) -> None:
        # --- Sentinel guard --------------------------------------------
        # A missing DS18B20 reports -1.0. Acting on it would read as "far
        # below the ON threshold" and drive the heater to full duty on a
        # reading that does not exist.
        if _is_sentinel(temp_c):
            if not self._sentinel_logged:
                log.warning(
                    "[heater] No valid temperature from the Arduino "
                    f"(received {temp_c!r}). Holding heater state and "
                    "watching for staleness."
                )
                self._sentinel_logged = True
            self._check_stale()
            return

        self._sentinel_logged = False
        self._last_valid_reading = time.monotonic()

        # --- Warnings ---------------------------------------------------
        if temp_c < self.warning_low_c:
            log.warning(
                f"[heater] Temperature LOW: {temp_c:.2f}°C "
                f"(threshold: {self.warning_low_c}°C)"
            )
        elif temp_c > self.warning_high_c:
            log.warning(
                f"[heater] Temperature HIGH: {temp_c:.2f}°C "
                f"(threshold: {self.warning_high_c}°C)"
            )
        else:
            log.debug(f"[heater] Temperature OK: {temp_c:.2f}°C")

        # --- Hysteresis switching --------------------------------------
        if not self._heater_on and temp_c < (self.target_c - self.hysteresis_c):
            self._set_heater(True)
        elif self._heater_on and temp_c > (self.target_c + self.hysteresis_c):
            self._set_heater(False)

    def _check_stale(self) -> None:
        """Force the heater off if valid data has stopped arriving."""
        if not self._heater_on:
            return
        if self._last_valid_reading is None:
            # Heater somehow on before any valid reading - shut it off.
            log.error("[heater] Heater is on with no valid reading ever received. Forcing off.")
            self._set_heater(False)
            return
        elapsed = time.monotonic() - self._last_valid_reading
        if elapsed > self.STALE_TIMEOUT_S:
            log.error(
                f"[heater] No valid temperature for {elapsed:.0f}s "
                f"(limit {self.STALE_TIMEOUT_S:.0f}s). Forcing heater off."
            )
            self._set_heater(False)

    def _set_heater(self, on: bool) -> None:
        if self._pwm is None:
            return
        self._heater_on = on
        self._pwm.ChangeDutyCycle(100.0 if on else 0.0)
        log.info(
            f"[heater] MOSFET {'ON  ← heater heating' if on else 'OFF ← heater idle'} "
            f"(GPIO{self.pwm_pin}, duty={'100%' if on else '0%'})"
        )

    @property
    def heater_on(self) -> bool:
        return self._heater_on


# ---------------------------------------------------------------------------
# Passive monitor - warnings only, no hardware commands
# ---------------------------------------------------------------------------

class PassiveHeaterController(BaseHeaterController):
    """
    Logs temperature warnings. Sends no commands to any hardware.
    """

    def __init__(self, target_c: float, warning_low_c: float, warning_high_c: float):
        self.target_c = target_c
        self.warning_low_c = warning_low_c
        self.warning_high_c = warning_high_c
        self._sentinel_logged = False

    def connect(self) -> None:
        log.info(
            f"[heater] Passive monitor active. "
            f"Target: {self.target_c}°C, "
            f"Warning range: {self.warning_low_c}-{self.warning_high_c}°C"
        )

    def disconnect(self) -> None:
        log.info("[heater] Passive monitor stopped.")

    def update(self, temp_c: float) -> None:
        # Same sentinel guard as the MOSFET controller. Without it the log
        # fills with "Temperature LOW: -1.00°C" once per block, which
        # drowns out real warnings.
        if _is_sentinel(temp_c):
            if not self._sentinel_logged:
                log.warning(
                    "[heater] No valid temperature from the Arduino "
                    f"(received {temp_c!r}). Suppressing further notices "
                    "until a real reading arrives."
                )
                self._sentinel_logged = True
            return

        self._sentinel_logged = False

        if temp_c < self.warning_low_c:
            log.warning(
                f"[heater] Temperature LOW: {temp_c:.2f}°C "
                f"(below {self.warning_low_c}°C threshold)"
            )
        elif temp_c > self.warning_high_c:
            log.warning(
                f"[heater] Temperature HIGH: {temp_c:.2f}°C "
                f"(above {self.warning_high_c}°C threshold)"
            )
        else:
            log.debug(f"[heater] Temperature OK: {temp_c:.2f}°C")
