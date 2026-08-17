"""Phase-two employee tabs: leave, documents, finance, performance and cash."""

import csv
from datetime import date, timedelta

from PyQt6.QtWidgets import (QComboBox,QDialog,QDialogButtonBox,QDoubleSpinBox,
    QFileDialog,QFormLayout,QHBoxLayout,QLabel,QLineEdit,QMessageBox,QPushButton,
    QTableWidgetItem,QVBoxLayout,QWidget)

from services import employee_service as service
from ui.employee_page import _button, _table
from ui.widgets.date_range_widget import DateRangeWidget
from ui.widgets.search_widget import ModernSearchWidget


def _employees(combo):
    for item in service.list_employees(status="Active"): combo.addItem(f"{item['employee_no']} — {item['full_name']}",item['id'])


def _export(headers, rows, parent):
    path,_=QFileDialog.getSaveFileName(parent,"Export report",f"employee-report-{date.today()}.csv","CSV (*.csv)")
    if not path:return
    with open(path,"w",newline="",encoding="utf-8-sig") as handle:
        writer=csv.writer(handle); writer.writerow(headers); writer.writerows(rows)
    QMessageBox.information(parent,"Export",f"Exported to:\n{path}")


class LeaveTab(QWidget):
    def __init__(self,user_id,can_manage):
        super().__init__(); self.user_id=user_id; self.can_manage=can_manage; self.rows=[]; top=QHBoxLayout(); self.search=ModernSearchWidget("Search employee..."); self.type_filter=QComboBox(); self.type_filter.addItems(["All Types","Annual","Sick","Unpaid","Emergency"]); self.filter=QComboBox(); self.filter.addItems(["All","Pending","Approved","Rejected","Cancelled"]); top.addWidget(self.search,1); top.addWidget(self.type_filter); top.addWidget(self.filter); top.addStretch(); top.addWidget(_button("New Request",self.create,True));
        if can_manage: top.addWidget(_button("Approve",lambda:self.review("Approved"))); top.addWidget(_button("Reject",lambda:self.review("Rejected")))
        self.table=_table(["Employee","Type","From","To","Days","Reason","Status","Review notes"]); lay=QVBoxLayout(self); lay.addLayout(top); lay.addWidget(self.table); self.search.search_changed.connect(lambda _text:self.refresh()); self.type_filter.currentTextChanged.connect(lambda _text:self.refresh()); self.filter.currentTextChanged.connect(lambda _text:self.refresh()); self.refresh()
    def refresh(self):
        rows=service.list_leave(self.filter.currentText());term=self.search.get_text().lower();leave_type=self.type_filter.currentText();self.rows=[x for x in rows if (not term or term in str(x.get('full_name') or '').lower() or term in str(x.get('employee_no') or '').lower()) and (leave_type=='All Types' or x.get('leave_type')==leave_type)]; self.table.setRowCount(len(self.rows))
        for r,x in enumerate(self.rows):
            for c,v in enumerate((x['full_name'],x['leave_type'],x['start_date'],x['end_date'],x['days'],x['reason'] or '',x['status'],x['review_notes'] or '')):self.table.setItem(r,c,QTableWidgetItem(str(v)))
    def create(self):
        d=QDialog(self); d.setWindowTitle("Leave Request"); f=QFormLayout(d); emp=QComboBox(); _employees(emp); typ=QComboBox(); typ.addItems(["Annual","Sick","Unpaid","Emergency"]); leave_range=DateRangeWidget(); days=QDoubleSpinBox(); days.setRange(.5,365); days.setValue(1); reason=QLineEdit();
        for label,w in (("Employee",emp),("Leave type",typ),("Leave dates",leave_range),("Days",days),("Reason",reason)):f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); b.accepted.connect(d.accept); b.rejected.connect(d.reject); f.addRow(b)
        if d.exec(): service.create_leave(emp.currentData(),typ.currentText(),leave_range.get_from_date(),leave_range.get_to_date(),days.value(),reason.text()); self.refresh()
    def review(self,status):
        row=self.table.currentRow()
        if row<0:return
        service.review_leave(self.rows[row]['id'],status,self.user_id); self.refresh()


