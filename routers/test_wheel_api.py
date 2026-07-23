import asyncio
import importlib
import sys
import types
import unittest
from enum import Enum


class WheelRouterTaskTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        motor = types.ModuleType("services.motor")

        class WheelDestination(str, Enum):
            A = "a"
            B = "b"

        class WheelMotion(str, Enum):
            FORWARD = "forward"

        class WheelPhase(str, Enum):
            OUTBOUND = "outbound"
            DWELL = "dwell"
            RETURNING = "returning"

        setattr(motor, "WheelBusyError", RuntimeError)
        setattr(motor, "WheelDestination", WheelDestination)
        setattr(motor, "WheelMotion", WheelMotion)
        setattr(motor, "WheelPhase", WheelPhase)
        setattr(motor, "advance_automatic_phase", lambda *_args: (False, {}))
        setattr(motor, "confirm_logistics_center", lambda: {})
        setattr(motor, "get_wheel_status", lambda: {})
        setattr(motor, "start_destination", lambda *_args: {})
        setattr(motor, "start_manual_motion", lambda *_args: {})
        setattr(motor, "stop_all_wheels", lambda: {})
        setattr(motor, "stop_manual_motion", lambda *_args: (False, {}))
        sys.modules["services.motor"] = motor

        huawei_module = types.ModuleType("services.huawei_iot")
        setattr(huawei_module, "huawei_iot", types.SimpleNamespace(get_status=lambda: {}))
        sys.modules["services.huawei_iot"] = huawei_module
        sys.modules.pop("routers.wheel_api", None)
        self.wheel_api = importlib.import_module("routers.wheel_api")

    async def asyncTearDown(self):
        await self.wheel_api.cancel_automatic_tasks()

    async def test_cancel_automatic_tasks_cancels_active_cycle(self):
        self.wheel_api.schedule_automatic_cycle(1, 60.0)
        tasks = list(self.wheel_api._automatic_tasks)
        self.assertEqual(len(tasks), 1)
        await self.wheel_api.cancel_automatic_tasks()
        self.assertTrue(tasks[0].cancelled())
        await asyncio.sleep(0)
        self.assertFalse(self.wheel_api._automatic_tasks)


if __name__ == "__main__":
    unittest.main()
