"""Start the isolated KAY POS Native Phase 2 preview."""
import ctypes
import os
import sys
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from native_pos.theme import NativeTheme
from native_pos.window import NativeWindow, app_icon
from utils.single_instance import SingleInstanceGuard, show_already_running_message

MUTEX = r'Global\KAY_POS_Native_SingleInstance_v1'

def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    smoke = '--smoke-test' in argv
    guard = SingleInstanceGuard(MUTEX + ('_Smoke' if smoke else ''))
    if not guard.acquire():
        show_already_running_message('KAY POS Native','KAY POS Native is already running.')
        return 0
    if sys.platform == 'win32':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('KAY.POSNative')
    app = QApplication(sys.argv)
    app.setApplicationName('KAY POS Native')
    app.setOrganizationName('KAY POS Native')
    from native_pos.release import metadata
    app.setApplicationVersion(metadata()['version'])
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)
    temporary = tempfile.TemporaryDirectory() if smoke else None
    window = NativeWindow(NativeTheme(app), Path(temporary.name) / 'config.json' if temporary else None)
    window.show_login(); app.processEvents()
    try:
        if smoke:
            valid = window.login_dialog.isVisible() and not window.isVisible() and window.windowTitle() == 'KAY POS Native'
            window.login_dialog.hide(); window.close(); app.processEvents()
            # A frozen, windowed Qt process can remain in DLL teardown after the
            # UI has closed. Smoke mode has no user data, so return its observed
            # result directly to the build process.
            os._exit(0 if valid else 2)
        return app.exec()
    finally:
        guard.release()
        if temporary: temporary.cleanup()

if __name__ == '__main__':
    raise SystemExit(main())
