"""KAY LAN/Wi-Fi Printer Agent (Phase 1 discovery and heartbeat)."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import socket
import sys
import tempfile
import time
import uuid
from pathlib import Path

import requests
from PyQt6.QtCore import QMarginsF, QSize, QSizeF, Qt
from PyQt6.QtGui import QFont, QImage, QPageLayout, QPageSize, QPainter
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo
from PyQt6.QtWidgets import QApplication


AGENT_VERSION = "1.0"


def agent_config_path() -> Path:
    root = Path(os.getenv("APPDATA") or Path.home()) / "KAY POS" / "Printer Agent"
    root.mkdir(parents=True, exist_ok=True)
    return root / "agent.json"


def load_agent_key() -> str:
    return str(load_agent_config().get("agent_key") or "")


def load_agent_config() -> dict:
    try:
        data = json.loads(agent_config_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def save_agent_config(**updates) -> dict:
    data = load_agent_config()
    data.update(updates)
    agent_config_path().write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def save_agent_key(agent_key: str) -> None:
    save_agent_config(agent_key=agent_key)


def startup_shortcut_path() -> Path:
    appdata = Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming")
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "KAY Printer Agent.cmd"


def startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'@start "" /min "{sys.executable}" --tray\n'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    executable = pythonw if pythonw.is_file() else Path(sys.executable)
    return f'@start "" /min "{executable}" "{Path(__file__).resolve()}" --tray\n'


def set_windows_startup(enabled: bool) -> Path:
    path = startup_shortcut_path()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(startup_command(), encoding="utf-8")
    else:
        path.unlink(missing_ok=True)
    return path


def enroll_agent(server_url: str, enrollment_key: str, verify_tls: bool) -> str:
    payload = heartbeat_payload()
    response = requests.post(
        f"{server_url.rstrip('/')}/api/printer/agents/enroll",
        json={"agent_id": payload["agent_id"], "computer_name": payload["computer_name"]},
        headers={"X-Printer-Enrollment-Key": enrollment_key},
        timeout=10,
        verify=verify_tls,
    )
    response.raise_for_status()
    agent_key = str((response.json().get("data") or {}).get("agent_key") or "")
    if not agent_key:
        raise RuntimeError("Printer Server did not return an Agent key")
    save_agent_key(agent_key)
    return agent_key


def stable_agent_id(computer_name: str | None = None) -> str:
    name = computer_name or socket.gethostname() or "unknown-pc"
    seed = f"{name.lower()}:{uuid.getnode():012x}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"kay-pos-printer-agent:{seed}"))


def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def discover_printers() -> list[dict]:
    default = QPrinterInfo.defaultPrinter()
    default_name = "" if default.isNull() else default.printerName()
    return [
        {"name": printer.printerName(), "is_default": printer.printerName() == default_name}
        for printer in QPrinterInfo.availablePrinters()
        if printer.printerName()
    ]


def heartbeat_payload() -> dict:
    computer_name = os.getenv("COMPUTERNAME") or socket.gethostname() or "Unknown PC"
    return {
        "agent_id": stable_agent_id(computer_name),
        "computer_name": computer_name,
        "ip_address": local_ip(),
        "platform": f"{platform.system()} {platform.release()}",
        "agent_version": AGENT_VERSION,
        "printers": discover_printers(),
    }


def send_heartbeat(server_url: str, timeout: float = 8.0, verify_tls: bool = True, agent_key: str = "") -> dict:
    response = requests.post(
        f"{server_url.rstrip('/')}/api/printer/agents/heartbeat",
        json=heartbeat_payload(),
        headers={"X-Printer-Agent-Key": agent_key} if agent_key else {},
        timeout=timeout,
        verify=verify_tls,
    )
    response.raise_for_status()
    return response.json()


def _printer_names() -> list[str]:
    return [item["name"] for item in discover_printers()]


def print_test_page(printer_name: str, payload: dict | None = None, copies: int = 1) -> None:
    info = next(
        (item for item in QPrinterInfo.availablePrinters() if item.printerName() == printer_name),
        None,
    )
    if info is None:
        raise RuntimeError(f"Printer is not installed: {printer_name}")
    printer = QPrinter(info)
    printer.setDocName("KAY Printer Server Test Page")
    printer.setCopyCount(max(1, min(int(copies or 1), 99)))
    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError(f"Windows could not start printer: {printer_name}")
    try:
        data = payload or {}
        computer_name = os.getenv("COMPUTERNAME") or socket.gethostname()
        title_font = QFont("Segoe UI", 22, QFont.Weight.Bold)
        body_font = QFont("Segoe UI", 11)
        page = printer.pageRect(QPrinter.Unit.DevicePixel)
        painter.setFont(title_font)
        painter.drawText(page.adjusted(80, 100, -80, -100), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter, "KAY Printer Server")
        painter.setFont(body_font)
        lines = [
            "Network Test Page",
            "",
            f"Target PC: {computer_name}",
            f"Printer: {printer_name}",
            f"Requested by: {data.get('requested_by') or 'KAY Server Manager'}",
            f"Message: {data.get('message') or 'LAN/Wi-Fi printing is connected successfully.'}",
            "",
            time.strftime("Printed: %Y-%m-%d %H:%M:%S"),
        ]
        painter.drawText(page.adjusted(120, 300, -120, -120), Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, "\n".join(lines))
    finally:
        painter.end()


def printer_resolution_for_quality(quality: str, supported: list[int] | tuple[int, ...] = ()) -> int:
    requested = {"draft": 150, "normal": 300, "high": 600}.get(str(quality or "normal").lower(), 300)
    available = [int(value) for value in supported if int(value) > 0]
    return min(available, key=lambda value: abs(value - requested)) if available else requested


def _configured_printer(printer_name: str, payload: dict, copies: int) -> QPrinter:
    info = next((item for item in QPrinterInfo.availablePrinters() if item.printerName() == printer_name), None)
    if info is None:
        raise RuntimeError(f"Printer is not installed: {printer_name}")
    printer = QPrinter(info)
    printer.setDocName(str(payload.get("filename") or "KAY Network Print Job"))
    printer.setCopyCount(max(1, min(int(copies or 1), 99)))
    paper = str(payload.get("paper_size") or "A4").upper()
    sizes = {
        "A4": QPageSize(QPageSize.PageSizeId.A4),
        "A5": QPageSize(QPageSize.PageSizeId.A5),
        "LETTER": QPageSize(QPageSize.PageSizeId.Letter),
        "4X6": QPageSize(QSizeF(101.6, 152.4), QPageSize.Unit.Millimeter, "4 x 6 in"),
        "5X7": QPageSize(QSizeF(127, 177.8), QPageSize.Unit.Millimeter, "5 x 7 in"),
        "58MM": QPageSize(QSizeF(58, 500), QPageSize.Unit.Millimeter, "58mm Receipt"),
        "80MM": QPageSize(QSizeF(80, 500), QPageSize.Unit.Millimeter, "80mm Receipt"),
    }
    if paper == "CUSTOM":
        width = max(20.0, min(float(payload.get("custom_width_mm") or 210.0), 1000.0))
        height = max(20.0, min(float(payload.get("custom_height_mm") or 297.0), 1000.0))
        sizes["CUSTOM"] = QPageSize(QSizeF(width, height), QPageSize.Unit.Millimeter, "Custom")
    printer.setPageSize(sizes.get(paper, sizes["A4"]))
    orientation = (
        QPageLayout.Orientation.Landscape
        if str(payload.get("orientation") or "portrait").lower() == "landscape"
        else QPageLayout.Orientation.Portrait
    )
    printer.setPageOrientation(orientation)
    if bool(payload.get("borderless")):
        page_layout = printer.pageLayout()
        page_layout.setMargins(QMarginsF(0, 0, 0, 0))
        printer.setPageLayout(page_layout)
    printer.setResolution(printer_resolution_for_quality(
        str(payload.get("quality") or "normal"), printer.supportedResolutions()
    ))
    printer.setColorMode(
        QPrinter.ColorMode.GrayScale
        if str(payload.get("color_mode") or "color").lower() == "grayscale"
        else QPrinter.ColorMode.Color
    )
    return printer


def _begin_painter(printer: QPrinter) -> QPainter:
    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError(f"Windows could not start printer: {printer.printerName()}")
    return painter


def print_image(printer_name: str, data: bytes, payload: dict, copies: int) -> None:
    image = QImage.fromData(data)
    if image.isNull():
        raise RuntimeError("The downloaded image could not be decoded")
    printer = _configured_printer(printer_name, payload, copies)
    painter = _begin_painter(printer)
    try:
        page = printer.pageRect(QPrinter.Unit.DevicePixel)
        scaled = image.scaled(QSize(int(page.width()), int(page.height())), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        x = int(page.x() + (page.width() - scaled.width()) / 2)
        y = int(page.y() + (page.height() - scaled.height()) / 2)
        painter.drawImage(x, y, scaled)
    finally:
        painter.end()


def print_pdf(printer_name: str, data: bytes, payload: dict, copies: int) -> None:
    document = QPdfDocument(None)
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_file.write(data)
            temp_path = temp_file.name
        error = document.load(temp_path)
        if error != QPdfDocument.Error.None_ or document.pageCount() < 1:
            raise RuntimeError(f"The downloaded PDF could not be opened ({error})")
        printer = _configured_printer(printer_name, payload, copies)
        painter = _begin_painter(printer)
        try:
            for page_index in range(document.pageCount()):
                if page_index:
                    printer.newPage()
                target = printer.pageRect(QPrinter.Unit.DevicePixel)
                image = document.render(page_index, QSize(int(target.width()), int(target.height())))
                painter.drawImage(target, image)
        finally:
            painter.end()
    finally:
        document.close()
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def print_text_receipt(printer_name: str, text: str, payload: dict, copies: int) -> None:
    printer = _configured_printer(printer_name, payload, copies)
    painter = _begin_painter(printer)
    try:
        paper = str(payload.get("paper_size") or "80MM").upper()
        font_size = 8 if paper == "58MM" else 10
        painter.setFont(QFont("Myanmar Text", font_size))
        page = printer.pageRect(QPrinter.Unit.DevicePixel)
        margin = max(12, int(page.width() * 0.04))
        painter.drawText(
            page.adjusted(margin, margin, -margin, -margin),
            Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            text,
        )
    finally:
        painter.end()


def print_escpos_raw(printer_name: str, data: bytes, copies: int) -> None:
    if os.name != "nt":
        raise RuntimeError("Raw ESC/POS printing is available only on Windows")
    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    handle = ctypes.c_void_p()
    if not winspool.OpenPrinterW(ctypes.c_wchar_p(printer_name), ctypes.byref(handle), None):
        raise ctypes.WinError(ctypes.get_last_error())
    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [("pDocName", ctypes.c_wchar_p), ("pOutputFile", ctypes.c_wchar_p), ("pDatatype", ctypes.c_wchar_p)]
    try:
        for _ in range(max(1, min(int(copies or 1), 99))):
            doc = DOC_INFO_1("KAY RAW Network Print Job", None, "RAW")
            if not winspool.StartDocPrinterW(handle, 1, ctypes.byref(doc)):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                if not winspool.StartPagePrinter(handle):
                    raise ctypes.WinError(ctypes.get_last_error())
                try:
                    written = ctypes.c_ulong()
                    buffer = ctypes.create_string_buffer(data)
                    if not winspool.WritePrinter(handle, buffer, len(data), ctypes.byref(written)):
                        raise ctypes.WinError(ctypes.get_last_error())
                    if written.value != len(data):
                        raise RuntimeError("Windows accepted only part of the RAW print job")
                finally:
                    winspool.EndPagePrinter(handle)
            finally:
                winspool.EndDocPrinter(handle)
    finally:
        winspool.ClosePrinter(handle)


def download_job_content(server_url: str, job_id: str, agent_id: str, agent_key: str, verify_tls: bool) -> bytes:
    response = requests.get(
        f"{server_url.rstrip('/')}/api/printer/jobs/{job_id}/content",
        timeout=30,
        verify=verify_tls,
        headers={"X-Printer-Agent-Id": agent_id, "X-Printer-Agent-Key": agent_key},
    )
    response.raise_for_status()
    if len(response.content) > 25 * 1024 * 1024:
        raise RuntimeError("Downloaded print document exceeds 25 MB")
    return response.content


def process_pending_jobs(server_url: str, agent_id: str, verify_tls: bool = True, agent_key: str = "") -> int:
    printers = _printer_names()
    agent_headers = {"X-Printer-Agent-Key": agent_key} if agent_key else {}
    response = requests.get(
        f"{server_url.rstrip('/')}/api/printer/agents/{agent_id}/jobs",
        params={"limit": 5},
        timeout=8,
        verify=verify_tls,
        headers=agent_headers,
    )
    response.raise_for_status()
    jobs = response.json().get("data") or []
    completed = 0
    for queued_job in jobs:
        job_id = queued_job["job_id"]
        claim = requests.post(
            f"{server_url.rstrip('/')}/api/printer/jobs/{job_id}/claim",
            json={"agent_id": agent_id, "printers": printers},
            timeout=8,
            verify=verify_tls,
            headers=agent_headers,
        )
        if claim.status_code == 409:
            continue
        claim.raise_for_status()
        job = claim.json().get("data") or {}
        status = "completed"
        error_message = ""
        try:
            job_type = job.get("job_type")
            payload = job.get("payload") or {}
            if job_type == "test_page":
                print_test_page(job["printer_name"], job.get("payload"), job.get("copies", 1))
            elif job_type in {"pdf", "image", "escpos_raw", "raw"}:
                content = download_job_content(server_url, job_id, agent_id, agent_key, verify_tls)
                if job_type == "pdf":
                    print_pdf(job["printer_name"], content, payload, job.get("copies", 1))
                elif job_type == "image":
                    print_image(job["printer_name"], content, payload, job.get("copies", 1))
                else:
                    print_escpos_raw(job["printer_name"], content, job.get("copies", 1))
            elif job_type == "text_receipt":
                if payload.get("asset_path"):
                    text = download_job_content(server_url, job_id, agent_id, agent_key, verify_tls).decode("utf-8-sig")
                else:
                    text = str(payload.get("text") or "")
                if not text:
                    raise RuntimeError("Receipt text is empty")
                print_text_receipt(job["printer_name"], text, payload, job.get("copies", 1))
            else:
                raise RuntimeError(f"Unsupported job type: {job_type}")
        except Exception as exc:
            status = "failed"
            error_message = str(exc)
        update = requests.post(
            f"{server_url.rstrip('/')}/api/printer/jobs/{job_id}/status",
            json={"agent_id": agent_id, "status": status, "error_message": error_message},
            timeout=8,
            verify=verify_tls,
            headers=agent_headers,
        )
        update.raise_for_status()
        if status == "completed":
            completed += 1
        else:
            print(f"Print job {job_id} failed: {error_message}", file=sys.stderr, flush=True)
    return completed


def run_agent_cycle(server_url: str, insecure: bool, agent_key: str) -> tuple[dict, int]:
    result = send_heartbeat(server_url, verify_tls=not insecure, agent_key=agent_key)
    agent = result.get("data") or {}
    completed = process_pending_jobs(
        server_url,
        agent.get("agent_id") or stable_agent_id(),
        verify_tls=not insecure,
        agent_key=agent_key,
    )
    return agent, completed


def main() -> int:
    saved_config = load_agent_config()
    parser = argparse.ArgumentParser(description="KAY LAN/Wi-Fi Printer Agent")
    parser.add_argument(
        "--server",
        default=os.getenv("KAY_PRINTER_SERVER_URL", str(saved_config.get("server_url") or "http://127.0.0.1:8000")),
        help="KAY POS server URL, for example http://192.168.1.10:8000",
    )
    parser.add_argument("--interval", type=float, default=10.0, help="Heartbeat interval in seconds")
    parser.add_argument("--once", action="store_true", help="Send one heartbeat and exit")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Allow the Server Manager's self-signed LAN HTTPS certificate",
    )
    parser.add_argument(
        "--enrollment-key",
        default=os.getenv("KAY_PRINTER_ENROLLMENT_KEY", ""),
        help="One-time key used to enroll this PC with a secured Printer Server",
    )
    parser.add_argument(
        "--reset-enrollment",
        action="store_true",
        help="Remove this PC's saved Agent key before enrolling again",
    )
    parser.add_argument("--tray", action="store_true", help="Run quietly in the Windows system tray")
    parser.add_argument("--configure", action="store_true", help="Open the Printer Agent setup window")
    parser.add_argument("--open-manager", action="store_true", help="Open the Printer Agent management window")
    parser.add_argument("--install-startup", action="store_true", help="Start Printer Agent after Windows login")
    parser.add_argument("--remove-startup", action="store_true", help="Remove Printer Agent from Windows startup")
    args = parser.parse_args()

    if args.install_startup:
        print(f"Windows startup enabled: {set_windows_startup(True)}")
        return 0
    if args.remove_startup:
        print(f"Windows startup removed: {set_windows_startup(False)}")
        return 0
    if args.configure:
        from printer_agent_gui import run_setup_dialog

        return run_setup_dialog()
    if args.tray or (getattr(sys, "frozen", False) and not args.once):
        from printer_agent_gui import run_tray_agent

        return run_tray_agent(open_manager=args.open_manager)

    app = QApplication.instance() or QApplication([sys.argv[0]])
    # Keep QApplication referenced while QPrinterInfo queries the Windows spooler.
    if args.reset_enrollment:
        agent_config_path().unlink(missing_ok=True)
    agent_key = load_agent_key()
    if not agent_key and args.enrollment_key:
        try:
            agent_key = enroll_agent(args.server, args.enrollment_key, not args.insecure)
            print("Printer Agent enrollment completed.", flush=True)
        except Exception as exc:
            print(f"Printer Agent enrollment failed: {exc}", file=sys.stderr, flush=True)
            return 1
    save_agent_config(server_url=args.server, insecure=bool(args.insecure))
    while True:
        try:
            agent, completed = run_agent_cycle(args.server, args.insecure, agent_key)
            print(
                f"Printer Agent online: {agent.get('computer_name', '')} · "
                f"{len(agent.get('printers') or [])} printer(s)",
                flush=True,
            )
            if completed:
                print(f"Completed {completed} print job(s)", flush=True)
        except Exception as exc:
            print(f"Printer Agent heartbeat failed: {exc}", file=sys.stderr, flush=True)
            if args.once:
                return 1
        if args.once:
            return 0
        time.sleep(max(3.0, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
