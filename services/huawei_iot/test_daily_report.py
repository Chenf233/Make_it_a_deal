import asyncio
import unittest
from datetime import date
from unittest.mock import AsyncMock, patch

from services.huawei_iot.daily_report import DailyParcelReportService


class DailyParcelReportServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_force_sync_refreshes_snapshot_and_reports_station_1(self):
        service = DailyParcelReportService()
        service.today = lambda: date(2026, 7, 24)
        snapshot = {
            "business_date": "2026-07-23",
            "target_a_count": 4,
            "target_b_count": 7,
            "report_status": "pending",
        }
        published = {**snapshot, "report_status": "published"}

        with (
            patch(
                "services.huawei_iot.daily_report.ParcelDailyCounterRepository.get",
                side_effect=[published, published],
            ),
            patch(
                "services.huawei_iot.daily_report.ParcelDailyCounterRepository.refresh_snapshot",
                return_value=snapshot,
            ) as refresh,
            patch(
                "services.huawei_iot.daily_report.ParcelDailyCounterRepository.mark_publishing"
            ),
            patch(
                "services.huawei_iot.daily_report.ParcelDailyCounterRepository.mark_published"
            ),
            patch(
                "services.huawei_iot.daily_report.huawei_iot.report_properties",
                new=AsyncMock(return_value="daily-2026-07-23"),
            ) as report,
            patch(
                "services.huawei_iot.daily_report.huawei_iot.wait_for_publish",
                new=AsyncMock(return_value={"event": "published"}),
            ),
        ):
            result = await service.sync_date(date(2026, 7, 23), force=True)

        refresh.assert_called_once_with(date(2026, 7, 23))
        self.assertIsNotNone(report.await_args)
        args, kwargs = report.await_args  # type: ignore[misc]
        self.assertEqual(args, (
            "Station_1",
            {"A_parcels_per_D": 4, "B_parcels_per_D": 7},
        ))
        self.assertRegex(kwargs["request_id"], r"^daily-2026-07-23-[0-9a-f]{32}$")
        self.assertTrue(result["queued"])

    async def test_non_force_published_date_does_not_republish(self):
        service = DailyParcelReportService()
        service.today = lambda: date(2026, 7, 24)
        row = {"business_date": "2026-07-23", "report_status": "published"}
        with (
            patch(
                "services.huawei_iot.daily_report.ParcelDailyCounterRepository.get",
                return_value=row,
            ),
            patch(
                "services.huawei_iot.daily_report.huawei_iot.report_properties",
                new=AsyncMock(),
            ) as report,
        ):
            result = await service.sync_date(date(2026, 7, 23))

        report.assert_not_awaited()
        self.assertEqual(result["reason"], "already_published")


if __name__ == "__main__":
    unittest.main()
