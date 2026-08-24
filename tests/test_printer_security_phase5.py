import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.printer_security import require_admin_key, require_client_key, require_lan_address
from server.printer_service import PrinterRegistry


class PrinterSecurityPhase5Tests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "security.db"

        def connect():
            return sqlite3.connect(self.db_path)

        self.registry = PrinterRegistry(connect)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_admin_key_is_enforced_only_when_configured(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("KAY_PRINTER_ADMIN_KEY", None)
            require_admin_key(None)
        with patch.dict(os.environ, {"KAY_PRINTER_ADMIN_KEY": "strong-admin-key"}):
            with self.assertRaises(PermissionError):
                require_admin_key("wrong")
            require_admin_key("strong-admin-key")

    def test_secured_api_accepts_only_lan_addresses(self):
        with patch.dict(os.environ, {"KAY_PRINTER_ADMIN_KEY": "enabled"}):
            require_lan_address("192.168.1.20")
            require_lan_address("127.0.0.1")
            with self.assertRaises(PermissionError):
                require_lan_address("8.8.8.8")

    def test_client_key_is_separate_from_admin_key(self):
        with patch.dict(os.environ, {
            "KAY_PRINTER_ADMIN_KEY": "admin-only",
            "KAY_PRINTER_CLIENT_KEY": "pos-clients",
        }):
            require_client_key("pos-clients")
            with self.assertRaises(PermissionError):
                require_client_key("admin-only")

    def test_agent_enrollment_authentication_and_disable(self):
        with patch.dict(os.environ, {"KAY_PRINTER_ADMIN_KEY": "enabled"}):
            agent, token = self.registry.enroll_agent("secure-agent-01", "SECURE-PC")
            self.assertTrue(token)
            self.assertNotIn("api_key_hash", agent)
            self.registry.authorize_agent("secure-agent-01", token)
            with self.assertRaises(PermissionError):
                self.registry.authorize_agent("secure-agent-01", "wrong-token")
            self.registry.set_agent_permissions("secure-agent-01", False, [])
            with self.assertRaisesRegex(PermissionError, "disabled"):
                self.registry.authorize_agent("secure-agent-01", token)

    def test_agent_job_type_permissions(self):
        with patch.dict(os.environ, {"KAY_PRINTER_ADMIN_KEY": "enabled"}):
            _, token = self.registry.enroll_agent("secure-agent-02", "RECEIPT-PC")
            self.registry.set_agent_permissions("secure-agent-02", True, ["text_receipt"])
            self.registry.authorize_agent("secure-agent-02", token, "text_receipt")
            with self.assertRaisesRegex(PermissionError, "not allowed"):
                self.registry.authorize_agent("secure-agent-02", token, "pdf")


if __name__ == "__main__":
    unittest.main()
