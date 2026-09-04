"""Native administration pages using ordinary Qt tables, forms and dialogs."""
from copy import deepcopy
import csv
from datetime import date
from urllib.parse import urlencode

from PyQt6.QtCore import QDate, Qt, QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QLineEdit, QDateEdit, QDialog, QMessageBox, QFileDialog, QPlainTextEdit)

from native_pos.admin_schema import EMPLOYEE_SECTIONS, SETTINGS
from native_pos.business_dialogs import FormDialog
from native_pos.catalog import CatalogSession
from native_pos.business import safe_csv
from native_pos.sales import table, fill


class EmployeeForm(FormDialog):
    def __init__(self, title, fields, data, record=None, parent=None):
        references = {}
        transformed = []
        record = deepcopy(record or {})
        for key, label, kind, default in fields:
            if kind in ('employee', 'shift', 'user'):
                options = data.get({'employee': 'employees', 'shift': 'shifts', 'user': 'users'}[kind], [])
                pairs = [('', None)] + [(f"{r.get('full_name') or r.get('name') or r.get('username')} [{r.get('employee_no') or r.get('username') or r['id']}]", r['id']) for r in options]
                if record.get(key) and not any(identifier == record[key] for _, identifier in pairs):
                    pairs.append((f'Existing link [{record[key]}]', record[key]))
                references[key] = dict(pairs)
                record[key] = next((name for name, identifier in pairs if identifier == record.get(key)), '')
                kind = tuple(name for name, _ in pairs)
            transformed.append((key, label, kind, default))
        self.references = references
        super().__init__(title, transformed, record, parent)

    def values(self):
        values = super().values()
        for key, options in self.references.items(): values[key] = options.get(values[key])
        return values


