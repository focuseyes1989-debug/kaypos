"""Employee Management page: profiles, attendance, shifts and payroll."""

from datetime import date
from pathlib import Path

from PyQt6.QtCore import QByteArray, QBuffer, QDate, QIODevice, QTime, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QFileDialog, QMessageBox, QPushButton, QSpinBox, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QTimeEdit, QVBoxLayout, QWidget,
)

from services import employee_service as service
from utils.permissions import PermissionManager
from ui.widgets.modern_button import ModernButton
from ui.widgets.search_widget import ModernSearchWidget
from ui.widgets.summary_card_widget import SummaryCardWidget
from ui.widgets.date_range_widget import DateRangeWidget


def _button(text, slot, primary=False):
    button = ModernButton(text, ModernButton.PRIMARY if primary else ModernButton.SECONDARY)
    lowered = text.lower()
    icon = ("add" if any(word in lowered for word in ("add", "new", "create", "open"))
            else "check_circle" if any(word in lowered for word in ("paid", "approve", "close session"))
            else "export" if "export" in lowered
            else "edit" if any(word in lowered for word in ("correct", "assign", "repayment", "rule"))
            else "refresh" if "refresh" in lowered
            else None)
    if icon:
        button.set_icon(icon)
    button.clicked.connect(slot)
    return button


def _table(headers):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    return table


def _as_bytes(value):
    return bytes(value) if value else b""


