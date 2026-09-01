import sqlite3
import tempfile
import unittest
from pathlib import Path

from server.service_order_service import ServiceOrderRepository


class ServiceJobBoardTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "jobs.db"
        self.repo = ServiceOrderRepository(lambda: sqlite3.connect(self.db_path))

    def tearDown(self):
        self.tempdir.cleanup()

    def test_simple_job_can_be_completed_directly_and_records_actor(self):
        job = self.repo.create({
            "received_at": "2026-09-02 10:30",
            "job_title": "Printer service",
            "complaint": "Paper jam",
            "expected_at": "2026-09-02 15:00",
            "internal_notes": "Call when ready",
        }, created_by="server-user")

        completed = self.repo.change_status(
            job["id"], "completed", changed_by="client-pc-2", note="Done",
        )

        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["completed_by"], "client-pc-2")
        self.assertTrue(completed["completed_at"])
        self.assertEqual(completed["status_history"][-1]["changed_by"], "client-pc-2")

    def test_completed_job_cannot_be_completed_by_second_client(self):
        job = self.repo.create({"job_title": "Test job"}, created_by="server-user")
        self.repo.change_status(job["id"], "completed", changed_by="client-pc-1")
        with self.assertRaises(ValueError):
            self.repo.change_status(job["id"], "completed", changed_by="client-pc-3")


if __name__ == "__main__":
    unittest.main()
