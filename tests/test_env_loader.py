import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.env_loader import save_project_env_values


class ProjectEnvWriterTests(unittest.TestCase):
    def test_updates_requested_value_and_preserves_other_lines(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "# Local settings\nUNCHANGED=value\nKAY_PRINTER_ENROLLMENT_KEY=old-key\n",
                encoding="utf-8",
            )
            new_key = "secure-enrollment-key-1234567890"
            with patch.dict(os.environ, {}, clear=False):
                saved_path = save_project_env_values(
                    {"KAY_PRINTER_ENROLLMENT_KEY": new_key}, path=env_path
                )
                self.assertEqual(saved_path, env_path.resolve())
                self.assertEqual(os.environ["KAY_PRINTER_ENROLLMENT_KEY"], new_key)

            text = env_path.read_text(encoding="utf-8")
            self.assertIn("# Local settings", text)
            self.assertIn("UNCHANGED=value", text)
            self.assertIn(f"KAY_PRINTER_ENROLLMENT_KEY={new_key}", text)
            self.assertNotIn("old-key", text)

    def test_appends_value_to_new_env_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            save_project_env_values({"KAY_PRINTER_ENROLLMENT_KEY": "x" * 32}, path=env_path)
            self.assertEqual(
                env_path.read_text(encoding="utf-8"),
                f"KAY_PRINTER_ENROLLMENT_KEY={'x' * 32}\n",
            )


if __name__ == "__main__":
    unittest.main()
