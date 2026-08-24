"""Authentication and LAN-boundary helpers for Printer Server endpoints."""

from __future__ import annotations

import hashlib
import ipaddress
import os
import secrets


def security_enabled() -> bool:
    return bool(os.getenv("KAY_PRINTER_ADMIN_KEY", "").strip())


def hash_secret(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def verify_secret(value: str, expected_hash: str) -> bool:
    return bool(value and expected_hash and secrets.compare_digest(hash_secret(value), expected_hash))


def require_admin_key(value: str | None) -> None:
    configured = os.getenv("KAY_PRINTER_ADMIN_KEY", "").strip()
    if configured and not value:
        raise PermissionError("Printer Server API key is required")
    if configured and not secrets.compare_digest(str(value), configured):
        raise PermissionError("Invalid Printer Server API key")


def require_client_key(value: str | None) -> None:
    configured = os.getenv("KAY_PRINTER_CLIENT_KEY", "").strip()
    if not configured:
        configured = os.getenv("KAY_PRINTER_ADMIN_KEY", "").strip()
    if configured and (not value or not secrets.compare_digest(str(value), configured)):
        raise PermissionError("Invalid Printer Client API key")


def require_enrollment_key(value: str | None) -> None:
    configured = os.getenv("KAY_PRINTER_ENROLLMENT_KEY", "").strip()
    if not configured:
        configured = os.getenv("KAY_PRINTER_ADMIN_KEY", "").strip()
    if configured and (not value or not secrets.compare_digest(str(value), configured)):
        raise PermissionError("Invalid Printer Agent enrollment key")


def require_lan_address(address: str | None) -> None:
    if not security_enabled():
        return
    try:
        ip = ipaddress.ip_address(str(address or ""))
    except ValueError as exc:
        raise PermissionError("Printer API is restricted to the local network") from exc
    if not (ip.is_private or ip.is_loopback or ip.is_link_local):
        raise PermissionError("Printer API is restricted to the local network")
