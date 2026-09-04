"""Native device configuration and server backup controls."""
import hashlib
import os
import tempfile
from pathlib import Path
from urllib.parse import quote

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QDialog, QPlainTextEdit, QMessageBox, QFileDialog, QLineEdit)

from native_pos.catalog import CatalogSession
from native_pos.business_dialogs import FormDialog
from native_pos.sales import table, fill


class OperationsPage(QWidget):
    def __init__(self, host, area):
        super().__init__(); self.host = host; self.area = area; self.loaded = False; self.ready = False; self.data = {}; self.records = []
        namespace = 'operations' if area == 'devices' else 'backups'
        attribute = namespace + '_session'
        if not getattr(host, attribute, None): setattr(host, attribute, CatalogSession(host, namespace))
        self.channel = getattr(host, attribute)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('ZKTeco Devices' if area == 'devices' else 'Server Backup / Restore Rehearsal'))
        row = QHBoxLayout(); self.view = QComboBox()
        self.view.addItems(['Devices', 'Employee mappings'] if area == 'devices' else ['Backups'])
        self.view.currentIndexChanged.connect(self.render)
        refresh = QPushButton('Refresh'); refresh.clicked.connect(self.refresh)
        row.addWidget(self.view); row.addStretch(); row.addWidget(refresh); layout.addLayout(row)
        self.notice = QLabel(); self.notice.setWordWrap(True); self.notice.setTextFormat(Qt.TextFormat.PlainText); layout.addWidget(self.notice)
        self.table = table([]); layout.addWidget(self.table, 1)
        self.details = QPlainTextEdit(); self.details.setReadOnly(True); self.details.setMaximumHeight(160); layout.addWidget(self.details)
        actions = QHBoxLayout(); self.buttons = []
        def button(title, handler, permission, selected=False):
            control = QPushButton(title); control.clicked.connect(handler); actions.addWidget(control)
            self.buttons.append((control, permission, selected))
        if area == 'devices':
            button('New…', lambda: self.edit(False), 'edit_settings')
            button('Edit…', lambda: self.edit(True), 'edit_settings', True)
            button('Test device', lambda: self.device_action('device.test'), 'edit_settings', True)
            button('Sync attendance…', lambda: self.device_action('device.sync'), 'manage_attendance', True)
            button('Delete mapping…', lambda: self.device_action('mapping.delete'), 'edit_settings', True)
        else:
            button('Create server snapshot…', self.backup, 'backup')
            button('Download…', self.download, 'backup', True)
            button('Restore separate copy…', self.rehearse, 'restore', True)
        self.recover = QPushButton('Recover pending operation'); self.recover.clicked.connect(self.channel.recover); actions.addWidget(self.recover)
        layout.addLayout(actions)
        self.table.itemSelectionChanged.connect(self.update_enabled)
        self.channel.changed.connect(self.update_enabled); self.channel.saved.connect(self.saved); host.runner.idle.connect(self.update_enabled)
        self.update_enabled()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.loaded: QTimer.singleShot(0, self.refresh)

    def refresh(self):
        if self.host.runner.busy or self.host.closing: return
        self.loaded = True; self.ready = False
        self.channel.run(lambda: self.channel.api._request('GET', '/api/native/' + self.channel.namespace), self.received, 'Loading server operations…')

    def received(self, data):
        self.data = data; self.ready = True; self.channel.message = data.get('message', 'Device communication runs on the POS Server. Native starts no automatic listener.'); self.render()

    def render(self, *args):
        self.records = self.data.get('records' if self.area == 'backups' else 'devices' if self.view.currentIndex() == 0 else 'mappings', [])
        columns = list(dict.fromkeys(k for r in self.records for k in r if k != 'revision'))
        self.table.setColumnCount(len(columns)); self.table.setHorizontalHeaderLabels([k.replace('_', ' ').title() for k in columns])
        fill(self.table, [[r.get(k, '') for k in columns] for r in self.records]); self.update_enabled()

    def selected(self):
        index = self.table.currentRow()
        return self.records[index] if 0 <= index < len(self.records) else None

    def update_enabled(self):
        if not hasattr(self, 'recover'): return
        enabled = self.ready and not self.host.runner.busy and not self.channel.pending and not self.channel.error
        for button, permission, selected in self.buttons:
            allowed = self.host.session and self.host.session.can(permission)
            if self.area == 'devices' and button.text() != 'Test device': allowed = allowed and self.host.session.can('manage_employees')
            button.setEnabled(bool(enabled and allowed and (self.selected() or not selected)))
            if self.area == 'devices':
                mapping = self.view.currentIndex() == 1
                if button.text() in ('Test device', 'Sync attendance…'): button.setVisible(not mapping)
                if button.text() == 'Delete mapping…': button.setVisible(mapping)
        self.recover.setEnabled(bool(self.channel.pending) and not self.host.runner.busy and not self.channel.error)
        self.view.setEnabled(not self.host.runner.busy)
        self.notice.setText(self.channel.error or ('Operation unresolved. Recover the same request before starting another.' if self.channel.pending else self.channel.message))

    def saved(self, result):
        import json
        self.details.setPlainText(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        self.loaded = False
        if self.isVisible(): self.refresh()

    def edit(self, existing):
        record = self.selected() if existing else None
        if existing and not record: return
        if self.view.currentIndex() == 0:
            fields = [('device_no', 'Device number', 'int', 1), ('name', 'Name', 'text', 'ZKTeco'), ('ip_address', 'IP address', 'text', ''),
                      ('port', 'Port', 'int', 4370), ('comm_key', 'Communication key (blank = keep)', 'text', ''), ('is_active', 'Active', 'bool', True)]
            dialog = FormDialog('ZKTeco device', fields, record, self); dialog.fields['comm_key'].setEchoMode(QLineEdit.EchoMode.Password)
            operation = 'device.save'; references = {}
        else:
            devices = {f"{r['device_no']} · {r['name']}": r['id'] for r in self.data.get('devices', [])}
            employees = {f"{r['employee_no']} · {r['full_name']}": r['id'] for r in self.data.get('employees', [])}
            if not devices or not employees: QMessageBox.information(self, 'Mapping', 'Create a device and employee first.'); return
            references = {'device_id': devices, 'employee_id': employees}
            data = dict(record or {})
            for key, values in references.items(): data[key] = next((name for name, value in values.items() if value == data.get(key)), '')
            fields = [('device_id', 'Device', tuple(devices), ''), ('employee_id', 'Employee', tuple(employees), ''), ('device_user_id', 'Device user ID', 'text', '')]
            dialog = FormDialog('Employee mapping', fields, data, self); operation = 'mapping.save'
        if dialog.exec() == QDialog.DialogCode.Accepted:
            values = dialog.values()
            for key, options in references.items(): values[key] = options.get(values[key])
            self.channel.submit(operation, values)

    def device_action(self, operation):
        record = self.selected()
        if not record: return
        message = {'device.test': 'Connect to this device and read its status?', 'device.sync': 'Read attendance for configured employees and import punches? Manual corrections are retained.', 'mapping.delete': 'Delete this employee mapping? Existing attendance history is retained.'}[operation]
        if QMessageBox.question(self, 'Confirm device operation', message) == QMessageBox.StandardButton.Yes: self.channel.submit(operation, record)

    def backup(self):
        if QMessageBox.question(self, 'Create backup', 'Create a database snapshot on the POS Server? External image/document files require a separate file backup.') == QMessageBox.StandardButton.Yes:
            self.channel.submit('backup.create', {})

    def rehearse(self):
        record = self.selected()
        if record and QMessageBox.question(self, 'Restore rehearsal', 'Verify this backup and restore it into a separate server test copy?') == QMessageBox.StandardButton.Yes:
            self.channel.submit('backup.rehearse', record)

    def download(self):
        record = self.selected()
        if not record: return
        path, _ = QFileDialog.getSaveFileName(self, 'Download server snapshot', record['name'], 'Database backups (*.db *.dump)')
        if not path: return
        self.channel.run(lambda: download_backup(self.channel.api, record, path), lambda _: self.details.setPlainText('Backup downloaded and SHA-256 verified: ' + path), 'Downloading backup…')


def download_backup(api, record, destination):
    path = Path(destination)
    descriptor, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.partial', dir=path.parent)
    os.close(descriptor); temporary = Path(name); digest = hashlib.sha256(); size = 0
    try:
        with api.session.get(api.server_url + '/api/native/backups/download/' + quote(record['name'], safe=''),
                headers={'Authorization': 'Bearer ' + api.token}, verify=api.verify_tls, timeout=(12, 60), stream=True, allow_redirects=False) as response:
            response.raise_for_status()
            if response.status_code != 200: raise ValueError('Unexpected backup download response')
            with temporary.open('wb') as stream:
                for block in response.iter_content(1024 * 1024):
                    size += len(block)
                    if size > record['size']: raise ValueError('Backup size changed; refresh before downloading')
                    digest.update(block); stream.write(block)
                stream.flush(); os.fsync(stream.fileno())
        if size != record['size'] or digest.hexdigest() != record['sha256']: raise ValueError('Backup download checksum mismatch')
        temporary.replace(path)
    finally: temporary.unlink(missing_ok=True)
