from __future__ import annotations

import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from service_job_client.window import ServiceJobClientWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("KAY Service Job Client")
    app.setOrganizationName("KAY")
    window = ServiceJobClientWindow()
    if not window.windowIcon().isNull():
        app.setWindowIcon(window.windowIcon())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

