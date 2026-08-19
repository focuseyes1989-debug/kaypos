"""Phase 1 user interface for the standalone Car Management client."""

from pathlib import Path

from PyQt6.QtCore import QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QScrollArea, QSpinBox, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from car_client.config import ServerSettings, SettingsStore
from car_client.form_preview_dialog import FormPreviewDialog
from car_client.form_print_dialog import FormPrintSettingsDialog
from car_client.network import CarServerClient
from car_client.records import DRIVER_FIELDS, FIELD_DEFINITIONS, VEHICLE_FIELDS, find_duplicate_records, validated_record


APP_STYLE = """
QWidget { background: #202328; color: #f2f3f5; font-family: "Segoe UI", "Myanmar Text"; font-size: 10pt; }
QLabel { background: transparent; border: none; }
QFrame#sidebar { background: #181a1f; border-right: 1px solid #343840; }
QLabel#brand { font-size: 18pt; font-weight: 700; color: #ffffff; }
QLabel#pageTitle { font-size: 20pt; font-weight: 700; }
QLabel#muted { color: #aeb3bd; }
QFrame#card { background: #2a2e34; border: 1px solid #3b4049; border-radius: 10px; }
QLineEdit, QSpinBox, QComboBox { background: #353a42; border: 1px solid #4a505b; border-radius: 6px; padding: 8px 10px; min-height: 20px; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid #5865f2; }
QTableWidget { background: #2a2e34; alternate-background-color: #25292f; border: 1px solid #3b4049; border-radius: 8px; gridline-color: #3b4049; }
QHeaderView::section { background: #20242a; color: #dfe2e7; border: none; border-right: 1px solid #3b4049; padding: 8px; font-weight: 600; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 3px 2px; }
QScrollBar::handle:vertical { background: #565d68; min-height: 32px; border-radius: 4px; }
QScrollBar::handle:vertical:hover { background: #6c7482; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; background: transparent; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px 3px; }
QScrollBar::handle:horizontal { background: #565d68; min-width: 32px; border-radius: 4px; }
QScrollBar::handle:horizontal:hover { background: #6c7482; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; background: transparent; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
QProgressBar#busy { min-height: 5px; max-height: 5px; border: none; border-radius: 2px; background: #343941; text-align: center; }
QProgressBar#busy::chunk { background: #5865f2; border-radius: 2px; }
QPushButton { background: #3a3f48; border: 1px solid #4c525e; border-radius: 6px; padding: 9px 16px; font-weight: 600; }
QPushButton:hover { background: #454b56; }
QPushButton#primary { background: #5865f2; border-color: #5865f2; color: white; }
QPushButton#primary:hover { background: #6874f4; }
QPushButton:disabled { color: #777d87; background: #30343a; }
QPushButton#nav { background: transparent; border: none; text-align: left; padding: 10px 12px; color: #b9bec8; }
QPushButton#nav:hover { background: #292d34; color: white; }
QPushButton#nav:checked { background: #343a55; color: white; border-left: 3px solid #5865f2; }
QLabel#status { border-radius: 6px; padding: 8px 12px; background: #343941; color: #c7cbd2; }
QLabel#status[status="success"] { background: #173d2b; color: #56d797; }
QLabel#status[status="error"] { background: #482428; color: #ff858d; }
QLabel#status[status="working"] { background: #31375b; color: #aeb5ff; }
"""


def _busy_bar():
    bar=QProgressBar();bar.setObjectName("busy");bar.setRange(0,0);bar.setTextVisible(False);bar.hide();return bar


class ConnectionTestThread(QThread):
    succeeded = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, settings: ServerSettings, parent=None):
        super().__init__(parent)
        self.settings = settings

    def run(self):
        try:
            CarServerClient(self.settings).test_connection()
            self.succeeded.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class SaveCarThread(QThread):
    succeeded = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, settings: ServerSettings, record: dict, parent=None):
        super().__init__(parent); self.settings=settings; self.record=record

    def run(self):
        try:
            CarServerClient(self.settings).save_car(self.record)
            self.succeeded.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class LoadCarsThread(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, settings: ServerSettings, term: str = "", parent=None):
        super().__init__(parent);self.settings=settings;self.term=term

    def run(self):
        try:self.succeeded.emit(CarServerClient(self.settings).search_cars(self.term))
        except Exception as exc:self.failed.emit(str(exc))


