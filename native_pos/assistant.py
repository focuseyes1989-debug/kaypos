"""Stock Qt assistant; no WebEngine or legacy dashboard widgets."""
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QPlainTextEdit, QMessageBox, QComboBox, QDateEdit, QFileDialog
from native_pos.sales import table, fill
from native_pos.assistant_queries import REPORT_CHOICES
from native_pos.report_export import display, write_csv


class AssistantPage(QWidget):
    def __init__(self, host):
        super().__init__(); self.host = host; self.loaded = True; self.result = {}
        body = QVBoxLayout(self); body.addWidget(QLabel('AI Pages · Native business assistant'))
        note = QLabel('Ask in English or Myanmar. Reports use your server permissions. Try “today sales”, “stock summary” or “open attendance”.')
        note.setWordWrap(True); body.addWidget(note)
        row = QHBoxLayout(); self.query = QLineEdit(); self.query.setMaxLength(1000)
        self.query.setPlaceholderText('ဒီနေ့ရောင်းအား / today sales')
        self.send = QPushButton('Ask'); self.send.clicked.connect(self.ask); self.query.returnPressed.connect(self.ask)
        row.addWidget(self.query, 1); row.addWidget(self.send); body.addLayout(row)
        reports = QHBoxLayout(); self.report_choice = QComboBox()
        for label, section, view in REPORT_CHOICES: self.report_choice.addItem(label, section + '/' + view)
        self.start = QDateEdit(QDate.currentDate()); self.end = QDateEdit(QDate.currentDate())
        for control in (self.start, self.end): control.setCalendarPopup(True); control.setDisplayFormat('yyyy-MM-dd')
        self.run_report = QPushButton('Run report'); self.run_report.clicked.connect(self.ask_report)
        for control in (self.report_choice, self.start, self.end, self.run_report): reports.addWidget(control)
        body.addLayout(reports)
        self.answer = QPlainTextEdit(); self.answer.setReadOnly(True); self.answer.setMaximumHeight(140); body.addWidget(self.answer)
        self.table_choice = QComboBox(); self.table_choice.currentIndexChanged.connect(self.show_table); body.addWidget(self.table_choice)
        self.row_count = QLabel(); body.addWidget(self.row_count)
        self.table = table([]); body.addWidget(self.table, 1)
        actions = QHBoxLayout(); self.previous = QPushButton('Previous period'); self.previous.clicked.connect(self.previous_period)
        self.export_button = QPushButton('Export selected table CSV…'); self.export_button.clicked.connect(self.export)
        actions.addWidget(self.previous); actions.addWidget(self.export_button); body.addLayout(actions)
        self.open_button = QPushButton('Open related page'); self.open_button.clicked.connect(self.open_page); body.addWidget(self.open_button); self.open_button.setEnabled(False)
        host.runner.idle.connect(self.update_enabled); self.update_enabled()

    def update_enabled(self):
        idle = not self.host.runner.busy
        self.send.setEnabled(idle); self.run_report.setEnabled(idle)
        report = self.result.get('report') or {}
        self.previous.setEnabled(idle and bool(report))
        self.export_button.setEnabled(idle and bool(report.get('tables')))

    def ask_report(self):
        if self.start.date() > self.end.date():
            QMessageBox.information(self, 'Report period', 'Start date must not be after end date.'); return
        section, view = self.report_choice.currentData().split('/')
        self.query.setText(f"report {section}/{view} {self.start.date().toString('yyyy-MM-dd')} {self.end.date().toString('yyyy-MM-dd')}")
        self.ask()

    def previous_period(self):
        report = self.result.get('report') or {}
        if not report or self.host.runner.busy: return
        first = QDate.fromString(report['start'], 'yyyy-MM-dd'); last = QDate.fromString(report['end'], 'yyyy-MM-dd')
        span = first.daysTo(last) + 1
        section = self.result.get('report_section') or ('summary' if self.result.get('route_id') == 1 else 'reports')
        self.query.setText(f"report {section}/{report['view']} {first.addDays(-span).toString('yyyy-MM-dd')} {first.addDays(-1).toString('yyyy-MM-dd')}")
        self.ask()

    def refresh(self): pass

    def ask(self):
        if self.host.runner.busy or self.host.closing or not self.query.text().strip(): return
        self.send.setEnabled(False); self.open_button.setEnabled(False); self.answer.setPlainText('Reading server data…'); self.table.setRowCount(0); self.result = {}
        self.table_choice.clear(); self.previous.setEnabled(False); self.export_button.setEnabled(False); self.run_report.setEnabled(False)
        query = self.query.text().strip()
        self.host.runner.start(lambda: self.host.store.client._request('POST', '/api/native/assistant', json={'query': query}), self.received, self.failed)

    def failed(self, message): self.answer.setPlainText(message); self.update_enabled()

    def received(self, result):
        self.result = result; report = result.get('report', {}); text = result['message']
        if report.get('metrics'): text += '\n' + '\n'.join(f"{k.replace('_', ' ').title()}: {v}" for k, v in report['metrics'].items())
        self.answer.setPlainText(text)
        tables = report.get('tables', [])
        self.table_choice.blockSignals(True); self.table_choice.clear()
        for item in tables: self.table_choice.addItem(f"{item['title']} ({len(item['rows']):,})")
        self.table_choice.blockSignals(False)
        if report:
            self.start.setDate(QDate.fromString(report['start'], 'yyyy-MM-dd')); self.end.setDate(QDate.fromString(report['end'], 'yyyy-MM-dd'))
            pair = (result.get('report_section') or ('summary' if result.get('route_id') == 1 else 'reports')) + '/' + report['view']
            index = self.report_choice.findData(pair)
            if index >= 0: self.report_choice.setCurrentIndex(index)
        self.show_table()
        self.open_button.setEnabled(result.get('route_id') in self.host.route_pages); self.update_enabled()

    def show_table(self, *args):
        if not hasattr(self, 'table'): return
        tables = (self.result.get('report') or {}).get('tables', [])
        index = self.table_choice.currentIndex()
        selected = tables[index] if 0 <= index < len(tables) else None
        rows = selected['rows'] if selected else self.result.get('records', [])
        self.row_count.setText(f'Showing {min(len(rows), 200):,} of {len(rows):,} rows. CSV exports the full selected report table.' if selected else f'{len(rows):,} matching record(s)')
        if len(rows) > 200:
            rows = rows[:200]
        columns = selected['columns'] if selected else [dict(key=k, label=k.replace('_', ' ').title(), kind='text') for k in (list(rows[0]) if rows else [])]
        self.table.setColumnCount(len(columns)); self.table.setHorizontalHeaderLabels([c['label'] for c in columns])
        fill(self.table, [[display(r.get(c['key']), c.get('kind', 'text')) for c in columns] for r in rows])
        self.table_choice.setToolTip('Preview shows up to 200 rows per table. CSV exports all rows of the selected table from this snapshot.')

    def export(self):
        report = self.result.get('report') or {}; tables = report.get('tables', [])
        index = self.table_choice.currentIndex()
        if self.host.runner.busy or not 0 <= index < len(tables): return
        path, _ = QFileDialog.getSaveFileName(self, 'Export full selected table', 'assistant-report.csv', 'CSV (*.csv)')
        if path:
            try: write_csv(path, report, tables[index])
            except (OSError, ValueError) as exc: QMessageBox.warning(self, 'Export failed', str(exc))

    def open_page(self):
        if self.host.runner.busy: return
        route = self.result.get('route_id')
        if route not in self.host.route_pages: return
        page = self.host.route_pages[route]
        tab = self.result.get('tab')
        if tab and hasattr(page, 'section'):
            index = page.section.findData(tab)
            if index >= 0:
                page.section.blockSignals(True); page.section.setCurrentIndex(index); page.section.blockSignals(False)
        report = self.result.get('report') or {}; filters = self.result.get('filters') or {}
        for attribute, key in [('start', 'start_date'), ('end', 'end_date')]:
            value = report.get(attribute) or filters.get(key)
            if value and hasattr(page, attribute): getattr(page, attribute).setDate(QDate.fromString(value, 'yyyy-MM-dd'))
        if report.get('view') and hasattr(page, 'view'):
            index = page.view.findData(report['view'])
            if index >= 0: page.view.setCurrentIndex(index)
        if filters.get('employee') and hasattr(page, 'search'): page.search.setText(filters['employee'])
        self.host.navigate(route)
        if hasattr(page, 'refresh'): page.refresh()
