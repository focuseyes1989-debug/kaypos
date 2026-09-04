from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog, QDialogButtonBox, QVBoxLayout,
    QHBoxLayout, QFormLayout, QLabel, QLineEdit, QPushButton, QComboBox, QFileDialog,
    QListWidget, QListWidgetItem, QStackedWidget, QSplitter, QToolBar, QStyleFactory,
    QFontComboBox, QSpinBox, QMessageBox, QGroupBox, QCheckBox, QStyle,
)
from native_pos.config import config_path, load_config, save_config
from native_pos.data import Target, open_store, create_practice_database
from native_pos.routes import ROUTES
from native_pos.tasks import TaskRunner


def app_icon():
    return QIcon(str(Path(__file__).resolve().parents[1] / 'assets' / 'kay' / 'kay_multi.ico'))

class LoginDialog(QDialog):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.setWindowTitle('Sign in · KAY POS Native')
        self.setWindowIcon(app_icon())
        self.setModal(True)
        self.setMinimumWidth(540)
        body = QVBoxLayout(self)
        body.setContentsMargins(24,24,24,24)
        title = QLabel('KAY POS Native')
        font = title.font(); font.setPointSize(font.pointSize()+4); font.setBold(True); title.setFont(font)
        body.addWidget(title)
        intro = QLabel('Phase 7 — Native Employees, Settings and Server Operations\nSign in to the existing POS Server.')
        intro.setWordWrap(True); body.addWidget(intro)
        form = QFormLayout(); self.form = form
        self.backend = QComboBox(); self.backend.addItems(['Server','SQLite','PostgreSQL'])
        self.backend.setCurrentText(config['backend'])
        self.server = QLineEdit(config['server_url'])
        self.insecure = QCheckBox('Allow self-signed HTTPS certificate')
        self.insecure.setChecked(config['insecure_tls'])
        self.database = QLineEdit(config['database']); self.database.setPlaceholderText('Select an existing test copy')
        self.browse = QPushButton('Browse…'); self.browse.clicked.connect(self.browse_database)
        row = QHBoxLayout(); row.addWidget(self.database,1); row.addWidget(self.browse); self.database_row = row
        self.schema = QLineEdit(config['schema'])
        self.username = QLineEdit(config['username'])
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow('Connection',self.backend); form.addRow('Server URL',self.server)
        form.addRow(self.insecure); form.addRow('SQLite file',row)
        form.addRow('PostgreSQL test schema',self.schema)
        form.addRow('Username',self.username); form.addRow('Password',self.password)
        body.addLayout(form)
        self.target_hint = QLabel(); self.target_hint.setWordWrap(True); self.target_hint.setTextFormat(Qt.TextFormat.PlainText)
        body.addWidget(self.target_hint)
        self.status = QLabel(''); self.status.setWordWrap(True); self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setMinimumHeight(38); body.addWidget(self.status)
        self.create = QPushButton('Create Practice File…')
        self.test = QPushButton('Test Connection')
        self.sign_in = QPushButton('Sign In'); self.sign_in.setDefault(True)
        self.cancel = QPushButton('Cancel'); self.cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        for button in (self.create,self.test,self.sign_in,self.cancel): buttons.addWidget(button)
        body.addLayout(buttons)
        self.backend.currentTextChanged.connect(self.update_target)
        self.server.textChanged.connect(self.update_target)
        self.database.textChanged.connect(self.update_target); self.schema.textChanged.connect(self.update_target)
        self.update_target()
    def target(self):
        return Target(self.backend.currentText(),self.database.text().strip(),self.schema.text().strip(),self.server.text().strip(),self.insecure.isChecked())
    def update_target(self):
        backend = self.backend.currentText()
        sqlite, server = backend == 'SQLite', backend == 'Server'
        self.form.setRowVisible(self.server, server)
        self.form.setRowVisible(self.insecure, server)
        self.form.setRowVisible(self.database_row, sqlite)
        self.form.setRowVisible(self.schema, backend == 'PostgreSQL')
        self.create.setVisible(sqlite)
        self.database.setEnabled(sqlite); self.browse.setEnabled(sqlite); self.create.setEnabled(sqlite)
        self.schema.setEnabled(backend == 'PostgreSQL')
        if server:
            self.target_hint.setText('Sign in with your existing POS Lite server account.\nServer: ' + self.server.text().strip())
        else:
            self.target_hint.setText('Read-only target: ' + self.target().label +
                ('\nUse a test copy, or create a new practice file.' if sqlite else '\nConnection comes from NATIVE_POS_TEST_DATABASE_URL. Credentials are not saved.'))
    def browse_database(self):
        path,_ = QFileDialog.getOpenFileName(self,'Select test database',self.database.text(),'SQLite (*.db *.sqlite *.sqlite3);;All files (*)')
        if path: self.database.setText(path)
    def set_busy(self, busy, message=''):
        self.setProperty('busy',busy)
        for widget in (self.backend,self.server,self.insecure,self.database,self.browse,self.schema,self.username,self.password,self.create,self.test,self.sign_in):
            widget.setEnabled(not busy)
        if not busy: self.update_target()
        self.status.setText(message)
    def reject(self):
        # The controller owns graceful shutdown; never destroy a running QThread.
        super().reject()