class DocumentsTab(QWidget):
    def __init__(self,can_manage):
        super().__init__(); self.rows=[]; top=QHBoxLayout(); self.search=ModernSearchWidget("Search employee or document no..."); self.type_filter=QComboBox(); self.type_filter.addItems(["All Types","Contract","National ID","Certificate","License","Other"]); self.expiring=QComboBox(); self.expiring.addItems(["All documents","Expiring in 30 days"]); top.addWidget(self.search,1); top.addWidget(self.type_filter); top.addWidget(self.expiring); top.addStretch(); top.addWidget(_button("Add Document",self.add,True)) if can_manage else None; self.table=_table(["Employee","Type","Document No","Issued","Expiry","File","Notes"]); lay=QVBoxLayout(self); lay.addLayout(top); lay.addWidget(self.table); self.search.search_changed.connect(lambda _text:self.refresh()); self.type_filter.currentTextChanged.connect(lambda _text:self.refresh()); self.expiring.currentIndexChanged.connect(lambda _index:self.refresh()); self.refresh()
    def refresh(self):
        rows=service.list_documents(30 if self.expiring.currentIndex()==1 else None);term=self.search.get_text().lower();doc_type=self.type_filter.currentText();self.rows=[x for x in rows if (not term or term in str(x.get('full_name') or '').lower() or term in str(x.get('employee_no') or '').lower() or term in str(x.get('document_no') or '').lower()) and (doc_type=='All Types' or x.get('document_type')==doc_type)]; self.table.setRowCount(len(self.rows))
        for r,x in enumerate(self.rows):
            for c,k in enumerate(("full_name","document_type","document_no","issued_date","expiry_date","file_path","notes")):self.table.setItem(r,c,QTableWidgetItem(str(x.get(k) or '')))
    def add(self):
        d=QDialog(self); d.setWindowTitle("Employee Document"); f=QFormLayout(d); emp=QComboBox(); _employees(emp); typ=QComboBox(); typ.addItems(["Contract","National ID","Certificate","License","Other"]); no=QLineEdit(); validity=DateRangeWidget(); validity.set_range(date.today().isoformat(),(date.today()+timedelta(days=365)).isoformat()); path=QLineEdit(); browse=QPushButton("Browse..."); browse.clicked.connect(lambda:path.setText(QFileDialog.getOpenFileName(d,"Choose document")[0])); file_row=QHBoxLayout(); file_row.addWidget(path); file_row.addWidget(browse); notes=QLineEdit();
        for label,w in (("Employee",emp),("Type",typ),("Document no",no),("Issued / Expiry",validity)):f.addRow(label,w)
        f.addRow("File",file_row); f.addRow("Notes",notes); b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); b.accepted.connect(d.accept); b.rejected.connect(d.reject); f.addRow(b)
        if d.exec(): service.add_document({'employee_id':emp.currentData(),'document_type':typ.currentText(),'document_no':no.text(),'issued_date':validity.get_from_date(),'expiry_date':validity.get_to_date(),'file_path':path.text(),'notes':notes.text()}); self.refresh()


class FinanceTab(QWidget):
    def __init__(self,user_id,can_manage):
        super().__init__(); self.user_id=user_id; self.can_manage=can_manage; self.rows=[]; top=QHBoxLayout(); self.search=ModernSearchWidget("Search employee..."); self.category=QComboBox(); self.category.addItems(["All Statuses","Outstanding","Repaid"]); top.addWidget(self.search,1); top.addWidget(self.category); top.addStretch();
        if can_manage: top.addWidget(_button("Salary Advance",self.add,True)); top.addWidget(_button("Record Repayment",self.repay)); top.addWidget(_button("Commission Rule",self.rule))
        self.table=_table(["Employee","Date","Amount","Repaid","Balance","Status","Notes"]); lay=QVBoxLayout(self); lay.addLayout(top); lay.addWidget(self.table); self.search.search_changed.connect(lambda _text:self.refresh()); self.category.currentTextChanged.connect(lambda _text:self.refresh()); self.refresh()
    def refresh(self):
        rows=service.list_advances();term=self.search.get_text().lower();status=self.category.currentText();self.rows=[x for x in rows if (not term or term in str(x.get('full_name') or '').lower() or term in str(x.get('employee_no') or '').lower()) and (status=='All Statuses' or x.get('status')==status)]; self.table.setRowCount(len(self.rows))
        for r,x in enumerate(self.rows):
            for c,v in enumerate((x['full_name'],x['advance_date'],x['amount'],x['repaid_amount'],x['balance'],x['status'],x['notes'] or '')):self.table.setItem(r,c,QTableWidgetItem(str(v)))
    def add(self):
        d=QDialog(self); f=QFormLayout(d); emp=QComboBox(); _employees(emp); day=DateRangeWidget(); amount=QDoubleSpinBox(); amount.setMaximum(999999999); notes=QLineEdit(); f.addRow("Employee",emp); f.addRow("Date",day); f.addRow("Amount",amount); f.addRow("Notes",notes); b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); b.accepted.connect(d.accept); b.rejected.connect(d.reject); f.addRow(b)
        if d.exec():service.add_advance(emp.currentData(),day.get_from_date(),amount.value(),notes.text(),self.user_id);self.refresh()
    def repay(self):
        row=self.table.currentRow()
        if row<0:return
        amount,ok=QDoubleSpinBox(),False; d=QDialog(self); f=QFormLayout(d); amount.setMaximum(float(self.rows[row]['balance'])); f.addRow("Repayment",amount); b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); b.accepted.connect(d.accept); b.rejected.connect(d.reject); f.addRow(b)
        if d.exec():service.repay_advance(self.rows[row]['id'],amount.value());self.refresh()
    def rule(self):
        d=QDialog(self); f=QFormLayout(d); emp=QComboBox(); _employees(emp); rate=QDoubleSpinBox(); rate.setRange(0,100); target=QDoubleSpinBox(); target.setMaximum(999999999); f.addRow("Employee",emp); f.addRow("Rate %",rate); f.addRow("Minimum target",target); b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); b.accepted.connect(d.accept); b.rejected.connect(d.reject); f.addRow(b)
        if d.exec():service.save_commission_rule(emp.currentData(),rate.value(),target.value())


