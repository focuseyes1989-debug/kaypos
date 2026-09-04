"""Native report previews from a disposable database; no network or printing."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import tempfile
from unittest.mock import Mock, patch

from PyQt6.QtCore import QDate, QRect, QEventLoop, QTimer
from PyQt6.QtGui import QFontDatabase, QFont
from PyQt6.QtWidgets import QApplication
from native_pos.data import Session, ServerStore, Target
from native_pos.theme import NativeTheme
from native_pos.window import NativeWindow
from native_pos.reports import ReportPreview
from native_pos.report_export import report_html
from tests.test_native_pos_phase6 import ReportDatabaseTests


def main():
    app=QApplication([]);app.setQuitOnLastWindowClosed(False)
    families=QFontDatabase.applicationFontFamilies(QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf'))
    if families:app.setFont(QFont(families[0],10))
    output=Path(__file__).resolve().parent;fixture=ReportDatabaseTests();fixture.setUp()
    try:
        with tempfile.TemporaryDirectory() as folder:
            window=NativeWindow(NativeTheme(app),Path(folder)/'config.json')
            with patch.object(window,'screen') as screen:
                screen.return_value.availableGeometry.return_value=QRect(0,0,1366,728);window._fit_display()
            window.session=Session(1,'cashier','Demo Admin','Admin',frozenset())
            window.store=ServerStore(Target('Server',server_url='https://offline-preview.invalid'))
            api=Mock();api.server_url='https://offline-preview.invalid'
            api._request.side_effect=lambda method,path,params:fixture.repo.read(fixture.user,**params)
            window.store.client=api;window.populate_routes()
            for page in window.route_pages.values():
                if hasattr(page,'loaded'):page.loaded=True
            window.identity.setText('Demo Admin · Admin\nOffline fixture data · 1366 × 768 screen baseline')
            window.show();app.processEvents()
            for route,view,name in [(0,'overview','dashboard-light.png'),(1,'items','sales-summary-light.png'),(12,'financial','financial-light.png')]:
                page=window.route_pages[route];page.start.setDate(QDate(2026,9,4));page.end.setDate(QDate(2026,9,4))
                page.view.setCurrentIndex(page.view.findData(view));window.navigate(route);page.refresh()
                loop=QEventLoop();window.runner.idle.connect(loop.quit);QTimer.singleShot(5000,loop.quit);loop.exec()
                app.processEvents();window.grab().save(str(output/name))
            page=window.route_pages[12]
            preview=ReportPreview(report_html(page.data,page.data['tables'][1]),window)
            preview.show();app.processEvents();preview.preview.updatePreview();preview.preview.fitInView();app.processEvents()
            preview.grab().save(str(output/'print-preview.png'));preview.close()
            window.config.update(style='Fusion',palette='Dark');window.theme.apply(window.config)
            app.processEvents();window.grab().save(str(output/'financial-dark.png'))
            window.close();app.processEvents()
    finally:fixture.doCleanups()


if __name__=='__main__':main()
