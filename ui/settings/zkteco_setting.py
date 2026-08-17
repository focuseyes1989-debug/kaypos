"""Settings Center page for multiple ZKTeco attendance devices."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox,QComboBox,QFormLayout,QGroupBox,QHBoxLayout,
    QLabel,QLineEdit,QMessageBox,QSpinBox,QTableWidget,QTableWidgetItem,QHeaderView,
    QVBoxLayout,QWidget)

from services import employee_service
from services import zkteco_service
from ui.widgets.modern_button import ModernButton


def button(text,icon,slot,primary=False):
    item=ModernButton(text,ModernButton.PRIMARY if primary else ModernButton.SECONDARY);item.set_icon(icon);item.clicked.connect(slot);return item


class ZKTecoSettingWidget(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.selected_device_id=None;self.mapping_rows=[];self.setup_ui();self.load_devices();self.load_mappings()

    def setup_ui(self):
        root=QVBoxLayout(self);root.setContentsMargins(24,20,24,24);root.setSpacing(14)
        title=QLabel("ZKTeco Attendance Devices");title.setStyleSheet("font-size:18pt;font-weight:800");root.addWidget(title)
        note=QLabel("Configure one or more ZKTeco devices. Each employee can have a different User ID on each device.");note.setWordWrap(True);root.addWidget(note)
        form_group=QGroupBox("Device Configuration");form=QFormLayout(form_group);self.device_no=QSpinBox();self.device_no.setRange(1,9999);self.name=QLineEdit("ZKTeco Device");self.ip=QLineEdit();self.ip.setPlaceholderText("192.168.110.245");self.port=QSpinBox();self.port.setRange(1,65535);self.port.setValue(4370);self.key=QSpinBox();self.key.setRange(0,999999999);self.active=QCheckBox("Active");self.active.setChecked(True)
        for label,widget in (("Device ID",self.device_no),("Name",self.name),("IP address",self.ip),("TCP port",self.port),("Comm Key",self.key),("Status",self.active)):form.addRow(label,widget)
        actions=QHBoxLayout();actions.addStretch();actions.addWidget(button("New","add",self.clear_form));actions.addWidget(button("Test Connection","check",self.test));actions.addWidget(button("Save Device","save",self.save,True));form.addRow(actions);root.addWidget(form_group)
        self.devices=QTableWidget(0,8);self.devices.setHorizontalHeaderLabels(["DB ID","Device ID","Name","IP","Port","Serial","Last Sync","Status"]);self.devices.setColumnHidden(0,True);self.devices.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);self.devices.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);self.devices.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);self.devices.cellClicked.connect(self.select_device);root.addWidget(self.devices)
        mapping_group=QGroupBox("Employee ↔ Device User ID Mapping");mapping_layout=QVBoxLayout(mapping_group);mapping_form=QHBoxLayout();self.map_device=QComboBox();self.map_employee=QComboBox();self.map_user_id=QLineEdit();self.map_user_id.setPlaceholderText("Device User ID");mapping_form.addWidget(self.map_device,1);mapping_form.addWidget(self.map_employee,2);mapping_form.addWidget(self.map_user_id,1);mapping_form.addWidget(button("Save Mapping","save",self.save_mapping,True));mapping_form.addWidget(button("Remove","delete",self.remove_mapping));mapping_layout.addLayout(mapping_form)
        self.mappings=QTableWidget(0,5);self.mappings.setHorizontalHeaderLabels(["ID","Device","Employee ID","Employee","Device User ID"]);self.mappings.setColumnHidden(0,True);self.mappings.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);self.mappings.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);self.mappings.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);mapping_layout.addWidget(self.mappings);root.addWidget(mapping_group,1)
        sync_row=QHBoxLayout();self.status=QLabel("");self.status.setWordWrap(True);sync_row.addWidget(self.status,1);sync_row.addWidget(button("Sync All Active Devices","refresh",self.sync_all,True));root.addLayout(sync_row)

    def load_devices(self):
        rows=zkteco_service.list_devices();self.device_rows=rows;self.devices.setRowCount(len(rows));self.map_device.clear()
        for r,x in enumerate(rows):
            vals=(x['id'],x['device_no'],x['name'],x['ip_address'],x['port'],x['serial_no'] or '',x['last_sync_at'] or '',"Active" if x['is_active'] else "Inactive")
            for c,v in enumerate(vals):self.devices.setItem(r,c,QTableWidgetItem(str(v)))
            if x['is_active']:self.map_device.addItem(f"Device {x['device_no']} — {x['name']}",x['id'])
        self.map_employee.clear()
        for e in employee_service.list_employees(status="Active"):self.map_employee.addItem(f"{e['employee_no']} — {e['full_name']}",e['id'])

    def load_mappings(self):
        self.mapping_rows=zkteco_service.list_mappings();self.mappings.setRowCount(len(self.mapping_rows))
        for r,x in enumerate(self.mapping_rows):
            for c,v in enumerate((x['id'],f"{x['device_no']} — {x['device_name']}",x['employee_no'],x['full_name'],x['device_user_id'])):self.mappings.setItem(r,c,QTableWidgetItem(str(v)))

    def select_device(self,row,_column):
        x=self.device_rows[row];self.selected_device_id=x['id'];self.device_no.setValue(int(x['device_no']));self.name.setText(x['name'] or '');self.ip.setText(x['ip_address']);self.port.setValue(int(x['port']));self.key.setValue(int(x['comm_key'] or 0));self.active.setChecked(bool(x['is_active']))

    def clear_form(self):
        self.selected_device_id=None;self.device_no.setValue(max([int(x['device_no']) for x in self.device_rows],default=0)+1);self.name.setText("ZKTeco Device");self.ip.clear();self.port.setValue(4370);self.key.setValue(0);self.active.setChecked(True)

    def data(self):return {"device_no":self.device_no.value(),"name":self.name.text().strip(),"ip_address":self.ip.text().strip(),"port":self.port.value(),"comm_key":self.key.value(),"is_active":self.active.isChecked()}

    def save(self):
        if not self.ip.text().strip():QMessageBox.warning(self,"ZKTeco Device","IP address is required.");return
        try:zkteco_service.save_device(self.data(),self.selected_device_id);self.load_devices();self.load_mappings();self.status.setText("Device saved successfully.")
        except Exception as exc:QMessageBox.critical(self,"Could not save device",str(exc))

    def test(self):
        if not self.ip.text().strip():QMessageBox.warning(self,"ZKTeco Device","IP address is required.");return
        self.status.setText("Testing connection...")
        try:
            x=zkteco_service.test_device(self.ip.text().strip(),self.port.value(),self.key.value());self.status.setText(f"Connected — Serial: {x['serial']} | Platform: {x['platform']} | Users: {x['users']} | Logs: {x['logs']}")
        except Exception as exc:self.status.setText(f"Connection failed: {exc}")

    def save_mapping(self):
        if self.map_device.currentData() is None or self.map_employee.currentData() is None or not self.map_user_id.text().strip():QMessageBox.warning(self,"Mapping","Device, employee and Device User ID are required.");return
        try:zkteco_service.save_mapping(self.map_device.currentData(),self.map_employee.currentData(),self.map_user_id.text().strip());self.load_mappings();self.map_user_id.clear()
        except Exception as exc:QMessageBox.critical(self,"Could not save mapping",str(exc))

    def remove_mapping(self):
        row=self.mappings.currentRow()
        if row<0:return
        answer=QMessageBox.question(self,"Remove Mapping","Remove the selected employee/device mapping?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if answer==QMessageBox.StandardButton.Yes:zkteco_service.delete_mapping(self.mapping_rows[row]['id']);self.load_mappings()

    def sync_all(self):
        try:
            results=zkteco_service.sync_configured_mappings();self.load_devices();self.status.setText(f"Sync complete — mappings: {len(results)}, new punches: {sum(x['inserted'] for x in results)}")
        except Exception as exc:QMessageBox.critical(self,"ZKTeco Sync Failed",str(exc))
