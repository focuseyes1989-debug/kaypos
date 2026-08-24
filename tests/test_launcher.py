import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from launcher import APPLICATIONS, INSTANCE_MUTEXES, LauncherMode, resolve_application_target, resolve_launch_target, should_auto_download_update
from utils.single_instance import SingleInstanceGuard, is_single_instance_running


class LauncherResolutionTests(unittest.TestCase):
    def test_resolve_launch_target_prefers_script_over_exe(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exe_path = Path(tmp_dir) / "ZAY_POS.exe"
            exe_path.write_bytes(b"placeholder")
            script_path = Path(tmp_dir) / "main.py"
            script_path.write_text("print('hello')", encoding="utf-8")

            command, source = resolve_launch_target(tmp_dir)

            self.assertEqual(source, "script")
            self.assertTrue(command[0].endswith(("pythonw.exe", "python.exe", "python")))
            self.assertEqual(command[1], str(script_path))

    def test_resolve_launch_target_falls_back_to_python_script(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            script_path = Path(tmp_dir) / "main.py"
            script_path.write_text("print('hello')", encoding="utf-8")

            command, source = resolve_launch_target(tmp_dir)

            self.assertEqual(source, "script")
            self.assertTrue(command[0].endswith(("pythonw.exe", "python.exe", "python")))
            self.assertEqual(command[1], str(script_path))

    def test_resolve_launch_target_supports_cashier_mode(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            script_path = Path(tmp_dir) / "cashier_main.py"
            script_path.write_text("print('cashier')", encoding="utf-8")

            command, source = resolve_launch_target(tmp_dir, mode="cashier")

            self.assertEqual(source, "script")
            self.assertEqual(command[1], str(script_path))

    def test_resolve_launch_target_supports_car_management(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            script_path = Path(tmp_dir) / "car_client_main.py"
            script_path.write_text("print('car')", encoding="utf-8")
            command, source = resolve_launch_target(tmp_dir, mode=LauncherMode.CAR)
            self.assertEqual(source, "script")
            self.assertEqual(command[1], str(script_path))

    def test_resolve_launch_target_supports_server_manager(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            script_path = Path(tmp_dir) / "server_manager.py"
            script_path.write_text("print('server')", encoding="utf-8")
            command, source = resolve_launch_target(tmp_dir, mode=LauncherMode.SERVER)
            self.assertEqual(source, "script")
            self.assertEqual(command[1], str(script_path))

    def test_printer_agent_launches_in_tray_mode(self):
        definition = next(item for item in APPLICATIONS if item.key == "printer")
        with tempfile.TemporaryDirectory() as tmp_dir:
            script_path = Path(tmp_dir) / "printer_agent.py"
            script_path.write_text("print('printer agent')", encoding="utf-8")
            command, source = resolve_application_target(definition, tmp_dir)
            self.assertEqual(source, "script")
            self.assertEqual(command[1], str(script_path))
            self.assertEqual(command[-1], "--tray")
            self.assertEqual(INSTANCE_MUTEXES["printer"], r"Global\KAY_Printer_Agent_SingleInstance_v1")

    def test_should_auto_download_update_requires_available_update(self):
        self.assertTrue(should_auto_download_update(True, True))
        self.assertFalse(should_auto_download_update(False, True))
        self.assertFalse(should_auto_download_update(True, False))

    @unittest.skipUnless(sys.platform == "win32", "Named mutexes are Windows-specific")
    def test_launcher_can_detect_an_existing_app_mutex(self):
        name = INSTANCE_MUTEXES["car"] + "_Test"
        guard = SingleInstanceGuard(name)
        self.assertFalse(is_single_instance_running(name))
        self.assertTrue(guard.acquire())
        try:
            self.assertTrue(is_single_instance_running(name))
        finally:
            guard.release()
        self.assertFalse(is_single_instance_running(name))


if __name__ == "__main__":
    unittest.main()
