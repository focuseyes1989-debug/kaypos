"""Native integration health and recoverable Telegram/cloud file editing."""
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QDialog, QLineEdit, QMessageBox
from native_pos.sales import table, fill
from native_pos.catalog import CatalogSession
from native_pos.business_dialogs import FormDialog


class TelegramSettingsDialog(FormDialog):
    def __init__(self, data, parent=None):
        super().__init__('Telegram · server file', [
            ('enabled', 'Enable Telegram', 'bool', False), ('listener_enabled', 'Enable command listener', 'bool', False),
            ('chat_id', 'Chat ID / @channel_name', 'text', ''), ('bot_token', 'Replacement bot token', 'text', ''),
            ('clear_token', 'Remove saved token', 'bool', False),
        ], data, parent)
        self.fields['bot_token'].setEchoMode(QLineEdit.EchoMode.Password)
        self.fields['bot_token'].setPlaceholderText('Leave blank to keep saved token' if data['token_configured'] else 'No token saved in server file')
        note = QLabel(data['message'] + '\nEnvironment overrides: ' + (', '.join(data['environment_overrides']) or 'None detected'))
        note.setWordWrap(True); self.body.insertWidget(0, note)


class CloudSettingsDialog(FormDialog):
    def __init__(self, data, parent=None):
        super().__init__('Cloud sync · server file', [
            ('enabled', 'Enable cloud sync', 'bool', False),
            ('interval_seconds', 'Sync interval (seconds)', 'int', 300),
            ('cloud_url', 'Replacement PostgreSQL URL', 'text', ''),
            ('clear_url', 'Remove saved cloud URL', 'bool', False),
        ], data, parent)
        self.fields['cloud_url'].setEchoMode(QLineEdit.EchoMode.Password)
        self.fields['cloud_url'].setPlaceholderText('Leave blank to keep saved URL' if data['url_configured'] else 'postgresql://user:password@host/database')
        self.fields['interval_seconds'].setRange(60, 86400)
        note = QLabel('Saved destination: ' + data['destination'] + '\n' + data['message'] + '\nEnvironment overrides: ' + (', '.join(data['environment_overrides']) or 'None detected'))
        note.setTextFormat(Qt.TextFormat.PlainText); note.setWordWrap(True); self.body.insertWidget(0, note)


