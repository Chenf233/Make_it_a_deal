import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from services.huawei_iot.process_manager import HuaweiIoTProcessManager


class FakeStdin:
    def __init__(self):
        self.writes = []

    def write(self, data):
        self.writes.append(data)

    async def drain(self):
        return None


class FakeProcess:
    def __init__(self):
        self.returncode = None
        self.stdin = FakeStdin()


class HuaweiIoTProcessManagerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = HuaweiIoTProcessManager()

    async def asyncTearDown(self):
        for task in (self.manager._report_task, self.manager._resync_task):
            if task and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_response_and_publish_event_are_distinct(self):
        future = asyncio.get_running_loop().create_future()
        self.manager._pending["report-1"] = future

        self.manager._handle_message({
            "event": "published",
            "id": "report-1",
            "station": "A",
            "value": 1,
        })

        self.assertFalse(future.done())
        self.assertEqual(self.manager.get_status()["last_destination"], "A")
        self.assertEqual(self.manager.get_status()["last_publish_result"], "success")

        self.manager._handle_message({
            "id": "report-1",
            "ok": True,
            "result": "queued",
        })

        response = await future
        self.assertEqual(response["result"], "queued")

    async def test_connection_events_update_status(self):
        self.manager._resync_current_counters = AsyncMock()

        self.manager._handle_message({"event": "ready", "state": "connecting"})
        await asyncio.sleep(0)
        self.assertTrue(self.manager._ready.is_set())
        self.manager._resync_current_counters.assert_awaited_once()

        self.manager._handle_message({"event": "connection", "state": "connected"})
        self.assertEqual(self.manager.get_status()["connection_state"], "connected")

        self.manager._handle_message({
            "event": "connection",
            "state": "disconnected",
            "error": "connection_lost",
        })
        status = self.manager.get_status()
        self.assertEqual(status["connection_state"], "disconnected")
        self.assertEqual(status["last_error"], "connection_lost")

    async def test_report_station_validation_and_disabled_mode(self):
        with self.assertRaises(ValueError):
            await self.manager.report_station("C", 1)

        with patch("services.huawei_iot.process_manager.settings.HUAWEI_IOT_ENABLED", False):
            report_id = await self.manager.report_station("A", 1)

        self.assertIsNone(report_id)
        self.assertTrue(self.manager._reports.empty())

    async def test_report_requires_running_manager(self):
        with patch("services.huawei_iot.process_manager.settings.HUAWEI_IOT_ENABLED", True):
            with self.assertRaisesRegex(RuntimeError, "未运行"):
                await self.manager.report_station("A", 1)

    async def test_request_writes_ndjson_and_correlates_response(self):
        self.manager._process = FakeProcess()

        request_task = asyncio.create_task(self.manager._request(
            "report_station",
            request_id="report-1",
            timeout=1,
            station="A",
            value=5,
        ))
        await self._wait_until(lambda: "report-1" in self.manager._pending)

        encoded = self.manager._process.stdin.writes[0]
        self.assertTrue(encoded.endswith(b"\n"))
        self.assertEqual(json.loads(encoded), {
            "id": "report-1",
            "op": "report_station",
            "station": "A",
            "value": 5,
        })

        self.manager._handle_message({
            "id": "report-1",
            "ok": True,
            "result": "queued",
        })
        response = await request_task
        self.assertEqual(response["result"], "queued")
        self.assertNotIn("report-1", self.manager._pending)

    async def test_request_timeout_cleans_pending_future(self):
        self.manager._process = FakeProcess()

        with self.assertRaises(asyncio.TimeoutError):
            await self.manager._request("status", request_id="timeout-1", timeout=0.01)

        self.assertNotIn("timeout-1", self.manager._pending)

    async def test_permanent_error_does_not_block_following_report(self):
        self.manager._process = FakeProcess()
        self.manager._ready.set()
        self.manager._report_task = asyncio.create_task(self.manager._dispatch_reports())

        await self.manager._reports.put({"id": "bad-1", "station": "A", "value": 1})
        await self.manager._reports.put({"id": "good-2", "station": "B", "value": 2})

        await self._wait_until(lambda: "bad-1" in self.manager._pending)
        self.manager._handle_message({
            "id": "bad-1",
            "ok": False,
            "error": "invalid_report",
        })

        await self._wait_until(lambda: "good-2" in self.manager._pending)
        self.manager._handle_message({
            "id": "good-2",
            "ok": True,
            "result": "queued",
        })

        await asyncio.wait_for(self.manager._reports.join(), timeout=1)
        self.assertTrue(self.manager._report_task and not self.manager._report_task.done())

    async def _wait_until(self, predicate, timeout=1):
        async def wait():
            while not predicate():
                await asyncio.sleep(0)

        await asyncio.wait_for(wait(), timeout=timeout)


if __name__ == "__main__":
    unittest.main()
