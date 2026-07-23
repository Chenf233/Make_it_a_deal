import importlib
import sys
import types
import unittest


class GPIOStub(types.ModuleType):
    BOARD = 10
    OUT = 1
    LOW = 0
    HIGH = 1

    def __init__(self):
        super().__init__("Hobot.GPIO")
        self.outputs = {}

    def setwarnings(self, _enabled):
        pass

    def setmode(self, _mode):
        pass

    def setup(self, pin, _mode, initial=LOW):
        self.outputs[pin] = initial

    def output(self, pin, value):
        self.outputs[pin] = value


class WheelStateMachineTests(unittest.TestCase):
    def setUp(self):
        self.gpio = GPIOStub()
        hobot = types.ModuleType("Hobot")
        setattr(hobot, "GPIO", self.gpio)
        sys.modules["Hobot"] = hobot
        sys.modules["Hobot.GPIO"] = self.gpio
        sys.modules.pop("services.motor", None)
        self.motor = importlib.import_module("services.motor")

    def assert_high_pins(self, *expected):
        high = {
            pin
            for pin in self.motor.WHEEL_PINS
            if self.gpio.outputs[pin] == self.gpio.HIGH
        }
        self.assertEqual(high, set(expected))

    def test_station_1_cycle_has_dwell_and_returns_to_center(self):
        result = self.motor.start_destination("a")
        token = result["token"]
        status = result["status"]
        self.assertEqual(status["destination"], "station_1")
        self.assertEqual(status["phase"], "outbound")
        self.assertEqual(status["location"], "unknown")
        self.assertTrue(status["busy"])
        self.assert_high_pins(
            self.motor.LEFT_FORWARD_PIN, self.motor.RIGHT_FORWARD_PIN
        )

        advanced, status = self.motor.advance_automatic_phase(token, "outbound")
        self.assertTrue(advanced)
        self.assertEqual(status["phase"], "dwell")
        self.assertEqual(status["location"], "station_1")
        self.assertTrue(status["busy"])
        self.assertIsNotNone(status["arrival_id"])
        self.assert_high_pins()
        with self.assertRaises(self.motor.WheelBusyError):
            self.motor.start_manual_motion("forward")

        advanced, status = self.motor.advance_automatic_phase(token, "dwell")
        self.assertTrue(advanced)
        self.assertEqual(status["motion"], "backward")
        self.assertEqual(status["phase"], "returning")
        self.assert_high_pins(
            self.motor.LEFT_BACKWARD_PIN, self.motor.RIGHT_BACKWARD_PIN
        )

        advanced, status = self.motor.advance_automatic_phase(token, "returning")
        self.assertTrue(advanced)
        self.assertEqual(status["location"], "logistics_center")
        self.assertIsNone(status["phase"])
        self.assertFalse(status["busy"])
        self.assertFalse(status["requires_homing"])
        self.assert_high_pins()

    def test_station_2_uses_reverse_outbound_and_forward_return(self):
        result = self.motor.start_destination("b")
        token = result["token"]
        self.assert_high_pins(
            self.motor.LEFT_BACKWARD_PIN, self.motor.RIGHT_BACKWARD_PIN
        )
        self.motor.advance_automatic_phase(token, "outbound")
        self.motor.advance_automatic_phase(token, "dwell")
        self.assert_high_pins(
            self.motor.LEFT_FORWARD_PIN, self.motor.RIGHT_FORWARD_PIN
        )

    def test_stop_invalidates_cycle_and_requires_confirmation(self):
        result = self.motor.start_destination("a")
        token = result["token"]
        stopped = self.motor.stop_all_wheels()
        self.assertEqual(stopped["location"], "unknown")
        self.assertTrue(stopped["requires_homing"])
        self.assertFalse(stopped["busy"])
        self.assert_high_pins()

        advanced, _status = self.motor.advance_automatic_phase(token, "outbound")
        self.assertFalse(advanced)
        with self.assertRaisesRegex(self.motor.WheelBusyError, "位置未知"):
            self.motor.start_destination("a")

        confirmed = self.motor.confirm_logistics_center()
        self.assertEqual(confirmed["location"], "logistics_center")
        self.assertFalse(confirmed["requires_homing"])

    def test_manual_recovery_is_allowed_but_ends_unknown(self):
        self.motor.start_manual_motion("turn-left")
        stopped, status = self.motor.stop_manual_motion("turn-left")
        self.assertTrue(stopped)
        self.assertEqual(status["location"], "unknown")
        self.assertTrue(status["requires_homing"])
        self.motor.start_manual_motion("forward")

    def test_transition_requires_matching_token_and_phase(self):
        result = self.motor.start_destination("a")
        token = result["token"]
        advanced, status = self.motor.advance_automatic_phase(token + 1, "outbound")
        self.assertFalse(advanced)
        self.assertEqual(status["phase"], "outbound")
        advanced, status = self.motor.advance_automatic_phase(token, "dwell")
        self.assertFalse(advanced)
        self.assertEqual(status["phase"], "outbound")


if __name__ == "__main__":
    unittest.main()
