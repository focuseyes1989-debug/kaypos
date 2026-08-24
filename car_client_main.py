"""Run the standalone KAY Car Management client."""

import sys

from PyQt6.QtWidgets import QApplication

from car_client.window import CarClientWindow, apply_app_identity


def main() -> int:
    from utils.single_instance import SingleInstanceGuard, show_already_running_message

    # Keep Car Management to one running instance per computer. This uses a
    # different mutex from KAY POS, so both applications may run together.
    instance_guard = SingleInstanceGuard(r"Global\KAY_Car_Management_SingleInstance_v1")
    if not instance_guard.acquire():
        show_already_running_message(
            title="KAY Car Management",
            message="KAY Car Management is already running on this computer.",
        )
        return 0

    app = QApplication(sys.argv)
    apply_app_identity(app)
    window = CarClientWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
