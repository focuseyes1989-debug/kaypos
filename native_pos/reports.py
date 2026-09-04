"""Native Dashboard, Sales Summary and Reports. No custom styles or painting."""
from copy import deepcopy

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, QDate, QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QComboBox, QDateEdit, QPushButton, QLineEdit, QTabWidget, QTableView, QHeaderView,
    QAbstractItemView, QPlainTextEdit, QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QTextBrowser)
from native_pos.report_export import display, write_csv, write_xlsx, report_html
from native_pos.receipt import ReceiptDialog


VIEW_LABELS = {
    'dashboard': [('overview','Overview'), ('daily','Daily totals'), ('items','Products')],
    'summary': [('overview','Overview / comparison'), ('daily','Daily totals'), ('hourly','Hourly sales'), ('items','Items / top sellers'),
        ('wholesale','Wholesale items'), ('categories','Categories'), ('parents','Parent categories'), ('groups','Category groups'),
        ('payments','Payment types'), ('returns','Refunded items')],
    'reports': [('financial','Financial summary / profit & loss'), ('monthly','Monthly profit & loss'), ('invoices','Sales invoices'),
        ('expenses','Expenses'), ('credit','Credit / collections'), ('inventory','Inventory valuation'), ('movements','Inventory movements')],
}


class ReportModel(QAbstractTableModel):
    def __init__(self, data, parent=None): super().__init__(parent); self.report = data; self.records = data['rows']; self.columns = data['columns']
    def rowCount(self, parent=QModelIndex()): return 0 if parent.isValid() else len(self.records)
    def columnCount(self, parent=QModelIndex()): return 0 if parent.isValid() else len(self.columns)
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid(): return None
        column = self.columns[index.column()]; value = self.records[index.row()].get(column['key'])
        if role == Qt.ItemDataRole.DisplayRole: return display(value, column['kind'])
        if role == Qt.ItemDataRole.UserRole: return value
        if role == Qt.ItemDataRole.TextAlignmentRole and column['kind'] != 'text': return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.ToolTipRole: return display(value, column['kind'])
        return None
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole: return None
        return self.columns[section]['label'] if orientation == Qt.Orientation.Horizontal else str(section+1)


class ReportPreview(QDialog):
    def __init__(self, html, parent=None):
        super().__init__(parent); self.setWindowTitle('Report preview'); self.resize(1040, 620)
        from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewWidget
        from PyQt6.QtGui import QTextDocument, QPageLayout, QPageSize
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QMarginsF
        self.printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        self.printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4)); self.printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        self.printer.setPageMargins(QMarginsF(10,10,10,10), QPageLayout.Unit.Millimeter)
        self.document = QTextDocument(self); self.document.setDefaultFont(QApplication.font()); self.document.setHtml(html)
        layout = QVBoxLayout(self); self.preview = QPrintPreviewWidget(self.printer, self)
        self.preview.paintRequested.connect(self.document.print); layout.addWidget(self.preview, 1)
        navigation = QHBoxLayout(); layout.addLayout(navigation); self.page_label = QLabel()
        previous = QPushButton('Previous page'); previous.clicked.connect(lambda: self.preview.setCurrentPage(max(1,self.preview.currentPage()-1)))
        next_page = QPushButton('Next page'); next_page.clicked.connect(lambda: self.preview.setCurrentPage(min(self.preview.pageCount(),self.preview.currentPage()+1)))
        fit = QPushButton('Fit page'); fit.clicked.connect(self.preview.fitInView)
        for widget in (previous,self.page_label,next_page,fit): navigation.addWidget(widget)
        self.preview.previewChanged.connect(lambda: self.page_label.setText(f'{self.preview.currentPage()} / {self.preview.pageCount()} pages'))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        button = buttons.addButton('Print / PDF…', QDialogButtonBox.ButtonRole.ActionRole); button.clicked.connect(self.print_report)
    def print_report(self):
        from PyQt6.QtPrintSupport import QPrintDialog
        if QPrintDialog(self.printer, self).exec() == QDialog.DialogCode.Accepted: self.document.print(self.printer)