class IntegrationsPage(QWidget):
    def __init__(self, host):
        super().__init__(); self.host = host; self.loaded = False; self.records = []
        if not getattr(host, 'telegram_session', None): host.telegram_session = CatalogSession(host, 'telegram')
        self.channel = host.telegram_session
        if not getattr(host, 'cloud_config_session', None): host.cloud_config_session = CatalogSession(host, 'cloud_config')
        self.cloud_channel = host.cloud_config_session
        layout = QVBoxLayout(self); layout.addWidget(QLabel('Integrations · existing server configuration'))
        self.table = table(['Service', 'Configured', 'Enabled', 'Owner / scope']); layout.addWidget(self.table, 1)
        self.message = QPlainTextEdit(); self.message.setReadOnly(True); self.message.setMaximumHeight(160); layout.addWidget(self.message)
        row = QHBoxLayout(); refresh = QPushButton('Refresh status'); refresh.clicked.connect(self.refresh); row.addWidget(refresh)
        self.test = QPushButton('Test selected connection'); self.test.clicked.connect(self.test_connection); row.addWidget(self.test); layout.addLayout(row)
        actions = QHBoxLayout(); self.edit = QPushButton('Telegram server settings…'); self.edit.clicked.connect(self.edit_telegram); actions.addWidget(self.edit)
        self.recover = QPushButton('Recover Telegram save'); self.recover.clicked.connect(self.channel.recover); actions.addWidget(self.recover); layout.addLayout(actions)
        cloud = QHBoxLayout(); self.cloud_edit = QPushButton('Cloud server settings…'); self.cloud_edit.clicked.connect(self.edit_cloud); cloud.addWidget(self.cloud_edit)
        self.cloud_recover = QPushButton('Recover cloud save'); self.cloud_recover.clicked.connect(self.cloud_channel.recover); cloud.addWidget(self.cloud_recover); layout.addLayout(cloud)
        self.channel.changed.connect(self.update_enabled)
        self.cloud_channel.changed.connect(self.update_enabled)
        self.table.itemSelectionChanged.connect(self.update_enabled); host.runner.idle.connect(self.update_enabled); self.update_enabled()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.loaded: QTimer.singleShot(0, self.refresh)

    def update_enabled(self):
        self.test.setEnabled(not self.host.runner.busy and self.host.session is not None and self.host.session.can('edit_settings') and 0 <= self.table.currentRow() < len(self.records) and self.records[self.table.currentRow()]['service'] != 'YouTube')
        admin = self.host.session and self.host.session.role.lower() == 'admin' and self.host.session.can('edit_settings')
        self.edit.setEnabled(bool(admin and not self.host.runner.busy and not self.channel.pending and not self.channel.error))
        if self.cloud_channel.pending: self.edit.setEnabled(False)
        self.recover.setEnabled(bool(admin and not self.host.runner.busy and self.channel.pending and not self.channel.error))
        self.cloud_edit.setEnabled(bool(admin and not self.host.runner.busy and not self.channel.pending and not self.cloud_channel.pending and not self.cloud_channel.error))
        self.cloud_recover.setEnabled(bool(admin and not self.host.runner.busy and self.cloud_channel.pending and not self.cloud_channel.error))
        message = self.channel.message
        if self.channel.pending: message += '\nA Telegram settings save is unresolved. Recover it before editing again.'
        if self.channel.error: message += '\nRecovery needs attention: ' + self.channel.error
        if self.cloud_channel.message: message += '\nCloud: ' + self.cloud_channel.message
        if self.cloud_channel.pending: message += '\nA cloud configuration save is unresolved. Recover it before editing the server file again.'
        if self.cloud_channel.error: message += '\nCloud recovery needs attention: ' + self.cloud_channel.error
        self.message.setPlainText(message)

    def refresh(self):
        if self.host.runner.busy or self.host.closing: return
        self.loaded = True; self.records = []; self.update_enabled()
        self.channel.run(lambda: self.host.store.client._request('GET', '/api/native/integrations'), self.received, 'Loading integration status…')

    def received(self, data):
        self.records = data['records']; fill(self.table, [[r[k] for k in ('service', 'configured', 'enabled', 'detail')] for r in self.records])
        self.channel.message = 'Connection tests read bot identity or run SELECT 1. No messages, uploads, playback, sync loops or cloud restores are started.'; self.update_enabled()

    def test_connection(self):
        if self.host.runner.busy: return
        index = self.table.currentRow()
        if not 0 <= index < len(self.records): return
        service = self.records[index]['service']; self.test.setEnabled(False); self.message.setPlainText('Checking ' + service + '…')
        def done(result): self.channel.message = result['message'] + (' · ' + result['account'] if result.get('account') else '')
        self.channel.run(lambda: self.host.store.client._request('POST', '/api/native/integrations/test', json={'service': service}), done, 'Checking ' + service + '…')

    def edit_telegram(self):
        if self.host.runner.busy or self.channel.pending or self.channel.error: return
        def received(data):
            if data['pending']:
                self.channel.message = 'The server has an unresolved Telegram save. Recover it from the originating Native account/PC before editing.'; return
            dialog = TelegramSettingsDialog(data, self)
            if dialog.exec() != QDialog.DialogCode.Accepted: return
            if QMessageBox.question(self, 'Save server Telegram configuration', 'Update the server .env Telegram settings? The existing server/listener owner controls applying these settings; environment overrides may take precedence.') != QMessageBox.StandardButton.Yes: return
            self.channel.submit('telegram.save', dialog.values())
        self.channel.run(lambda: self.host.store.client._request('GET', '/api/native/telegram'), received, 'Loading server Telegram settings…')

    def edit_cloud(self):
        channel = self.cloud_channel
        if self.host.runner.busy or channel.pending or channel.error: return
        def received(data):
            if data['pending']:
                channel.message = 'The server file has an unresolved configuration save. Recover it from the originating Native account/PC before editing.'; return
            dialog = CloudSettingsDialog(data, self)
            if dialog.exec() != QDialog.DialogCode.Accepted: return
            if QMessageBox.question(self, 'Save cloud configuration', 'Update the server file cloud settings? No sync or pull starts now. The existing service owner must apply these settings; inspect environment overrides and destination before enabling its scheduler.') != QMessageBox.StandardButton.Yes: return
            channel.submit('cloud.save', dialog.values())
        channel.run(lambda: self.host.store.client._request('GET', '/api/native/cloud_config'), received, 'Loading cloud server settings…')
