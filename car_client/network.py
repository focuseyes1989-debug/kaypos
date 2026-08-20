"""Small line-delimited JSON client for the LAN Car Management service."""

from __future__ import annotations

import json
import socket
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from car_client.config import ServerSettings
from car_client.offline_store import OfflineCarStore


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
        self.offline = OfflineCarStore()
        self.last_mode = "unknown"

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

    def _cloud_request(self, request_type: str, data=None) -> dict:
        if not self.settings.cloud_url:
            raise CarConnectionError("Cloud service is not configured.")
        body = json.dumps({"type": str(request_type).upper(), "data": data}, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.settings.cloud_url}/api/car/request",
            data=body,
            headers={"Content-Type": "application/json", "X-Car-API-Key": self.settings.cloud_api_key},
            method="POST",
        )
        try:
            # Cloud hosts and remote PostgreSQL can take longer than the LAN,
            # especially while a free instance is warming up or returning a
            # large initial record set.
            with urlopen(request, timeout=max(self.settings.timeout, 30)) as response:
                result = json.loads(response.read(MAX_RESPONSE_BYTES).decode("utf-8"))
        except HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("detail")
            except Exception:
                detail = None
            raise CarProtocolError(str(detail or f"Cloud server rejected the request ({exc.code}).")) from exc
        except (URLError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise CarConnectionError(f"Could not connect to the cloud Car service: {exc}") from exc
        if result.get("status") != "SUCCESS":
            raise CarProtocolError(str(result.get("message") or "Cloud server request failed."))
        return result

    def _online_request(self, request_type: str, data=None) -> dict:
        try:
            result = self.request(request_type, data, retries=1)
            self.last_mode = "lan"
            return result
        except CarConnectionError as lan_error:
            if not self.settings.cloud_url:
                raise lan_error
            result = self._cloud_request(request_type, data)
            self.last_mode = "cloud"
            return result

    def _sync_pending(self) -> int:
        synced = 0
        for item in self.offline.pending():
            payload = dict(item["payload"])
            operation = item["operation"]
            if operation == "SAVE_DATA":
                payload.pop("id", None)
            self._online_request(operation, payload)
            self.offline.complete(item["queue_id"])
            synced += 1
        if synced:
            records = list(self._online_request("GET_DATA").get("data") or [])
            self.offline.replace_cache(records)
        return synced

    def test_connection(self) -> None:
        # A unique search validates both the TCP service and its database access
        # without downloading the existing car records.
        self._online_request("SEARCH_DATA", f"__connection_test_{uuid.uuid4().hex}__")
        self._sync_pending()

    def save_car(self, data: dict) -> None:
        try:
            self._sync_pending()
            self._online_request("SAVE_DATA", data)
        except CarConnectionError:
            if not self.settings.offline_enabled:
                raise
            self.last_mode = "offline"
            self.offline.queue_save(data)

    def get_cars(self) -> list[dict]:
        try:
            self._sync_pending()
            records = list(self._online_request("GET_DATA").get("data") or [])
            self.offline.replace_cache(records)
            return records
        except CarConnectionError:
            if not self.settings.offline_enabled:
                raise
            self.last_mode = "offline"
            return self.offline.all()

    def search_cars(self, term: str) -> list[dict]:
        term = str(term or "").strip()
        if not term:
            return self.get_cars()
        try:
            self._sync_pending()
            return list(self._online_request("SEARCH_DATA", term).get("data") or [])
        except CarConnectionError:
            if not self.settings.offline_enabled:
                raise
            self.last_mode = "offline"
            return self.offline.search(term)

    def update_car(self, data: dict) -> None:
        try:
            self._sync_pending()
            self._online_request("UPDATE_DATA", data)
        except CarConnectionError:
            if not self.settings.offline_enabled:
                raise
            self.last_mode = "offline"
            if int(data.get("id") or 0) < 0:
                raise CarProtocolError("A newly-created offline record must sync before it can be edited.")
            self.offline.queue_update(data)

    def delete_car(self, record_id: int) -> None:
        try:
            self._sync_pending()
            self._online_request("DELETE_DATA", {"id": int(record_id)})
        except CarConnectionError:
            if not self.settings.offline_enabled:
                raise
            self.last_mode = "offline"
            if int(record_id) < 0:
                raise CarProtocolError("A newly-created offline record must sync before it can be deleted.")
            self.offline.queue_delete(record_id)
