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