class RecordActionThread(QThread):
    succeeded = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, settings: ServerSettings, action: str, payload, parent=None):
        super().__init__(parent);self.settings=settings;self.action=action;self.payload=payload

    def run(self):
        try:
            client=CarServerClient(self.settings)
            if self.action=="update":client.update_car(self.payload)
            elif self.action=="delete":client.delete_car(self.payload)
            else:raise ValueError("Unknown record action.")
            self.succeeded.emit()
        except Exception as exc:self.failed.emit(str(exc))


class DuplicateCheckThread(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self,settings:ServerSettings,record:dict,exclude_id=None,parent=None):
        super().__init__(parent);self.settings=settings;self.record=record;self.exclude_id=exclude_id

    def run(self):
        try:
            records=CarServerClient(self.settings).get_cars()
            self.succeeded.emit(find_duplicate_records(records,self.record,self.exclude_id))
        except Exception as exc:self.failed.emit(str(exc))


class CarRecordDialog(QDialog):
    def __init__(self,record:dict,parent=None,editable=False):
        super().__init__(parent);self.record=record;self.editable=editable;self.inputs={}
        self.setWindowTitle("Edit Car Record" if editable else "Car Record Details");self.setMinimumWidth(720)
        layout=QVBoxLayout(self);grid=QGridLayout();grid.setHorizontalSpacing(18);grid.setVerticalSpacing(9)
        for index,(key,label,_placeholder) in enumerate(FIELD_DEFINITIONS):
            row=index//2;column=(index%2)*2;grid.addWidget(QLabel(label.replace(" *","")),row,column)
            editor=QLineEdit(str(record.get(key) or ""));editor.setReadOnly(not editable);self.inputs[key]=editor;grid.addWidget(editor,row,column+1)
        grid.setColumnStretch(1,1);grid.setColumnStretch(3,1);layout.addLayout(grid)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel) if editable else QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        if editable:buttons.accepted.connect(self._accept_validated);buttons.rejected.connect(self.reject)
        else:buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_validated(self):
        try:self.result_record=validated_record({key:editor.text() for key,editor in self.inputs.items()});self.result_record["id"]=self.record["id"]
        except ValueError as exc:QMessageBox.warning(self,"Required Information",str(exc));return
        self.accept()


