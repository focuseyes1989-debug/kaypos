import json
import socketserver
import tempfile
import threading
import unittest
from pathlib import Path

from PyQt6.QtCore import QSettings

from car_client.config import ServerSettings, SettingsStore
from car_client.form_templates import compose_form_fields, template_path
from car_client.form_print_dialog import parse_page_sequence
from car_client.network import CarServerClient
from car_client.records import find_duplicate_records, validated_record


class _Handler(socketserver.StreamRequestHandler):
    requests = []

    def handle(self):
        request = json.loads(self.rfile.readline().decode("utf-8"))
        self.requests.append(request)
        self.wfile.write(b'{"status":"SUCCESS","data":[]}\n')


class _DropFirstHandler(socketserver.StreamRequestHandler):
    attempts = 0

    def handle(self):
        self.rfile.readline();type(self).attempts += 1
        if type(self).attempts == 1:
            return
        self.wfile.write(b'{"status":"SUCCESS","data":[]}\n')


class CarClientPhase1Tests(unittest.TestCase):
    def test_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = QSettings(str(Path(folder) / "client.ini"), QSettings.Format.IniFormat)
            store = SettingsStore(settings)
            expected = ServerSettings("10.0.0.25", 12345, 8)
            store.save(expected)
            self.assertEqual(store.load(), expected)

    def test_connection_uses_car_server_protocol(self):
        server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            CarServerClient(ServerSettings("127.0.0.1", server.server_address[1], 2)).test_connection()
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_record_validation_and_save_protocol(self):
        record = validated_record({
            "car_number": " 1A/1234 ", "driver_name": " Mg Mg ",
            "nrc_number": " 123456 ", "phone_number": " 09123456789 ",
        })
        self.assertEqual(record["car_number"], "1A/1234")
        self.assertEqual(record["driver_name"], "Mg Mg")
        with self.assertRaises(ValueError):
            validated_record({"car_number": "", "driver_name": "Mg Mg", "nrc_number": "123"})
        _Handler.requests.clear()
        server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            CarServerClient(ServerSettings("127.0.0.1", server.server_address[1], 2)).save_car(record)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)
        self.assertEqual(_Handler.requests[-1]["type"], "SAVE_DATA")
        self.assertEqual(_Handler.requests[-1]["data"], record)

    def test_get_and_search_record_protocol(self):
        _Handler.requests.clear()
        server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        client = CarServerClient(ServerSettings("127.0.0.1", server.server_address[1], 2))
        try:
            self.assertEqual(client.get_cars(), [])
            self.assertEqual(client.search_cars("Toyota"), [])
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)
        self.assertEqual([item["type"] for item in _Handler.requests], ["GET_DATA", "SEARCH_DATA"])
        self.assertEqual(_Handler.requests[-1]["data"], "Toyota")

    def test_update_delete_and_duplicate_detection(self):
        candidate={"id":2,"car_number":"1A/1234","nrc_number":"NRC-100","engine_number":"ENG-2","frame_number":""}
        rows=[{"id":1,"car_number":"1a/1234","nrc_number":"nrc-100","engine_number":"ENG-2"},{"id":2,"car_number":"OLD","nrc_number":"NRC-100","engine_number":"ENG-2"}]
        self.assertEqual([item["id"] for item in find_duplicate_records(rows,candidate,exclude_id=2)],[1])
        _Handler.requests.clear();server=socketserver.ThreadingTCPServer(("127.0.0.1",0),_Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        client=CarServerClient(ServerSettings("127.0.0.1",server.server_address[1],2))
        try:
            client.update_car(candidate);client.delete_car(2)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)
        self.assertEqual([item["type"] for item in _Handler.requests],["UPDATE_DATA","DELETE_DATA"])
        self.assertEqual(_Handler.requests[-1]["data"],{"id":2})

    def test_same_car_with_different_driver_is_not_duplicate(self):
        existing=[{"id":1,"car_number":"1A/1234","nrc_number":"NRC-OLD","engine_number":"SAME-ENGINE","frame_number":"SAME-FRAME"}]
        new_driver={"car_number":"1a/1234","nrc_number":"NRC-NEW","engine_number":"SAME-ENGINE","frame_number":"SAME-FRAME"}
        self.assertEqual(find_duplicate_records(existing,new_driver),[])

    def test_safe_read_request_retries_one_dropped_connection(self):
        _DropFirstHandler.attempts=0;server=socketserver.ThreadingTCPServer(("127.0.0.1",0),_DropFirstHandler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            CarServerClient(ServerSettings("127.0.0.1",server.server_address[1],2)).test_connection()
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)
        self.assertEqual(_DropFirstHandler.attempts,2)

    def test_unicode_driver_input_is_preserved(self):
        record=validated_record({"car_number":"1A/1234","driver_name":"မောင်မောင်","nrc_number":"၁၂၃၄၅၆"})
        self.assertEqual(record["driver_name"],"မောင်မောင်")
        self.assertEqual(record["nrc_number"],"၁၂၃၄၅၆")

    def test_form_fields_are_composed_from_selected_record(self):
        fields = compose_form_fields({
            "kind_of_car": "Saloon", "type_of_car": "Toyota Probox",
            "car_number": "1A/1234", "driver_name": "မောင်မောင်",
            "age": "35", "nrc_place": "12/LaMaNa(N)",
            "nrc_number": "123456", "phone_number": "09123456789",
        })
        self.assertEqual(fields["kind_and_type_of_car"], "Saloon Toyota Probox")
        self.assertEqual(fields["driver_name_and_age"], "မောင်မောင် (35)")
        self.assertEqual(fields["nrc_and_number"], "12/LaMaNa(N) 123456")
        self.assertEqual(fields["phone_number"], "09123456789")

    def test_all_four_form_templates_are_available(self):
        for page_number in range(1, 5):
            self.assertTrue(template_path(page_number).is_file())

    def test_manual_form_print_sequence(self):
        self.assertEqual(parse_page_sequence("1,1,2,3,4,2,3,2,3,4"), [1,1,2,3,4,2,3,2,3,4])
        self.assertEqual(parse_page_sequence("1 2;3,4"), [1,2,3,4])
        with self.assertRaises(ValueError):
            parse_page_sequence("1,5")


if __name__ == "__main__":
    unittest.main()
