import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["ZAY_POS_DB_BACKEND"] = "sqlite"

from fastapi import HTTPException

from server.api import STATIC_DIR, car_owner_print_page, public_car_qr_lookup


class CarPrintWebTests(unittest.TestCase):
    def test_owner_page_is_mobile_safe_and_contains_no_private_fields(self):
        page = Path(STATIC_DIR) / "car_print.html"
        text = page.read_text(encoding="utf-8")
        self.assertIn('name="viewport"', text)
        self.assertIn("/api/car/qr/", text)
        self.assertIn("confirmButton", text)
        self.assertIn("/api/car/print-jobs", text)
        self.assertIn("1, 2, 3, 4, 2, 3, 2, 3, 4", text)
        self.assertIn('id="copies"', text)
        self.assertIn('id="printer"', text)
        self.assertIn("/api/car/printers", text)
        self.assertNotIn("nrc_number", text)
        self.assertNotIn("phone_number", text)

    def test_page_route_serves_owner_interface_without_cache(self):
        response = car_owner_print_page()
        self.assertEqual(Path(response.path), Path(STATIC_DIR) / "car_print.html")
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_kiosk_page_accepts_scanner_input_and_returns_to_next_customer(self):
        text = (Path(STATIC_DIR) / "car_kiosk.html").read_text(encoding="utf-8")
        self.assertIn("scanInput", text)
        self.assertIn("/car/print?t=", text)
        owner = (Path(STATIC_DIR) / "car_print.html").read_text(encoding="utf-8")
        self.assertIn('location.href = "/car/kiosk"', owner)

    @patch("server.car_management_service.CarRepository.resolve_qr_token")
    def test_public_lookup_returns_only_repository_summary(self, resolve):
        resolve.return_value = {"id": 1, "car_number": "1A/1", "driver_name": "A", "vehicle": "Toyota"}
        result = public_car_qr_lookup("x" * 43)
        self.assertEqual(result["data"]["car_number"], "1A/1")
        self.assertNotIn("nrc_number", result["data"])

    @patch("server.car_management_service.CarRepository.resolve_qr_token", return_value=None)
    def test_public_lookup_rejects_disabled_token(self, _resolve):
        with self.assertRaises(HTTPException) as caught:
            public_car_qr_lookup("x" * 43)
        self.assertEqual(caught.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
