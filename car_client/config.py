"""Persistent connection settings for the Car Management client."""

from dataclasses import dataclass

from PyQt6.QtCore import QSettings


DEFAULT_HOST = "192.168.110.196"
DEFAULT_PORT = 12345
DEFAULT_TIMEOUT = 5


@dataclass(frozen=True)
class ServerSettings:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    timeout: int = DEFAULT_TIMEOUT

    def validated(self) -> "ServerSettings":
        host = self.host.strip()
        if not host:
            raise ValueError("Server IP or host name is required.")
        if not 1 <= int(self.port) <= 65535:
            raise ValueError("Port must be between 1 and 65535.")
        if not 1 <= int(self.timeout) <= 30:
            raise ValueError("Timeout must be between 1 and 30 seconds.")
        return ServerSettings(host, int(self.port), int(self.timeout))


class SettingsStore:
    def __init__(self, settings: QSettings | None = None):
        self.settings = settings or QSettings("KAY POS", "Car Management Client")

    def load(self) -> ServerSettings:
        return ServerSettings(
            str(self.settings.value("server/host", DEFAULT_HOST)),
            int(self.settings.value("server/port", DEFAULT_PORT)),
            int(self.settings.value("server/timeout", DEFAULT_TIMEOUT)),
        ).validated()

    def save(self, value: ServerSettings) -> ServerSettings:
        value = value.validated()
        self.settings.setValue("server/host", value.host)
        self.settings.setValue("server/port", value.port)
        self.settings.setValue("server/timeout", value.timeout)
        self.settings.sync()
        return value
