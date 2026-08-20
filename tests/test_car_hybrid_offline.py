import tempfile
import unittest
from pathlib import Path

from car_client.offline_store import OfflineCarStore


RECORD = {
    "car_number": "1A/1234",
    "driver_name": "Mg Mg",
    "kind_of_car": "Car",
    "type_of_car": "Toyota",
    "age": "30",
    "nrc_place": "12/ABC",
    "nrc_number": "123456",
    "phone_number": "091234567",
    "address": "Yangon",
    "engine_number": "ENG-1",
    "frame_number": "FRAME-1",
}


class OfflineCarStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = OfflineCarStore(Path(self.temp_dir.name) / "offline.db")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_offline_save_is_cached_and_queued(self):
        record_id = self.store.queue_save(RECORD)
        self.assertLess(record_id, 0)
        self.assertEqual(self.store.all()[0]["car_number"], "1A/1234")
        self.assertEqual(self.store.pending_count(), 1)
        self.assertEqual(self.store.pending()[0]["operation"], "SAVE_DATA")

    def test_update_and_delete_change_cache_and_queue(self):
        record = {**RECORD, "id": 10, "timestamp": "2026-08-20 10:00:00"}
        self.store.replace_cache([record])
        self.store.queue_update({**record, "driver_name": "Ma Ma"})
        self.assertEqual(self.store.all()[0]["driver_name"], "Ma Ma")
        self.store.queue_delete(10)
        self.assertEqual(self.store.all(), [])
        self.assertEqual([item["operation"] for item in self.store.pending()], ["UPDATE_DATA", "DELETE_DATA"])

    def test_completed_queue_item_is_removed(self):
        self.store.queue_save(RECORD)
        item = self.store.pending()[0]
        self.store.complete(item["queue_id"])
        self.assertEqual(self.store.pending_count(), 0)


if __name__ == "__main__":
    unittest.main()
