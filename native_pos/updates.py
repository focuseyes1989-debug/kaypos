"""Explicit metadata-only update check using the existing Launcher source."""
import re
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton
from native_pos.tasks import TaskRunner


def version_status(local, published):
    def parse(value):
        match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', value.strip())
        return tuple(map(int, match.groups())) if match else None
    before, after = parse(local), parse(published)
    if before is None or after is None: return 'Version comparison unavailable; verify the release manually.'
    if after > before: return 'A newer KAY POS package version is published.'
    if after < before: return 'Local package version is ahead of published metadata; do not downgrade automatically.'
    return 'Package versions match. This does not prove that source commits match.'


def check_release():
    from launcher import current_version, fetch_latest_update, UPDATE_URL
    local = current_version(); result = fetch_latest_update()
    if not isinstance(result, dict) or not isinstance(result.get('version'), str) or not result['version'].strip():
        raise ValueError('Published version metadata is missing or invalid.')
    return dict(local=local, published=result['version'], notes=str(result.get('release_notes') or ''), source=UPDATE_URL,
                status=version_status(local, result['version']))


class UpdateCheckDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle('KAY POS package update information'); self.resize(760, 520)
        self.runner = TaskRunner(self)
        body = QVBoxLayout(self)
        self.details = QPlainTextEdit(); self.details.setReadOnly(True); body.addWidget(self.details)
        self.details.setPlainText('Check the existing Launcher version source on GitHub. Nothing is checked automatically.\n\nThis metadata describes the KAY POS package, not a verified Native installer or the running POS Server version.\n\nFor source installations, update the appropriate checkout and restart that application/server after saving work. Package updates remain managed outside Native.')
        row = QHBoxLayout(); body.addLayout(row)
        self.check = QPushButton('Check now'); self.check.clicked.connect(self.refresh); row.addWidget(self.check)
        self.close_button = QPushButton('Close'); self.close_button.clicked.connect(self.reject); row.addWidget(self.close_button)
        self.runner.idle.connect(self.update_enabled)

    def update_enabled(self):
        self.check.setEnabled(not self.runner.busy); self.close_button.setEnabled(not self.runner.busy)

    def refresh(self):
        if self.runner.busy: return
        self.details.setPlainText('Checking published KAY POS package metadata…')
        self.runner.start(check_release, self.received, lambda error: self.details.setPlainText('Update check failed. Check network access and try again.\n\nNo application files were changed.'))
        self.update_enabled()

    def received(self, result):
        self.details.setPlainText(f"Local package version: {result['local']}\nPublished package version: {result['published']}\n\n{result['status']}\n\nSource: {result['source']}\n\nRelease notes:\n{result['notes']}\n\nThis is shared KAY POS package metadata, not a verified Native installer or the running POS Server version. No download, installation, Git pull or restart was performed.")

    def reject(self):
        if not self.runner.busy: super().reject()

    def closeEvent(self, event):
        if self.runner.busy: event.ignore()
        else: super().closeEvent(event)