def _photo_pixmap(photo_data, size):
    pixmap=QPixmap();data=_as_bytes(photo_data)
    if not data or not pixmap.loadFromData(data,"PNG"):return QPixmap()
    scaled=pixmap.scaled(size,size,Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation)
    x=max(0,(scaled.width()-size)//2);y=max(0,(scaled.height()-size)//2)
    return scaled.copy(x,y,size,size)


def _normalized_photo_png(path):
    image=QImage(path)
    if image.isNull():raise ValueError("The selected image could not be opened")
    image=image.scaled(256,256,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
    data=QByteArray();buffer=QBuffer(data)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly) or not image.save(buffer,"PNG"):
        raise ValueError("The selected image could not be converted to PNG")
    return bytes(data)


def _employee_photo_data(employee):
    data=_as_bytes(employee.get("photo_data"))
    path=employee.get("photo_path")
    if not data and path and Path(path).is_file():
        try:return _normalized_photo_png(str(path))
        except ValueError:return b""
    return data


class EmployeeDialog(QDialog):
    def __init__(self, employee=None, parent=None):
        super().__init__(parent); self.employee = employee or {}; self.setWindowTitle("Employee Profile"); self.resize(560, 650)
        form = QFormLayout(); self.fields = {}
        for key, label in (("employee_no","Employee ID *"),("full_name","Full name *"),("zkteco_user_id","ZKTeco User ID"),("phone","Phone"),("national_id","National ID"),("position","Position"),("department","Department"),("branch","Branch"),("emergency_contact_name","Emergency contact"),("emergency_contact_phone","Emergency phone")):
            field=QLineEdit(str(self.employee.get(key) or "")); self.fields[key]=field; form.addRow(label,field)
        if not self.fields["employee_no"].text(): self.fields["employee_no"].setText(service.next_number("EMP","employees"))
        self.hire=DateRangeWidget(); self.hire.set_range(self.employee.get("hire_date") or QDate.currentDate().toString("yyyy-MM-dd"))
        form.addRow("Hire date *",self.hire)
        self.has_dob=QCheckBox("Set date of birth"); self.has_dob.setChecked(bool(self.employee.get("date_of_birth"))); self.dob=DateRangeWidget(); self.dob.set_range(self.employee.get("date_of_birth") or QDate.currentDate().toString("yyyy-MM-dd")); self.dob.setEnabled(self.has_dob.isChecked()); self.has_dob.toggled.connect(self.dob.setEnabled); dob_row=QVBoxLayout(); dob_row.addWidget(self.has_dob); dob_row.addWidget(self.dob); form.addRow("Date of birth",dob_row)
        self.status=QComboBox(); self.status.addItems(["Active","On Leave","Resigned"]); self.status.setCurrentText(self.employee.get("employment_status") or "Active"); form.addRow("Status",self.status)
        self.user=QComboBox(); self.user.addItem("No POS account",None)
        for uid, username, full_name in service.list_users(): self.user.addItem(f"{username} — {full_name or ''}",uid)
        linked=self.employee.get("user_id"); idx=self.user.findData(linked); self.user.setCurrentIndex(max(0,idx)); form.addRow("POS account",self.user)
        self.photo_data=_employee_photo_data(self.employee);self.photo_preview=QLabel();self.photo_preview.setFixedSize(84,84);self.photo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter);self.photo_preview.setStyleSheet("border: 1px solid #9aa0a6; border-radius: 8px;");self.photo=QLineEdit(self.employee.get("photo_path") or "");self.photo.setReadOnly(True);photo_buttons=QHBoxLayout();photo_buttons.addWidget(self.photo,1);photo_buttons.addWidget(_button("Browse...",self.choose_photo));photo_buttons.addWidget(_button("Remove",self.remove_photo));photo_box=QVBoxLayout();photo_box.addWidget(self.photo_preview);photo_box.addLayout(photo_buttons);form.addRow("Photo",photo_box);self.update_photo_preview()
        self.address=QTextEdit(self.employee.get("address") or ""); self.address.setMaximumHeight(70); form.addRow("Address",self.address)
        self.notes=QTextEdit(self.employee.get("notes") or ""); self.notes.setMaximumHeight(70); form.addRow("Notes",self.notes)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout=QVBoxLayout(self); layout.addLayout(form); layout.addWidget(buttons)
    def accept(self):
        if not self.fields["employee_no"].text().strip() or not self.fields["full_name"].text().strip(): QMessageBox.warning(self,"Required","Employee ID and full name are required."); return
        super().accept()
    def data(self):
        result={key:field.text().strip() for key,field in self.fields.items()}; result.update({"hire_date":self.hire.get_from_date(),"date_of_birth":self.dob.get_from_date() if self.has_dob.isChecked() else None,"employment_status":self.status.currentText(),"user_id":self.user.currentData(),"photo_path":self.photo.text().strip(),"photo_data":self.photo_data or None,"address":self.address.toPlainText().strip(),"notes":self.notes.toPlainText().strip()}); return result
    def choose_photo(self):
        path,_=QFileDialog.getOpenFileName(self,"Choose employee photo","","Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            try:self.photo_data=_normalized_photo_png(path);self.photo.setText(Path(path).name);self.update_photo_preview()
            except Exception as exc:QMessageBox.warning(self,"Employee Photo",str(exc))
    def remove_photo(self):
        self.photo_data=b"";self.photo.clear();self.update_photo_preview()
    def update_photo_preview(self):
        pixmap=_photo_pixmap(self.photo_data,80)
        if pixmap.isNull():self.photo_preview.setPixmap(QPixmap());self.photo_preview.setText("No photo")
        else:self.photo_preview.setText("");self.photo_preview.setPixmap(pixmap)


class EmployeesTab(QWidget):
    data_changed = pyqtSignal()
    def __init__(self, can_manage=True):
        super().__init__(); self.can_manage=can_manage; self.rows=[]; top=QHBoxLayout(); self.search=ModernSearchWidget("Search by name, employee ID or phone..."); self.status=QComboBox(); self.status.addItems(["All","Active","On Leave","Resigned"]); all_rows=service.list_employees(); self.position=QComboBox(); self.department=QComboBox(); self.branch=QComboBox(); self.position.addItem("All Positions");self.department.addItem("All Departments");self.branch.addItem("All Branches");[self.position.addItem(x) for x in sorted({str(e.get('position') or '') for e in all_rows if e.get('position')})];[self.department.addItem(x) for x in sorted({str(e.get('department') or '') for e in all_rows if e.get('department')})];[self.branch.addItem(x) for x in sorted({str(e.get('branch') or '') for e in all_rows if e.get('branch')})]; top.addWidget(self.search,1); top.addWidget(self.status);top.addWidget(self.position);top.addWidget(self.department);top.addWidget(self.branch); top.addWidget(_button("Add Employee",self.add,True)) if can_manage else None
        self.table=_table(["Profile","Employee ID","Name","Position","Phone","Branch","POS Account","Status"]); self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents); self.table.doubleClicked.connect(self.edit); layout=QVBoxLayout(self); layout.addLayout(top); layout.addWidget(self.table); self.search.search_changed.connect(lambda _text:self.refresh()); self.status.currentTextChanged.connect(lambda _status:self.refresh());self.position.currentTextChanged.connect(lambda _text:self.refresh());self.department.currentTextChanged.connect(lambda _text:self.refresh());self.branch.currentTextChanged.connect(lambda _text:self.refresh()); self.refresh()
    def refresh(self):
        rows=service.list_employees(self.search.get_text(),self.status.currentText());position=self.position.currentText();department=self.department.currentText();branch=self.branch.currentText();self.rows=[x for x in rows if (position=="All Positions" or str(x.get('position') or '')==position) and (department=="All Departments" or str(x.get('department') or '')==department) and (branch=="All Branches" or str(x.get('branch') or '')==branch)]; self.table.setRowCount(len(self.rows))
        for r,item in enumerate(self.rows):
            self.table.setRowHeight(r,58);photo=QLabel();photo.setAlignment(Qt.AlignmentFlag.AlignCenter);pixmap=_photo_pixmap(_employee_photo_data(item),50)
            if pixmap.isNull():photo.setText("👤")
            else:photo.setPixmap(pixmap)
            self.table.setCellWidget(r,0,photo)
            for c,key in enumerate(("employee_no","full_name","position","phone","branch","username","employment_status"),1): self.table.setItem(r,c,QTableWidgetItem(str(item.get(key) or "")))
    def add(self):
        dialog=EmployeeDialog(parent=self)
        if dialog.exec():
            try: service.save_employee(dialog.data()); self.refresh(); self.data_changed.emit()
            except Exception as exc: QMessageBox.critical(self,"Could not save",str(exc))
    def edit(self):
        if not self.can_manage or self.table.currentRow()<0:return
        employee=self.rows[self.table.currentRow()]; dialog=EmployeeDialog(employee,self)
        if dialog.exec():
            try: service.save_employee(dialog.data(),employee["id"]); self.refresh(); self.data_changed.emit()
            except Exception as exc: QMessageBox.critical(self,"Could not save",str(exc))


