import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import printer_agent


class PrinterAgentPhase6Tests(unittest.TestCase):
    def test_quality_uses_nearest_windows_printer_resolution(self):
        self.assertEqual(printer_agent.printer_resolution_for_quality("draft", [300, 600]), 300)
        self.assertEqual(printer_agent.printer_resolution_for_quality("normal", [203, 300, 600]), 300)
        self.assertEqual(printer_agent.printer_resolution_for_quality("high", [300, 1200]), 300)
        self.assertEqual(printer_agent.printer_resolution_for_quality("high", []), 600)
    def test_configuration_updates_preserve_agent_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "agent.json"
            with patch("printer_agent.agent_config_path", return_value=config_path):
                printer_agent.save_agent_config(agent_key="secret-token")
                printer_agent.save_agent_config(server_url="https://server:8000", insecure=True)
                config = printer_agent.load_agent_config()
            self.assertEqual(config["agent_key"], "secret-token")
            self.assertEqual(config["server_url"], "https://server:8000")
            self.assertTrue(config["insecure"])

    def test_windows_startup_can_be_enabled_and_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            startup_path = Path(tmp) / "KAY Printer Agent.cmd"
            with patch("printer_agent.startup_shortcut_path", return_value=startup_path):
                result = printer_agent.set_windows_startup(True)
                self.assertEqual(result, startup_path)
                self.assertTrue(startup_path.is_file())
                self.assertIn("--tray", startup_path.read_text(encoding="utf-8"))
                printer_agent.set_windows_startup(False)
                self.assertFalse(startup_path.exists())

    def test_agent_cycle_heartbeats_before_polling_queue(self):
        heartbeat = {"data": {"agent_id": "agent-123", "computer_name": "PC1", "printers": []}}
        with patch("printer_agent.send_heartbeat", return_value=heartbeat) as send:
            with patch("printer_agent.process_pending_jobs", return_value=2) as process:
                agent, completed = printer_agent.run_agent_cycle("https://server:8000", True, "token")
        self.assertEqual(agent["agent_id"], "agent-123")
        self.assertEqual(completed, 2)
        send.assert_called_once_with("https://server:8000", verify_tls=False, agent_key="token")
        process.assert_called_once_with(
            "https://server:8000", "agent-123", verify_tls=False, agent_key="token"
        )


if __name__ == "__main__":
    unittest.main()
