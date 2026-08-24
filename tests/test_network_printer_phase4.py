import unittest
from unittest.mock import Mock, patch

from services.network_printer_client import (
    list_network_printers,
    machine_setting_key,
    queue_receipt,
)


class NetworkPrinterPhase4Tests(unittest.TestCase):
    def test_machine_settings_are_isolated(self):
        self.assertEqual(
            machine_setting_key("network_printer_name", "COUNTER PC 1"),
            "network_printer_name__counter-pc-1",
        )
        self.assertNotEqual(
            machine_setting_key("network_printer_name", "PC-1"),
            machine_setting_key("network_printer_name", "PC-2"),
        )

    @patch("services.network_printer_client.network_printer_settings")
    def test_local_mode_does_not_submit_network_job(self, settings):
        settings.return_value = {"receipt_printer_mode": "local"}
        with patch("services.network_printer_client.requests.post") as post:
            result = queue_receipt(10, ["Receipt"])
        self.assertFalse(result.handled)
        post.assert_not_called()

    @patch("services.network_printer_client.network_printer_settings")
    def test_network_receipt_is_queued_with_sale_idempotency_key(self, settings):
        settings.return_value = {
            "receipt_printer_mode": "network",
            "network_printer_server_url": "https://server:8000",
            "network_printer_agent_id": "agent-123456",
            "network_printer_name": "Receipt 80mm",
            "network_printer_verify_tls": "0",
            "network_printer_local_fallback": "1",
            "receipt_paper_size": "0",
        }
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"data": {"job_id": "job-1"}}
        with patch("services.network_printer_client.requests.post", return_value=response) as post:
            result = queue_receipt(42, ["Line 1", "Line 2"], request_key="pos-sale-42")
        self.assertTrue(result.handled)
        self.assertTrue(result.success)
        self.assertEqual(result.job_id, "job-1")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["request_key"], "pos-sale-42")
        self.assertEqual(payload["job_type"], "text_receipt")
        self.assertEqual(payload["payload"]["paper_size"], "80MM")

    @patch("services.network_printer_client.network_printer_settings")
    def test_network_failure_allows_configured_local_fallback(self, settings):
        settings.return_value = {
            "receipt_printer_mode": "network",
            "network_printer_server_url": "https://server:8000",
            "network_printer_agent_id": "agent-123456",
            "network_printer_name": "Receipt 80mm",
            "network_printer_verify_tls": "0",
            "network_printer_local_fallback": "1",
            "receipt_paper_size": "1",
        }
        with patch("services.network_printer_client.requests.post", side_effect=OSError("offline")):
            result = queue_receipt(43, ["Receipt"])
        self.assertFalse(result.handled)
        self.assertFalse(result.success)
        self.assertIn("offline", result.message)

    def test_only_online_printers_are_selectable(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"data": [
            {"agent_id": "a1", "computer_name": "PC1", "is_online": True, "printers": [
                {"printer_name": "Online", "status": "online", "is_default": True},
                {"printer_name": "Removed", "status": "offline", "is_default": False},
            ]},
            {"agent_id": "a2", "computer_name": "PC2", "is_online": False, "printers": [
                {"printer_name": "Offline", "status": "offline", "is_default": True},
            ]},
        ]}
        with patch("services.network_printer_client.requests.get", return_value=response):
            printers = list_network_printers("https://server:8000")
        self.assertEqual([item["printer_name"] for item in printers], ["Online"])


if __name__ == "__main__":
    unittest.main()
