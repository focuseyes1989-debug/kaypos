"""Run KAY POS browser cashier server on the local network."""

from __future__ import annotations

import argparse
import ipaddress
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

import uvicorn

from utils.env_loader import load_project_env


def _local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _can_bind(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            return True
    except OSError:
        return False


def _ensure_https_cert(ip: str, cert_dir: Path) -> tuple[Path, Path]:
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "HTTPS mode requires the 'cryptography' package. "
            "Install it with: python -m pip install -r requirements.txt"
        ) from exc

    cert_dir.mkdir(parents=True, exist_ok=True)
    key_path = cert_dir / "kaypos-local.key"
    cert_path = cert_dir / "kaypos-local.crt"
    if key_path.exists() and cert_path.exists():
        return cert_path, key_path

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "MM"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "KAY POS"),
            x509.NameAttribute(NameOID.COMMON_NAME, "kaypos.local"),
        ]
    )
    alt_names = [
        x509.DNSName("localhost"),
        x509.DNSName("kaypos.local"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
    ]
    try:
        alt_names.append(x509.IPAddress(ipaddress.ip_address(ip)))
    except ValueError:
        pass

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=5))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run KAY POS Cashier Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", default=8000, type=int, help="Server port")
    parser.add_argument("--https", action="store_true", help="Run with a local HTTPS certificate for mobile camera access")
    parser.add_argument("--cert-dir", default="database/certs", help="Directory for generated HTTPS certificate files")
    args = parser.parse_args()
    load_project_env()

    ip = _local_ip()
    if not _can_bind(args.host, args.port):
        print(
            f"Port {args.port} is already in use. "
            f"KAY POS Cashier may already be running at http://{ip}:{args.port}",
            flush=True,
        )
        raise SystemExit(1)

    print("KAY POS Cashier Server", flush=True)
    scheme = "https" if args.https else "http"
    cert_path = key_path = None
    if args.https:
        cert_path, key_path = _ensure_https_cert(ip, Path(args.cert_dir))
        print(f"HTTPS certificate: {cert_path}", flush=True)
    print(f"Local:   {scheme}://127.0.0.1:{args.port}", flush=True)
    print(f"Network: {scheme}://{ip}:{args.port}", flush=True)
    print("Keep this window open while browser cashier clients are using POS.", flush=True)

    uvicorn.run(
        "server.api:app",
        host=args.host,
        port=args.port,
        reload=False,
        ssl_certfile=str(cert_path) if cert_path else None,
        ssl_keyfile=str(key_path) if key_path else None,
    )


if __name__ == "__main__":
    main()