class AttendanceTab(QWidget):
    def __init__(self,user_id,can_manage):
        super().__init__(); self.user_id=user_id; self.can_manage=can_manage; self.rows=[]; top=QHBoxLayout(); self.date_range=DateRangeWidget(); self.search=ModernSearchWidget("Search employee or ID..."); self.employee_filter=QComboBox();self.employee_filter.addItem("All Employees",None);[self.employee_filter.addItem(f"{e['employee_no']} — {e['full_name']}",e['id']) for e in service.list_employees(status='Active')];self.issue=QComboBox();self.issue.addItems(["All Records","Missing Check-in","Missing Check-out","Check-in before Shift","Check-in after Shift"]); self.category=QComboBox(); self.category.addItems(["All Statuses","Present","Late","Incomplete","Absent","Half-day","Leave"]); top.addWidget(self.date_range,1); top.addWidget(self.search,1);top.addWidget(self.employee_filter);top.addWidget(self.issue); top.addWidget(self.category); top.addStretch(); top.addWidget(_button("Sync K20",self.sync_k20,True)) if can_manage else None; top.addWidget(_button("Add / Correct",self.record)) if can_manage else None
        self.total_count=QLabel("Total Records: 0"); self.total_count.setStyleSheet("font-size: 14px; font-weight: 600; padding: 4px 2px;")
        self.table=_table(["Date","Employee ID","Name","Check in","Check out","Status","Late (min)","Notes","Correction reason"]); layout=QVBoxLayout(self); layout.addLayout(top); layout.addWidget(self.total_count); layout.addWidget(self.table); self.date_range.date_range_changed.connect(lambda _from,_to:self.refresh()); self.search.search_changed.connect(lambda _text:self.refresh());self.employee_filter.currentIndexChanged.connect(lambda _index:self.refresh());self.issue.currentTextChanged.connect(lambda _text:self.refresh()); self.category.currentTextChanged.connect(lambda _text:self.refresh()); self.refresh()
    def refresh(self):
        rows=service.list_attendance(self.date_range.get_from_date(),self.date_range.get_to_date()); term=self.search.get_text().lower(); status=self.category.currentText();employee_id=self.employee_filter.currentData();issue=self.issue.currentText()
        def issue_matches(x):
            if issue=="Missing Check-in":return not x.get("check_in")
            if issue=="Missing Check-out":return not x.get("check_out")
            if issue=="Check-in before Shift":return bool(x.get("check_in") and x.get("shift_start")) and str(x.get("check_in"))[:5]<str(x.get("shift_start"))[:5]
            if issue=="Check-in after Shift":return bool(x.get("check_in") and x.get("shift_start")) and str(x.get("check_in"))[:5]>str(x.get("shift_start"))[:5]
            return True
        self.rows=[x for x in rows if (not term or term in str(x.get("full_name") or "").lower() or term in str(x.get("employee_no") or "").lower()) and (employee_id is None or x.get("employee_id")==employee_id) and issue_matches(x) and (status=="All Statuses" or x.get("status")==status)]; self.total_count.setText(f"Total Records: {len(self.rows):,}"); self.table.setRowCount(len(self.rows))
        for r,item in enumerate(self.rows):
            for c,key in enumerate(("attendance_date","employee_no","full_name","check_in","check_out","status","late_minutes","notes","correction_reason")): self.table.setItem(r,c,QTableWidgetItem(str(item.get(key) or "")))
    def record(self):
        employees=service.list_employees(status="Active")
        if not employees: QMessageBox.information(self,"Employees","Add an active employee first."); return
        dialog=QDialog(self); dialog.setWindowTitle("Attendance"); form=QFormLayout(dialog); employee=QComboBox(); [employee.addItem(f"{x['employee_no']} — {x['full_name']}",x['id']) for x in employees]; cin=QTimeEdit(QTime.currentTime()); cout=QTimeEdit(); cout.setSpecialValueText("Not set"); cout.setTime(QTime(0,0)); status=QComboBox(); status.addItems(["Present","Late","Incomplete","Absent","Half-day","Leave"]); notes=QLineEdit(); reason=QLineEdit(); form.addRow("Employee",employee); form.addRow("Check in",cin); form.addRow("Check out",cout); form.addRow("Status",status); form.addRow("Notes",notes); form.addRow("Correction reason",reason); buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); form.addRow(buttons)
        if dialog.exec(): service.save_attendance(employee.currentData(),self.date_range.get_from_date(),cin.time().toString("HH:mm"),"" if cout.time()==QTime(0,0) else cout.time().toString("HH:mm"),status.currentText(),notes.text(),self.user_id,reason.text()); self.refresh()
    def sync_k20(self):
        try:
            from services.zkteco_service import sync_configured_mappings
            results=sync_configured_mappings(); imported=sum(x["inserted"] for x in results); days=sum(x["attendance_days"] for x in results); self.refresh(); QMessageBox.information(self,"ZKTeco Sync",f"Sync complete.\nNew punches: {imported}\nAttendance days updated: {days}")
        except Exception as exc: QMessageBox.critical(self,"ZKTeco Sync Failed",str(exc))


