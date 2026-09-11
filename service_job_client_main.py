from __future__ import annotations

import sys
import ctypes

from PyQt6.QtWidgets import QApplication, QStyleFactory

from service_job_client.window import ServiceJobClientWindow


def main() -> int:
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("KAY.ServiceJobClient")
    app = QApplication(sys.argv)
    app.setApplicationName("KAY Service Job Client")
    app.setOrganizationName("KAY")
    fusion = QStyleFactory.create("Fusion")
    if fusion is not None:
        app.setStyle(fusion)
        app.setPalette(fusion.standardPalette())
    window = ServiceJobClientWindow()
    if not window.windowIcon().isNull():
        app.setWindowIcon(window.windowIcon())
    window.show_login_dialog()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
