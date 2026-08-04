import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from launcher import resolve_launch_target, should_auto_download_update


class LauncherResolutionTests(unittest.TestCase):
    def test_resolve_launch_target_prefers_script_over_exe(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exe_path = Path(tmp_dir) / "ZAY_POS.exe"
            exe_path.write_bytes(b"placeholder")
            script_path = Path(tmp_dir) / "main.py"
            script_path.write_text("print('hello')", encoding="utf-8")

            command, source = resolve_launch_target(tmp_dir)

            self.assertEqual(source, "script")
            self.assertTrue(command[0].endswith("python.exe") or command[0].endswith("python"))
            self.assertEqual(command[1], str(script_path))

    def test_resolve_launch_target_falls_back_to_python_script(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            script_path = Path(tmp_dir) / "main.py"
            script_path.write_text("print('hello')", encoding="utf-8")

            command, source = resolve_launch_target(tmp_dir)

            self.assertEqual(source, "script")
            self.assertTrue(command[0].endswith("python.exe") or command[0].endswith("python"))
            self.assertEqual(command[1], str(script_path))

    def test_resolve_launch_target_supports_cashier_mode(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            script_path = Path(tmp_dir) / "cashier_main.py"
            script_path.write_text("print('cashier')", encoding="utf-8")

            command, source = resolve_launch_target(tmp_dir, mode="cashier")

            self.assertEqual(source, "script")
            self.assertEqual(command[1], str(script_path))

    def test_should_auto_download_update_requires_available_update(self):
        self.assertTrue(should_auto_download_update(True, True))
        self.assertFalse(should_auto_download_update(False, True))
        self.assertFalse(should_auto_download_update(True, False))


if __name__ == "__main__":
    unittest.main()
