import unittest

from printer_agent_gui import _api_headers, generate_security_key, printer_visibility_key


class PrinterAgentUiTests(unittest.TestCase):
    def test_visibility_key_distinguishes_pc_and_printer(self):
        first = printer_visibility_key("agent-a", "Receipt")
        self.assertNotEqual(first, printer_visibility_key("agent-b", "Receipt"))
        self.assertNotEqual(first, printer_visibility_key("agent-a", "Office"))

    def test_client_and_admin_headers_use_the_correct_keys(self):
        config = {"client_api_key": "client", "admin_api_key": "admin"}
        self.assertEqual(_api_headers(config), {"X-Printer-Api-Key": "client"})
        self.assertEqual(_api_headers(config, admin=True), {"X-Printer-Api-Key": "admin"})

    def test_admin_header_falls_back_to_client_key(self):
        self.assertEqual(
            _api_headers({"client_api_key": "shared"}, admin=True),
            {"X-Printer-Api-Key": "shared"},
        )

    def test_generated_security_keys_are_strong_and_copy_friendly(self):
        first = generate_security_key()
        second = generate_security_key()
        self.assertGreaterEqual(len(first), 32)
        self.assertNotEqual(first, second)
        self.assertNotIn("\n", first)
        self.assertNotIn("=", first)

if __name__ == "__main__":
    unittest.main()