class CarClientWindow(QMainWindow):
    def __init__(self, store: SettingsStore | None = None):
        super().__init__()
        self.store = store or SettingsStore()
        self.connection_thread = None
        self.save_thread = None
        self.records_thread = None
        self.car_picker_thread = None
        self.record_action_thread = None
        self.duplicate_thread = None
        self.pending_duplicate_action = None
        self.records = [];self.current_page=1;self.records_loaded=False
        self.last_record_term = ""
        self.setWindowTitle("KAY Car Management")
        self.setMinimumSize(860, 520)
        self.resize(980, 620)
        self.setStyleSheet(APP_STYLE)
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        root = QWidget(); self.setCentralWidget(root)
        shell = QHBoxLayout(root); shell.setContentsMargins(0, 0, 0, 0); shell.setSpacing(0)
        sidebar = QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(230)
        side = QVBoxLayout(sidebar); side.setContentsMargins(22, 28, 22, 22); side.setSpacing(10)
        brand = QLabel("KAY CAR"); brand.setObjectName("brand")
        subtitle = QLabel("Management Client"); subtitle.setObjectName("muted")
        side.addWidget(brand); side.addWidget(subtitle); side.addSpacing(24)
        self.input_nav=QPushButton("Car Data Input");self.input_nav.setObjectName("nav");self.input_nav.setCheckable(True)
        self.records_nav=QPushButton("Car Records");self.records_nav.setObjectName("nav");self.records_nav.setCheckable(True)
        self.print_nav=QPushButton("Print");self.print_nav.setObjectName("nav");self.print_nav.setCheckable(True)
        self.connection_nav=QPushButton("Server Connection");self.connection_nav.setObjectName("nav");self.connection_nav.setCheckable(True)
        side.addWidget(self.input_nav);side.addWidget(self.records_nav);side.addWidget(self.print_nav);side.addWidget(self.connection_nav);side.addStretch()
        version = QLabel("LAN Client · Phase 2"); version.setObjectName("muted"); side.addWidget(version)
        shell.addWidget(sidebar)

        content = QWidget(); body = QVBoxLayout(content); body.setContentsMargins(38, 32, 38, 32); body.setSpacing(18)
        title = QLabel("Server Connection"); title.setObjectName("pageTitle")
        description = QLabel("Connect this client to the KAY POS Car Management service on your shop LAN/Wi-Fi.")
        description.setObjectName("muted"); description.setWordWrap(True)
        body.addWidget(title); body.addWidget(description)

        card = QFrame(); card.setObjectName("card"); form = QVBoxLayout(card); form.setContentsMargins(24, 24, 24, 24); form.setSpacing(10)
        form.addWidget(QLabel("Server IP or host name"))
        self.host_input = QLineEdit(); self.host_input.setPlaceholderText("Example: 192.168.110.196"); form.addWidget(self.host_input)
        row = QHBoxLayout(); row.setSpacing(14)
        port_box = QVBoxLayout(); port_box.addWidget(QLabel("Port")); self.port_input = QSpinBox(); self.port_input.setRange(1, 65535); port_box.addWidget(self.port_input)
        timeout_box = QVBoxLayout(); timeout_box.addWidget(QLabel("Timeout (seconds)")); self.timeout_input = QSpinBox(); self.timeout_input.setRange(1, 30); timeout_box.addWidget(self.timeout_input)
        row.addLayout(port_box, 1); row.addLayout(timeout_box, 1); form.addLayout(row)
        connection_feedback=QHBoxLayout();self.status_label = QLabel("Settings loaded. Test the connection before continuing."); self.status_label.setObjectName("status");self.retry_connection_button=QPushButton("Retry");self.retry_connection_button.hide();self.retry_connection_button.clicked.connect(self.test_connection);connection_feedback.addWidget(self.status_label,1);connection_feedback.addWidget(self.retry_connection_button);form.addLayout(connection_feedback);self.connection_busy=_busy_bar();form.addWidget(self.connection_busy)
        actions = QHBoxLayout(); actions.addStretch()
        self.save_button = QPushButton("Save Settings"); self.test_button = QPushButton("Test Connection"); self.test_button.setObjectName("primary")
        self.save_button.clicked.connect(self.save_settings); self.test_button.clicked.connect(self.test_connection)
        actions.addWidget(self.save_button); actions.addWidget(self.test_button); form.addLayout(actions)
        body.addWidget(card); body.addStretch()
        note = QLabel("No PostgreSQL password is stored on this client. Data access stays behind the KAY POS server.")
        note.setObjectName("muted"); note.setWordWrap(True); body.addWidget(note)
        self.pages=QStackedWidget();self.pages.addWidget(self._build_input_page());self.pages.addWidget(self._build_records_page());self.pages.addWidget(self._build_print_page());self.pages.addWidget(content);shell.addWidget(self.pages,1)
        self.input_nav.clicked.connect(lambda:self._show_page(0));self.records_nav.clicked.connect(lambda:self._show_page(1));self.print_nav.clicked.connect(lambda:self._show_page(2));self.connection_nav.clicked.connect(lambda:self._show_page(3));self._show_page(0)

    def _build_print_page(self):
        page=QWidget();body=QVBoxLayout(page);body.setContentsMargins(38,32,38,32);body.setSpacing(14)
        title=QLabel("Print");title.setObjectName("pageTitle");description=QLabel("Set the default form page order and Windows printer preferences. These settings are reused for every selected car record.");description.setObjectName("muted");description.setWordWrap(True)
        body.addWidget(title);body.addWidget(description)
        self.print_settings_panel=FormPrintSettingsDialog(None,page,embedded=True);self.print_settings_panel.setObjectName("card");body.addWidget(self.print_settings_panel);body.addStretch()
        note=QLabel("To print database data, open Car Records, select a record, choose Auto Fill Forms, then Print Settings.");note.setObjectName("muted");note.setWordWrap(True);body.addWidget(note)
        return page

    def _build_input_page(self):
        page=QWidget();body=QVBoxLayout(page);body.setContentsMargins(38,32,38,32);body.setSpacing(16)
        title=QLabel("Car Data Input");title.setObjectName("pageTitle")
        description=QLabel("Add a new vehicle and driver record to the central Car Management database.");description.setObjectName("muted")
        body.addWidget(title);body.addWidget(description)
        mode_row=QHBoxLayout();mode_row.addWidget(QLabel("Entry Mode:"));self.entry_mode=QComboBox();self.entry_mode.addItem("New Car and Driver","new");self.entry_mode.addItem("Existing Car · New Driver","existing");mode_row.addWidget(self.entry_mode);mode_row.addStretch();body.addLayout(mode_row)
        self.existing_car_picker=QFrame();self.existing_car_picker.setObjectName("card");picker_layout=QHBoxLayout(self.existing_car_picker);picker_layout.setContentsMargins(14,10,14,10)
        picker_layout.addWidget(QLabel("Choose Existing Car:"));self.existing_car_combo=QComboBox();self.existing_car_combo.setEditable(True);self.existing_car_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert);self.existing_car_combo.setMinimumWidth(320);self.existing_car_combo.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive);self.existing_car_combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.load_existing_cars_button=QPushButton("Load Cars");picker_layout.addWidget(self.existing_car_combo,1);picker_layout.addWidget(self.load_existing_cars_button);body.addWidget(self.existing_car_picker);self.existing_car_picker.hide()
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.Shape.NoFrame)
        card=QFrame();card.setObjectName("card");grid=QGridLayout(card);grid.setContentsMargins(24,22,24,22);grid.setHorizontalSpacing(18);grid.setVerticalSpacing(9)
        self.car_inputs={}
        for index,(key,label,placeholder) in enumerate(FIELD_DEFINITIONS):
            row=index//2;column=(index%2)*2
            caption=QLabel(label);editor=QLineEdit();editor.setPlaceholderText(placeholder);editor.setClearButtonEnabled(True)
            grid.addWidget(caption,row,column);grid.addWidget(editor,row,column+1);self.car_inputs[key]=editor
        grid.setColumnStretch(1,1);grid.setColumnStretch(3,1);scroll.setWidget(card);body.addWidget(scroll,1)
        input_feedback=QHBoxLayout();self.input_status=QLabel("Fields marked with * are required.");self.input_status.setObjectName("status");self.retry_input_button=QPushButton("Retry Save");self.retry_input_button.hide();self.retry_input_button.clicked.connect(self.save_car_record);input_feedback.addWidget(self.input_status,1);input_feedback.addWidget(self.retry_input_button);body.addLayout(input_feedback);self.input_busy=_busy_bar();body.addWidget(self.input_busy)
        actions=QHBoxLayout();actions.addStretch();self.clear_button=QPushButton("Clear");self.save_car_button=QPushButton("Save Record");self.save_car_button.setObjectName("primary")
        self.clear_button.clicked.connect(self.clear_car_form);self.save_car_button.clicked.connect(self.save_car_record)
        actions.addWidget(self.clear_button);actions.addWidget(self.save_car_button);body.addLayout(actions)
        self.entry_mode.currentIndexChanged.connect(self._entry_mode_changed);self.existing_car_combo.currentIndexChanged.connect(self._existing_car_selected);self.load_existing_cars_button.clicked.connect(self._load_existing_cars)
        return page

    def _entry_mode_changed(self,_index):
        existing=self.entry_mode.currentData()=="existing";self.existing_car_picker.setVisible(existing)
        for field in VEHICLE_FIELDS:self.car_inputs[field].setReadOnly(existing)
        if existing:
            for field in VEHICLE_FIELDS:self.car_inputs[field].clear()
            if self.existing_car_combo.count()==0:self._load_existing_cars()
        else:
            for field in VEHICLE_FIELDS:self.car_inputs[field].clear()
            self._set_input_status("New Car mode. Enter vehicle and driver information.")

    def _load_existing_cars(self):
        if self.car_picker_thread and self.car_picker_thread.isRunning():return
        try:settings=self.store.load()
        except ValueError as exc:self._set_input_status(str(exc),"error");return
        self.load_existing_cars_button.setEnabled(False);self._set_input_status("Loading existing cars...","working")
        self.car_picker_thread=LoadCarsThread(settings,"",self);self.car_picker_thread.succeeded.connect(self._existing_cars_received);self.car_picker_thread.failed.connect(lambda message:self._set_input_status(message,"error"));self.car_picker_thread.finished.connect(self._car_picker_finished);self.car_picker_thread.start()

    def _existing_cars_received(self,records):
        unique={}
        for record in records or []:
            key=str(record.get("car_number") or "").strip().casefold()
            if key and key not in unique:unique[key]=record
        self.existing_car_combo.blockSignals(True);self.existing_car_combo.clear();self.existing_car_combo.addItem("Select or type a car number...",None)
        for record in sorted(unique.values(),key=lambda item:str(item.get("car_number") or "").casefold()):
            detail=str(record.get("type_of_car") or record.get("kind_of_car") or "").strip();label=f"{record.get('car_number')} — {detail}" if detail else str(record.get("car_number"));self.existing_car_combo.addItem(label,record)
        self.existing_car_combo.setCurrentIndex(0);self.existing_car_combo.blockSignals(False);self._set_input_status(f"Loaded {len(unique):,} unique car(s). Choose one, then enter the new driver information.","success")

    def _car_picker_finished(self):
        self.load_existing_cars_button.setEnabled(True);thread=self.car_picker_thread;self.car_picker_thread=None
        if thread:thread.deleteLater()

    def _existing_car_selected(self,_index):
        record=self.existing_car_combo.currentData()
        for field in VEHICLE_FIELDS:self.car_inputs[field].setText(str(record.get(field) or "") if isinstance(record,dict) else "")
        if isinstance(record,dict):self.car_inputs["driver_name"].setFocus();self._set_input_status("Vehicle details selected. Enter the new driver information.")

    def _build_records_page(self):
        page=QWidget();body=QVBoxLayout(page);body.setContentsMargins(30,28,30,24);body.setSpacing(12)
        title=QLabel("Car Records");title.setObjectName("pageTitle");description=QLabel("Browse and search records stored in the central PostgreSQL database.");description.setObjectName("muted")
        body.addWidget(title);body.addWidget(description)
        tools=QHBoxLayout();self.record_search=QLineEdit();self.record_search.setPlaceholderText("Search car number, driver, NRC, phone or address...");self.record_search.returnPressed.connect(self.search_records)
        self.search_button=QPushButton("Search");self.refresh_button=QPushButton("Refresh");self.clear_search_button=QPushButton("Clear Search")
        self.search_button.setObjectName("primary");self.search_button.clicked.connect(self.search_records);self.refresh_button.clicked.connect(self.refresh_records);self.clear_search_button.clicked.connect(self.clear_record_search)
        tools.addWidget(self.record_search,1);tools.addWidget(self.search_button);tools.addWidget(self.clear_search_button);tools.addWidget(self.refresh_button);body.addLayout(tools)
        headers=("ID","Car Number","Driver Name","Kind","Car Type","Age","NRC","Phone","Address","Engine No.","Frame No.","Updated")
        self.records_table=QTableWidget(0,len(headers));self.records_table.setHorizontalHeaderLabels(headers);self.records_table.setAlternatingRowColors(True);self.records_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.records_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.records_table.verticalHeader().setVisible(False)
        header=self.records_table.horizontalHeader();header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents);header.setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch);header.setMinimumSectionSize(70)
        body.addWidget(self.records_table,1)
        record_actions=QHBoxLayout();record_actions.addStretch();self.form_record_button=QPushButton("Auto Fill Forms");self.form_record_button.setObjectName("primary");self.view_record_button=QPushButton("View");self.edit_record_button=QPushButton("Edit");self.delete_record_button=QPushButton("Delete")
        self.form_record_button.clicked.connect(self.open_selected_forms);self.view_record_button.clicked.connect(self.view_selected_record);self.edit_record_button.clicked.connect(self.edit_selected_record);self.delete_record_button.clicked.connect(self.delete_selected_record);self.records_table.doubleClicked.connect(self.view_selected_record)
        record_actions.addWidget(self.form_record_button);record_actions.addWidget(self.view_record_button);record_actions.addWidget(self.edit_record_button);record_actions.addWidget(self.delete_record_button);body.addLayout(record_actions)
        footer=QHBoxLayout();self.record_count=QLabel("0 records");self.record_count.setObjectName("muted");footer.addWidget(self.record_count);footer.addStretch();footer.addWidget(QLabel("Rows:"))
        self.rows_per_page=QComboBox();self.rows_per_page.addItems(["10","25","50","100"]);self.rows_per_page.setCurrentText("25");self.rows_per_page.currentTextChanged.connect(self._page_size_changed);footer.addWidget(self.rows_per_page)
        self.previous_button=QPushButton("Previous");self.next_button=QPushButton("Next");self.page_label=QLabel("Page 1 / 1");self.previous_button.clicked.connect(lambda:self._change_page(-1));self.next_button.clicked.connect(lambda:self._change_page(1))
        footer.addWidget(self.previous_button);footer.addWidget(self.page_label);footer.addWidget(self.next_button);body.addLayout(footer)
        records_feedback=QHBoxLayout();self.records_status=QLabel("Open this page to load records.");self.records_status.setObjectName("status");self.retry_records_button=QPushButton("Retry");self.retry_records_button.hide();self.retry_records_button.clicked.connect(lambda:self._load_records(self.last_record_term));records_feedback.addWidget(self.records_status,1);records_feedback.addWidget(self.retry_records_button);body.addLayout(records_feedback);self.records_busy=_busy_bar();body.addWidget(self.records_busy)
        return page

    def _show_page(self,index):
        self.pages.setCurrentIndex(index);self.input_nav.setChecked(index==0);self.records_nav.setChecked(index==1);self.print_nav.setChecked(index==2);self.connection_nav.setChecked(index==3)
        if index==1 and not self.records_loaded:self.refresh_records()

    def _set_records_status(self,text,status="",retry=False):
        self.records_status.setText(text);self.records_status.setProperty("status",status)
        self.records_status.style().unpolish(self.records_status);self.records_status.style().polish(self.records_status);self.records_busy.setVisible(status=="working");self.retry_records_button.setVisible(bool(retry and status=="error"))

    def search_records(self):self._load_records(self.record_search.text())
    def refresh_records(self):self._load_records("")
    def clear_record_search(self):self.record_search.clear();self.refresh_records()

    def _load_records(self,term):
        if self.records_thread and self.records_thread.isRunning():return
        try:settings=self.store.load()
        except ValueError as exc:self._set_records_status(str(exc),"error");return
        self.last_record_term=str(term or "").strip();self.search_button.setEnabled(False);self.refresh_button.setEnabled(False);self._set_records_status("Loading records from the server...","working")
        self.records_thread=LoadCarsThread(settings,self.last_record_term,self);self.records_thread.succeeded.connect(self._records_received);self.records_thread.failed.connect(lambda message:self._set_records_status(message,"error",True));self.records_thread.finished.connect(self._records_thread_finished);self.records_thread.start()

    def _records_received(self,records):
        self.records=list(records or []);self.current_page=1;self.records_loaded=True;self._render_records_page();self._set_records_status(f"Loaded {len(self.records):,} record(s).","success")

    def _records_thread_finished(self):
        self.search_button.setEnabled(True);self.refresh_button.setEnabled(True)
        thread=self.records_thread;self.records_thread=None
        if thread:thread.deleteLater()

    def _render_records_page(self):
        size=int(self.rows_per_page.currentText());pages=max(1,(len(self.records)+size-1)//size);self.current_page=max(1,min(self.current_page,pages));start=(self.current_page-1)*size;visible=self.records[start:start+size]
        self.visible_records=visible;self.records_table.setRowCount(len(visible))
        for row,record in enumerate(visible):
            nrc=" / ".join(x for x in (str(record.get("nrc_place") or "").strip(),str(record.get("nrc_number") or "").strip()) if x)
            values=(record.get("id"),record.get("car_number"),record.get("driver_name"),record.get("kind_of_car"),record.get("type_of_car"),record.get("age"),nrc,record.get("phone_number"),record.get("address"),record.get("engine_number"),record.get("frame_number"),record.get("timestamp"))
            for column,value in enumerate(values):self.records_table.setItem(row,column,QTableWidgetItem(str(value or "")))
        self.record_count.setText(f"{len(self.records):,} records");self.page_label.setText(f"Page {self.current_page} / {pages}");self.previous_button.setEnabled(self.current_page>1);self.next_button.setEnabled(self.current_page<pages)

    def _page_size_changed(self,_value):self.current_page=1;self._render_records_page()
    def _change_page(self,step):self.current_page+=step;self._render_records_page()

    def _selected_record(self):
        row=self.records_table.currentRow()
        if row<0 or row>=len(getattr(self,"visible_records",[])):
            QMessageBox.information(self,"Car Records","Select a record from the table first.");return None
        return self.visible_records[row]

    def view_selected_record(self,*_args):
        record=self._selected_record()
        if record:CarRecordDialog(record,self,False).exec()

    def open_selected_forms(self):
        record=self._selected_record()
        if record:FormPreviewDialog(record,self).exec()

    def edit_selected_record(self):
        record=self._selected_record()
        if not record:return
        dialog=CarRecordDialog(record,self,True)
        if dialog.exec():self._begin_duplicate_check(dialog.result_record,"update",record.get("id"))

    def delete_selected_record(self):
        record=self._selected_record()
        if not record:return
        answer=QMessageBox.question(self,"Delete Car Record",f"Delete {record.get('car_number') or 'this record'} for {record.get('driver_name') or 'this driver'}?\n\nThis action cannot be undone.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if answer==QMessageBox.StandardButton.Yes:self._start_record_action("delete",int(record["id"]))

    def _set_record_actions_enabled(self,enabled):
        for button in (self.form_record_button,self.view_record_button,self.edit_record_button,self.delete_record_button):button.setEnabled(enabled)

    def _start_record_action(self,action,payload):
        if self.record_action_thread and self.record_action_thread.isRunning():return
        try:settings=self.store.load()
        except ValueError as exc:self._set_records_status(str(exc),"error");return
        self._set_record_actions_enabled(False);self._set_records_status("Updating the server..." if action=="update" else "Deleting record...","working")
        self.record_action_thread=RecordActionThread(settings,action,payload,self);self.record_action_thread.succeeded.connect(lambda:self._record_action_succeeded(action));self.record_action_thread.failed.connect(lambda message:self._set_records_status(message,"error"));self.record_action_thread.finished.connect(self._record_action_finished);self.record_action_thread.start()

    def _record_action_succeeded(self,action):
        self._set_records_status("Record updated successfully." if action=="update" else "Record deleted successfully.","success");self.records_loaded=False

    def _record_action_finished(self):
        self._set_record_actions_enabled(True);thread=self.record_action_thread;self.record_action_thread=None
        if thread:thread.deleteLater()
        if not self.records_loaded:QTimer.singleShot(0,self.refresh_records)

    def _set_input_status(self,text,status="",retry=False):
        self.input_status.setText(text);self.input_status.setProperty("status",status)
        self.input_status.style().unpolish(self.input_status);self.input_status.style().polish(self.input_status);self.input_busy.setVisible(status=="working");self.retry_input_button.setVisible(bool(retry and status=="error"))

    def clear_car_form(self):
        if self.entry_mode.currentData()=="existing":
            for field in DRIVER_FIELDS:self.car_inputs[field].clear()
            self._existing_car_selected(self.existing_car_combo.currentIndex());self.car_inputs["driver_name"].setFocus();self._set_input_status("Driver information cleared. The selected vehicle is unchanged.")
        else:
            for editor in self.car_inputs.values():editor.clear()
            self.car_inputs["car_number"].setFocus();self._set_input_status("Form cleared. Fields marked with * are required.")

    def save_car_record(self):
        if self.save_thread and self.save_thread.isRunning():return
        try:
            record=validated_record({key:editor.text() for key,editor in self.car_inputs.items()})
            settings=self.store.load()
        except ValueError as exc:
            self._set_input_status(str(exc),"error");return
        self._begin_duplicate_check(record,"save")

    def _begin_duplicate_check(self,record,action,exclude_id=None):
        if self.duplicate_thread and self.duplicate_thread.isRunning():return
        try:settings=self.store.load()
        except ValueError as exc:
            (self._set_input_status if action=="save" else self._set_records_status)(str(exc),"error");return
        self.pending_duplicate_action=(action,record);self.save_car_button.setEnabled(False);self.clear_button.setEnabled(False);self._set_record_actions_enabled(False)
        (self._set_input_status if action=="save" else self._set_records_status)("Checking for duplicate records...","working")
        self.duplicate_thread=DuplicateCheckThread(settings,record,exclude_id,self);self.duplicate_thread.succeeded.connect(self._duplicates_checked);self.duplicate_thread.failed.connect(self._duplicate_check_failed);self.duplicate_thread.finished.connect(self._duplicate_check_finished);self.duplicate_thread.start()

    def _duplicates_checked(self,duplicates):
        action,record=self.pending_duplicate_action
        proceed=True
        if duplicates:
            examples=", ".join(str(item.get("car_number") or item.get("id")) for item in duplicates[:3])
            proceed=QMessageBox.question(self,"Possible Duplicate",f"Found {len(duplicates)} record(s) with the same Car Number and driver NRC: {examples}.\n\nSave this car-driver record anyway?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes
        if proceed:
            if action=="save":self._start_car_save(record)
            else:self._start_record_action("update",record)
        else:(self._set_input_status if action=="save" else self._set_records_status)("Operation cancelled. No data was changed.","error")

    def _duplicate_check_failed(self,message):
        action,_record=self.pending_duplicate_action
        if action=="save":self._set_input_status(message,"error",True)
        else:self._set_records_status(message,"error")

    def _duplicate_check_finished(self):
        thread=self.duplicate_thread;self.duplicate_thread=None;self.pending_duplicate_action=None
        if thread:thread.deleteLater()
        save_busy=self.save_thread is not None;action_busy=self.record_action_thread is not None
        self.save_car_button.setEnabled(not save_busy);self.clear_button.setEnabled(not save_busy);self._set_record_actions_enabled(not action_busy)

    def _start_car_save(self,record):
        settings=self.store.load();self.save_car_button.setEnabled(False);self.clear_button.setEnabled(False);self._set_input_status("Saving record to the server...","working")
        self.save_thread=SaveCarThread(settings,record,self);self.save_thread.succeeded.connect(self._car_saved);self.save_thread.failed.connect(self._car_save_failed);self.save_thread.finished.connect(self._save_thread_finished);self.save_thread.start()

    def _car_saved(self):
        if self.entry_mode.currentData()=="existing":
            for field in DRIVER_FIELDS:self.car_inputs[field].clear()
            self._existing_car_selected(self.existing_car_combo.currentIndex());focus=self.car_inputs["driver_name"]
        else:
            for editor in self.car_inputs.values():editor.clear()
            focus=self.car_inputs["car_number"]
        self.records_loaded=False;self._set_input_status("Car record saved successfully.","success");focus.setFocus()

    def _car_save_failed(self,message):self._set_input_status(message,"error",True)

    def _save_thread_finished(self):
        self.save_car_button.setEnabled(True);self.clear_button.setEnabled(True)
        thread=self.save_thread;self.save_thread=None
        if thread:thread.deleteLater()

    def _load_settings(self):
        try:
            value = self.store.load()
        except ValueError:
            value = ServerSettings()
        self.host_input.setText(value.host); self.port_input.setValue(value.port); self.timeout_input.setValue(value.timeout)

    def current_settings(self) -> ServerSettings:
        return ServerSettings(self.host_input.text(), self.port_input.value(), self.timeout_input.value()).validated()

    def _set_status(self, text: str, status: str = "", retry=False):
        self.status_label.setText(text); self.status_label.setProperty("status", status)
        self.status_label.style().unpolish(self.status_label); self.status_label.style().polish(self.status_label);self.connection_busy.setVisible(status=="working");self.retry_connection_button.setVisible(bool(retry and status=="error"))

    def save_settings(self):
        try:
            value = self.store.save(self.current_settings())
            self._set_status(f"Saved: {value.host}:{value.port}", "success")
        except ValueError as exc:
            self._set_status(str(exc), "error")

    def test_connection(self):
        if self.connection_thread and self.connection_thread.isRunning():
            return
        try:
            value = self.store.save(self.current_settings())
        except ValueError as exc:
            self._set_status(str(exc), "error"); return
        self.test_button.setEnabled(False); self.save_button.setEnabled(False)
        self._set_status(f"Connecting to {value.host}:{value.port}...", "working")
        self.connection_thread = ConnectionTestThread(value, self)
        self.connection_thread.succeeded.connect(lambda: self._connection_finished(True, ""))
        self.connection_thread.failed.connect(lambda message: self._connection_finished(False, message))
        self.connection_thread.finished.connect(self._thread_finished)
        self.connection_thread.start()

    def _connection_finished(self, success: bool, message: str):
        if success:
            self._set_status("Connected successfully. Car Management service and database are ready.", "success")
        else:
            self._set_status(message, "error", True)

    def _thread_finished(self):
        self.test_button.setEnabled(True); self.save_button.setEnabled(True)
        thread = self.connection_thread; self.connection_thread = None
        if thread: thread.deleteLater()

    def closeEvent(self, event: QCloseEvent):
        if ((self.connection_thread and self.connection_thread.isRunning()) or
                (self.save_thread and self.save_thread.isRunning()) or
                (self.records_thread and self.records_thread.isRunning()) or
                (self.car_picker_thread and self.car_picker_thread.isRunning()) or
                (self.record_action_thread and self.record_action_thread.isRunning()) or
                (self.duplicate_thread and self.duplicate_thread.isRunning())):
            if self.pages.currentIndex()==0:self._set_input_status("A server request is still running. Please wait before closing.","working")
            elif self.pages.currentIndex()==1:self._set_records_status("A server request is still running. Please wait before closing.","working")
            else:self._set_status("A server request is still running. Please wait before closing.", "working")
            event.ignore(); return
        super().closeEvent(event)


def apply_app_identity(app: QApplication):
    app.setApplicationName("KAY Car Management")
    app.setOrganizationName("KAY POS")
    icon_path = Path(__file__).resolve().parents[1] / "assets" / "kay" / "kay_multi.ico"
    if icon_path.exists(): app.setWindowIcon(QIcon(str(icon_path)))
