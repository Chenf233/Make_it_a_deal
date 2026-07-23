import tempfile
import unittest
import sys
import types
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo


if "numpy" not in sys.modules:
    class _FakeArray:
        def astype(self, _dtype):
            return self

    numpy_stub = types.ModuleType("numpy")
    numpy_stub.ndarray = _FakeArray
    numpy_stub.float32 = "float32"
    numpy_stub.random = types.SimpleNamespace(rand=lambda *_args: _FakeArray())
    sys.modules["numpy"] = numpy_stub

from database.db_manager import DatabaseManager
from database.models import ParcelDailyCounterRepository, ParcelRepository


class ParcelDailyCounterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.db")
        self.db_patch = patch("database.db_manager.DB_PATH", self.db_path)
        self.db_patch.start()
        DatabaseManager.init_db()

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_target_location_is_required(self):
        with self.assertRaises(ValueError):
            ParcelRepository.add_parcel("missing-target", receiver_phone="13800000000")

    def test_snapshot_recomputes_after_backend_edits(self):
        parcel = ParcelRepository.add_parcel(
            "target-a", receiver_phone="13800000000", target_location="A"
        )
        now = datetime(2026, 7, 23, 23, 59, tzinfo=ZoneInfo("Asia/Shanghai"))

        result = ParcelRepository.complete_pickup(parcel["parcel_id"], now)
        duplicate = ParcelRepository.complete_pickup(parcel["parcel_id"], now)
        first = ParcelDailyCounterRepository.refresh_snapshot(date(2026, 7, 23))

        self.assertEqual(result["target_location"], "A")
        self.assertIsNone(duplicate)
        self.assertEqual((first["target_a_count"], first["target_b_count"]), (1, 0))

        ParcelRepository.update_parcel(parcel["parcel_id"], target_location="B")
        second = ParcelDailyCounterRepository.refresh_snapshot(date(2026, 7, 23))
        self.assertEqual((second["target_a_count"], second["target_b_count"]), (0, 1))

        ParcelRepository.update_parcel(parcel["parcel_id"], status=1)
        third = ParcelDailyCounterRepository.refresh_snapshot(date(2026, 7, 23))
        self.assertEqual((third["target_a_count"], third["target_b_count"]), (0, 0))

    def test_backend_can_update_in_time_and_changes_list_order(self):
        first = ParcelRepository.add_parcel(
            "in-time-first", cabinet_number="A01",
            receiver_phone="13800000000", target_location="A"
        )
        second = ParcelRepository.add_parcel(
            "in-time-second", cabinet_number="A02",
            receiver_phone="13800000001", target_location="B"
        )

        self.assertTrue(ParcelRepository.update_parcel(
            first["parcel_id"], in_time="2026-07-23 12:00:00"
        ))
        self.assertTrue(ParcelRepository.update_parcel(
            second["parcel_id"], in_time="2026-07-22 12:00:00"
        ))

        updated = ParcelRepository.get_parcel_by_id(first["parcel_id"])
        ordered = ParcelRepository.get_all_parcels()
        self.assertEqual(updated["in_time"], "2026-07-23 12:00:00")
        self.assertEqual(
            [parcel["parcel_id"] for parcel in ordered[:2]],
            [first["parcel_id"], second["parcel_id"]],
        )

    def test_update_in_time_rejects_invalid_format(self):
        parcel = ParcelRepository.add_parcel(
            "invalid-in-time", cabinet_number="A03",
            receiver_phone="13800000002", target_location="A"
        )

        with self.assertRaisesRegex(ValueError, "入库时间格式"):
            ParcelRepository.update_parcel(
                parcel["parcel_id"], in_time="2026-7-23 12:00"
            )

    def test_picked_up_parcel_rejects_in_time_after_out_time(self):
        parcel = ParcelRepository.add_parcel(
            "picked-in-time", cabinet_number="A04",
            receiver_phone="13800000003", target_location="B", status=2
        )
        original = ParcelRepository.get_parcel_by_id(parcel["parcel_id"])
        out_time = datetime.strptime(original["out_time"], "%Y-%m-%d %H:%M:%S")
        invalid_in_time = out_time.replace(year=out_time.year + 1).strftime("%Y-%m-%d %H:%M:%S")

        with self.assertRaisesRegex(ValueError, "入库时间不能晚于出库时间"):
            ParcelRepository.update_parcel(
                parcel["parcel_id"], in_time=invalid_in_time
            )

        unchanged = ParcelRepository.get_parcel_by_id(parcel["parcel_id"])
        self.assertEqual(unchanged["in_time"], original["in_time"])

    def test_status_and_future_in_time_cannot_create_invalid_pickup(self):
        parcel = ParcelRepository.add_parcel(
            "future-pickup", cabinet_number="A05",
            receiver_phone="13800000004", target_location="A"
        )

        with self.assertRaisesRegex(ValueError, "入库时间不能晚于出库时间"):
            ParcelRepository.update_parcel(
                parcel["parcel_id"],
                status=2,
                in_time="2999-01-01 00:00:00",
            )

        unchanged = ParcelRepository.get_parcel_by_id(parcel["parcel_id"])
        self.assertEqual(unchanged["status"], 1)
        self.assertIsNone(unchanged["out_time"])

    def test_backend_out_time_edit_moves_parcel_to_selected_business_date(self):
        parcel = ParcelRepository.add_parcel(
            "edited-out-time", cabinet_number="B01",
            receiver_phone="13800000005", target_location="B", status=2
        )

        self.assertTrue(ParcelRepository.update_parcel(
            parcel["parcel_id"],
            in_time="2026-07-21 09:00:00",
            out_time="2026-07-22 10:30:00",
        ))

        selected = ParcelDailyCounterRepository.refresh_snapshot(date(2026, 7, 22))
        following = ParcelDailyCounterRepository.refresh_snapshot(date(2026, 7, 23))
        updated = ParcelRepository.get_parcel_by_id(parcel["parcel_id"])
        self.assertEqual(updated["out_time"], "2026-07-22 10:30:00")
        self.assertEqual((selected["target_a_count"], selected["target_b_count"]), (0, 1))
        self.assertEqual((following["target_a_count"], following["target_b_count"]), (0, 0))

    def test_out_time_before_in_time_is_rejected(self):
        parcel = ParcelRepository.add_parcel(
            "invalid-out-time", cabinet_number="B02",
            receiver_phone="13800000006", target_location="A", status=2
        )

        with self.assertRaisesRegex(ValueError, "入库时间不能晚于出库时间"):
            ParcelRepository.update_parcel(
                parcel["parcel_id"],
                in_time="2026-07-22 11:00:00",
                out_time="2026-07-22 10:00:00",
            )

    def test_non_picked_up_parcel_cannot_have_out_time(self):
        parcel = ParcelRepository.add_parcel(
            "invalid-status-out-time", cabinet_number="B03",
            receiver_phone="13800000007", target_location="B"
        )

        with self.assertRaisesRegex(ValueError, "只有已取件包裹可以设置出库时间"):
            ParcelRepository.update_parcel(
                parcel["parcel_id"], out_time="2026-07-22 10:00:00"
            )

    def test_existing_schema_drops_legacy_parcels(self):
        with DatabaseManager.get_connection() as conn:
            conn.execute("DROP TABLE parcels")
            conn.execute('''
                CREATE TABLE parcels (
                    parcel_id INTEGER PRIMARY KEY,
                    tracking_no TEXT,
                    cabinet_number TEXT,
                    receiver_phone TEXT,
                    status INTEGER
                )
            ''')
            conn.execute(
                "INSERT INTO parcels VALUES (1, 'legacy', 'A01', '13800000000', 1)"
            )
            conn.commit()

        DatabaseManager.init_db()

        with DatabaseManager.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM parcels").fetchone()[0]
            columns = {row[1] for row in conn.execute("PRAGMA table_info(parcels)")}
        self.assertEqual(count, 0)
        self.assertIn("target_location", columns)


if __name__ == "__main__":
    unittest.main()
