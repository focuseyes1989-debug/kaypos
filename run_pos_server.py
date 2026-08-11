"""Run KAY POS browser cashier server on the local network."""

from __future__ import annotations

import argparse
import socket

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run KAY POS Cashier Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", default=8000, type=int, help="Server port")
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
    print(f"Local:   http://127.0.0.1:{args.port}", flush=True)
    print(f"Network: http://{ip}:{args.port}", flush=True)
    print("Keep this window open while browser cashier clients are using POS.", flush=True)

    uvicorn.run("server.api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
