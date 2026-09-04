"""Start the isolated KAY POS Native Phase 2 preview."""
import ctypes
import sys
from PyQt6.QtWidgets import QApplication
from native_pos.theme import NativeTheme
from native_pos.window import NativeWindow, app_icon
from utils.single_instance import SingleInstanceGuard, show_already_running_message

MUTEX = r'Global\KAY_POS_Native_SingleInstance_v1'

def main():
    guard = SingleInstanceGuard(MUTEX)
    if not guard.acquire():
        show_already_running_message('KAY POS Native','KAY POS Native is already running.')
        return 0
    if sys.platform == 'win32':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('KAY.POSNative')
    app = QApplication(sys.argv)
    app.setApplicationName('KAY POS Native')
    app.setOrganizationName('KAY POS Native')
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)
    window = NativeWindow(NativeTheme(app))
    window.show_login()
    try:
        return app.exec()
    finally:
        guard.release()

if __name__ == '__main__':
    raise SystemExit(main())
