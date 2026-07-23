import asyncio
import json
import logging
import uuid
from contextlib import suppress
from pathlib import Path

from core.config import settings

logger = logging.getLogger("SmartStation")
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class HuaweiIoTProcessManager:
    def __init__(self):
        self._process = None
        self._supervisor_task = None
        self._report_task = None
        self._stdout_task = None
        self._stderr_task = None
        self._resync_task = None
        self._stopping = False
        self._ready = asyncio.Event()
        self._write_lock = asyncio.Lock()
        self._pending = {}
        self._publish_waiters = {}
        self._publish_results = {}
        self._reports = asyncio.Queue()
        self._state = {
            "enabled": settings.HUAWEI_IOT_ENABLED,
            "process_running": False,
            "pid": None,
            "connection_state": "disabled" if not settings.HUAWEI_IOT_ENABLED else "stopped",
            "last_service_id": None,
            "last_publish_result": None,
            "last_error": None,
            "pending_reports": 0,
            "restart_count": 0,
        }

    def get_status(self):
        status = dict(self._state)
        status["pending_reports"] = self._reports.qsize()
        return status

    async def start(self):
        if not settings.HUAWEI_IOT_ENABLED or self._supervisor_task is not None:
            return
        self._stopping = False
        self._supervisor_task = asyncio.create_task(self._supervise(), name="huawei-iot-supervisor")
        self._report_task = asyncio.create_task(self._dispatch_reports(), name="huawei-iot-reports")

    async def stop(self):
        self._stopping = True
        self._ready.clear()

        if self._process and self._process.returncode is None:
            with suppress(Exception):
                await self._request("shutdown", timeout=2.0)
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    self._process.kill()
                    await self._process.wait()

        tasks = (self._report_task, self._supervisor_task, self._stdout_task, self._stderr_task, self._resync_task)
        for task in tasks:
            if task:
                task.cancel()
        for task in tasks:
            if task:
                with suppress(asyncio.CancelledError):
                    await task

        self._fail_pending(RuntimeError("华为云 IoT 子进程已停止"))
        self._fail_publish_waiters(RuntimeError("华为云 IoT 子进程已停止"))
        self._process = None
        self._supervisor_task = None
        self._report_task = None
        self._stdout_task = None
        self._stderr_task = None
        self._resync_task = None
        self._state.update({"process_running": False, "pid": None, "connection_state": "stopped"})

    async def report_properties(self, service_id: str, properties: dict, request_id: str | None = None):
        if not service_id or not isinstance(properties, dict) or not properties:
            raise ValueError("service_id 和 properties 不能为空")
        if not settings.HUAWEI_IOT_ENABLED:
            logger.info("华为云 IoT 已禁用，跳过服务 %s 的属性上报", service_id)
            return None
        if self._supervisor_task is None or self._stopping:
            raise RuntimeError("华为云 IoT 子进程管理器未运行")
        report_id = request_id or f"properties-{uuid.uuid4().hex}"
        await self._reports.put({
            "id": report_id,
            "service_id": service_id,
            "properties": properties,
        })
        return report_id

    async def wait_for_publish(self, request_id: str, timeout: float | None = None):
        completed = self._publish_results.pop(request_id, None)
        if completed:
            if completed.get("event") == "published":
                return completed
            raise RuntimeError(completed.get("error", "属性发布失败"))
        future = asyncio.get_running_loop().create_future()
        self._publish_waiters[request_id] = future
        try:
            return await asyncio.wait_for(
                future, timeout=timeout or max(settings.HUAWEI_IOT_REQUEST_TIMEOUT * 4, 20.0)
            )
        finally:
            self._publish_waiters.pop(request_id, None)

    async def _supervise(self):
        backoff = 1
        while not self._stopping:
            executable = self._resolve_path(settings.HUAWEI_IOT_EXECUTABLE)
            config = self._resolve_path(settings.HUAWEI_IOT_CONFIG)
            missing = executable if not executable.is_file() else config if not config.is_file() else None
            if missing:
                self._state.update({
                    "connection_state": "unavailable",
                    "last_error": f"未找到华为云 IoT 文件：{missing}",
                })
                logger.warning(self._state["last_error"])
                await asyncio.sleep(min(backoff, 30))
                backoff = min(backoff * 2, 30)
                continue

            try:
                self._process = await asyncio.create_subprocess_exec(
                    str(executable), "--config", str(config),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(executable.parent),
                )
                self._state.update({
                    "process_running": True,
                    "pid": self._process.pid,
                    "connection_state": "starting",
                    "last_error": None,
                })
                self._stdout_task = asyncio.create_task(self._read_stdout())
                self._stderr_task = asyncio.create_task(self._read_stderr())
                backoff = 1
                return_code = await self._process.wait()
                await self._finish_reader_tasks()
                if self._stopping:
                    break
                self._ready.clear()
                self._fail_pending(RuntimeError(f"华为云 IoT 子进程退出：{return_code}"))
                self._state.update({
                    "process_running": False,
                    "pid": None,
                    "connection_state": "exited",
                    "last_error": f"子进程异常退出，返回码 {return_code}",
                    "restart_count": self._state["restart_count"] + 1,
                })
                logger.error(self._state["last_error"])
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._ready.clear()
                self._state.update({
                    "process_running": False,
                    "pid": None,
                    "connection_state": "failed",
                    "last_error": str(exc),
                })
                logger.exception("启动华为云 IoT 子进程失败")

            await asyncio.sleep(min(backoff, 30))
            backoff = min(backoff * 2, 30)

    async def _finish_reader_tasks(self):
        for task in (self._stdout_task, self._stderr_task):
            if task:
                with suppress(asyncio.CancelledError):
                    await task
        self._stdout_task = None
        self._stderr_task = None

    async def _read_stdout(self):
        while self._process and self._process.stdout:
            line = await self._process.stdout.readline()
            if not line:
                return
            try:
                self._handle_message(json.loads(line.decode("utf-8")))
            except (UnicodeDecodeError, json.JSONDecodeError):
                logger.error("华为云 IoT 子进程输出了无效协议行：%r", line)

    async def _read_stderr(self):
        while self._process and self._process.stderr:
            line = await self._process.stderr.readline()
            if not line:
                return
            logger.info("[station_iotd] %s", line.decode("utf-8", errors="replace").rstrip())

    def _handle_message(self, message):
        request_id = message.get("id")
        if request_id and "ok" in message and request_id in self._pending:
            future = self._pending.pop(request_id)
            if not future.done():
                future.set_result(message)
            return

        event = message.get("event")
        if event == "ready":
            self._ready.set()
            self._state["connection_state"] = message.get("state", "connecting")
        elif event == "connection":
            self._state["connection_state"] = message.get("state", "unknown")
            self._state["last_error"] = message.get("error")
        elif event in {"published", "publish_failed"}:
            self._state["last_service_id"] = message.get("service_id")
            self._state["last_publish_result"] = "success" if event == "published" else "failed"
            self._state["last_error"] = message.get("error")
            waiter = self._publish_waiters.get(message.get("id"))
            if waiter and not waiter.done():
                if event == "published":
                    waiter.set_result(message)
                else:
                    waiter.set_exception(RuntimeError(message.get("error", "属性发布失败")))
            elif message.get("id"):
                self._publish_results[message["id"]] = message

    async def _dispatch_reports(self):
        while True:
            report = await self._reports.get()
            try:
                while not self._stopping:
                    await self._ready.wait()
                    try:
                        response = await self._request(
                            "report_properties",
                            request_id=report["id"],
                            service_id=report["service_id"],
                            properties=report["properties"],
                        )
                        if response.get("ok"):
                            break
                        error = response.get("error", "C 子进程拒绝上报")
                        if error in {"invalid_report", "invalid_request", "unknown_operation"}:
                            logger.error("丢弃不可重试的华为云上报 %s：%s", report["id"], error)
                            break
                        raise RuntimeError(error)
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        self._state["last_error"] = str(exc)
                        await asyncio.sleep(1)
            finally:
                self._reports.task_done()

    async def _request(self, operation, request_id=None, timeout=None, **payload):
        if not self._process or self._process.returncode is not None or not self._process.stdin:
            raise RuntimeError("华为云 IoT 子进程未运行")
        request_id = request_id or uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            async with self._write_lock:
                message = {"id": request_id, "op": operation, **payload}
                self._process.stdin.write((json.dumps(message, ensure_ascii=True) + "\n").encode("utf-8"))
                await self._process.stdin.drain()
            return await asyncio.wait_for(future, timeout=timeout or settings.HUAWEI_IOT_REQUEST_TIMEOUT)
        finally:
            self._pending.pop(request_id, None)

    def _fail_pending(self, exc):
        for future in self._pending.values():
            if not future.done():
                future.set_exception(exc)
        self._pending.clear()

    def _fail_publish_waiters(self, exc):
        for future in self._publish_waiters.values():
            if not future.done():
                future.set_exception(exc)
        self._publish_waiters.clear()

    @staticmethod
    def _resolve_path(value):
        path = Path(value)
        return path if path.is_absolute() else PROJECT_ROOT / path


huawei_iot = HuaweiIoTProcessManager()