class AdminPage(QWidget):
    def __init__(self, host, area):
        super().__init__(); self.host = host; self.area = area; self.loaded = False
        self.data = {}; self.records = []; self.offset = 0; self.ready = False
        if not getattr(host, 'admin_session', None): host.admin_session = CatalogSession(host, 'admin')
        self.channel = host.admin_session
        if not getattr(host, 'files_session', None): host.files_session = CatalogSession(host, 'files')
        self.files_channel = host.files_session
        body = QVBoxLayout(self)
        title = QLabel({'employees': 'Employees', 'settings': 'Settings', 'users': 'Users & Roles', 'activity': 'Activity Log'}[area])
        font = title.font(); font.setBold(True); font.setPointSize(font.pointSize() + 3); title.setFont(font); body.addWidget(title)
        filters = QHBoxLayout(); self.section = QComboBox()
        if area == 'employees':
            for key, (label, permission, *_rest) in EMPLOYEE_SECTIONS.items():
                if host.session.can(permission): self.section.addItem(label, key)
        elif area == 'settings':
            for key in SETTINGS: self.section.addItem(key.title(), key)
        elif area == 'users': self.section.addItem('Users', 'users'); self.section.addItem('Roles', 'roles')
        else: self.section.addItem('Activity log', 'activity')
        self.start = QDateEdit(QDate.currentDate().addDays(1-QDate.currentDate().day())); self.end = QDateEdit(QDate.currentDate())
        for widget in (self.start, self.end): widget.setCalendarPopup(True); widget.setDisplayFormat('yyyy-MM-dd')
        self.search = QLineEdit(); self.search.setPlaceholderText('Filter loaded rows' if area != 'activity' else 'Actor or action')
        self.refresh_button = QPushButton('Refresh'); self.refresh_button.clicked.connect(self.refresh)
        for widget in (self.section, self.start, self.end, self.search, self.refresh_button): filters.addWidget(widget)
        body.addLayout(filters)
        self.status = QLabel(); self.status.setWordWrap(True); self.status.setTextFormat(Qt.TextFormat.PlainText); body.addWidget(self.status)
        self.table = table([]); body.addWidget(self.table, 1)
        self.details = QPlainTextEdit(); self.details.setReadOnly(True); self.details.setMaximumHeight(100); body.addWidget(self.details)
        actions = QHBoxLayout()
        self.new_button = QPushButton('New…'); self.new_button.clicked.connect(self.new)
        self.edit_button = QPushButton('Edit…'); self.edit_button.clicked.connect(self.edit)
        self.special_button = QPushButton('Action…'); self.special_button.clicked.connect(self.special)
        self.file_button = QPushButton('Attachment…'); self.file_button.clicked.connect(self.attachment)
        self.export_button = QPushButton('Export loaded rows CSV…'); self.export_button.clicked.connect(self.export)
        self.recover_button = QPushButton('Recover pending change'); self.recover_button.clicked.connect(self.recover)
        self.previous = QPushButton('Previous'); self.previous.clicked.connect(lambda: self.paging(-100))
        self.next = QPushButton('Next'); self.next.clicked.connect(lambda: self.paging(100))
        for widget in (self.new_button, self.edit_button, self.special_button, self.file_button, self.export_button, self.previous, self.next, self.recover_button): actions.addWidget(widget)
        body.addLayout(actions)
        if area == 'settings':
            self.printer_button = QPushButton('Receipt printer settings · this PC…')
            self.printer_button.clicked.connect(self.printer_settings)
            body.addWidget(self.printer_button)
            self.network_button = QPushButton('Network printer / recover print…'); self.network_button.clicked.connect(self.network_printer)
            body.addWidget(self.network_button)
            self.database_button = QPushButton('Server database diagnostics…'); self.database_button.clicked.connect(self.database_diagnostics)
            body.addWidget(self.database_button)
        self.section.currentIndexChanged.connect(self.section_changed)
        self.start.dateChanged.connect(self.invalidate); self.end.dateChanged.connect(self.invalidate)
        self.search.returnPressed.connect(self.refresh if area == 'activity' else self.render)
        if area != 'activity': self.search.textChanged.connect(self.render)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        self.channel.changed.connect(self.update_enabled); self.channel.saved.connect(self.saved)
        self.files_channel.changed.connect(self.update_enabled); self.files_channel.saved.connect(self.saved)
        host.runner.idle.connect(self.update_enabled)
        self.update_enabled()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.loaded: QTimer.singleShot(0, self.refresh)

    def key(self): return self.section.currentData()

    def invalidate(self, *args):
        self.ready = False; self.records = []; self.data = {}; self.render(); self.update_enabled()

    def section_changed(self):
        self.offset = 0; self.invalidate(); self.refresh()

    def paging(self, change):
        self.offset = max(0, self.offset + change); self.refresh()

    def refresh(self):
        if self.host.runner.busy or self.host.closing or not self.key(): return
        self.loaded = True; self.ready = False; self.records = []; self.render()
        params = dict(section=self.key(), start=self.start.date().toString('yyyy-MM-dd'), end=self.end.date().toString('yyyy-MM-dd'), offset=self.offset,
                      query=self.search.text() if self.area == 'activity' else '')
        self.channel.run(lambda: self.channel.api._request('GET', '/api/native/admin?' + urlencode(params)), self.received, 'Loading administration…')

    def received(self, result):
        self.data = result; self.ready = True
        if self.key() in SETTINGS:
            labels = {field[0]: field[1] for field in SETTINGS[self.key()]}
            self.records = [dict(setting=labels[k], value=v) for k, v in result['values'].items()]
        else: self.records = result.get('records', [])
        self.channel.message = f'{len(self.records)} record(s)'
        self.render(); self.update_enabled()

    def render(self, *args):
        if not hasattr(self, 'table'): return
        query = self.search.text().casefold() if self.area != 'activity' else ''
        self.visible_records = [r for r in self.records if not query or query in ' '.join(str(v) for k, v in r.items() if k != 'revision').casefold()]
        preferred = ['employee_no', 'employee_name', 'full_name', 'name', 'username', 'attendance_date', 'period_month', 'status']
        keys = list(dict.fromkeys(k for r in self.records for k in r if k not in ('revision', 'photo_path', 'photo_data')))
        compact = {
            'employees': ['employee_no', 'full_name', 'phone', 'position', 'department', 'hire_date', 'employment_status'],
            'shifts': ['name', 'start_time', 'end_time', 'break_minutes', 'is_overnight', 'is_active'],
            'assignments': ['employee_name', 'shift_id', 'effective_from', 'effective_to', 'weekly_off_days'],
            'attendance': ['employee_name', 'attendance_date', 'check_in', 'check_out', 'status', 'late_minutes', 'correction_reason'],
            'leave': ['employee_name', 'leave_type', 'start_date', 'end_date', 'days', 'status', 'reason'],
            'payroll': ['payroll_no', 'employee_name', 'period_month', 'basic_salary', 'net_salary', 'status', 'paid_date'],
            'documents': ['employee_name', 'document_type', 'document_no', 'issued_date', 'expiry_date'],
            'advances': ['employee_name', 'advance_date', 'amount', 'repaid_amount', 'status', 'notes'],
            'commission': ['employee_name', 'rate_percent', 'target_amount', 'active'],
            'cash': ['employee_name', 'opened_at', 'opening_cash', 'expected_cash', 'actual_cash', 'difference', 'status'],
            'users': ['username', 'full_name', 'role', 'is_active'],
            'roles': ['name', 'description', 'permissions'],
            'activity': ['created_at', 'username', 'action', 'details'],
        }
        self.columns = [k for k in compact.get(self.key(), [k for k in preferred if k in keys] + [k for k in keys if k not in preferred]) if k in keys]
        self.table.setColumnCount(len(self.columns)); self.table.setHorizontalHeaderLabels([k.replace('_', ' ').title() for k in self.columns])
        money_keys = {'net_salary', 'expected_cash', 'actual_cash', 'difference', 'repaid_amount', 'sales_total', 'discount_total', 'commission_amount'}
        if self.key() in EMPLOYEE_SECTIONS:
            money_keys.update(k for k, _, kind, _ in EMPLOYEE_SECTIONS[self.key()][4] if kind == 'money')
        def displayed(record, key):
            value = record.get(key)
            if value is None: return ''
            return f'{float(value):,.2f}' if key in money_keys else value
        fill(self.table, [[displayed(r, k) for k in self.columns] for r in self.visible_records])
        self.selection_changed()

    def selected(self):
        index = self.table.currentRow()
        return self.visible_records[index] if 0 <= index < len(getattr(self, 'visible_records', [])) else None

    def selection_changed(self):
        if not hasattr(self, 'details'): return
        record = self.selected()
        self.details.setPlainText('\n'.join(f"{k.replace('_', ' ').title()}: {v}" for k, v in (record or {}).items() if k != 'revision'))
        self.update_enabled()

    def update_enabled(self):
        if not hasattr(self, 'recover_button'): return
        busy = self.host.runner.busy or self.channel.busy
        editable = self.ready and not busy and not self.channel.pending and not self.channel.error
        key = self.key(); selected = self.selected()
        manage = EMPLOYEE_SECTIONS[key][3] if key in EMPLOYEE_SECTIONS else 'edit_settings' if key in SETTINGS else 'edit_user'
        allowed = self.host.session and self.host.session.can(manage)
        if key in ('users', 'roles'): allowed = allowed and self.host.session.role.lower() == 'admin'
        self.new_button.setVisible(key in EMPLOYEE_SECTIONS and key != 'performance' or key in ('roles', 'users'))
        self.new_button.setEnabled(bool(editable and allowed))
        self.edit_button.setVisible(key in ('employees', 'shifts', 'assignments', 'attendance', 'commission', 'users', 'roles') or key in SETTINGS)
        self.edit_button.setText('Edit settings…' if key in SETTINGS else 'Edit…')
        self.edit_button.setEnabled(bool(editable and allowed and (selected or key in SETTINGS)))
        special = {'leave': 'Review leave…', 'payroll': 'Pay salary…', 'advances': 'Repay advance…', 'cash': 'Close session…', 'assignments': 'Delete assignment…'}
        self.special_button.setVisible(key in special); self.special_button.setText(special.get(key, 'Action…'))
        self.special_button.setEnabled(bool(editable and allowed and selected))
        self.file_button.setVisible(key in ('employees', 'documents', 'receipt'))
        self.file_button.setText('Logo / QR…' if key == 'receipt' else 'Photo…' if key == 'employees' else 'File…')
        self.file_button.setEnabled(bool(self.ready and not busy and (selected or key == 'receipt')))
        self.export_button.setEnabled(self.ready and not busy and bool(self.records))
        recoverable = (self.channel.pending and not self.channel.error) or (self.files_channel.pending and not self.files_channel.error)
        self.recover_button.setEnabled(bool(recoverable) and not busy)
        for widget in (self.section, self.start, self.end, self.refresh_button): widget.setEnabled(not busy)
        for widget in (self.start, self.end): widget.setVisible(key in ('attendance', 'payroll', 'leave', 'advances', 'performance', 'activity'))
        self.previous.setVisible(self.area == 'activity'); self.next.setVisible(self.area == 'activity')
        self.previous.setEnabled(not busy and self.offset > 0); self.next.setEnabled(not busy and len(self.records) == 100)
        if self.channel.error: message = 'Recovery needs attention: ' + self.channel.error
        elif self.channel.pending: message = 'An administration change is unresolved. Recover it before another edit.'
        else: message = self.channel.message
        files = self.files_channel
        if files.error: message += '\nAttachment recovery needs attention: ' + files.error
        elif files.pending: message += '\nAn attachment change is unresolved. Use Recover pending change before uploading again. ' + files.message
        elif files.message: message += '\n' + files.message
        if key == 'cash': message += '\nExpected cash = opening cash + completed cash sales since opening (original POS rule).'
        if key == 'users': message += '\nDeactivate accounts to preserve their transaction history. Leave the password blank to keep it.'
        self.status.setText(message)
        if hasattr(self, 'printer_button'):
            self.printer_button.setEnabled(bool(not busy and self.host.session and self.host.session.can('edit_settings')))
            self.database_button.setEnabled(bool(not busy and self.host.session and self.host.session.can('edit_settings')))
            self.network_button.setEnabled(bool(not busy and self.host.session and (self.host.session.can('edit_settings') or self.host.session.can('print_receipt'))))

    def network_printer(self):
        if self.host.runner.busy: return
        from native_pos.network_print import NetworkPrinterDialog
        NetworkPrinterDialog(self.host, self).exec()

    def database_diagnostics(self):
        if self.host.runner.busy or not self.host.session.can('edit_settings'): return
        from native_pos.database_diagnostics import DatabaseDiagnosticsDialog
        DatabaseDiagnosticsDialog(self.host, self).exec()

    def printer_settings(self):
        if self.host.runner.busy or not self.host.session.can('edit_settings'): return
        from native_pos.printing import PrinterSettingsDialog
        PrinterSettingsDialog(self.host, self).exec()

    def recover(self):
        (self.files_channel if self.files_channel.pending else self.channel).recover()

    def saved(self, result):
        self.loaded = False
        if self.isVisible(): self.refresh()

    def new(self): self.open_editor(None)
    def edit(self): self.open_editor(self.selected())

    def attachment(self):
        from native_pos.files import open_attachment
        if self.key() == 'receipt':
            from PyQt6.QtWidgets import QInputDialog
            choice, ok = QInputDialog.getItem(self, 'Receipt image', 'Image', ['Logo', 'QR'], 0, False)
            if ok: open_attachment(self, choice.lower())
        elif self.selected(): open_attachment(self, 'photo' if self.key() == 'employees' else 'document', self.selected()['id'])

    def open_editor(self, record):
        if not self.ready or self.channel.pending or self.host.runner.busy: return
        key = self.key()
        if key in EMPLOYEE_SECTIONS:
            fields = EMPLOYEE_SECTIONS[key][4]
            initial = record or {'period_month': date.today().strftime('%Y-%m')}
            dialog = EmployeeForm(self.section.currentText(), fields, self.data, initial, self)
            operation = f'employee.{key}.save'
        elif key in SETTINGS:
            dialog = FormDialog(self.section.currentText(), SETTINGS[key], dict(self.data['values'], revision=self.data['revision']), self)
            operation = 'settings.save'
        elif key == 'roles':
            fields = [('name', 'Role name', 'text', ''), ('description', 'Description', 'text', ''), ('permissions', 'Permissions (comma-separated keys)', 'memo', '')]
            dialog = FormDialog('Role', fields, record, self); operation = 'role.save'
        elif key == 'users':
            fields = ([] if record else [('username', 'Username', 'text', '')]) + [('full_name', 'Full name', 'text', ''), ('role', 'Role', tuple(self.data['roles']), 'Cashier'), ('is_active', 'Active', 'bool', True), ('password', 'Password (blank = keep existing)', 'text', '')]
            dialog = FormDialog('Account · ' + (record or {}).get('username', 'New'), fields, record, self)
            dialog.fields['password'].setEchoMode(QLineEdit.EchoMode.Password); operation = 'user.save'
        else: return
        if dialog.exec() == QDialog.DialogCode.Accepted:
            values = dialog.values()
            if key in SETTINGS: values['section'] = key
            self.channel.submit(operation, values)

    def special(self):
        record = self.selected(); key = self.key()
        if not record or self.channel.pending or self.host.runner.busy: return
        if key == 'assignments':
            if QMessageBox.question(self, 'Delete assignment', 'Delete this shift assignment and recalculate uncorrected attendance?') == QMessageBox.StandardButton.Yes:
                self.channel.submit('employee.assignments.delete', record)
            return
        actions = {
            'leave': ('review', [('status', 'Decision', ('Approved', 'Rejected', 'Cancelled'), 'Approved'), ('review_notes', 'Review notes', 'memo', '')]),
            'payroll': ('pay', [('paid_date', 'Paid date', 'date', ''), ('payment_method', 'Payment method', 'text', 'Cash')]),
            'advances': ('repay', [('amount', 'Repayment amount', 'money', 0)]),
            'cash': ('close', [('actual_cash', 'Counted cash', 'money', 0)]),
        }
        action, fields = actions[key]
        dialog = FormDialog(self.special_button.text(), fields, record, self)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        values = dialog.values()
        review = '\n'.join(f'{k.replace("_", " ").title()}: {v}' for k, v in values.items() if k not in ('id', 'revision'))
        if key == 'payroll': review = f"Pay salary {float(record['net_salary']):,.2f} and create salary expense?\n" + review
        if QMessageBox.question(self, 'Confirm employee change', review) == QMessageBox.StandardButton.Yes:
            self.channel.submit(f'employee.{key}.{action}', values)

    def export(self):
        if not self.ready: return
        path, _ = QFileDialog.getSaveFileName(self, 'Export loaded rows', self.key() + '.csv', 'CSV (*.csv)')
        if path:
            try:
                with open(path, 'w', newline='', encoding='utf-8-sig') as stream:
                    writer = csv.writer(stream); writer.writerow(self.columns)
                    writer.writerows([[safe_csv(r.get(k, '')) for k in self.columns] for r in self.visible_records])
            except OSError as exc: QMessageBox.warning(self, 'Export failed', str(exc))
