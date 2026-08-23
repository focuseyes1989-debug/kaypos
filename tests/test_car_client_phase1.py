import json
import socketserver
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path

from PyQt6.QtCore import QSettings

from car_client.config import ServerSettings, SettingsStore
from car_client.form_templates import compose_form_fields, template_path
from car_client.form_print_dialog import parse_page_sequence
from car_client.window import calculate_dashboard_alerts, calculate_dashboard_insights, calculate_dashboard_summary, filter_dashboard_records, recent_dashboard_records
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
            expected = ServerSettings("10.0.0.25", 12345, 8, "", "", True, "https://10.0.0.25:8000")
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

    def test_dashboard_phase2_summary(self):
        rows = [
            {"car_number":"1A/1","driver_name":"A","nrc_number":"NRC-1","timestamp":"2026-08-19 09:00:00","kind_of_car":"Car","type_of_car":"Toyota","age":"30","phone_number":"09","address":"A","engine_number":"E1","frame_number":"F1"},
            {"car_number":"1a/1","driver_name":"B","nrc_number":"NRC-2","timestamp":"2026-08-19T10:00:00","kind_of_car":"Car","type_of_car":"Toyota","age":"31","phone_number":"09","address":"A","engine_number":"E1","frame_number":"F1"},
            {"car_number":"2B/2","driver_name":"A","nrc_number":"nrc-1","timestamp":"2026-08-18 10:00:00","kind_of_car":"","type_of_car":"Honda","age":"30","phone_number":"09","address":"A","engine_number":"E2","frame_number":"F2"},
        ]
        summary = calculate_dashboard_summary(rows, date(2026, 8, 19))
        self.assertEqual(summary, {"total_records":3,"unique_cars":2,"total_drivers":2,"multiple_driver_cars":1,"added_today":2,"missing_information":1})

    def test_dashboard_phase3_recent_activity(self):
        rows = [
            {"id":1,"timestamp":"2026-08-18 10:00:00"},
            {"id":3,"timestamp":"2026-08-19T12:00:00"},
            {"id":2,"timestamp":"2026-08-19 09:00:00"},
        ]
        self.assertEqual([row["id"] for row in recent_dashboard_records(rows, 2)], [3, 2])

    def test_dashboard_phase4_quality_alerts_allow_multiple_drivers(self):
        rows = [
            {"id":1,"car_number":"1A","nrc_number":"N1","kind_of_car":"Car","type_of_car":"Toyota","engine_number":"E1","frame_number":"F1","age":"30","phone_number":"09","address":"A"},
            {"id":2,"car_number":"1a","nrc_number":"N2","kind_of_car":"Car","type_of_car":"Toyota","engine_number":"E1","frame_number":"F1","age":"","phone_number":"","address":"A"},
            {"id":3,"car_number":"2B","nrc_number":"N3","kind_of_car":"Van","type_of_car":"Honda","engine_number":"E2","frame_number":"F2","age":"40","phone_number":"09","address":"B"},
            {"id":4,"car_number":"2b","nrc_number":"n3","kind_of_car":"Van","type_of_car":"Honda","engine_number":"DIFFERENT","frame_number":"F2","age":"40","phone_number":"09","address":"B"},
        ]
        alerts=calculate_dashboard_alerts(rows)
        self.assertEqual([row["id"] for row in alerts["missing_age"]],[2])
        self.assertEqual([row["id"] for row in alerts["missing_phone"]],[2])
        self.assertEqual([row["id"] for row in alerts["possible_duplicates"]],[3,4])
        self.assertEqual([row["id"] for row in alerts["vehicle_conflicts"]],[3,4])
        self.assertNotIn(1,[row["id"] for row in alerts["possible_duplicates"]])

    def test_dashboard_phase5_date_filter_and_insights(self):
        rows=[
            {"car_number":"1A","nrc_number":"N1","timestamp":"2026-08-19 09:00:00","kind_of_car":"Car","type_of_car":"Toyota","age":"30","phone_number":"09","address":"A","engine_number":"E","frame_number":"F"},
            {"car_number":"1A","nrc_number":"N2","timestamp":"2026-08-18 09:00:00","kind_of_car":"Car","type_of_car":"Toyota","age":"31","phone_number":"09","address":"A","engine_number":"E","frame_number":"F"},
            {"car_number":"2B","nrc_number":"N3","timestamp":"2026-07-01 09:00:00","kind_of_car":"Van","type_of_car":"Honda","age":"","phone_number":"09","address":"B","engine_number":"E2","frame_number":"F2"},
        ]
        today_rows=filter_dashboard_records(rows,"today",date(2026,8,19));self.assertEqual(len(today_rows),1)
        custom_rows=filter_dashboard_records(rows,"custom",date(2026,8,19),date(2026,7,1),date(2026,7,31));self.assertEqual(len(custom_rows),1)
        insights=calculate_dashboard_insights(rows);self.assertEqual(insights["types"],[('Toyota',1),('Honda',1)]);self.assertEqual(insights["reused"][0],('1A',2));self.assertEqual((insights["complete"],insights["incomplete"]),(2,1))


if __name__ == "__main__":
    unittest.main()
