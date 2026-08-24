"""Managed storage for documents waiting in the network print queue."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path


MAX_PRINT_ASSET_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".bmp": "image",
    ".txt": "text_receipt",
    ".escpos": "escpos_raw",
    ".bin": "escpos_raw",
}


def asset_root() -> Path:
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    root = base / "database" / "network_print_assets"
    root.mkdir(parents=True, exist_ok=True)
    return root


def validate_upload(filename: str, data: bytes) -> tuple[str, str]:
    suffix = Path(str(filename or "")).suffix.lower()
    job_type = ALLOWED_EXTENSIONS.get(suffix)
    if not job_type:
        raise ValueError("Supported files: PDF, PNG, JPG, JPEG, BMP, TXT, ESCPOS, BIN")
    if not data:
        raise ValueError("Uploaded print file is empty")
    if len(data) > MAX_PRINT_ASSET_BYTES:
        raise ValueError("Print file exceeds the 25 MB limit")
    if job_type == "pdf" and not data.startswith(b"%PDF-"):
        raise ValueError("The uploaded file is not a valid PDF")
    return suffix, job_type


def store_asset(filename: str, data: bytes) -> tuple[str, str, str]:
    suffix, job_type = validate_upload(filename, data)
    asset_id = str(uuid.uuid4())
    path = asset_root() / f"{asset_id}{suffix}"
    path.write_bytes(data)
    return asset_id, str(path), job_type


def resolve_asset(path_value: str) -> Path:
    root = asset_root().resolve()
    path = Path(str(path_value or "")).resolve()
    if root != path and root not in path.parents:
        raise ValueError("Invalid print asset path")
    if not path.is_file():
        raise FileNotFoundError("Print asset is no longer available")
    return path

