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
