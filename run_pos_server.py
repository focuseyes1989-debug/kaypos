"""Run KAY POS browser cashier server on the local network."""

from __future__ import annotations

import argparse
import socket

import uvicorn


def _local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run KAY POS Cashier Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", default=8000, type=int, help="Server port")
    args = parser.parse_args()

    ip = _local_ip()
    print("KAY POS Cashier Server")
    print(f"Local:   http://127.0.0.1:{args.port}")
    print(f"Network: http://{ip}:{args.port}")
    print("Keep this window open while browser cashier clients are using POS.")

    uvicorn.run("server.api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
