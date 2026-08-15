import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import receipt_images


class ReceiptImageStorageTests(unittest.TestCase):
    def test_save_restore_and_clear_receipt_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "pos.db"
            image_path = root / "logo.png"
            image_path.write_bytes(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
                b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
                b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT"
                b"\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfe"
                b"\xdc\xccY\xe7\x00\x00\x00\x00IEND\xaeB`\x82"
            )

            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
            conn.commit()
            conn.close()

            with mock.patch("utils.receipt_images.get_db_dir", return_value=str(root)), mock.patch(
                "utils.receipt_images.connect_db", side_effect=lambda: sqlite3.connect(db_path)
            ):
                saved_path = receipt_images.save_receipt_image("logo", str(image_path))
                self.assertTrue(os.path.exists(saved_path))

                os.remove(saved_path)
                restored_path = receipt_images.resolve_receipt_image_path("logo")
                self.assertTrue(os.path.exists(restored_path))
                self.assertEqual(Path(restored_path).read_bytes(), image_path.read_bytes())

                receipt_images.clear_receipt_image("logo", remove_file=True)
                self.assertEqual(receipt_images.resolve_receipt_image_path("logo"), "")

                conn = sqlite3.connect(db_path)
                values = dict(conn.execute("SELECT key, value FROM settings").fetchall())
                conn.close()
                self.assertEqual(values["shop_logo"], "")
                self.assertEqual(values["shop_logo_image"], "")


if __name__ == "__main__":
    unittest.main()