class ShiftsTab(QWidget):
    def __init__(self,can_manage):
        super().__init__(); self.can_manage=can_manage; self.rows=[]; self.assignment_rows=[]; top=QHBoxLayout(); self.search=ModernSearchWidget("Search shift or employee..."); self.category=QComboBox(); self.category.addItems(["All Types","Day Shift","Overnight"]); top.addWidget(self.search,1); top.addWidget(self.category); top.addStretch(); top.addWidget(_button("New Shift",self.add_shift)) if can_manage else None; top.addWidget(_button("Assign Shift",self.assign,True)) if can_manage else None; self.table=_table(["Shift","Start","End","Break (min)","Overnight"]); self.assignment_table=_table(["Employee ID","Employee","Assigned Shift","Hours","Effective From","Effective To","Weekly Off"]); assignment_header=QHBoxLayout();assignment_header.addWidget(QLabel("Employee Shift Assignments"));assignment_header.addStretch();assignment_header.addWidget(_button("Edit Assignment",self.edit_assignment)) if can_manage else None;assignment_header.addWidget(_button("Delete Assignment",self.delete_assignment)) if can_manage else None; layout=QVBoxLayout(self); layout.addLayout(top); layout.addWidget(QLabel("Shift Definitions")); layout.addWidget(self.table,1); layout.addLayout(assignment_header); layout.addWidget(self.assignment_table,1); self.assignment_table.doubleClicked.connect(self.edit_assignment) if can_manage else None; self.search.search_changed.connect(lambda _text:self.refresh()); self.category.currentTextChanged.connect(lambda _text:self.refresh()); self.refresh()
    def refresh(self):
        rows=service.list_shifts();term=self.search.get_text().lower();category=self.category.currentText();self.rows=[x for x in rows if (not term or term in str(x.get("name") or "").lower()) and (category=="All Types" or (category=="Overnight" and x.get("is_overnight")) or (category=="Day Shift" and not x.get("is_overnight")))]; self.table.setRowCount(len(self.rows))
        for r,item in enumerate(self.rows):
            for c,value in enumerate((item["name"],item["start_time"],item["end_time"],item["break_minutes"],"Yes" if item["is_overnight"] else "No")): self.table.setItem(r,c,QTableWidgetItem(str(value)))
        assignments=service.list_employee_shift_assignments();self.assignment_rows=[x for x in assignments if not term or term in str(x.get("full_name") or "").lower() or term in str(x.get("employee_no") or "").lower() or term in str(x.get("shift_name") or "").lower()];self.assignment_table.setRowCount(len(self.assignment_rows))
        for r,item in enumerate(self.assignment_rows):
            values=(item["employee_no"],item["full_name"],item["shift_name"],f"{item['start_time']} - {item['end_time']}",item["effective_from"],item["effective_to"] or "Current",item["weekly_off_days"] or "")
            for c,value in enumerate(values):self.assignment_table.setItem(r,c,QTableWidgetItem(str(value)))
    def add_shift(self):
        d=QDialog(self); d.setWindowTitle("New Shift"); f=QFormLayout(d); name=QLineEdit(); start=QTimeEdit(QTime(8,0)); end=QTimeEdit(QTime(17,0)); br=QSpinBox(); br.setRange(0,240); br.setValue(60); overnight=QComboBox(); overnight.addItems(["No","Yes"]); [f.addRow(label,w) for label,w in (("Name",name),("Start",start),("End",end),("Break minutes",br),("Overnight",overnight))]; b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); b.accepted.connect(d.accept); b.rejected.connect(d.reject); f.addRow(b)
        if d.exec() and name.text().strip(): service.save_shift(name.text().strip(),start.time().toString("HH:mm"),end.time().toString("HH:mm"),br.value(),overnight.currentText()=="Yes"); self.refresh()
    def assign(self):
        employees=service.list_employees(status="Active"); shifts=service.list_shifts()
        if not employees or not shifts: QMessageBox.warning(self,"Assign Shift","An active employee and an active shift are required."); return
        d=QDialog(self); d.setWindowTitle("Assign Shift"); f=QFormLayout(d); emp=QComboBox(); shift=QComboBox(); [emp.addItem(x["full_name"],x["id"]) for x in employees]; [shift.addItem(x["name"],x["id"]) for x in shifts]; effective=DateRangeWidget(); off=QLineEdit(); off.setPlaceholderText("e.g. Sunday"); [f.addRow(label,w) for label,w in (("Employee",emp),("Shift",shift),("Effective from",effective),("Weekly off",off))]; b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); b.accepted.connect(d.accept); b.rejected.connect(d.reject); f.addRow(b)
        if d.exec():
            try:
                service.assign_shift(emp.currentData(),shift.currentData(),effective.get_from_date(),off.text().strip());service.recalculate_attendance_categories(emp.currentData());self.refresh();QMessageBox.information(self,"Shift","Shift assigned successfully. Attendance categories were recalculated from the effective date.")
            except Exception as exc:QMessageBox.critical(self,"Could not assign shift",str(exc))

    def _selected_assignment(self):
        row=self.assignment_table.currentRow()
        if row<0 or row>=len(self.assignment_rows):
            QMessageBox.information(self,"Shift Assignment","Select an assignment from the table first.");return None
        return self.assignment_rows[row]

    def edit_assignment(self, *_args):
        item=self._selected_assignment()
        if not item:return
        employees=service.list_employees();shifts=service.list_shifts()
        d=QDialog(self);d.setWindowTitle("Edit Shift Assignment");f=QFormLayout(d)
        emp=QComboBox();shift=QComboBox()
        [emp.addItem(f"{x['employee_no']} — {x['full_name']}",x['id']) for x in employees]
        [shift.addItem(x["name"],x["id"]) for x in shifts]
        emp.setCurrentIndex(max(0,emp.findData(item["employee_id"])));shift.setCurrentIndex(max(0,shift.findData(item["shift_id"])))
        effective=DateRangeWidget();effective.set_range(item["effective_from"])
        has_end=QCheckBox("Set effective-to date");has_end.setChecked(bool(item.get("effective_to")))
        effective_to=DateRangeWidget();effective_to.set_range(item.get("effective_to") or item["effective_from"]);effective_to.setEnabled(has_end.isChecked());has_end.toggled.connect(effective_to.setEnabled)
        off=QLineEdit(item.get("weekly_off_days") or "");off.setPlaceholderText("e.g. Sunday")
        f.addRow("Employee",emp);f.addRow("Shift",shift);f.addRow("Effective from",effective);f.addRow(has_end);f.addRow("Effective to",effective_to);f.addRow("Weekly off",off)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);f.addRow(buttons)
        if d.exec():
            try:
                old_employee_id=service.update_shift_assignment(item["id"],emp.currentData(),shift.currentData(),effective.get_from_date(),effective_to.get_from_date() if has_end.isChecked() else None,off.text().strip())
                service.recalculate_attendance_categories(old_employee_id)
                if emp.currentData()!=old_employee_id:service.recalculate_attendance_categories(emp.currentData())
                self.refresh();QMessageBox.information(self,"Shift Assignment","Assignment updated successfully.")
            except Exception as exc:QMessageBox.critical(self,"Could not update assignment",str(exc))

    def delete_assignment(self):
        item=self._selected_assignment()
        if not item:return
        reply=QMessageBox.question(self,"Delete Shift Assignment",f"Delete {item['employee_no']} — {item['shift_name']} assignment?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if reply!=QMessageBox.StandardButton.Yes:return
        try:
            employee_id=service.delete_shift_assignment(item["id"]);service.recalculate_attendance_categories(employee_id);self.refresh();QMessageBox.information(self,"Shift Assignment","Assignment deleted.")
        except Exception as exc:QMessageBox.critical(self,"Could not delete assignment",str(exc))


class PayrollTab(QWidget):
    def __init__(self,user,can_manage):
        super().__init__(); self.user=user; self.can_manage=can_manage; self.rows=[]; top=QHBoxLayout(); self.period=QLineEdit(date.today().strftime("%Y-%m")); self.period.setMaximumWidth(110); self.search=ModernSearchWidget("Search employee or payroll no..."); self.category=QComboBox(); self.category.addItems(["All Statuses","Draft","Paid"]); top.addWidget(QLabel("Month:")); top.addWidget(self.period); top.addWidget(self.search,1); top.addWidget(self.category); top.addStretch(); top.addWidget(_button("Create Payroll",self.create,True)) if can_manage else None; top.addWidget(_button("Mark Paid",self.pay)) if can_manage else None; self.table=_table(["Payroll No","Employee","Month","Basic","Additions","Deductions","Net Salary","Status","Paid Date"]); layout=QVBoxLayout(self); layout.addLayout(top); layout.addWidget(self.table); self.period.textChanged.connect(lambda _text:self.refresh()); self.search.search_changed.connect(lambda _text:self.refresh()); self.category.currentTextChanged.connect(lambda _text:self.refresh()); self.refresh()
    def refresh(self):
        rows=service.list_payrolls(self.period.text().strip());term=self.search.get_text().lower();status=self.category.currentText();self.rows=[x for x in rows if (not term or term in str(x.get("full_name") or "").lower() or term in str(x.get("employee_no") or "").lower() or term in str(x.get("payroll_no") or "").lower()) and (status=="All Statuses" or x.get("status")==status)]; self.table.setRowCount(len(self.rows))
        for r,x in enumerate(self.rows):
            additions=sum(float(x[k] or 0) for k in ("allowance","overtime_amount","bonus")); deductions=sum(float(x[k] or 0) for k in ("late_deduction","absence_deduction","advance_deduction","other_deduction")); values=(x["payroll_no"],x["full_name"],x["period_month"],f"{x['basic_salary']:,.2f}",f"{additions:,.2f}",f"{deductions:,.2f}",f"{x['net_salary']:,.2f}",x["status"],x["paid_date"] or "")
            for c,value in enumerate(values): self.table.setItem(r,c,QTableWidgetItem(str(value)))
    def create(self):
        employees=service.list_employees(status="Active")
        if not employees:return
        d=QDialog(self); d.setWindowTitle("Create Payroll"); f=QFormLayout(d); emp=QComboBox(); [emp.addItem(x["full_name"],x["id"]) for x in employees]; month=QLineEdit(self.period.text()); widgets={}
        f.addRow("Employee",emp); f.addRow("Month",month)
        for key,label in (("basic_salary","Basic salary"),("allowance","Allowance"),("overtime_amount","Overtime"),("bonus","Bonus"),("late_deduction","Late deduction"),("absence_deduction","Absence deduction"),("advance_deduction","Advance deduction"),("other_deduction","Other deduction")):
            w=QDoubleSpinBox(); w.setMaximum(999999999); w.setDecimals(2); widgets[key]=w; f.addRow(label,w)
        notes=QLineEdit(); f.addRow("Notes",notes); b=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); b.accepted.connect(d.accept); b.rejected.connect(d.reject); f.addRow(b)
        if d.exec():
            data={k:w.value() for k,w in widgets.items()}; data.update({"employee_id":emp.currentData(),"period_month":month.text().strip(),"notes":notes.text()})
            try: service.save_payroll(data,self.user["id"]); self.refresh()
            except Exception as exc: QMessageBox.critical(self,"Could not create payroll",str(exc))
    def pay(self):
        row=self.table.currentRow()
        if row<0:return
        record=self.rows[row]
        if record["status"]=="Paid": QMessageBox.information(self,"Payroll","This payroll is already paid."); return
        d=QDialog(self); f=QFormLayout(d); paid=DateRangeWidget(); method=QComboBox(); method.addItems(["Cash","Bank Transfer","Mobile Payment"]); f.addRow("Paid date",paid); f.addRow("Payment method",method); b=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); b.accepted.connect(d.accept); b.rejected.connect(d.reject); f.addRow(b)
        if d.exec(): service.pay_payroll(record["id"],paid.get_from_date(),method.currentText(),self.user.get("username","Admin")); self.refresh()


