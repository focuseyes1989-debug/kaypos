"""Run the standalone KAY Car Management client."""

import sys

from PyQt6.QtWidgets import QApplication

from car_client.window import CarClientWindow, apply_app_identity


def main() -> int:
    app = QApplication(sys.argv)
    apply_app_identity(app)
    window = CarClientWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
