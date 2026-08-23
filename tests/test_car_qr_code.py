import unittest

from PIL import Image

from car_client.qr_code import qr_access_url, record_qr_png, suggested_qr_filename


class CarQrCodeTests(unittest.TestCase):
    def setUp(self):
        self.record = {
            "id": 42,
            "car_number": "1A/1234",
            "driver_name": "မောင်မောင်",
            "kind_of_car": "Saloon",
            "type_of_car": "Toyota Probox",
            "phone_number": "091234567",
        }

    def test_access_url_uses_explicit_owner_url_or_lan_without_personal_data(self):
        token = "secret-token"
        cloud = qr_access_url(token, "192.168.1.10", "https://cars.example.com")
        lan = qr_access_url(token, "192.168.1.10")
        self.assertEqual(cloud, "https://cars.example.com/car/print?t=secret-token")
        self.assertEqual(lan, "https://192.168.1.10:8000/car/print?t=secret-token")
        self.assertNotIn(self.record["driver_name"], cloud)

    def test_png_is_a_valid_square_qr_image(self):
        from io import BytesIO

        image = Image.open(BytesIO(record_qr_png("https://cars.example.com/car/print?t=token")))
        self.assertEqual(image.format, "PNG")
        self.assertEqual(image.width, image.height)
        self.assertGreater(image.width, 100)

    def test_filename_is_windows_safe(self):
        self.assertEqual(suggested_qr_filename(self.record), "1A_1234_qr.png")


if __name__ == "__main__":
    unittest.main()
