"""
test_heater_controller.py - Tests for the heater controller.

WHAT TO TEST HERE:
    PassiveHeaterController has no hardware dependency and can be fully
    tested now. MOSFETHeaterController requires mocking RPi.GPIO.

    1. PASSIVE - CONNECT/DISCONNECT:
       Verify connect() and disconnect() complete without error.

    2. PASSIVE - WARNING WHEN TOO COLD:
       Call update() with temp below TEMP_WARNING_LOW_C.
       Verify a WARNING is logged.
       Hint: use self.assertLogs("actuators.heater_controller", level="WARNING")

    3. PASSIVE - WARNING WHEN TOO HOT:
       Call update() with temp above TEMP_WARNING_HIGH_C.
       Verify a WARNING is logged.

    4. PASSIVE - NO WARNING IN RANGE:
       Call update() with temp inside the warning range.
       Verify no WARNING is emitted.

    5. MOSFET - HEATER TURNS ON WHEN COLD:
       Mock RPi.GPIO. Call update() with temp below (target - hysteresis).
       Verify _set_heater(True) fires and PWM.ChangeDutyCycle is called with 100.

    6. MOSFET - HEATER TURNS OFF WHEN HOT:
       Mock RPi.GPIO. Set _heater_on = True manually.
       Call update() with temp above (target + hysteresis).
       Verify _set_heater(False) fires and PWM.ChangeDutyCycle is called with 0.

    7. MOSFET - HYSTERESIS HOLDS:
       With heater on and temp still inside the hysteresis band, verify
       the heater state does not change (no chatter).
       Example: target=22.5, hysteresis=2.5, heater on, temp=21.0
       → still inside band, heater must stay ON.

    8. MOSFET - MISSING PIN RAISES:
       Verify connect() raises RuntimeError if pwm_pin=None.

    9. MOSFET - HEATER OFF ON DISCONNECT:
       Set _heater_on = True, call disconnect(), verify PWM.ChangeDutyCycle(0)
       is called before cleanup.

    10. MOSFET - heater_on PROPERTY:
        Verify the heater_on property reflects internal state correctly.

    11. BUILD FUNCTION - MOSFET SELECTED:
        Patch config.HEATER_CONTROLLER = "mosfet" and config.HEATER_PWM_PIN = 12.
        Verify build_heater_controller() returns a MOSFETHeaterController.

    12. BUILD FUNCTION - UNKNOWN CONTROLLER RAISES:
        Patch config.HEATER_CONTROLLER = "banana".
        Verify ValueError is raised.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from actuators.heater_controller import (
    MOSFETHeaterController,
    PassiveHeaterController
)


class TestPassiveHeaterController(unittest.TestCase):

    def _make(self):
        return PassiveHeaterController(
            target_c=22.5,
            warning_low_c=20.0,
            warning_high_c=25.0,
        )

    def test_connect_and_disconnect(self):
        # TODO: verify both complete without error
        pass

    def test_warning_logged_when_too_cold(self):
        # TODO: update(15.0) → WARNING logged
        pass

    def test_warning_logged_when_too_hot(self):
        # TODO: update(30.0) → WARNING logged
        pass

    def test_no_warning_when_in_range(self):
        # TODO: update(22.5) → no WARNING
        pass


class TestMOSFETHeaterController(unittest.TestCase):

    def _make(self, pin=12):
        return MOSFETHeaterController(
            target_c=22.5,
            hysteresis_c=2.5,
            warning_low_c=20.0,
            warning_high_c=25.0,
            pwm_pin=pin,
            pwm_freq_hz=1000,
        )

    def test_connect_raises_without_pin(self):
        # TODO: pwm_pin=None → RuntimeError on connect()
        pass

    def test_heater_turns_on_when_cold(self):
        # TODO: mock RPi.GPIO, call update(19.0) (below 22.5-2.5=20)
        # verify _heater_on is True and PWM.ChangeDutyCycle called with 100
        pass

    def test_heater_turns_off_when_hot(self):
        # TODO: mock RPi.GPIO, set _heater_on = True
        # call update(26.0) (above 22.5+2.5=25)
        # verify _heater_on is False and PWM.ChangeDutyCycle called with 0
        pass

    def test_hysteresis_prevents_chatter(self):
        # TODO: heater ON, temp = 21.0 (inside band: 20 < 21 < 25)
        # verify heater state does not change
        pass

    def test_heater_off_on_disconnect(self):
        # TODO: set _heater_on = True, call disconnect()
        # verify PWM.ChangeDutyCycle(0) called before cleanup
        # verify heater_on is False after disconnect
        pass

    def test_heater_on_property(self):
        # TODO: verify heater_on == False initially
        # after triggering ON, verify heater_on == True
        pass

    def test_warning_still_logged_when_mosfet_active(self):
        # TODO: even when MOSFET is controlling the heater, temperature
        # warnings should still be logged if temp goes out of warning range
        pass


class TestBuildHeaterController(unittest.TestCase):

    def test_mosfet_selected_by_config(self):
        # TODO: patch config.HEATER_CONTROLLER = "mosfet", config.HEATER_PWM_PIN = 12
        # verify build_heater_controller() returns MOSFETHeaterController
        pass

    def test_passive_selected_by_config(self):
        # TODO: patch config.HEATER_CONTROLLER = "passive"
        # verify build_heater_controller() returns PassiveHeaterController
        pass

    def test_unknown_controller_raises(self):
        # TODO: patch config.HEATER_CONTROLLER = "banana"
        # verify ValueError is raised
        pass


if __name__ == "__main__":
    unittest.main()
