import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import server_manager


class ServerManagerStartupTests(unittest.TestCase):
    def test_source_auto_start_uses_pythonw_on_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            python = Path(tmp) / "python.exe"
            pythonw = Path(tmp) / "pythonw.exe"
            pythonw.touch()

            with (
                patch.object(server_manager.sys, "frozen", False, create=True),
                patch.object(server_manager.sys, "executable", str(python)),
                patch.object(server_manager.os, "name", "nt"),
            ):
                command = server_manager.auto_start_command()

        self.assertTrue(command.startswith(f'"{pythonw}" '))
        self.assertIn('server_manager.py" --auto-start --minimized', command)

    def test_source_auto_start_falls_back_when_pythonw_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            python = Path(tmp) / "python.exe"

            with (
                patch.object(server_manager.sys, "frozen", False, create=True),
                patch.object(server_manager.sys, "executable", str(python)),
                patch.object(server_manager.os, "name", "nt"),
            ):
                command = server_manager.auto_start_command()

        self.assertTrue(command.startswith(f'"{python}" '))


if __name__ == "__main__":
    unittest.main()
