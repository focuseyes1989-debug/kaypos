import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
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

    def test_start_records_worker_and_preserves_start_after_completion(self):
        job = self.repo.create({"job_title": "Test"}, created_by="server")
        started = self.repo.change_status(job["id"], "in_progress", changed_by="tech1")
        self.assertEqual(started["started_by"], "tech1")
        self.assertTrue(started["started_at"])
        self.assertEqual(self.repo.list()[0]["started_by"], "tech1")
        with self.assertRaises(ValueError):
            self.repo.change_status(job["id"], "in_progress", changed_by="tech2")
        completed = self.repo.change_status(job["id"], "completed", changed_by="tech1")
        self.assertEqual(completed["started_at"], started["started_at"])
        self.assertEqual(completed["started_by"], "tech1")
        self.assertEqual(completed["completed_by"], "tech1")

    def test_simultaneous_start_has_one_winner(self):
        job = self.repo.create({"job_title": "Shared"}, created_by="server")
        def claim(actor):
            try:
                self.repo.change_status(job["id"], "in_progress", changed_by=actor)
                return actor
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, ["tech1", "tech2"]))
        winners = [actor for actor in results if actor]
        self.assertEqual(len(winners), 1)
        stored = self.repo.get(job["id"])
        self.assertEqual(stored["started_by"], winners[0])
        self.assertEqual(len(stored["status_history"]), 2)

    def test_work_completion_and_collection_have_separate_audits(self):
        job = self.repo.create({"job_title": "Print", "internal_notes": "Deposit 5000"}, created_by="server")
        with self.assertRaises(ValueError):
            self.repo.change_status(job["id"], "delivered", changed_by="cashier")
        self.repo.change_status(job["id"], "in_progress", changed_by="tech")
        finished = self.repo.change_status(job["id"], "ready_for_pickup", changed_by="tech")
        self.assertEqual(finished["completed_by"], "tech")
        self.assertTrue(finished["completed_at"])
        self.assertIsNone(finished["delivered_at"])
        with self.assertRaises(ValueError):
            self.repo.change_status(job["id"], "ready_for_pickup", changed_by="other-tech")
        collected = self.repo.change_status(job["id"], "delivered", changed_by="cashier")
        self.assertEqual(collected["completed_by"], "tech")
        self.assertEqual(collected["completed_at"], finished["completed_at"])
        self.assertEqual(collected["delivered_by"], "cashier")
        self.assertTrue(collected["delivered_at"])
        self.assertEqual(collected["internal_notes"], "Deposit 5000")
        self.assertEqual(collected["status_history"][-1]["changed_by"], "cashier")
        with self.assertRaises(ValueError):
            self.repo.change_status(job["id"], "ready_for_pickup", changed_by="tech")

    def test_legacy_in_progress_without_worker_can_finish_before_collection(self):
        job = self.repo.create({"job_title": "Legacy active job", "internal_notes": "Deposit 5000"}, created_by="server")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE service_orders SET status = 'in_progress', started_by = NULL, started_at = NULL WHERE id = ?", (job["id"],))
        conn.close()
        finished = self.repo.change_status(job["id"], "ready_for_pickup", changed_by="tech")
        self.assertEqual(finished["status"], "ready_for_pickup")
        self.assertEqual(finished["completed_by"], "tech")
        self.assertTrue(finished["completed_at"])
        self.assertIsNone(finished["started_by"])
        self.assertIsNone(finished["delivered_at"])
        self.assertEqual(finished["internal_notes"], "Deposit 5000")

    def test_simultaneous_collection_has_one_winner(self):
        job = self.repo.create({"job_title": "Shared"}, created_by="server")
        self.repo.change_status(job["id"], "ready_for_pickup", changed_by="tech")
        def collect(actor):
            try:
                self.repo.change_status(job["id"], "delivered", changed_by=actor)
                return actor
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            winners = [actor for actor in pool.map(collect, ["cashier1", "cashier2"]) if actor]
        self.assertEqual(len(winners), 1)
        stored = self.repo.get(job["id"])
        self.assertEqual(stored["delivered_by"], winners[0])
        self.assertEqual(stored["completed_by"], "tech")

    def test_legacy_completion_does_not_replace_work_completion_audit(self):
        job = self.repo.create({"job_title": "Legacy"}, created_by="server")
        finished = self.repo.change_status(job["id"], "ready_for_pickup", changed_by="tech")
        self.repo.change_status(job["id"], "completed", changed_by="cashier")
        collected = self.repo.change_status(job["id"], "delivered", changed_by="collector")
        self.assertEqual(collected["completed_by"], "tech")
        self.assertEqual(collected["completed_at"], finished["completed_at"])
        self.assertEqual(collected["delivered_by"], "collector")


if __name__ == "__main__":
    unittest.main()
