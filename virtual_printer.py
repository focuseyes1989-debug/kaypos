"""Windows virtual-printer bridge for KAY Printer Agent.

The Windows queue renders through an installed PCL6 driver to a localhost RAW
TCP port.  This bridge captures each spool connection and forwards the bytes
through the existing authenticated Printer Server queue.
"""

from __future__ import annotations

import base64
import socket
import subprocess
import threading
import uuid

import requests


VIRTUAL_PRINTER_NAME = "KAY Network Printer"
VIRTUAL_PORT_NAME = "KAY_NETWORK_RAW"
VIRTUAL_HOST = "127.0.0.1"
VIRTUAL_PORT = 19100
DEFAULT_DRIVER = "Xerox Global Print Driver PCL6"
MAX_RAW_JOB_BYTES = 25 * 1024 * 1024


def _encoded_powershell(script: str) -> str:
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


def _run_elevated(script: str) -> None:
    encoded = _encoded_powershell(script)
    wrapper = (
        "$p=Start-Process powershell.exe -Verb RunAs -Wait -PassThru "
        f"-ArgumentList @('-NoProfile','-EncodedCommand','{encoded}'); exit $p.ExitCode"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", wrapper],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        timeout=120,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Windows printer setup failed (exit code {result.returncode})")


def installed_printer_drivers() -> list[str]:
    if not hasattr(subprocess, "CREATE_NO_WINDOW"):
        return []
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", "Get-PrinterDriver | Select-Object -ExpandProperty Name"],
        capture_output=True, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=20, check=False,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def install_virtual_printer(driver_name: str = DEFAULT_DRIVER) -> None:
    safe_driver = str(driver_name).replace("'", "''")
    script = fr"""
$ErrorActionPreference='Stop'
$driver='{safe_driver}'
if (-not (Get-PrinterDriver -Name $driver -ErrorAction SilentlyContinue)) {{
  throw "Required printer driver is not installed: $driver"
}}
if (-not (Get-PrinterPort -Name '{VIRTUAL_PORT_NAME}' -ErrorAction SilentlyContinue)) {{
  Add-PrinterPort -Name '{VIRTUAL_PORT_NAME}' -PrinterHostAddress '{VIRTUAL_HOST}' -PortNumber {VIRTUAL_PORT}
}}
$portKey="HKLM:\SYSTEM\CurrentControlSet\Control\Print\Monitors\Standard TCP/IP Port\Ports\{VIRTUAL_PORT_NAME}"
if (Test-Path $portKey) {{
  Set-ItemProperty -Path $portKey -Name 'SNMP Enabled' -Type DWord -Value 0
}}
$printer=Get-Printer -Name '{VIRTUAL_PRINTER_NAME}' -ErrorAction SilentlyContinue
if ($printer) {{
  Set-Printer -Name '{VIRTUAL_PRINTER_NAME}' -DriverName $driver -PortName '{VIRTUAL_PORT_NAME}'
}} else {{
  Add-Printer -Name '{VIRTUAL_PRINTER_NAME}' -DriverName $driver -PortName '{VIRTUAL_PORT_NAME}'
}}
"""
    _run_elevated(script)


def remove_virtual_printer() -> None:
    script = f"""
$ErrorActionPreference='Stop'
Remove-Printer -Name '{VIRTUAL_PRINTER_NAME}' -ErrorAction SilentlyContinue
Remove-PrinterPort -Name '{VIRTUAL_PORT_NAME}' -ErrorAction SilentlyContinue
"""
    _run_elevated(script)


class VirtualPrinterBridge:
    def __init__(self, config_loader, status_callback=None):
        self.config_loader = config_loader
        self.status_callback = status_callback or (lambda _message, _error=False: None)
        self._stop = threading.Event()
        self._thread = None
        self._server = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve, name="KAYVirtualPrinter", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._server:
            try:
                self._server.close()
            except OSError:
                pass

    def _serve(self) -> None:
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server = server
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((VIRTUAL_HOST, VIRTUAL_PORT))
            server.listen(5)
            server.settimeout(1.0)
            self.status_callback(f"Virtual printer bridge ready on {VIRTUAL_HOST}:{VIRTUAL_PORT}", False)
            while not self._stop.is_set():
                try:
                    connection, _address = server.accept()
                except socket.timeout:
                    continue
                threading.Thread(target=self._capture, args=(connection,), daemon=True).start()
        except OSError as exc:
            if not self._stop.is_set():
                self.status_callback(f"Virtual printer bridge failed: {exc}", True)

    def _capture(self, connection: socket.socket) -> None:
        data = bytearray()
        try:
            connection.settimeout(30)
            while True:
                chunk = connection.recv(64 * 1024)
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > MAX_RAW_JOB_BYTES:
                    raise RuntimeError("Virtual print job exceeds the 25 MB queue limit")
            if data:
                self._forward(bytes(data))
        except Exception as exc:
            self.status_callback(f"Virtual print job failed: {exc}", True)
        finally:
            connection.close()

    def _forward(self, data: bytes) -> None:
        config = self.config_loader() or {}
        target = config.get("virtual_printer_target") or {}
        server_url = str(config.get("server_url") or "").strip()
        client_key = str(config.get("client_api_key") or "")
        if not server_url or not target.get("agent_id") or not target.get("printer_name"):
            raise RuntimeError("Select a Virtual Printer target in Printer Agent first")
        response = requests.post(
            f"{server_url.rstrip('/')}/api/printer/jobs/upload",
            headers={"X-Printer-API-Key": client_key} if client_key else {},
            files={"file": (f"KAY-Virtual-{uuid.uuid4()}.pcl", data, "application/octet-stream")},
            data={
                "target_agent_id": target["agent_id"],
                "printer_name": target["printer_name"],
                "request_key": f"virtual-{uuid.uuid4()}",
                "copies": 1,
                "source_agent_id": "kay-windows-virtual-printer",
            },
            timeout=60,
            verify=not bool(config.get("insecure", False)),
        )
        response.raise_for_status()
        self.status_callback(f"Virtual print job queued for {target['printer_name']}", False)