class AppearanceDialog(QDialog):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.setWindowTitle('Native Appearance')
        form = QFormLayout(self)
        self.style = QComboBox(); self.style.addItems(['System']+list(QStyleFactory.keys())); self.style.setCurrentText(config['style'])
        self.palette = QComboBox(); self.palette.addItems(['System','Light','Dark']); self.palette.setCurrentText(config['palette'])
        self.family = QFontComboBox(); self.family.setCurrentFont(QFont(config['font_family']) if config['font_family'] else QApplication.font())
        self.size = QSpinBox(); self.size.setRange(8,20); self.size.setValue(config['font_size'])
        for name,widget in [('Qt style',self.style),('Palette',self.palette),('Font',self.family),('Font size',self.size)]: form.addRow(name,widget)
        note = QLabel('Light and Dark use Fusion for consistent colors. System uses the available platform style.\nThese preferences apply only to KAY POS Native.')
        note.setWordWrap(True); form.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)
    def values(self):
        return dict(style=self.style.currentText(),palette=self.palette.currentText(),font_family=self.family.currentFont().family(),font_size=self.size.value())

class NativeWindow(QMainWindow):
    def __init__(self, theme, settings_path=None):
        super().__init__()
        self.settings_path = settings_path
        self.config = load_config(settings_path)
        self.theme = theme
        self.theme.apply(self.config)
        self.setWindowTitle('KAY POS Native · Phase 7')
        self.setWindowIcon(app_icon())
        self._fit_display()
        self.session = self.store = self.pending_store = None
        self.closing = False
        self.runner = TaskRunner(self); self.runner.idle.connect(self._finish_close)
        self._build_shell()
        self.login_dialog = LoginDialog(self,self.config)
        self.login_dialog.sign_in.clicked.connect(self.login)
        self.login_dialog.test.clicked.connect(self.test_connection)
        self.login_dialog.create.clicked.connect(self.create_practice)
        self.login_dialog.rejected.connect(self.close)

    def _fit_display(self):
        # 1366x768 is the supported screen baseline, not a client-area size
        # that would extend behind the Windows title bar or taskbar.
        screen = self.screen()
        available = screen.availableGeometry() if screen else None
        border = max(4, self.style().pixelMetric(QStyle.PixelMetric.PM_DefaultFrameWidth) * 2)
        title = self.style().pixelMetric(QStyle.PixelMetric.PM_TitleBarHeight)
        width = max(1, available.width() - border) if available else 1366
        height = max(1, available.height() - title - border) if available else 768
        self.setMinimumSize(min(1366,width),min(768,height))
        self.resize(min(self.config['width'],width),min(self.config['height'],height))

    def _build_shell(self):
        file_menu = self.menuBar().addMenu('&File')
        self.logout_action = QAction('Sign Out',self); self.logout_action.triggered.connect(self.logout); file_menu.addAction(self.logout_action)
        exit_action = QAction('Exit',self); exit_action.triggered.connect(self.close); file_menu.addAction(exit_action)
        self.view_menu = self.menuBar().addMenu('&Pages')
        settings = self.menuBar().addMenu('&Appearance')
        appearance = QAction('Style, palette and font…',self); appearance.triggered.connect(self.appearance); settings.addAction(appearance)
        help_menu = self.menuBar().addMenu('&Help')
        info = QAction('Phase 7 status',self)
        info.triggered.connect(lambda: QMessageBox.information(self,'KAY POS Native','Phase 7: Employees, Settings, Users, Devices, Backup, Native Assistant and Telegram/cloud server-file editing.\nUpdate/restart the POS Server for these features.\nAdvanced AI diagnostics, cloud sync/pull, PostgreSQL restore and live device checks are pending.'))
        help_menu.addAction(info)
        toolbar = QToolBar('Workspace',self); toolbar.setMovable(False); self.addToolBar(toolbar)
        self.refresh_action = QAction('Refresh access',self); self.refresh_action.setShortcut('F5'); self.refresh_action.triggered.connect(self.refresh_access)
        toolbar.addAction(self.refresh_action); toolbar.addAction(appearance); toolbar.addAction(self.logout_action)
        self.cashier_action = QAction('Cashier mode', self); self.cashier_action.setCheckable(True)
        self.cashier_action.setShortcut('Ctrl+Shift+C'); self.cashier_action.setEnabled(False)
        self.cashier_action.toggled.connect(self.cashier_mode); toolbar.addAction(self.cashier_action)
        root = QWidget(); layout = QVBoxLayout(root)
        self.identity = QLabel(); self.identity.setTextFormat(Qt.TextFormat.PlainText); layout.addWidget(self.identity)
        self.banner = QLabel('Phase 7 · Employees, Settings and Server Operations · Standard Qt widgets'); layout.addWidget(self.banner)
        split = QSplitter()
        self.navigation = QListWidget(); self.navigation.setMinimumWidth(165)
        self.pages = QStackedWidget()
        split.addWidget(self.navigation); split.addWidget(self.pages); split.setStretchFactor(1,1)
        layout.addWidget(split,1); self.setCentralWidget(root)
        self.navigation.currentItemChanged.connect(self._selection_changed)
        self.route_pages = {}
        self.statusBar().showMessage('Signed out')

    def show_login(self):
        if self.closing: return
        self.login_dialog.password.clear()
        self.login_dialog.set_busy(False)
        self.login_dialog.show()
        screen = self.screen()
        if screen:
            frame = self.login_dialog.frameGeometry(); frame.moveCenter(screen.availableGeometry().center()); self.login_dialog.move(frame.topLeft())
        self.login_dialog.raise_(); self.login_dialog.activateWindow(); self.login_dialog.username.setFocus()

    def _remember_target(self):
        d = self.login_dialog
        self.config.update(backend=d.backend.currentText(),database=d.database.text().strip(),schema=d.schema.text().strip(),username=d.username.text().strip(),server_url=d.server.text().strip(),insecure_tls=d.insecure.isChecked())
        self._save()
    def _save(self):
        try:
            save_config(self.config,self.settings_path)
        except OSError:
            self.statusBar().showMessage('Could not save Native preferences; this session remains usable.')

    def _task(self, operation, success, message):
        if self.runner.busy or self.closing: return
        self.login_dialog.set_busy(True,message)
        self.refresh_action.setEnabled(False); self.logout_action.setEnabled(False)
        def finished(result=None,error=None):
            self.refresh_action.setEnabled(True); self.logout_action.setEnabled(True)
            if self.closing: return
            self.login_dialog.set_busy(False,error or '')
            if error:
                self.statusBar().showMessage(error)
            else:
                success(result)
        self.runner.start(operation,lambda value: finished(result=value),lambda error: finished(error=error))

    def test_connection(self):
        if self.runner.busy or self.closing: return
        store = open_store(self.login_dialog.target())
        def operation():
            try:
                return store.diagnose()
            finally:
                if hasattr(store,'close'): store.close()
        def connected(message):
            self._remember_target(); self.login_dialog.status.setText(message)
        self._task(operation,connected,'Testing connection…')

    def create_practice(self):
        if self.runner.busy: return
        d = self.login_dialog
        username,password = d.username.text().strip(),d.password.text()
        if not username or len(password)<8:
            d.status.setText('Enter a username and practice password (at least 8 characters) first.'); return
        path,_ = QFileDialog.getSaveFileName(d,'Create NEW practice database',str(config_path().parent/'practice.db'),'SQLite (*.db)')
        if not path: return
        def created(database):
            d.database.setText(database); self._remember_target()
            d.status.setText('Practice file created. Sign in with the credentials you just entered.')
        self._task(lambda: create_practice_database(path,username,password),created,'Creating new practice file…')

    def login(self):
        if self.runner.busy or self.closing: return
        d = self.login_dialog
        username,password = d.username.text().strip(),d.password.text()
        store = open_store(d.target())
        self.pending_store = store
        def accepted(session):
            self.session,self.store = session,store
            self.pending_store = None
            self._remember_target(); d.password.clear()
            self.populate_routes(); self.show(); d.accept()
        def authenticate():
            try:
                return store.authenticate(username,password)
            except Exception:
                if hasattr(store,'close'): store.close()
                raise
        self._task(authenticate,accepted,'Signing in…')

    def populate_routes(self):
        previous = self.navigation.currentItem().data(Qt.ItemDataRole.UserRole) if self.navigation.currentItem() else None
        self.navigation.blockSignals(True); self.navigation.clear(); self.view_menu.clear()
        while self.pages.count():
            page = self.pages.widget(0); self.pages.removeWidget(page); page.deleteLater()
        self.route_pages = {}
        if getattr(self, 'catalog_session', None): self.catalog_session.deleteLater()
        self.catalog_session = None
        if getattr(self, 'business_session', None): self.business_session.deleteLater()
        self.business_session = None
        if getattr(self, 'admin_session', None): self.admin_session.deleteLater()
        self.admin_session = None
        for attribute in ('operations_session', 'backups_session', 'files_session', 'telegram_session', 'cloud_config_session'):
            if getattr(self, attribute, None): getattr(self, attribute).deleteLater()
            setattr(self, attribute, None)
        for route in ROUTES:
            if not self.session.can(route.permission): continue
            item = QListWidgetItem(route.title); item.setData(Qt.ItemDataRole.UserRole,route.id); self.navigation.addItem(item)
            page = QWidget(); body = QVBoxLayout(page)
            title = QLabel(route.title); font=title.font(); font.setPointSize(font.pointSize()+4); font.setBold(True); title.setFont(font); body.addWidget(title)
            group = QGroupBox('Migration status'); form = QFormLayout(group)
            form.addRow('Availability',QLabel(f'Planned for Phase {route.phase}'))
            form.addRow('Current version',QLabel('Use the existing KAY POS for this operation.'))
            body.addWidget(group); body.addStretch()
            if route.id == 5 and self.store.target.backend == 'Server':
                from native_pos.sales import SalesPage
                page.deleteLater()
                page = SalesPage(self)
            elif route.id in (2, 9, 3) and self.store.target.backend == 'Server':
                from native_pos.catalog import CatalogPage
                page.deleteLater()
                page = CatalogPage(self, {2: 'products', 9: 'discounts', 3: 'inventory'}[route.id])
            elif route.id in (4, 6, 7, 10) and self.store.target.backend == 'Server':
                from native_pos.business import BusinessPage
                page.deleteLater()
                page = BusinessPage(self, {4: 'receipts', 6: 'customers', 7: 'expenses', 10: 'restaurant'}[route.id])
            elif route.id in (0, 1, 12) and self.store.target.backend == 'Server':
                from native_pos.reports import ReportPage
                page.deleteLater()
                page = ReportPage(self, {0: 'dashboard', 1: 'summary', 12: 'reports'}[route.id])
            elif route.id in (11, 13, 14, 15) and self.store.target.backend == 'Server':
                from native_pos.admin import AdminPage
                page.deleteLater()
                page = AdminPage(self, {11: 'employees', 13: 'settings', 14: 'users', 15: 'activity'}[route.id])
            elif route.id in (16, 17) and self.store.target.backend == 'Server':
                from native_pos.operations import OperationsPage
                page.deleteLater()
                page = OperationsPage(self, 'devices' if route.id == 16 else 'backups')
            elif route.id == 8 and self.store.target.backend == 'Server':
                from native_pos.assistant import AssistantPage
                page.deleteLater()
                page = AssistantPage(self)
            elif route.id == 18 and self.store.target.backend == 'Server':
                from native_pos.integrations import IntegrationsPage
                page.deleteLater()
                page = IntegrationsPage(self)
            self.route_pages[route.id] = page; self.pages.addWidget(page)
            action = QAction(route.title,self); action.triggered.connect(lambda checked=False,rid=route.id:self.navigate(rid)); self.view_menu.addAction(action)
        if not self.route_pages:
            empty=QLabel('No page permissions were returned for this account. Check permissions with your administrator. For older servers, update and restart the POS Server, then sign in again.')
            empty.setWordWrap(True); self.pages.addWidget(empty)
        self.navigation.blockSignals(False)
        self.cashier_action.setEnabled(5 in self.route_pages)
        self.identity.setText(f'{self.session.full_name} · {self.session.role}\n{self.store.target.label}')
        self.statusBar().showMessage('KAY POS Native · Background services stay on the existing server')
        if self.navigation.count():
            self.navigate(previous if previous in self.route_pages else 5 if 5 in self.route_pages else self.navigation.item(0).data(Qt.ItemDataRole.UserRole))

    def navigate(self, route_id):
        route = next((r for r in ROUTES if r.id==route_id),None)
        if not self.session or not route or not self.session.can(route.permission) or route_id not in self.route_pages:
            return False
        for index in range(self.navigation.count()):
            if self.navigation.item(index).data(Qt.ItemDataRole.UserRole)==route_id:
                self.navigation.setCurrentRow(index); break
        self.pages.setCurrentWidget(self.route_pages[route_id]); return True
    def _selection_changed(self, current, previous):
        if current: self.navigate(current.data(Qt.ItemDataRole.UserRole))

    def cashier_mode(self, enabled):
        self.navigation.setVisible(not enabled)
        self.identity.setVisible(not enabled); self.banner.setVisible(not enabled)
        if enabled: self.navigate(5)

    def refresh_access(self):
        # Reauthenticate rather than retain a stale privilege snapshot.
        if self.session and not self.runner.busy:
            self.logout()
            self.login_dialog.status.setText('Sign in again to refresh account permissions.')

    def appearance(self):
        dialog = AppearanceDialog(self,self.config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config.update(dialog.values()); style=self.theme.apply(self.config); self._save()
            self.statusBar().showMessage(f'Native appearance saved · active Qt style: {style}')

    def logout(self):
        if self.runner.busy: return
        if not self._can_leave_sales(): return
        self.cashier_action.setChecked(False); self.cashier_action.setEnabled(False)
        self.config.update(width=self.width(),height=self.height()); self._save()
        if hasattr(self.store,'close'): self.store.close()
        self.session=self.store=None
        self.navigation.clear(); self.view_menu.clear(); self.route_pages={}
        while self.pages.count():
            page=self.pages.widget(0); self.pages.removeWidget(page); page.deleteLater()
        self.identity.clear(); self.show_login(); self.hide()

    def _can_leave_sales(self):
        page = self.route_pages.get(5)
        return page.can_leave() if hasattr(page, 'can_leave') else True

    def closeEvent(self,event):
        if not self.closing and not self._can_leave_sales():
            event.ignore(); return
        self.closing=True
        self.config.update(width=self.width(),height=self.height()); self._save()
        self.login_dialog.hide(); self.hide()
        if self.runner.busy:
            event.ignore(); return
        for store in (self.store,self.pending_store):
            if hasattr(store,'close'): store.close()
        self.store=self.pending_store=None
        event.accept(); QApplication.instance().quit()
    def _finish_close(self):
        if self.closing and not self.runner.busy: self.close()
