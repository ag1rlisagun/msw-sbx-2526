"""
heater_controller.py - Heater control interface.

HOW IT FITS INTO THE SYSTEM:
    - The Pi reads temperature via the DS18B20 (temperature_sensor.py).
    - main.py passes each reading to HeaterController.update(temp_c).
    - The controller decides whether to turn the heater on or off based
      on the target temperature and hysteresis band from config.py.

CONTROLLER OPTIONS - set HEATER_CONTROLLER in config.py:

    "ssr"      - Solid State Relay controlled directly by the Pi (RECOMMENDED).
                 Pi outputs HIGH/LOW on a single GPIO pin to the SSR control
                 input. The SSR switches the heater circuit silently with no
                 moving parts. Uses simple on/off hysteresis. This is the
                 fully implemented option - just set HEATER_SSR_PIN in
                 config.py and you're done.

    "passive"  - Log temperature warnings only, send no commands to hardware.
                 Safe with any setup. Use during development or when the
                 heater is managed manually.

HYSTERESIS (SSR only):
    Heater turns ON  when temp drops below (target - hysteresis).
    Heater turns OFF when temp rises above (target + hysteresis).

    With SAMPLE_INTERVAL_S = 1.0, the SSR could in theory switch every
    second if the temperature hovers right at the setpoint. To avoid this,
    keep HEATER_HYSTERESIS_C >= 1.0. If the SSR is chattering during
    testing, increase HEATER_HYSTERESIS_C in config.py - no code change
    needed.

SSR WIRING:
    Most SSR modules have a 3-32V DC control input.
    Pi GPIO (3.3V) is sufficient to trigger them.

        Pi GPIO pin (HEATER_SSR_PIN)  →  SSR DC+ (control input)
        Pi GND                        →  SSR DC- (control ground)
        Heater live wire              →  SSR AC Load terminal 1
        Mains live wire               →  SSR AC Load terminal 2
        Heater neutral / mains neutral connected directly (bypass SSR).

    ⚠ The SSR load side carries mains voltage. Have the mains wiring
      inspected by someone qualified before connecting power.

    Verify correct switching with a multimeter across the SSR load
    terminals BEFORE connecting the heater. GPIO HIGH should give
    near-zero resistance across the load terminals.
"""

import logging

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class BaseHeaterController:
    """
    Interface all controller implementations must satisfy.

    main.py calls:
        controller.connect()         - once at startup
        controller.update(temp_c)    - on every temperature reading
        controller.disconnect()      - once at shutdown
    """

    def connect(self) -> None:
        """Configure hardware. Raise RuntimeError on failure."""
        raise NotImplementedError

    def disconnect(self) -> None:
        """Release GPIO and ensure heater is off."""
        raise NotImplementedError

    def update(self, temp_c: float) -> None:
        """React to a new temperature reading."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# SSR controller - Pi GPIO → SSR control input (RECOMMENDED)
# ---------------------------------------------------------------------------

class SSRHeaterController(BaseHeaterController):
    """
    Controls a Solid State Relay from a single Pi GPIO pin using on/off
    hysteresis. Also works for mechanical relay modules with a 3.3V-
    compatible control input.

    Heater turns ON  when temp drops below (target_c - hysteresis_c).
    Heater turns OFF when temp rises above (target_c + hysteresis_c).

    To activate (config.py):
        HEATER_CONTROLLER   = "ssr"
        HEATER_SSR_PIN      = <BCM GPIO pin number wired to SSR control input>
        HEATER_HYSTERESIS_C = 1.0   # increase if SSR chatters
    """

    def __init__(
        self,
        target_c: float,
        hysteresis_c: float,
        warning_low_c: float,
        warning_high_c: float,
        ssr_pin: int = None,
    ):
        self.target_c = target_c
        self.hysteresis_c = hysteresis_c
        self.warning_low_c = warning_low_c
        self.warning_high_c = warning_high_c
        self.ssr_pin = ssr_pin
        self._heater_on = False
        self._gpio = None

    def connect(self) -> None:
        if self.ssr_pin is None:
            raise RuntimeError(
                "[heater] HEATER_SSR_PIN is not set in config.py. "
                "Set it to the BCM GPIO pin number wired to the SSR control input."
            )
        import RPi.GPIO as GPIO
        self._gpio = GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.ssr_pin, GPIO.OUT, initial=GPIO.LOW)
        log.info(
            f"[heater] SSR controller ready on GPIO{self.ssr_pin}. "
            f"Target: {self.target_c}°C  |  "
            f"ON below {self.target_c - self.hysteresis_c:.1f}°C  |  "
            f"OFF above {self.target_c + self.hysteresis_c:.1f}°C"
        )

    def disconnect(self) -> None:
        """Always ensure heater is off before releasing GPIO."""
        if self._gpio is not None:
            self._set_ssr(False)
            self._gpio.cleanup(self.ssr_pin)
            self._gpio = None
        log.info("[heater] SSR controller disconnected. Heater off.")

    def update(self, temp_c: float) -> None:
        # Warning checks - always run, regardless of heater state
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

        # Hysteresis switching
        if not self._heater_on and temp_c < (self.target_c - self.hysteresis_c):
            self._set_ssr(True)
        elif self._heater_on and temp_c > (self.target_c + self.hysteresis_c):
            self._set_ssr(False)

    def _set_ssr(self, on: bool) -> None:
        if self._gpio is None:
            return
        self._heater_on = on
        self._gpio.output(self.ssr_pin, self._gpio.HIGH if on else self._gpio.LOW)
        log.info(
            f"[heater] SSR {'ON  ← heater heating' if on else 'OFF ← heater idle'} "
            f"(GPIO{self.ssr_pin})"
        )

    @property
    def heater_on(self) -> bool:
        """Current SSR state - readable by tests and external callers."""
        return self._heater_on


# ---------------------------------------------------------------------------
# Passive monitor - warnings only, no hardware commands
# ---------------------------------------------------------------------------

class PassiveHeaterController(BaseHeaterController):
    """
    Logs temperature warnings. Sends no commands to any hardware.

    Use when:
      - Heater hardware is not yet connected or decided.
      - The heater is managed manually before flight.
      - You want anomaly logging without any control action.
    """

    def __init__(self, target_c: float, warning_low_c: float, warning_high_c: float):
        self.target_c = target_c
        self.warning_low_c = warning_low_c
        self.warning_high_c = warning_high_c

    def connect(self) -> None:
        log.info(
            f"[heater] Passive monitor active. "
            f"Target: {self.target_c}°C, "
            f"Warning range: {self.warning_low_c}-{self.warning_high_c}°C"
        )

    def disconnect(self) -> None:
        log.info("[heater] Passive monitor stopped.")

    def update(self, temp_c: float) -> None:
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
