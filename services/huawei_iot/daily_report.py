import asyncio
import logging
import uuid
from contextlib import suppress
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from core.config import settings
from database.models import ParcelDailyCounterRepository
from services.huawei_iot.process_manager import huawei_iot

logger = logging.getLogger("SmartStation")


class DailyParcelReportService:
    def __init__(self):
        self._task = None
        self._sync_lock = asyncio.Lock()
        self._timezone = ZoneInfo(settings.HUAWEI_IOT_BUSINESS_TIMEZONE)

    async def start(self):
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="daily-parcel-report")

    async def stop(self):
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def today(self) -> date:
        return datetime.now(self._timezone).date()

    async def sync_date(self, business_date: date, force: bool = False) -> dict:
        if business_date >= self.today():
            raise ValueError("只能同步已经结束的业务日期")
        async with self._sync_lock:
            existing = await asyncio.to_thread(ParcelDailyCounterRepository.get, business_date)
            if existing and existing["report_status"] == "published" and not force:
                return {**existing, "queued": False, "reason": "already_published"}
            if not settings.HUAWEI_IOT_ENABLED:
                raise RuntimeError("华为云 IoT 已禁用")

            row = await asyncio.to_thread(
                ParcelDailyCounterRepository.refresh_snapshot, business_date
            )
            request_id = f"daily-{business_date.isoformat()}-{uuid.uuid4().hex}"
            await asyncio.to_thread(ParcelDailyCounterRepository.mark_publishing, business_date.isoformat())
            try:
                await huawei_iot.report_properties(
                    settings.HUAWEI_IOT_DAILY_SERVICE_ID,
                    {
                        settings.HUAWEI_IOT_DAILY_PROPERTY_A: row["target_a_count"],
                        settings.HUAWEI_IOT_DAILY_PROPERTY_B: row["target_b_count"],
                    },
                    request_id=request_id,
                )
                await huawei_iot.wait_for_publish(request_id)
                await asyncio.to_thread(ParcelDailyCounterRepository.mark_published, business_date.isoformat())
            except Exception as exc:
                await asyncio.to_thread(
                    ParcelDailyCounterRepository.mark_failed, business_date.isoformat(), str(exc)
                )
                raise
            published = await asyncio.to_thread(ParcelDailyCounterRepository.get, business_date)
            return {
                **(published or row),
                "queued": True,
                "request_id": request_id,
            }

    async def sync_pending(self):
        yesterday = self.today() - timedelta(days=1)
        if await asyncio.to_thread(ParcelDailyCounterRepository.get, yesterday) is None:
            await asyncio.to_thread(ParcelDailyCounterRepository.ensure_date, yesterday)
        rows = await asyncio.to_thread(
            ParcelDailyCounterRepository.list_before, self.today(), True
        )
        for row in rows:
            try:
                await self.sync_date(date.fromisoformat(row["business_date"]))
            except Exception:
                logger.exception("日结上报失败：%s", row["business_date"])
                break

    async def _run(self):
        while True:
            await self.sync_pending()
            now = datetime.now(self._timezone)
            next_midnight = datetime.combine(now.date() + timedelta(days=1), time(), self._timezone)
            seconds_to_midnight = max((next_midnight - now).total_seconds(), 1) + 1
            await asyncio.sleep(min(seconds_to_midnight, 60))


daily_parcel_reports = DailyParcelReportService()
