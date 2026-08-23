import sqlite3
import json
import socket
import tempfile
import unittest
from pathlib import Path

from server.car_management_service import CarManagementTCPService, CarRepository, CarRequestHandler


class CarManagementServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "cars.db"

        def connect():
            return sqlite3.connect(self.db_path)

        self.repository = CarRepository(connect)
        self.repository.ensure_schema()
        self.handler = CarRequestHandler(self.repository)

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def record(**overrides):
        data = {
            "car_number": "1A-1234",
            "driver_name": "Test Driver",
            "kind_of_car": "Sedan",
            "type_of_car": "Toyota",
            "age": "(30)",
            "nrc_place": "12/ABC",
            "nrc_number": "123456",
            "phone_number": "09123456789",
            "address": "Yangon",
            "engine_number": "ENG-1",
            "frame_number": "FRAME-1",
        }
        data.update(overrides)
        return data

    def test_crud_protocol(self):
        self.assertEqual(self.handler.process({"type": "SAVE_DATA", "data": self.record()})["status"], "SUCCESS")
        rows = self.handler.process({"type": "GET_DATA", "data": None})["data"]
        self.assertEqual(len(rows), 1)
        record_id = rows[0]["id"]

        updated = self.record(id=record_id, driver_name="Updated Driver")
        self.assertEqual(self.handler.process({"type": "UPDATE_DATA", "data": updated})["status"], "SUCCESS")
        matches = self.handler.process({"type": "SEARCH_DATA", "data": "updated"})["data"]
        self.assertEqual(matches[0]["driver_name"], "Updated Driver")

        self.assertEqual(self.handler.process({"type": "DELETE_DATA", "data": {"id": record_id}})["status"], "SUCCESS")
        self.assertEqual(self.handler.process({"type": "GET_DATA", "data": None})["data"], [])

    def test_required_fields_are_validated(self):
        result = self.handler.process({"type": "SAVE_DATA", "data": {"car_number": "1A"}})
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("Driver Name", result["message"])

    def test_secure_qr_issue_resolve_rotate_and_revoke(self):
        self.handler.process({"type": "SAVE_DATA", "data": self.record()})
        record_id = self.repository.all()[0]["id"]
        first = self.handler.process({"type": "ISSUE_QR", "data": {"id": record_id}})
        self.assertEqual(first["status"], "SUCCESS")
        token = first["data"]["token"]
        self.assertGreaterEqual(len(token), 32)
        self.assertNotIn("nrc_number", first["data"]["record"])
        again = self.handler.process({"type": "ISSUE_QR", "data": {"id": record_id}})
        self.assertEqual(again["data"]["token"], token)

        resolved = self.handler.process({"type": "RESOLVE_QR", "data": {"token": token}})
        self.assertEqual(resolved["data"]["car_number"], "1A-1234")
        self.assertNotIn("phone_number", resolved["data"])

        rotated = self.handler.process({"type": "ISSUE_QR", "data": {"id": record_id, "rotate": True}})
        self.assertNotEqual(rotated["data"]["token"], token)
        self.assertEqual(self.handler.process({"type": "RESOLVE_QR", "data": {"token": token}})["status"], "ERROR")

        self.assertEqual(self.handler.process({"type": "REVOKE_QR", "data": {"id": record_id}})["status"], "SUCCESS")
        current = rotated["data"]["token"]
        self.assertEqual(self.handler.process({"type": "RESOLVE_QR", "data": {"token": current}})["status"], "ERROR")

    def test_print_job_queue_is_persistent_idempotent_and_tracks_status(self):
        self.handler.process({"type": "SAVE_DATA", "data": self.record()})
        record_id = self.repository.all()[0]["id"]
        token = self.repository.issue_qr_token(record_id)["token"]
        self.repository.register_print_printers("TEST-PC", ["Test Printer"], "Test Printer")
        first = self.repository.create_print_job(token, "request-key-123456789", 2, "Test Printer")
        duplicate = self.repository.create_print_job(token, "request-key-123456789", 2, "Test Printer")
        self.assertEqual(first["job_id"], duplicate["job_id"])
        self.assertEqual(first["status"], "pending")
        self.assertEqual(first["copies"], 2)
        self.assertEqual(first["printer_name"], "Test Printer")
        self.assertEqual(first["page_sequence"], [1, 2, 3, 4, 2, 3, 2, 3, 4])
        self.assertEqual(len(self.repository.pending_print_jobs(printer_names=["Test Printer"])), 1)

        printing = self.repository.claim_print_job(first["job_id"], ["Test Printer"])
        self.assertEqual(printing["status"], "printing")
        self.assertEqual(printing["record"]["nrc_number"], "123456")
        with self.assertRaises(ValueError):
            self.repository.claim_print_job(first["job_id"], ["Test Printer"])
        completed = self.repository.update_print_job_status(first["job_id"], "completed")
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(self.repository.pending_print_jobs(printer_names=["Test Printer"]), [])
        with self.assertRaises(ValueError):
            self.repository.update_print_job_status(first["job_id"], "pending")
        reprint = self.repository.create_print_job(token, "second-request-key-12345", 1, "Test Printer")
        self.assertNotEqual(reprint["job_id"], first["job_id"])
        events = [row["event"] for row in self.repository.print_audit()]
        self.assertIn("job_created", events)
        self.assertIn("job_claimed", events)
        self.assertIn("status_completed", events)
        self.assertGreaterEqual(events.count("job_created"), 2)

    def test_print_job_rejects_disabled_qr(self):
        self.handler.process({"type": "SAVE_DATA", "data": self.record()})
        record_id = self.repository.all()[0]["id"]
        token = self.repository.issue_qr_token(record_id)["token"]
        self.repository.revoke_qr_token(record_id)
        with self.assertRaises(ValueError):
            self.repository.create_print_job(token, "request-key-123456789", 1)

    def test_stale_printing_job_is_recovered_and_audited(self):
        self.handler.process({"type": "SAVE_DATA", "data": self.record()})
        record_id = self.repository.all()[0]["id"]
        token = self.repository.issue_qr_token(record_id)["token"]
        self.repository.register_print_printers("TEST-PC", ["Test Printer"], "Test Printer")
        job = self.repository.create_print_job(token, "stale-request-key-123", 1, "Test Printer")
        self.repository.claim_print_job(job["job_id"], ["Test Printer"])
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("UPDATE car_print_jobs SET updated_at='2020-01-01 00:00:00' WHERE public_id=?", (job["job_id"],))
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(self.repository.recover_stale_print_jobs(10), 1)
        recovered = self.repository.get_print_job(job["job_id"])
        self.assertEqual(recovered["status"], "failed")
        self.assertIn("stopped", recovered["error_message"])

    def test_tcp_service_uses_existing_client_protocol(self):
        service = CarManagementTCPService("127.0.0.1", 0, self.handler)
        service.start()
        try:
            port = service._socket.getsockname()[1]
            with socket.create_connection(("127.0.0.1", port), timeout=3) as client:
                client.sendall(json.dumps({"type": "GET_DATA", "data": None}).encode("utf-8"))
                response = b""
                while b"\n" not in response:
                    response += client.recv(4096)
            payload = json.loads(response.split(b"\n", 1)[0].decode("utf-8"))
            self.assertEqual(payload, {"status": "SUCCESS", "data": []})
        finally:
            service.stop()


if __name__ == "__main__":
    unittest.main()
