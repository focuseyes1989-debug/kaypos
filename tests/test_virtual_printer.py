import unittest
from unittest.mock import patch

from virtual_printer import (
    VIRTUAL_HOST, VIRTUAL_PORT, VIRTUAL_PRINTER_NAME, VirtualPrinterBridge,
    _encoded_powershell,
)
from server.printer_assets import validate_upload


class VirtualPrinterTests(unittest.TestCase):
    def test_powershell_encoding_round_trips_unicode(self):
        script = f"Write-Output '{VIRTUAL_PRINTER_NAME}'"
        import base64
        decoded = base64.b64decode(_encoded_powershell(script)).decode("utf-16-le")
        self.assertEqual(decoded, script)

    @patch("virtual_printer.requests.post")
    def test_raw_job_is_forwarded_to_configured_remote_target(self, post):
        post.return_value.raise_for_status.return_value = None
        bridge = VirtualPrinterBridge(lambda: {
            "server_url": "https://server:8000", "client_api_key": "client-key",
            "insecure": True,
            "virtual_printer_target": {"agent_id": "agent-1", "printer_name": "Xerox PCL6"},
        })
        bridge._forward(b"\x1b%-12345X PCL DATA")
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["data"]["target_agent_id"], "agent-1")
        self.assertEqual(kwargs["data"]["printer_name"], "Xerox PCL6")
        self.assertEqual(kwargs["headers"]["X-Printer-API-Key"], "client-key")
        self.assertFalse(kwargs["verify"])
        self.assertTrue(kwargs["files"]["file"][0].endswith(".pcl"))

    def test_bridge_is_bound_to_loopback_only(self):
        self.assertEqual(VIRTUAL_HOST, "127.0.0.1")
        self.assertGreater(VIRTUAL_PORT, 1024)

    def test_pcl_upload_is_classified_as_generic_raw_print(self):
        self.assertEqual(validate_upload("office-job.pcl", b"\x1b%-12345X PCL DATA"), (".pcl", "raw"))


if __name__ == "__main__":
    unittest.main()
