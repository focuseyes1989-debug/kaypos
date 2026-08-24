import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from printer_agent import stable_agent_id
from server.printer_assets import resolve_asset, store_asset, validate_upload
from server.printer_service import PrinterRegistry


class PrinterServerPhase1Tests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "printer-registry.db"

        def connect():
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        self.connect = connect
        self.registry = PrinterRegistry(connect)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_agent_id_is_stable_per_computer(self):
        self.assertEqual(stable_agent_id("COUNTER-PC"), stable_agent_id("COUNTER-PC"))
        self.assertNotEqual(stable_agent_id("COUNTER-PC"), stable_agent_id("OFFICE-PC"))

    def test_heartbeat_registers_pc_and_printers(self):
        agent = self.registry.heartbeat(
            "agent-0001",
            "COUNTER-PC",
            "192.168.1.21",
            [
                {"name": "Receipt 80mm", "is_default": True},
                {"name": "Office A4", "is_default": False},
            ],
        )
        self.assertTrue(agent["is_online"])
        self.assertEqual(agent["computer_name"], "COUNTER-PC")
        self.assertEqual(len(agent["printers"]), 2)
        self.assertEqual(
            [item["printer_name"] for item in agent["printers"]],
            ["Receipt 80mm", "Office A4"],
        )

    def test_later_heartbeat_marks_removed_printer_unavailable(self):
        self.registry.heartbeat(
            "agent-0002", "OFFICE-PC", "192.168.1.22",
            [{"name": "Old Printer", "is_default": True}],
        )
        agent = self.registry.heartbeat(
            "agent-0002", "OFFICE-PC", "192.168.1.22",
            [{"name": "New Printer", "is_default": True}],
        )
        statuses = {item["printer_name"]: item["status"] for item in agent["printers"]}
        self.assertEqual(statuses, {"New Printer": "online", "Old Printer": "offline"})

    def test_printer_can_be_disabled_without_heartbeat_resetting_it(self):
        self.registry.heartbeat(
            "agent-printer-toggle", "PHOTO-PC", "192.168.1.25",
            [{"name": "Photo Printer", "is_default": True}],
        )
        agent = self.registry.set_printer_enabled("agent-printer-toggle", "Photo Printer", False)
        self.assertFalse(agent["printers"][0]["is_enabled"])

        # A normal Agent heartbeat updates availability but preserves the
        # administrator's per-printer permission.
        agent = self.registry.heartbeat(
            "agent-printer-toggle", "PHOTO-PC", "192.168.1.25",
            [{"name": "Photo Printer", "is_default": True}],
        )
        self.assertFalse(agent["printers"][0]["is_enabled"])
        with self.assertRaisesRegex(ValueError, "disabled"):
            self.registry.create_job(
                "disabled-printer-job-001", "agent-printer-toggle", "Photo Printer"
            )

        agent = self.registry.set_printer_enabled("agent-printer-toggle", "Photo Printer", True)
        self.assertTrue(agent["printers"][0]["is_enabled"])
        job = self.registry.create_job(
            "reenabled-printer-job-001", "agent-printer-toggle", "Photo Printer"
        )
        self.assertEqual(job["status"], "pending")

    def test_stale_agent_and_its_printers_are_offline(self):
        self.registry.heartbeat(
            "agent-0003", "STORE-PC", "192.168.1.23",
            [{"name": "Store Printer", "is_default": True}],
        )
        stale = (datetime.now() - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
        conn = self.connect()
        conn.execute("UPDATE printer_agents SET last_seen=? WHERE agent_id=?", (stale, "agent-0003"))
        conn.commit()
        conn.close()

        agent = self.registry.get_agent("agent-0003")
        self.assertFalse(agent["is_online"])
        self.assertEqual(agent["printers"][0]["status"], "offline")

    def _register_queue_printer(self):
        self.registry.heartbeat(
            "agent-queue-01", "QUEUE-PC", "192.168.1.30",
            [{"name": "Queue Printer", "is_default": True}],
        )

    def test_job_queue_is_idempotent_and_claim_is_atomic(self):
        self._register_queue_printer()
        first = self.registry.create_job(
            "request-key-queue-001", "agent-queue-01", "Queue Printer"
        )
        duplicate = self.registry.create_job(
            "request-key-queue-001", "agent-queue-01", "Queue Printer"
        )
        self.assertEqual(first["job_id"], duplicate["job_id"])
        self.assertEqual(len(self.registry.pending_jobs("agent-queue-01")), 1)

        claimed = self.registry.claim_job(
            first["job_id"], "agent-queue-01", ["Queue Printer"]
        )
        self.assertEqual(claimed["status"], "printing")
        self.assertEqual(claimed["attempts"], 1)
        with self.assertRaisesRegex(ValueError, "no longer available"):
            self.registry.claim_job(first["job_id"], "agent-queue-01", ["Queue Printer"])

    def test_failed_job_can_retry_and_complete(self):
        self._register_queue_printer()
        job = self.registry.create_job(
            "request-key-queue-002", "agent-queue-01", "Queue Printer"
        )
        self.registry.claim_job(job["job_id"], "agent-queue-01", ["Queue Printer"])
        failed = self.registry.finish_job(
            job["job_id"], "agent-queue-01", "failed", "Paper unavailable"
        )
        self.assertEqual(failed["status"], "failed")
        retried = self.registry.retry_job(job["job_id"])
        self.assertEqual(retried["status"], "pending")
        self.registry.claim_job(job["job_id"], "agent-queue-01", ["Queue Printer"])
        completed = self.registry.finish_job(
            job["job_id"], "agent-queue-01", "completed"
        )
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["attempts"], 2)
        self.assertEqual(
            [event["event"] for event in self.registry.job_audit(job["job_id"])],
            ["created", "claimed", "failed", "retried", "claimed", "completed"],
        )

    def test_stale_printing_job_times_out(self):
        self._register_queue_printer()
        job = self.registry.create_job(
            "request-key-queue-003", "agent-queue-01", "Queue Printer"
        )
        self.registry.claim_job(job["job_id"], "agent-queue-01", ["Queue Printer"])
        stale = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        conn = self.connect()
        conn.execute("UPDATE network_print_jobs SET claimed_at=? WHERE job_id=?", (stale, job["job_id"]))
        conn.commit()
        conn.close()
        self.assertEqual(self.registry.recover_stale_jobs(60), 1)
        recovered = next(item for item in self.registry.list_jobs() if item["job_id"] == job["job_id"])
        self.assertEqual(recovered["status"], "failed")
        self.assertEqual(recovered["error_message"], "Print Agent timed out")

    def test_phase3_asset_validation_and_safe_storage(self):
        with patch("server.printer_assets.asset_root", return_value=Path(self.temp_dir.name)):
            asset_id, stored_path, job_type = store_asset("sample.pdf", b"%PDF-1.4\n%%EOF")
            self.assertTrue(asset_id)
            self.assertEqual(job_type, "pdf")
            self.assertEqual(resolve_asset(stored_path).read_bytes(), b"%PDF-1.4\n%%EOF")
        with self.assertRaisesRegex(ValueError, "Supported files"):
            validate_upload("malware.exe", b"MZ")
        with self.assertRaisesRegex(ValueError, "valid PDF"):
            validate_upload("fake.pdf", b"not-a-pdf")

    def test_phase3_document_formats_enter_the_same_queue(self):
        self._register_queue_printer()
        for index, job_type in enumerate(("pdf", "image", "text_receipt", "escpos_raw"), start=1):
            job = self.registry.create_job(
                f"phase3-format-request-{index}",
                "agent-queue-01",
                "Queue Printer",
                job_type=job_type,
                payload={"asset_path": f"document-{index}", "paper_size": "A4"},
                copies=2,
            )
            self.assertEqual(job["job_type"], job_type)
            self.assertEqual(job["copies"], 2)
        self.assertEqual(len(self.registry.pending_jobs("agent-queue-01", 10)), 4)


if __name__ == "__main__":
    unittest.main()
