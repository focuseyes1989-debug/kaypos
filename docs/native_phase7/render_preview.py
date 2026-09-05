"""Preview fixture data only; never connect a server, device or production DB."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tempfile
from unittest.mock import Mock, patch

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QFontDatabase, QFont
from PyQt6.QtWidgets import QApplication
from native_pos.data import Session, ServerStore, Target
from native_pos.theme import NativeTheme
from native_pos.window import NativeWindow
from native_pos.admin import EmployeeForm
from native_pos.admin_schema import EMPLOYEE_FIELDS
from tests.test_native_pos_phase7 import AdminDatabaseTests


def main():
    app = QApplication([]); app.setQuitOnLastWindowClosed(False)
    families = QFontDatabase.applicationFontFamilies(QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf'))
    if families: app.setFont(QFont(families[0], 10))
    output = Path(__file__).resolve().parent; fixture = AdminDatabaseTests(); fixture.setUp()
    try:
        fixture.command('employee.payroll.save', dict(employee_id=1, period_month='2026-09', basic_salary=500000, allowance=30000, late_deduction=5000))
        with tempfile.TemporaryDirectory() as folder:
            window = NativeWindow(NativeTheme(app), Path(folder) / 'config.json')
            with patch.object(window, 'screen') as screen:
                screen.return_value.availableGeometry.return_value = QRect(0, 0, 1366, 728); window._fit_display()
            window.session = Session(1, 'admin', 'Demo Administrator', 'Admin', frozenset())
            window.store = ServerStore(Target('Server', server_url='https://offline-preview.invalid'))
            api = Mock(); api.server_url = 'https://offline-preview.invalid'
            api._request.side_effect = RuntimeError('Preview must never make API calls')
            window.store.client = api; window.populate_routes()
            for page in window.route_pages.values():
                if hasattr(page, 'loaded'): page.loaded = True
            window.identity.setText('Demo Admin · Admin\nOffline fixture · 1366 × 768 display baseline')
            window.show(); app.processEvents()
            for route, section, name in [(11, 'employees', 'employees-light.png'), (11, 'payroll', 'payroll-light.png'), (13, 'general', 'settings-light.png'), (14, 'users', 'users-light.png')]:
                page = window.route_pages[route]; page.section.blockSignals(True)
                page.section.setCurrentIndex(page.section.findData(section)); page.section.blockSignals(False)
                page.received(fixture.read(section)); window.navigate(route); app.processEvents()
                window.grab().save(str(output / name))
            window.navigate(11); page = window.route_pages[11]; page.section.blockSignals(True); page.section.setCurrentIndex(0); page.section.blockSignals(False)
            page.received(fixture.read('employees'))
            form = EmployeeForm('Employee profile', EMPLOYEE_FIELDS, page.data, page.records[0], window)
            form.show(); app.processEvents(); form.grab().save(str(output / 'employee-form.png')); form.close()
            from native_pos.files import AttachmentDialog
            from native_pos.receipt import ReceiptDialog
            from server.native_files import FilesRepository
            from tests.test_native_pos_files import png
            import types, base64
            from uuid import uuid4
            files = FilesRepository(types.SimpleNamespace(**fixture.scope), fixture.employee)
            asset = files.read(fixture.user, 'photo', 1)
            files.command(fixture.user, str(uuid4()), 'photo.save', dict(kind='photo', id=1, revision=asset['revision'], filename='fixture.jpg', content=base64.b64encode(png()).decode()))
            asset = files.read(fixture.user, 'photo', 1)
            dialog = AttachmentDialog(window, 'photo', 1, asset, window)
            dialog.show(); app.processEvents(); dialog.grab().save(str(output / 'employee-photo.png')); dialog.close()
            receipt = ReceiptDialog(dict(invoice_no='PREVIEW-ONLY', items=[dict(product_name='Fixture item', qty=1, price=1000, total=1000)], total=1000,
                                         receipt_settings=dict(shop_name='KAY POS · Fixture', shop_logo_image='data:image/png;base64,' + asset['content'])), window)
            receipt.show(); app.processEvents(); receipt.grab().save(str(output / 'receipt-image.png')); receipt.close()
            from native_pos.printing import PrinterSettingsDialog
            with patch('native_pos.printing.QPrinterInfo.availablePrinterNames', return_value=['Fixture thermal printer']):
                printer_dialog = PrinterSettingsDialog(window, window)
                printer_dialog.paper.setCurrentText('80mm'); printer_dialog.show(); app.processEvents()
                printer_dialog.grab().save(str(output / 'printer-settings.png')); printer_dialog.close()
            from native_pos.network_print import NetworkPrinterDialog
            network_dialog = NetworkPrinterDialog(window, window)
            network_dialog.server.setText('https://offline-preview.invalid'); network_dialog.agent.setText('fixture-agent'); network_dialog.printer.setText('Fixture thermal printer')
            network_dialog.show(); app.processEvents(); network_dialog.grab().save(str(output / 'network-printer.png')); network_dialog.close()
            from server.native_database import DatabaseRepository
            from native_pos.database_diagnostics import DatabaseDiagnosticsDialog
            diagnostics = DatabaseDiagnosticsDialog(window, window)
            diagnostics.integrity.setChecked(True)
            diagnostics.received(DatabaseRepository(types.SimpleNamespace(**fixture.scope)).read(fixture.user, True))
            diagnostics.show(); app.processEvents(); diagnostics.grab().save(str(output / 'database-diagnostics.png')); diagnostics.close()
            from server.native_telegram import TelegramRepository
            from native_pos.integrations import TelegramSettingsDialog
            telegram_data = TelegramRepository(types.SimpleNamespace(**fixture.scope), Path(folder) / 'fixture-server.env', {}).read(fixture.user)
            telegram_dialog = TelegramSettingsDialog(telegram_data, window)
            telegram_dialog.show(); app.processEvents(); telegram_dialog.grab().save(str(output / 'telegram-settings.png')); telegram_dialog.close()
            from server.native_cloud_config import CloudConfigRepository
            from native_pos.integrations import CloudSettingsDialog
            cloud_data = CloudConfigRepository(types.SimpleNamespace(**fixture.scope), Path(folder) / 'fixture-server.env', {}).read(fixture.user)
            cloud_dialog = CloudSettingsDialog(cloud_data, window)
            cloud_dialog.show(); app.processEvents(); cloud_dialog.grab().save(str(output / 'cloud-settings.png')); cloud_dialog.close()
            integrations = window.route_pages[18]
            integrations.received({'records': [
                dict(service='Telegram', configured=True, enabled=True, detail='Fixture configuration; no live request.'),
                dict(service='Cloud sync', configured=True, enabled=False, detail='Manual sync/pull uses explicit confirmation.'),
                dict(service='YouTube', configured=True, enabled=True, detail='Playback stays in the original customer display.'),
            ]})
            integrations.cloud_operations.message = 'Effective destination fixture.cloud.invalid:5432 / pos; no operation was run.'
            integrations.update_enabled(); window.navigate(18); app.processEvents(); window.grab().save(str(output / 'cloud-operations.png'))
            from server.native_assistant import AssistantRepository
            from server.native_backup import BackupRepository
            from uuid import uuid4
            import json
            asset_root = Path(folder) / 'managed-assets'; (asset_root / 'images').mkdir(parents=True)
            (asset_root / 'images' / 'fixture.txt').write_text('Disposable preview asset', encoding='utf-8')
            backup_repo = BackupRepository(types.SimpleNamespace(**fixture.scope), Path(folder) / 'backups', asset_root)
            snapshot = backup_repo.create(fixture.user, str(uuid4()))
            backup_page = window.route_pages[17]
            backup_page.received(backup_repo.read(fixture.user)); backup_page.table.selectRow(0)
            backup_page.details.setPlainText(json.dumps(backup_repo.verify(fixture.user, snapshot['name'], snapshot['sha256']), indent=2))
            window.navigate(17); app.processEvents(); window.grab().save(str(output / 'backup-verification.png'))
            package = backup_repo.package(fixture.user, str(uuid4()))
            backup_page.received(backup_repo.read(fixture.user))
            package_index = next(i for i, record in enumerate(backup_page.records) if record['name'] == package['name'])
            backup_page.table.selectRow(package_index)
            backup_page.details.setPlainText(json.dumps(backup_repo.rehearse(fixture.user, package['name'], package['sha256']), indent=2))
            app.processEvents(); window.grab().save(str(output / 'backup-package-rehearsal.png'))
            from native_pos.updates import UpdateCheckDialog
            update_dialog = UpdateCheckDialog(window)
            update_dialog.received(dict(local='1.0.0', published='1.1.0', status='Fixture: a newer package version is published.', source='Preview fixture; no network request', notes='Example package release notes.'))
            update_dialog.show(); app.processEvents(); update_dialog.grab().save(str(output / 'update-information.png')); update_dialog.close()
            from native_pos.saved_questions import QuestionStore, SavedQuestionsDialog
            questions = SavedQuestionsDialog(QuestionStore(Path(folder) / 'questions', 'preview'), 'today sales', window)
            questions.name.setText('Today sales'); questions.save(); questions.show(); app.processEvents()
            questions.grab().save(str(output / 'saved-questions.png')); questions.close()
            from native_pos.error_diagnostics import ErrorDiagnosticsDialog
            error_dialog = ErrorDiagnosticsDialog(window)
            error_dialog.input.setPlainText('OperationalError: database is locked')
            error_dialog.analyze(); error_dialog.show(); app.processEvents()
            error_dialog.grab().save(str(output / 'error-diagnostics.png')); error_dialog.close()
            assistant = window.route_pages[8]
            assistant.received(AssistantRepository(types.SimpleNamespace(**fixture.scope), fixture.employee).ask(fixture.user, 'digest 2026-09-01 2026-09-04'))
            window.navigate(8); app.processEvents(); window.grab().save(str(output / 'sales-digest.png'))
            assistant.received(AssistantRepository(types.SimpleNamespace(**fixture.scope), fixture.employee).ask(fixture.user, 'report reports/credit 2026-09-01 2026-09-04'))
            window.navigate(8); app.processEvents(); window.grab().save(str(output / 'assistant-reports.png')); window.navigate(11)
            window.config.update(style='Fusion', palette='Dark'); window.theme.apply(window.config)
            app.processEvents(); window.grab().save(str(output / 'employees-dark.png'))
            window.close(); app.processEvents()
    finally: fixture.doCleanups()


if __name__ == '__main__': main()