class EmployeeManagementPage(QWidget):
    def __init__(self,current_user,parent=None):
        super().__init__(parent); service.ensure_employee_schema(); self.current_user=current_user; perms=PermissionManager.get_user_permissions(current_user["id"]); layout=QVBoxLayout(self); title=QLabel("Employee Management"); title.setStyleSheet("font-size:20px;font-weight:700"); layout.addWidget(title)
        summary=service.employee_summary(); cards=QHBoxLayout(); cards.setSpacing(12); self.summary_cards={}
        card_definitions=[("active","Active Employees",summary["active"],"groups","#5865f2",False)]
        if "leave" in perms:card_definitions.append(("pending_leave","Pending Leave",summary["pending_leave"],"calendar_month","#f39c12",False))
        if "employee_documents" in perms:card_definitions.append(("expiring_documents","Documents Expiring",summary["expiring_documents"],"warning","#e74c3c",False))
        if "employee_finance" in perms:card_definitions.append(("outstanding_advances","Outstanding Advances",summary["outstanding_advances"],"payments","#16a085",True))
        for key,label,value,icon,color,is_currency in card_definitions:
            card=SummaryCardWidget(label,value,icon,color,icon_is_svg=True); card.set_value(value,currency_symbol="Ks" if is_currency else None,is_currency=is_currency); self.summary_cards[key]=card; cards.addWidget(card)
        layout.addLayout(cards); tabs=QTabWidget(); employee_tab=EmployeesTab("manage_employees" in perms); employee_tab.data_changed.connect(self.refresh_summary); tabs.addTab(employee_tab,"Employees")
        if "attendance" in perms: tabs.addTab(AttendanceTab(current_user["id"],"manage_attendance" in perms),"Attendance")
        if "shifts" in perms: tabs.addTab(ShiftsTab("manage_shifts" in perms),"Shifts")
        if "payroll" in perms: tabs.addTab(PayrollTab(current_user,"manage_payroll" in perms),"Payroll")
        from ui.employee_phase_two import LeaveTab, DocumentsTab, FinanceTab, PerformanceTab, CashSessionsTab
        if "leave" in perms: tabs.addTab(LeaveTab(current_user["id"],"manage_leave" in perms),"Leave")
        if "employee_documents" in perms: tabs.addTab(DocumentsTab("manage_employees" in perms),"Documents")
        if "employee_finance" in perms: tabs.addTab(FinanceTab(current_user["id"],"manage_employee_finance" in perms),"Advances & Commission")
        if "employee_performance" in perms: tabs.addTab(PerformanceTab(),"Performance")
        if "cash_sessions" in perms: tabs.addTab(CashSessionsTab(current_user["id"],"manage_cash_sessions" in perms),"Cash Sessions")
        tabs.currentChanged.connect(lambda _index:self.refresh_summary()); layout.addWidget(tabs)

    def refresh_summary(self):
        summary=service.employee_summary()
        for key,card in self.summary_cards.items():
            card.set_value(summary.get(key,0),currency_symbol="Ks" if key=="outstanding_advances" else None,is_currency=key=="outstanding_advances")
