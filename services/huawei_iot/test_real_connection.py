import asyncio
import json
import os
import shutil
import subprocess
import unittest
import uuid
from collections import deque
from pathlib import Path

from core.config import settings
from services.huawei_iot.process_manager import PROJECT_ROOT


RUN_REAL_TEST = os.getenv("RUN_HUAWEI_IOT_INTEGRATION_TEST") == "1"


@unittest.skipUnless(
    RUN_REAL_TEST,
    "设置 RUN_HUAWEI_IOT_INTEGRATION_TEST=1 后才会连接真实华为云",
)
class HuaweiIoTRealConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if os.name != "posix" or not Path("/proc").is_dir():
            self.skipTest("真实连接测试仅支持带 /proc 的 Linux/RDK 环境")

        running = self._find_running_smartstation_processes()
        if running:
            details = "\n".join(f"PID {pid}: {command}" for pid, command in running)
            self.fail(
                "检测到 SmartStation、Uvicorn 或 station_iotd 正在运行。"
                "真实测试必须独占华为设备连接，请先停止这些进程：\n"
                f"{details}"
            )

        self.executable = self._resolve_path(
            os.getenv("HUAWEI_IOT_EXECUTABLE", settings.HUAWEI_IOT_EXECUTABLE)
        )
        self.config_path = self._resolve_path(
            os.getenv("HUAWEI_IOT_CONFIG", settings.HUAWEI_IOT_CONFIG)
        )
        self.connection_timeout = float(os.getenv("HUAWEI_IOT_CONNECT_TIMEOUT", "45"))
        self.publish_timeout = float(os.getenv("HUAWEI_IOT_PUBLISH_TIMEOUT", "20"))

        self.assertTrue(self.executable.is_file(), f"未找到 station_iotd：{self.executable}")
        self.assertTrue(os.access(self.executable, os.X_OK), f"station_iotd 不可执行：{self.executable}")
        self.assertTrue(self.config_path.is_file(), f"未找到真实配置：{self.config_path}")
        self._validate_config_and_dependencies()

        from database.db_manager import DatabaseManager
        from database.models import StationCounterRepository

        DatabaseManager.init_db()
        self.counters = StationCounterRepository.get_counters()
        self.stderr_lines = deque(maxlen=100)
        self.seen_messages = []
        self.process = await asyncio.create_subprocess_exec(
            str(self.executable),
            "--config",
            str(self.config_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.executable.parent),
        )
        self.stderr_task = asyncio.create_task(self._read_stderr())

    async def asyncTearDown(self):
        process = getattr(self, "process", None)
        if process and process.returncode is None:
            try:
                await self._send({"id": "cleanup-shutdown", "op": "shutdown"})
                await asyncio.wait_for(process.wait(), timeout=5)
            except Exception:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

        task = getattr(self, "stderr_task", None)
        if task:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_real_connection_reports_current_a_and_b_values(self):
        await self._wait_for_message(
            lambda message: message.get("event") == "ready",
            timeout=10,
            description="station_iotd ready 事件",
        )
        await self._wait_for_message(
            lambda message: message.get("event") == "connection"
            and message.get("state") == "connected",
            timeout=self.connection_timeout,
            description="华为云鉴权连接成功事件",
        )

        await self._report_and_wait("A", self.counters["counter_a"])
        await self._report_and_wait("B", self.counters["counter_b"])

        status_id = f"integration-status-{uuid.uuid4().hex}"
        await self._send({"id": status_id, "op": "status"})
        status = await self._wait_for_message(
            lambda message: message.get("id") == status_id and message.get("ok") is True,
            timeout=5,
            description="状态查询响应",
        )
        self.assertEqual(status.get("state"), "connected")
        self.assertEqual(status.get("pending_reports"), 0)

        shutdown_id = f"integration-shutdown-{uuid.uuid4().hex}"
        await self._send({"id": shutdown_id, "op": "shutdown"})
        shutdown = await self._wait_for_message(
            lambda message: message.get("id") == shutdown_id and message.get("ok") is True,
            timeout=5,
            description="正常关闭响应",
        )
        self.assertEqual(shutdown.get("result"), "stopping")
        return_code = await asyncio.wait_for(self.process.wait(), timeout=10)
        self.assertEqual(return_code, 0, self._diagnostics("station_iotd 未正常退出"))

    async def _report_and_wait(self, station, value):
        request_id = f"integration-{station.lower()}-{uuid.uuid4().hex}"
        await self._send({
            "id": request_id,
            "op": "report_station",
            "station": station,
            "value": value,
        })

        accepted = False
        published = False
        deadline = asyncio.get_running_loop().time() + self.publish_timeout
        while not (accepted and published):
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                self.fail(self._diagnostics(f"等待 {station} 地发布成功超时"))
            message = await self._read_message(remaining)
            if message.get("id") != request_id:
                continue
            if "ok" in message:
                self.assertTrue(message.get("ok"), self._diagnostics(str(message)))
                self.assertIn(message.get("result"), {"queued", "already_queued"})
                accepted = True
            elif message.get("event") == "published":
                self.assertEqual(message.get("station"), station)
                self.assertEqual(message.get("value"), value)
                published = True
            elif message.get("event") == "publish_failed":
                self.fail(self._diagnostics(f"{station} 地发布失败：{message}"))

    async def _send(self, message):
        if self.process.returncode is not None:
            self.fail(self._diagnostics(f"station_iotd 已退出，返回码 {self.process.returncode}"))
        self.process.stdin.write((json.dumps(message, ensure_ascii=True) + "\n").encode("utf-8"))
        await self.process.stdin.drain()

    async def _wait_for_message(self, predicate, timeout, description):
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                self.fail(self._diagnostics(f"等待{description}超时"))
            message = await self._read_message(remaining)
            if predicate(message):
                return message

    async def _read_message(self, timeout):
        if self.process.returncode is not None:
            self.fail(self._diagnostics(f"station_iotd 提前退出：{self.process.returncode}"))
        try:
            line = await asyncio.wait_for(self.process.stdout.readline(), timeout=timeout)
        except asyncio.TimeoutError:
            self.fail(self._diagnostics("等待 station_iotd stdout 超时"))
        if not line:
            return_code = await self.process.wait()
            self.fail(self._diagnostics(f"station_iotd stdout 已关闭，返回码 {return_code}"))
        try:
            message = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.fail(self._diagnostics(f"station_iotd 输出无效 JSON：{line!r}，{exc}"))
        self.seen_messages.append(message)
        return message

    async def _read_stderr(self):
        while True:
            line = await self.process.stderr.readline()
            if not line:
                return
            self.stderr_lines.append(line.decode("utf-8", errors="replace").rstrip())

    def _validate_config_and_dependencies(self):
        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.fail(f"无法读取 station_iotd 配置：{exc}")

        required = {"work_path", "address", "port", "device_id", "secret"}
        missing = sorted(required - set(config))
        self.assertFalse(missing, f"station_iotd 配置缺少字段：{missing}")
        work_path = Path(config["work_path"])
        if not work_path.is_absolute():
            work_path = self.executable.parent / work_path
        self.assertTrue((work_path / "conf" / "rootcert.pem").is_file(), "未找到 conf/rootcert.pem")

        ldd = shutil.which("ldd")
        if ldd:
            result = subprocess.run(
                [ldd, str(self.executable)],
                capture_output=True,
                text=True,
                check=False,
            )
            output = f"{result.stdout}\n{result.stderr}"
            self.assertEqual(result.returncode, 0, output)
            self.assertNotIn("not found", output.lower(), output)

    def _find_running_smartstation_processes(self):
        matches = []
        own_pid = os.getpid()
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit() or int(entry.name) == own_pid:
                continue
            try:
                raw = (entry / "cmdline").read_bytes()
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                continue
            if not raw:
                continue
            command = raw.replace(b"\0", b" ").decode("utf-8", errors="replace").strip()
            lowered = command.lower()
            is_iot_daemon = "station_iotd" in lowered
            is_uvicorn = "uvicorn" in lowered and "main:app" in lowered
            is_smartstation_main = "python" in lowered and "smartstation" in lowered and "main.py" in lowered
            if is_iot_daemon or is_uvicorn or is_smartstation_main:
                matches.append((int(entry.name), command))
        return matches

    def _diagnostics(self, message):
        protocol = "\n".join(json.dumps(item, ensure_ascii=False) for item in self.seen_messages[-30:])
        stderr = "\n".join(self.stderr_lines)
        return f"{message}\n--- protocol ---\n{protocol}\n--- stderr ---\n{stderr}"

    @staticmethod
    def _resolve_path(value):
        path = Path(value)
        return path if path.is_absolute() else PROJECT_ROOT / path


if __name__ == "__main__":
    unittest.main()
