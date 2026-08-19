"""Small line-delimited JSON client for the LAN Car Management service."""

from __future__ import annotations

import json
import socket
import time
import uuid

from car_client.config import ServerSettings


MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class CarClientError(RuntimeError):
    """Base class for user-facing Car Management client errors."""


class CarConnectionError(CarClientError):
    pass


class CarProtocolError(CarClientError):
    pass


class CarServerClient:
    def __init__(self, settings: ServerSettings):
        self.settings = settings.validated()

    def request(self, request_type: str, data=None, retries: int = 0) -> dict:
        last_error = None
        for attempt in range(max(0, int(retries)) + 1):
            try:
                return self._request_once(request_type, data)
            except CarConnectionError as exc:
                last_error = exc
                if attempt < retries:
                    time.sleep(0.25)
        raise last_error or CarConnectionError("The server request failed.")

    def _request_once(self, request_type: str, data=None) -> dict:
        payload = json.dumps(
            {"type": str(request_type).upper(), "data": data},
            ensure_ascii=False,
        ).encode("utf-8") + b"\n"
        chunks = []
        total = 0
        try:
            with socket.create_connection(
                (self.settings.host, self.settings.port),
                timeout=self.settings.timeout,
            ) as connection:
                connection.settimeout(self.settings.timeout)
                connection.sendall(payload)
                while total < MAX_RESPONSE_BYTES:
                    part = connection.recv(min(65536, MAX_RESPONSE_BYTES - total))
                    if not part:
                        break
                    chunks.append(part)
                    total += len(part)
                    if b"\n" in part:
                        break
        except socket.timeout as exc:
            raise CarConnectionError(
                f"Connection to {self.settings.host}:{self.settings.port} timed out after "
                f"{self.settings.timeout} seconds. Check the LAN/Wi-Fi connection and server status."
            ) from exc
        except (ConnectionError, OSError) as exc:
            raise CarConnectionError(
                f"Could not connect to {self.settings.host}:{self.settings.port}. "
                "Check that KAY POS Server Manager is running and the firewall allows port "
                f"{self.settings.port}."
            ) from exc
        if total >= MAX_RESPONSE_BYTES:
            raise CarProtocolError("The server response exceeded the 8 MB safety limit.")
        raw = b"".join(chunks).split(b"\n", 1)[0]
        if not raw:
            raise CarConnectionError("The server closed the connection without a response. You can retry safely.")
        try:
            response = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CarProtocolError("The server returned an invalid response. Confirm that this is the Car Management service port.") from exc
        if response.get("status") != "SUCCESS":
            raise CarProtocolError(str(response.get("message") or "Server request failed."))
        return response

    def test_connection(self) -> None:
        # A unique search validates both the TCP service and its database access
        # without downloading the existing car records.
        self.request("SEARCH_DATA", f"__connection_test_{uuid.uuid4().hex}__", retries=1)

    def save_car(self, data: dict) -> None:
        self.request("SAVE_DATA", data)

    def get_cars(self) -> list[dict]:
        return list(self.request("GET_DATA", retries=1).get("data") or [])

    def search_cars(self, term: str) -> list[dict]:
        term = str(term or "").strip()
        return self.get_cars() if not term else list(self.request("SEARCH_DATA", term, retries=1).get("data") or [])

    def update_car(self, data: dict) -> None:
        self.request("UPDATE_DATA", data)

    def delete_car(self, record_id: int) -> None:
        self.request("DELETE_DATA", {"id": int(record_id)})