class ReportPage(QWidget):
    def __init__(self, host, section):
        super().__init__(host); self.host = host; self.section = section; self.api = host.store.client
        self.loaded = False; self.data = None; self.models = []; self.proxies = []; self.tables = []
        body = QVBoxLayout(self); filters = QHBoxLayout()
        self.preset = QComboBox(); self.preset.addItems(['Today', 'This month', 'Last month', 'This year', 'Custom'])
        self.start = QDateEdit(); self.end = QDateEdit()
        for field in (self.start, self.end): field.setCalendarPopup(True); field.setDisplayFormat('yyyy-MM-dd')
        self.preset.setCurrentIndex(0 if section == 'dashboard' else 1); self.apply_preset()
        self.preset.activated.connect(self.apply_preset)
        self.start.dateChanged.connect(self.dates_changed); self.end.dateChanged.connect(self.dates_changed)
        self.view = QComboBox()
        for key, label in VIEW_LABELS[section]:
            if key == 'credit' and not host.session.can('credit'): continue
            if key in {'inventory','movements'} and not host.session.can('inventory'): continue
            self.view.addItem(label, key)
        self.view.activated.connect(self.refresh)
        self.refresh_button = QPushButton('Refresh'); self.refresh_button.clicked.connect(self.refresh)
        for widget in (self.preset, self.start, self.end, self.view, self.refresh_button): filters.addWidget(widget)
        body.addLayout(filters)
        self.status = QLabel('Connect to the updated POS Server for Phase 6 reports.'); self.status.setWordWrap(True); self.status.setTextFormat(Qt.TextFormat.PlainText); body.addWidget(self.status)
        self.metrics = QGridLayout(); self.metric_labels = []
        for index in range(6):
            group = QGroupBox(); layout = QVBoxLayout(group); value = QLabel('—'); value.setTextFormat(Qt.TextFormat.PlainText)
            font = value.font(); font.setPointSize(font.pointSize()+2); font.setBold(True); value.setFont(font)
            layout.addWidget(value); self.metrics.addWidget(group, 0, index); self.metric_labels.append((group,value))
        body.addLayout(self.metrics)
        self.context = QLabel(); self.context.setWordWrap(True); self.context.setTextFormat(Qt.TextFormat.PlainText); body.addWidget(self.context)
        self.search = QLineEdit(); self.search.setPlaceholderText('Filter table rows (summary totals retain the full date range)'); self.search.textChanged.connect(self.filter_rows); body.addWidget(self.search)
        self.tabs = QTabWidget(); self.tabs.currentChanged.connect(self.row_count); body.addWidget(self.tabs, 1)
        self.notes = QPlainTextEdit(); self.notes.setReadOnly(True); self.notes.setMaximumHeight(95); self.notes.hide(); body.addWidget(self.notes)
        actions = QHBoxLayout(); self.count = QLabel(); actions.addWidget(self.count, 1)
        definitions = QPushButton('Definitions'); definitions.setCheckable(True); definitions.toggled.connect(self.notes.setVisible); actions.addWidget(definitions)
        self.csv = QPushButton('Table CSV…'); self.csv.clicked.connect(lambda: self.export(False)); actions.addWidget(self.csv)
        self.xlsx = QPushButton('Workbook XLSX…'); self.xlsx.clicked.connect(lambda: self.export(True)); actions.addWidget(self.xlsx)
        self.preview = QPushButton('Preview / Print…'); self.preview.clicked.connect(self.print_preview); actions.addWidget(self.preview)
        body.addLayout(actions); self.host.runner.idle.connect(self.enabled); self.enabled()

    def apply_preset(self):
        preset = self.preset.currentText(); today = QDate.currentDate(); first = QDate(today.year(), today.month(), 1)
        start, end = today, today
        if preset == 'This month': start = first
        elif preset == 'Last month': start, end = first.addMonths(-1), first.addDays(-1)
        elif preset == 'This year': start = QDate(today.year(), 1, 1)
        elif preset == 'Custom': return
        for widget, value in ((self.start, start), (self.end, end)):
            widget.blockSignals(True); widget.setDate(value); widget.blockSignals(False)
        if hasattr(self, 'status'): self.invalidate()

    def dates_changed(self):
        self.preset.setCurrentText('Custom'); self.invalidate()

    def invalidate(self):
        self.data = None; self.loaded = False; self.clear_tables(); self.notes.clear(); self.context.clear()
        for group, value in self.metric_labels: value.setText('—')
        self.status.setText('Date range changed. Click Refresh to load the report.'); self.enabled()

    def enabled(self):
        busy = self.host.runner.busy or self.host.closing
        for widget in (self.preset,self.start,self.end,self.view,self.refresh_button): widget.setEnabled(not busy)
        for widget in (self.csv,self.xlsx,self.preview): widget.setEnabled(not busy and bool(self.data) and bool(self.proxies))

    def run(self, operation, success, message):
        if self.host.runner.busy or self.host.closing: return False
        self.status.setText(message); self.host.logout_action.setEnabled(False); self.host.refresh_action.setEnabled(False)
        def done(value=None, error=None):
            self.host.logout_action.setEnabled(True); self.host.refresh_action.setEnabled(True)
            if self.host.closing: return
            try:
                if error: self.status.setText(error)
                else: success(value)
            except Exception as exc: self.status.setText(str(exc))
            finally: self.enabled()
        self.host.runner.start(operation, lambda data: done(value=data), lambda error: done(error=error)); self.enabled(); return True

    def showEvent(self, event):
        super().showEvent(event)
        if not self.loaded: QTimer.singleShot(0, self.refresh)

    def refresh(self):
        if self.host.runner.busy or self.host.closing: return
        if self.start.date() > self.end.date(): self.status.setText('Start date must be before end date.'); return
        params = dict(section=self.section, view=self.view.currentData(), start=self.start.date().toString('yyyy-MM-dd'), end=self.end.date().toString('yyyy-MM-dd'))
        # Clear stale report values before a new request: failed refreshes must
        # not leave old totals underneath a new date range or view name.
        self.data = None; self.loaded = False; self.clear_tables(); self.notes.clear(); self.context.clear()
        for group, value in self.metric_labels: value.setText('—')
        self.run(lambda: self.api._request('GET', '/api/native/reports', params=params), self.render, 'Loading report snapshot…')

    def clear_tables(self):
        while self.tabs.count():
            page = self.tabs.widget(0); self.tabs.removeTab(0); page.deleteLater()
        self.models = []; self.proxies = []; self.tables = []

    def render(self, result):
        if result.get('version') != 1: raise ValueError('Update and restart the POS Server for Phase 6 reports.')
        self.clear_tables(); self.data = result; self.loaded = True
        metrics = result.get('metrics', {}); snapshot = result.get('snapshot', {})
        choices = [('net','Net sales'), ('invoice_total','Invoice total'), ('discount','Discount'), ('transactions','Completed receipts'), ('refunds','Refund invoices'), ('cogs','COGS')]
        if self.section != 'summary': choices = [('invoice_total','Invoice total'), ('cogs','COGS'), ('expenses','Expenses'), ('net_profit','Invoice profit'), ('refunds','Refund invoices'), ('transactions','Completed receipts')]
        if snapshot and not metrics: choices = [(key, key.replace('_',' ').title() + ' · current') for key in snapshot]
        for index, (group, label) in enumerate(self.metric_labels):
            group.setVisible(index < len(choices))
            if index < len(choices):
                key, title = choices[index]; group.setTitle(title); label.setText(display(metrics.get(key, snapshot.get(key)), 'integer' if key=='transactions' else 'money'))
        for data in result['tables']:
            view = QTableView(); model = ReportModel(data, view); proxy = QSortFilterProxyModel(view); proxy.setSourceModel(model)
            proxy.setSortRole(Qt.ItemDataRole.UserRole); proxy.setFilterKeyColumn(-1); proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            view.setModel(proxy); view.setSortingEnabled(True); view.sortByColumn(-1, Qt.SortOrder.AscendingOrder)
            view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); view.setAlternatingRowColors(True)
            view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive); view.horizontalHeader().setStretchLastSection(True)
            view.setColumnWidth(0, 220)
            for column in range(1, model.columnCount()): view.setColumnWidth(column, 140)
            view.doubleClicked.connect(lambda index, source=model, filtered=proxy: self.drilldown(source.records[filtered.mapToSource(index).row()]))
            self.models.append(model); self.proxies.append(proxy); self.tables.append(view); self.tabs.addTab(view, data['title'])
        notes = list(result.get('notes', []))
        context = []
        if snapshot: context.append('Current (not date-filtered): ' + ' · '.join(key.replace('_',' ').title() + ': ' + display(value, 'number') for key,value in snapshot.items()))
        if result.get('previous_period'): notes.insert(0, 'Previous period: ' + result['previous_period']['start'] + ' to ' + result['previous_period']['end'])
        if result.get('previous_period'): context.append(notes[0])
        self.context.setText('\n'.join(context)); self.context.setVisible(bool(context))
        self.notes.setPlainText('\n'.join(notes))
        self.status.setText(f"{result['start']} to {result['end']} · Snapshot {result['as_of']} · {result.get('currency','')} · {int(metrics.get('estimated_lines',0))} estimated cost lines")
        self.filter_rows(); self.enabled()

    def filter_rows(self):
        for proxy in self.proxies: proxy.setFilterFixedString(self.search.text())
        self.row_count()

    def row_count(self):
        index = self.tabs.currentIndex()
        if not hasattr(self, 'count'): return
        if 0 <= index < len(self.proxies): self.count.setText(f'{self.proxies[index].rowCount():,} shown / {self.models[index].rowCount():,} rows')
        else: self.count.clear()

    def captured_table(self, index):
        model, proxy = self.models[index], self.proxies[index]
        data = deepcopy(model.report)
        data['rows'] = [deepcopy(model.records[proxy.mapToSource(proxy.index(row,0)).row()]) for row in range(proxy.rowCount())]
        return data

    def export(self, workbook):
        if not self.data or self.tabs.currentIndex() < 0: return
        extension = 'xlsx' if workbook else 'csv'
        path, _ = QFileDialog.getSaveFileName(self, 'Export report snapshot', f"{self.section}-{self.data['start']}-{self.data['end']}.{extension}", f'{extension.upper()} (*.{extension})')
        if not path: return
        if not path.lower().endswith('.' + extension): path += '.' + extension
        report = deepcopy(self.data); filter_text = self.search.text()
        tables = [self.captured_table(i) for i in range(len(self.models))] if workbook else [self.captured_table(self.tabs.currentIndex())]
        self.run(lambda: write_xlsx(path, report, tables, filter_text) if workbook else write_csv(path, report, tables[0], filter_text),
            lambda _: self.status.setText('Exported snapshot: ' + path), 'Exporting report…')

    def print_preview(self):
        if not self.data or self.tabs.currentIndex() < 0: return
        report, data, text = deepcopy(self.data), self.captured_table(self.tabs.currentIndex()), self.search.text()
        self.run(lambda: report_html(report, data, text), lambda html: ReportPreview(html, self).exec(), 'Preparing report preview…')

    def drilldown(self, record):
        if self.host.session.can('receipts') and self.data and self.data['view'] == 'invoices' and record.get('id'):
            self.run(lambda: self.api._request('GET', '/api/native/business', params=dict(section='receipts',record_id=record['id'])),
                lambda receipt: ReceiptDialog(receipt,self,self.host.session.can('print_receipt')).exec(), 'Loading receipt…')
