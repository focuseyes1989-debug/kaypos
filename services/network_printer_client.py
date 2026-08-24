"""POS-facing client for routing receipts to the LAN printer queue."""

from __future__ import annotations

import uuid
import re
import socket
from dataclasses import dataclass

import requests

from models.database import connect_db


@dataclass(frozen=True)
class NetworkPrintResult:
    handled: bool
    success: bool
    message: str = ""
    job_id: str = ""


def _settings(keys: tuple[str, ...]) -> dict[str, str]:
    conn = connect_db()
    try:
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in keys)
        cursor.execute(f"SELECT key, value FROM settings WHERE key IN ({placeholders})", keys)
        return {str(key): str(value or "") for key, value in cursor.fetchall()}
    finally:
        conn.close()


def machine_setting_key(key: str, computer_name: str | None = None) -> str:
    machine = computer_name or socket.gethostname() or "unknown-pc"
    safe_machine = re.sub(r"[^a-z0-9_.-]+", "-", machine.strip().lower())[:80]
    return f"{key}__{safe_machine}"


def network_printer_settings() -> dict[str, str]:
    base_keys = (
        "receipt_printer_mode",
        "network_printer_server_url",
        "network_printer_agent_id",
        "network_printer_name",
        "network_printer_verify_tls",
        "network_printer_local_fallback",
        "network_printer_api_key",
        "receipt_paper_size",
    )
    scoped_keys = tuple(machine_setting_key(key) for key in base_keys[:-1])
    raw = _settings(base_keys + scoped_keys)
    values = {key: raw.get(machine_setting_key(key), raw.get(key, "")) for key in base_keys[:-1]}
    values["receipt_paper_size"] = raw.get("receipt_paper_size", "0")
    values.setdefault("receipt_printer_mode", "local")
    values.setdefault("network_printer_verify_tls", "0")
    values.setdefault("network_printer_local_fallback", "1")
    return values


def list_network_printers(server_url: str, verify_tls: bool = False, api_key: str = "") -> list[dict]:
    response = requests.get(
        f"{server_url.rstrip('/')}/api/printer/agents",
        timeout=8,
        verify=verify_tls,
        headers={"X-Printer-API-Key": api_key} if api_key else {},
    )
    response.raise_for_status()
    agents = response.json().get("data") or []
    result = []
    for agent in agents:
        for printer in agent.get("printers") or []:
            if agent.get("is_online") and printer.get("status") == "online":
                result.append({
                    "agent_id": agent.get("agent_id"),
                    "computer_name": agent.get("computer_name"),
                    "ip_address": agent.get("ip_address"),
                    "printer_name": printer.get("printer_name"),
                    "is_default": bool(printer.get("is_default")),
                })
    return result


def queue_receipt(
    sale_id: int,
    lines: list[str],
    *,
    request_key: str | None = None,
    copies: int = 1,
) -> NetworkPrintResult:
    settings = network_printer_settings()
    if settings.get("receipt_printer_mode", "local") != "network":
        return NetworkPrintResult(False, False)

    server_url = settings.get("network_printer_server_url", "").strip()
    agent_id = settings.get("network_printer_agent_id", "").strip()
    printer_name = settings.get("network_printer_name", "").strip()
    if not server_url or not agent_id or not printer_name:
        fallback = settings.get("network_printer_local_fallback", "1") == "1"
        return NetworkPrintResult(not fallback, False, "Network receipt printer settings are incomplete.")

    paper_index = settings.get("receipt_paper_size", "0")
    paper_size = {"0": "80MM", "1": "58MM", "2": "A4"}.get(paper_index, "80MM")
    payload = {
        "request_key": request_key or f"pos-receipt-{sale_id}-{uuid.uuid4()}",
        "target_agent_id": agent_id,
        "printer_name": printer_name,
        "job_type": "text_receipt",
        "payload": {
            "text": "\n".join(str(line) for line in lines),
            "paper_size": paper_size,
            "orientation": "portrait",
            "filename": f"receipt-{sale_id}.txt",
            "sale_id": sale_id,
        },
        "copies": max(1, min(int(copies or 1), 99)),
        "source_agent_id": "kay-pos",
    }
    try:
        response = requests.post(
            f"{server_url.rstrip('/')}/api/printer/jobs",
            json=payload,
            timeout=10,
            verify=settings.get("network_printer_verify_tls") == "1",
            headers={"X-Printer-API-Key": settings.get("network_printer_api_key", "")},
        )
        response.raise_for_status()
        job = response.json().get("data") or {}
        return NetworkPrintResult(
            True,
            True,
            f"Receipt queued on {printer_name}.",
            str(job.get("job_id") or ""),
        )
    except Exception as exc:
        fallback = settings.get("network_printer_local_fallback", "1") == "1"
        message = f"Network receipt print failed: {exc}"
        return NetworkPrintResult(not fallback, False, message)
