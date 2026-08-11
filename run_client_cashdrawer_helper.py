"""Run a local helper on each cashier client PC for printer cash-drawer pulses.

Browsers cannot send raw ESC/POS commands directly to local printers. This
helper listens only on 127.0.0.1 and lets the browser cashier request a local
cash drawer pulse from the client computer.
"""

from __future__ import annotations

import argparse
import ctypes
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


DRAWER_KICK_COMMAND = b"\x1b\x70\x00\x19\xfa"


def send_cash_drawer_pulse(printer_name: str) -> None:
    if not printer_name:
        raise ValueError("printer_name is required")

    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)

    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [
            ("pDocName", ctypes.c_wchar_p),
            ("pOutputFile", ctypes.c_wchar_p),
            ("pDatatype", ctypes.c_wchar_p),
        ]

    h_printer = ctypes.c_void_p()
    if not winspool.OpenPrinterW(ctypes.c_wchar_p(printer_name), ctypes.byref(h_printer), None):
        raise ctypes.WinError(ctypes.get_last_error())

    try:
        doc_info = DOC_INFO_1("Open Cash Drawer", None, "RAW")
        if not winspool.StartDocPrinterW(h_printer, 1, ctypes.byref(doc_info)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not winspool.StartPagePrinter(h_printer):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                written = ctypes.c_ulong(0)
                buffer = ctypes.create_string_buffer(DRAWER_KICK_COMMAND)
                if not winspool.WritePrinter(h_printer, buffer, len(DRAWER_KICK_COMMAND), ctypes.byref(written)):
                    raise ctypes.WinError(ctypes.get_last_error())
            finally:
                winspool.EndPagePrinter(h_printer)
        finally:
            winspool.EndDocPrinter(h_printer)
    finally:
        winspool.ClosePrinter(h_printer)


class Handler(BaseHTTPRequestHandler):
    printer_name = ""

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._send_json(200, {"ok": True})

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"ok": True, "printer_name": self.printer_name})
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/open-cashdrawer":
            self._send_json(404, {"ok": False, "error": "not found"})
            return

        try:
            send_cash_drawer_pulse(self.printer_name)
            self._send_json(200, {"ok": True, "printer_name": self.printer_name})
        except Exception as exc:
            self._send_json(500, {"ok": False, "error": str(exc)})

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="ZAY POS client cash drawer helper")
    parser.add_argument("--printer", required=True, help="Client receipt printer queue name")
    parser.add_argument("--port", type=int, default=8765, help="Local helper port")
    args = parser.parse_args()

    Handler.printer_name = args.printer
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print("ZAY POS Client Cash Drawer Helper")
    print(f"Listening: http://127.0.0.1:{args.port}")
    print(f"Printer:   {args.printer}")
    print("Keep this window open while using browser cashier on this client PC.")
    server.serve_forever()


if __name__ == "__main__":
    main()
