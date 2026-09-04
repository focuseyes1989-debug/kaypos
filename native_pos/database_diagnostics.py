"""Stock Qt database diagnostics and explicit local JSON export."""
import json
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton, QPlainTextEdit, QFileDialog, QMessageBox
from native_pos.sales import table, fill
from native_pos.tasks import TaskRunner
from native_pos.report_export import atomic_output


class DatabaseDiagnosticsDialog(QDialog):
    def __init__(self, host, parent=None):
        super().__init__(parent); self.host = host; self.report = None; self.runner = TaskRunner(self)
        self.setWindowTitle('POS Server database diagnostics'); self.resize(950, 560)
        body = QVBoxLayout(self)
        self.summary = QLabel('Inspect the connected POS Server database. Choose Run checks to begin.'); self.summary.setWordWrap(True); self.summary.setTextFormat(Qt.TextFormat.PlainText); body.addWidget(self.summary)
        self.table = table(['Table', 'Scope', 'Status', 'Missing columns', 'Columns found']); body.addWidget(self.table, 1)
        self.details = QPlainTextEdit(); self.details.setReadOnly(True); self.details.setMaximumHeight(155); body.addWidget(self.details)
        row = QHBoxLayout(); self.integrity = QCheckBox('Include SQLite quick_check'); row.addWidget(self.integrity)
        self.run_button = QPushButton('Run checks'); self.run_button.clicked.connect(self.refresh); row.addWidget(self.run_button)
        self.export_button = QPushButton('Export diagnostic JSON…'); self.export_button.clicked.connect(self.export); row.addWidget(self.export_button)
        close = QPushButton('Close'); close.clicked.connect(self.reject); row.addWidget(close); body.addLayout(row)
        self.runner.idle.connect(self.update_enabled); self.update_enabled()

    def update_enabled(self):
        allowed = self.host.session and self.host.session.can('settings') and self.host.session.can('edit_settings')
        self.run_button.setEnabled(bool(allowed and not self.runner.busy)); self.integrity.setEnabled(not self.runner.busy)
        self.export_button.setEnabled(bool(self.report) and not self.runner.busy)

    def refresh(self):
        if self.runner.busy or not self.host.session.can('edit_settings'): return
        self.report = None; self.table.setRowCount(0); self.details.clear(); self.summary.setText('Checking POS Server database…')
        integrity = self.integrity.isChecked()
        self.runner.start(lambda: self.host.store.client._request('GET', '/api/native/database/diagnostics', params={'integrity': str(integrity).lower()}), self.received, self.summary.setText)
        self.update_enabled()

    def received(self, report):
        self.report = report
        self.summary.setText(f"{report['backend']} {report['version']} · Schema: {report['schema_status']} · Integrity: {report['integrity']['status']}\nChecked: {report['checked_at']} · Journal: {report['journal_mode']}")
        fill(self.table, [[r[k] for k in ('table', 'scope', 'status', 'missing_columns', 'columns_found')] for r in report['records']])
        self.details.setPlainText('\n'.join(report['integrity']['details'] + report['notes'])); self.update_enabled()

    def export(self):
        if not self.report or self.runner.busy: return
        path, _ = QFileDialog.getSaveFileName(self, 'Export database diagnostics', 'native-database-diagnostics.json', 'JSON (*.json)')
        if path:
            try:
                with atomic_output(path) as temporary: temporary.write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding='utf-8')
            except (OSError, ValueError) as exc: QMessageBox.warning(self, 'Export failed', str(exc))

    def reject(self):
        if not self.runner.busy: super().reject()

    def closeEvent(self, event):
        if self.runner.busy: event.ignore()
        else: super().closeEvent(event)
