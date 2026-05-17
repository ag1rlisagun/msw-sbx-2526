"""
heater_controller.py - Heater control interface.

HOW IT FITS INTO THE SYSTEM:
    - The Pi reads temperature via the DS18B20 (temperature_sensor.py).
    - main.py passes each reading to HeaterController.update(temp_c).
    - The controller decides whether to turn the heater on or off based
      on the target temperature and hysteresis band from config.py.

CONTROLLER OPTIONS - set HEATER_CONTROLLER in config.py:

    "mosfet"   - MOSFET + PWM controlled by the Pi (NEW - from FRR schematic).
                 Pi outputs a PWM signal on a GPIO pin to the MOSFET gate.
                 Power comes from 28V CSA supply via buck converter.
                 A mechanical thermostat provides hardware safety cutoff at 25°C.
                 Uses on/off hysteresis (PWM duty = 100% or 0%).

    "passive"  - Log temperature warnings only, send no commands to hardware.
                 Safe with any setup. Use during development or when the
                 heater is managed manually.

HYSTERESIS (MOSFET):
    Heater turns ON  when temp drops below (target - hysteresis).
    Heater turns OFF when temp rises above (target + hysteresis).

MOSFET WIRING (from FRR schematic, Figure 5):
    Pi GPIO12/PWM0 (physical pin 32) → MOSFET gate (via gate resistor)
    28V CSA supply → Buck converter (LM2576HVS) → regulated ~20-24V
    Buck output → MOSFET drain → Cartridge heater → GND
    Mechanical thermostat in series → hardware cutoff at 25°C

    The cartridge heater is immersible in water. Power is limited to
    ~10W via PWM duty cycle control.
"""

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
# MOSFET PWM controller (NEW - from FRR schematic)
# ---------------------------------------------------------------------------

class MOSFETHeaterController(BaseHeaterController):
    """
    Controls a cartridge heater via MOSFET + PWM from a single Pi GPIO pin.
    Uses on/off hysteresis. PWM duty cycle is set to 100% (full on) or 0%
    (off). If finer power control is needed in the future, the duty cycle
    can be adjusted to limit power draw.

    To activate (config.py):
        HEATER_CONTROLLER    = "mosfet"
        HEATER_PWM_PIN       = 12       # GPIO12/PWM0 from schematic
        HEATER_PWM_FREQ_HZ   = 1000     # 1 kHz switching frequency
        HEATER_HYSTERESIS_C  = 2.5      # ON below 20°C, OFF above 25°C
    """

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
        self._pwm.start(0)  # start with 0% duty (heater off)
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
            self._set_heater(True)
        elif self._heater_on and temp_c > (self.target_c + self.hysteresis_c):
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