class PerformanceTab(QWidget):
    def __init__(self):
        super().__init__(); self.rows=[]; top=QHBoxLayout(); self.date_range=DateRangeWidget(); self.search=ModernSearchWidget("Search employee..."); self.branch=QComboBox(); self.branch.addItem("All Branches"); [self.branch.addItem(x) for x in sorted({str(e.get('branch') or '') for e in service.list_employees(status='Active') if e.get('branch')})]; top.addWidget(self.date_range,1); top.addWidget(self.search,1); top.addWidget(self.branch); top.addWidget(_button("Refresh",self.refresh,True)); top.addStretch(); top.addWidget(_button("Export CSV",self.export)); self.headers=["Employee ID","Employee","Branch","Sales","Revenue","Refunds","Discounts","Target","Rate %","Commission"]; self.table=_table(self.headers); lay=QVBoxLayout(self); lay.addLayout(top); lay.addWidget(self.table); self.date_range.set_range((date.today()-timedelta(days=30)).isoformat(),date.today().isoformat()); self.date_range.date_range_changed.connect(lambda _from,_to:self.refresh()); self.search.search_changed.connect(lambda _text:self.refresh()); self.branch.currentTextChanged.connect(lambda _text:self.refresh()); self.refresh()
    def values(self,x):return (x['employee_no'],x['full_name'],x['branch'] or '',x['sale_count'],x['sales_total'],x['refund_count'],x['discount_total'],x['target_amount'],x['commission_rate'],x['commission_amount'])
    def refresh(self):
        rows=service.performance_report(self.date_range.get_from_date(),self.date_range.get_to_date());term=self.search.get_text().lower();branch=self.branch.currentText();self.rows=[x for x in rows if (not term or term in str(x.get('full_name') or '').lower() or term in str(x.get('employee_no') or '').lower()) and (branch=='All Branches' or str(x.get('branch') or '')==branch)]; self.table.setRowCount(len(self.rows))
        for r,x in enumerate(self.rows):
            for c,v in enumerate(self.values(x)):self.table.setItem(r,c,QTableWidgetItem(str(v)))
    def export(self):_export(self.headers,[self.values(x) for x in self.rows],self)


class CashSessionsTab(QWidget):
    def __init__(self,user_id,can_manage):
        super().__init__(); self.user_id=user_id; self.rows=[]; top=QHBoxLayout(); self.search=ModernSearchWidget("Search employee..."); self.category=QComboBox(); self.category.addItems(["All Statuses","Open","Closed"]); top.addWidget(self.search,1); top.addWidget(self.category); top.addStretch();
        if can_manage:top.addWidget(_button("Open Session",self.open,True));top.addWidget(_button("Close Session",self.close))
        self.table=_table(["Employee","Opened","Opening Cash","Closed","Expected","Actual","Difference","Status"]); lay=QVBoxLayout(self);lay.addLayout(top);lay.addWidget(self.table);self.search.search_changed.connect(lambda _text:self.refresh());self.category.currentTextChanged.connect(lambda _text:self.refresh());self.refresh()
    def refresh(self):
        rows=service.list_cash_sessions();term=self.search.get_text().lower();status=self.category.currentText();self.rows=[x for x in rows if (not term or term in str(x.get('full_name') or '').lower() or term in str(x.get('employee_no') or '').lower()) and (status=='All Statuses' or x.get('status')==status)];self.table.setRowCount(len(self.rows))
        for r,x in enumerate(self.rows):
            for c,k in enumerate(("full_name","opened_at","opening_cash","closed_at","expected_cash","actual_cash","difference","status")):self.table.setItem(r,c,QTableWidgetItem(str(x.get(k) or '')))
    def open(self):
        d=QDialog(self);f=QFormLayout(d);emp=QComboBox();_employees(emp);cash=QDoubleSpinBox();cash.setMaximum(999999999);notes=QLineEdit();f.addRow("Employee",emp);f.addRow("Opening cash",cash);f.addRow("Notes",notes);b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(d.accept);b.rejected.connect(d.reject);f.addRow(b)
        if d.exec():
            try:service.open_cash_session(emp.currentData(),cash.value(),self.user_id,notes.text());self.refresh()
            except Exception as exc:QMessageBox.warning(self,"Cash Session",str(exc))
    def close(self):
        row=self.table.currentRow()
        if row<0 or self.rows[row]['status']!='Open':return
        d=QDialog(self);f=QFormLayout(d);cash=QDoubleSpinBox();cash.setMaximum(999999999);f.addRow("Actual cash",cash);b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);b.accepted.connect(d.accept);b.rejected.connect(d.reject);f.addRow(b)
        if d.exec():service.close_cash_session(self.rows[row]['id'],cash.value(),self.user_id);self.refresh()
