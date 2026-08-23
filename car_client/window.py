"""Phase 1 user interface for the standalone Car Management client."""

from datetime import date, datetime
from collections import Counter
import os
from pathlib import Path

from PyQt6.QtCore import QDate, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QScrollArea, QSpinBox, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from car_client.config import ServerSettings, SettingsStore
from car_client.dashboard_charts import CompletenessChart, HorizontalBarChart
from car_client.form_preview_dialog import FormPreviewDialog
from car_client.form_print_dialog import FormPrintSettingsDialog, available_printer_names, print_record_pages, saved_printer_name
from car_client.network import CarServerClient
from car_client.qr_code import CarQrDialog, qr_access_url
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


def _normalized(value) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _driver_identity(record: dict) -> str:
    nrc = _normalized(record.get("nrc_number"))
    if nrc:
        return f"nrc:{nrc}"
    return f"fallback:{_normalized(record.get('driver_name'))}|{_normalized(record.get('phone_number'))}"


def calculate_dashboard_summary(records, today: date | None = None) -> dict[str, int]:
    """Calculate Phase 2 cards without treating repeated car-driver rows as unique."""
    records = list(records or [])
    today = today or date.today()
    unique_cars = set()
    unique_drivers = set()
    drivers_by_car = {}
    added_today = 0
    missing_information = 0
    important_fields = ("kind_of_car", "type_of_car", "age", "phone_number", "address", "engine_number", "frame_number")
    for record in records:
        car = _normalized(record.get("car_number"))
        driver = _driver_identity(record)
        if car:
            unique_cars.add(car)
            drivers_by_car.setdefault(car, set()).add(driver)
        if driver != "fallback:|":
            unique_drivers.add(driver)
        stamp = str(record.get("timestamp") or "").strip()
        try:
            if datetime.fromisoformat(stamp.replace("Z", "+00:00")).date() == today:
                added_today += 1
        except ValueError:
            pass
        if any(not str(record.get(field) or "").strip() for field in important_fields):
            missing_information += 1
    return {
        "total_records": len(records),
        "unique_cars": len(unique_cars),
        "total_drivers": len(unique_drivers),
        "multiple_driver_cars": sum(1 for drivers in drivers_by_car.values() if len(drivers) > 1),
        "added_today": added_today,
        "missing_information": missing_information,
    }


def recent_dashboard_records(records, limit=10) -> list[dict]:
    """Return the latest activity rows using the legacy timestamp field."""
    limit = max(1, int(limit))
    return sorted(
        list(records or []),
        key=lambda record: str(record.get("timestamp") or "").strip().replace("T", " "),
        reverse=True,
    )[:limit]


def calculate_dashboard_alerts(records) -> dict[str, list[dict]]:
    """Group actionable quality issues while allowing one car to have many drivers."""
    records = list(records or [])
    alerts = {
        "missing_age": [row for row in records if not str(row.get("age") or "").strip()],
        "missing_phone": [row for row in records if not str(row.get("phone_number") or "").strip()],
        "missing_address": [row for row in records if not str(row.get("address") or "").strip()],
        "missing_engine": [row for row in records if not str(row.get("engine_number") or "").strip()],
        "missing_frame": [row for row in records if not str(row.get("frame_number") or "").strip()],
    }
    duplicate_groups = {}
    cars = {}
    for row in records:
        car = _normalized(row.get("car_number"))
        nrc = _normalized(row.get("nrc_number"))
        if car and nrc:
            duplicate_groups.setdefault((car, nrc), []).append(row)
        if car:
            cars.setdefault(car, []).append(row)
    alerts["possible_duplicates"] = [
        row for group in duplicate_groups.values() if len(group) > 1 for row in group
    ]
    conflicting_cars = {
        car for car, rows in cars.items()
        if len({tuple(_normalized(row.get(field)) for field in ("kind_of_car", "type_of_car", "engine_number", "frame_number")) for row in rows}) > 1
    }
    alerts["vehicle_conflicts"] = [row for row in records if _normalized(row.get("car_number")) in conflicting_cars]
    return alerts


def _record_date(record: dict) -> date | None:
    stamp=str(record.get("timestamp") or "").strip()
    try:return datetime.fromisoformat(stamp.replace("Z","+00:00")).date()
    except ValueError:return None


def filter_dashboard_records(records,period="all",today:date|None=None,start:date|None=None,end:date|None=None):
    today=today or date.today();period=str(period or "all")
    if period=="all":return list(records or [])
    if period=="today":start=end=today
    elif period=="week":start=date.fromordinal(today.toordinal()-today.weekday());end=today
    elif period=="month":start=today.replace(day=1);end=today
    elif period=="year":start=today.replace(month=1,day=1);end=today
    elif period=="custom" and start and end:
        if start>end:start,end=end,start
    else:return list(records or [])
    return [record for record in records or [] if (stamp:=_record_date(record)) is not None and start<=stamp<=end]


def calculate_dashboard_insights(records) -> dict:
    records=list(records or []);type_cars={};kind_cars={};months=Counter();drivers_by_car={};car_labels={}
    important=("kind_of_car","type_of_car","age","phone_number","address","engine_number","frame_number")
    complete=0
    for index,record in enumerate(records):
        type_name=str(record.get("type_of_car") or "Unknown").strip() or "Unknown";kind_name=str(record.get("kind_of_car") or "Unknown").strip() or "Unknown"
        stamp=_record_date(record)
        if stamp:months[stamp.strftime("%Y-%m")]+=1
        car=_normalized(record.get("car_number"));driver=_driver_identity(record);car_key=car or f"row:{index}"
        type_cars.setdefault(type_name,set()).add(car_key);kind_cars.setdefault(kind_name,set()).add(car_key)
        if car:drivers_by_car.setdefault(car,set()).add(driver);car_labels.setdefault(car,str(record.get("car_number") or car))
        if all(str(record.get(field) or "").strip() for field in important):complete+=1
    month_data=sorted(months.items())[-6:]
    reused=sorted(((car_labels[car],len(drivers)) for car,drivers in drivers_by_car.items()),key=lambda item:(-item[1],item[0]))[:6]
    types=Counter({label:len(cars) for label,cars in type_cars.items()});kinds=Counter({label:len(cars) for label,cars in kind_cars.items()})
    return {"monthly":month_data,"types":types.most_common(6),"kinds":kinds.most_common(6),"reused":reused,"complete":complete,"incomplete":len(records)-complete}


class ConnectionTestThread(QThread):
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, settings: ServerSettings, parent=None):
        super().__init__(parent)
        self.settings = settings

    def run(self):
        try:
            client=CarServerClient(self.settings);client.test_connection()
            self.succeeded.emit(client.last_mode)
        except Exception as exc:
            self.failed.emit(str(exc))


class SaveCarThread(QThread):
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, settings: ServerSettings, record: dict, parent=None):
        super().__init__(parent); self.settings=settings; self.record=record

    def run(self):
        try:
            client=CarServerClient(self.settings);client.save_car(self.record)
            self.succeeded.emit(client.last_mode)
        except Exception as exc:
            self.failed.emit(str(exc))


class LoadCarsThread(QThread):
    succeeded = pyqtSignal(object, str)
    failed = pyqtSignal(str)

    def __init__(self, settings: ServerSettings, term: str = "", parent=None):
        super().__init__(parent);self.settings=settings;self.term=term

    def run(self):
        try:
            client=CarServerClient(self.settings);records=client.search_cars(self.term)
            self.succeeded.emit(records,client.last_mode)
        except Exception as exc:self.failed.emit(str(exc))


class RecordActionThread(QThread):
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, settings: ServerSettings, action: str, payload, parent=None):
        super().__init__(parent);self.settings=settings;self.action=action;self.payload=payload

    def run(self):
        try:
            client=CarServerClient(self.settings)
            if self.action=="update":client.update_car(self.payload)
            elif self.action=="delete":client.delete_car(self.payload)
            else:raise ValueError("Unknown record action.")
            self.succeeded.emit(client.last_mode)
        except Exception as exc:self.failed.emit(str(exc))


class IssueQrThread(QThread):
    succeeded = pyqtSignal(object, str)
    failed = pyqtSignal(str)

    def __init__(self, settings: ServerSettings, record_id: int, parent=None):
        super().__init__(parent);self.settings=settings;self.record_id=record_id

    def run(self):
        try:
            client=CarServerClient(self.settings);result=client.issue_qr(self.record_id)
            self.succeeded.emit(result,client.last_mode)
        except Exception as exc:self.failed.emit(str(exc))


class PrintAgentNetworkThread(QThread):
    succeeded = pyqtSignal(object, str)
    failed = pyqtSignal(str)

    def __init__(self, settings: ServerSettings, action: str, payload=None, parent=None):
        super().__init__(parent);self.settings=settings;self.action=action;self.payload=payload or {}

    def run(self):
        try:
            client=CarServerClient(self.settings)
            if self.action=="poll":
                printers=list(self.payload.get("printers") or [])
                client.register_print_agent(self.payload.get("client_name","Car Client"),printers,self.payload.get("default_printer",""))
                jobs=client.pending_print_jobs(1,printers)
                result=client.claim_print_job(jobs[0]["job_id"],printers) if jobs else None
            elif self.action=="status":
                result=client.update_print_job(
                    self.payload["job_id"],self.payload["status"],self.payload.get("error_message","")
                )
            else:raise ValueError("Unknown Print Agent action.")
            self.succeeded.emit(result,client.last_mode)
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


class DashboardAlertDialog(QDialog):
    def __init__(self,title:str,records:list[dict],parent=None):
        super().__init__(parent);self.records=list(records or [])
        self.setWindowTitle(title);self.setMinimumSize(820,480);self.resize(980,600)
        layout=QVBoxLayout(self);heading=QLabel(title);heading.setStyleSheet("font-size: 16pt; font-weight: 700;");layout.addWidget(heading)
        summary=QLabel(f"{len(self.records):,} affected record(s)");summary.setObjectName("muted");layout.addWidget(summary)
        headers=("ID","Car Number","Driver","Age","NRC","Phone","Engine No.","Frame No.")
        self.table=QTableWidget(len(self.records),len(headers));self.table.setHorizontalHeaderLabels(headers);self.table.setAlternatingRowColors(True);self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.table.verticalHeader().setVisible(False)
        for row,record in enumerate(self.records):
            nrc=" ".join(part for part in (str(record.get("nrc_place") or "").strip(),str(record.get("nrc_number") or "").strip()) if part)
            values=(record.get("id"),record.get("car_number"),record.get("driver_name"),record.get("age"),nrc,record.get("phone_number"),record.get("engine_number"),record.get("frame_number"))
            for column,value in enumerate(values):self.table.setItem(row,column,QTableWidgetItem(str(value or "")))
        header=self.table.horizontalHeader();header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents);header.setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch);layout.addWidget(self.table,1)
        actions=QHBoxLayout();actions.addStretch();view=QPushButton("View Record");close=QPushButton("Close");view.clicked.connect(self.view_record);close.clicked.connect(self.accept);self.table.doubleClicked.connect(self.view_record);actions.addWidget(view);actions.addWidget(close);layout.addLayout(actions)

    def view_record(self,*_args):
        row=self.table.currentRow()
        if row<0 or row>=len(self.records):
            QMessageBox.information(self,"Data Quality Alert","Select a record first.");return
        CarRecordDialog(self.records[row],self,False).exec()


class DashboardSettingsDialog(QDialog):
    CARD_LABELS=(("total_records","Total Records"),("unique_cars","Unique Cars"),("total_drivers","Total Drivers"),("multiple_driver_cars","Multiple-driver Cars"),("added_today","Added Today"),("missing_information","Missing Information"))

    def __init__(self,visibility:dict[str,bool],parent=None):
        super().__init__(parent);self.setWindowTitle("Dashboard Settings");self.setMinimumWidth(390);layout=QVBoxLayout(self)
        title=QLabel("Visible Summary Cards");title.setStyleSheet("font-size: 15pt; font-weight: 700;");layout.addWidget(title);description=QLabel("Choose which summary cards appear on the Dashboard.");description.setObjectName("muted");layout.addWidget(description);self.checks={}
        for key,label in self.CARD_LABELS:
            check=QCheckBox(label);check.setChecked(visibility.get(key,True));layout.addWidget(check);self.checks[key]=check
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self._save);buttons.rejected.connect(self.reject);layout.addWidget(buttons)

    def _save(self):
        if not any(check.isChecked() for check in self.checks.values()):
            QMessageBox.warning(self,"Dashboard Settings","Keep at least one summary card visible.");return
        self.visibility={key:check.isChecked() for key,check in self.checks.items()};self.accept()


class CarClientWindow(QMainWindow):
    def __init__(self, store: SettingsStore | None = None):
        super().__init__()
        self.store = store or SettingsStore()
        self.connection_thread = None
        self.dashboard_thread = None
        self.save_thread = None
        self.records_thread = None
        self.car_picker_thread = None
        self.record_action_thread = None
        self.qr_thread = None
        self.print_agent_thread = None
        self.pending_print_status = None
        self.duplicate_thread = None
        self.pending_duplicate_action = None
        self.records = [];self.current_page=1;self.records_loaded=False
        self.dashboard_needs_refresh=True;self.dashboard_recent_records=[];self.dashboard_alert_records={};self.dashboard_all_records=[]
        self.last_record_term = ""
        self.setWindowTitle("KAY Car Management")
        self.setMinimumSize(900, 560)
        self.resize(1120, 720)
        self.setStyleSheet(APP_STYLE)
        self._build_ui()
        self._load_settings()
        self.print_agent_timer=QTimer(self);self.print_agent_timer.setInterval(5000);self.print_agent_timer.timeout.connect(self.poll_print_agent);self.print_agent_timer.start()
        QTimer.singleShot(1200,self.poll_print_agent)

    def _build_ui(self):
        root = QWidget(); self.setCentralWidget(root)
        shell = QHBoxLayout(root); shell.setContentsMargins(0, 0, 0, 0); shell.setSpacing(0)
        sidebar = QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(230)
        side = QVBoxLayout(sidebar); side.setContentsMargins(22, 28, 22, 22); side.setSpacing(10)
        brand = QLabel("KAY CAR"); brand.setObjectName("brand")
        subtitle = QLabel("Management Client"); subtitle.setObjectName("muted")
        side.addWidget(brand); side.addWidget(subtitle); side.addSpacing(24)
        self.dashboard_nav=QPushButton("Dashboard");self.dashboard_nav.setObjectName("nav");self.dashboard_nav.setCheckable(True)
        self.input_nav=QPushButton("Car Data Input");self.input_nav.setObjectName("nav");self.input_nav.setCheckable(True)
        self.records_nav=QPushButton("Car Records");self.records_nav.setObjectName("nav");self.records_nav.setCheckable(True)
        self.print_nav=QPushButton("Print");self.print_nav.setObjectName("nav");self.print_nav.setCheckable(True)
        self.connection_nav=QPushButton("Server Connection");self.connection_nav.setObjectName("nav");self.connection_nav.setCheckable(True)
        side.addWidget(self.dashboard_nav);side.addWidget(self.input_nav);side.addWidget(self.records_nav);side.addWidget(self.print_nav);side.addWidget(self.connection_nav);side.addStretch()
        version = QLabel("Hybrid · LAN / Cloud / Offline"); version.setObjectName("muted"); side.addWidget(version)
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
        form.addSpacing(12)
        form.addWidget(QLabel("Cloud HTTPS URL (optional)"))
        self.cloud_url_input=QLineEdit();self.cloud_url_input.setPlaceholderText("https://your-cloud-domain.example");form.addWidget(self.cloud_url_input)
        form.addWidget(QLabel("Cloud API key"))
        self.cloud_api_key_input=QLineEdit();self.cloud_api_key_input.setEchoMode(QLineEdit.EchoMode.Password);form.addWidget(self.cloud_api_key_input)
        form.addWidget(QLabel("Owner QR Web URL (optional · blank uses HTTPS LAN port 8000)"))
        self.owner_web_url_input=QLineEdit();self.owner_web_url_input.setPlaceholderText("https://192.168.110.196:8000");form.addWidget(self.owner_web_url_input)
        self.offline_enabled_check=QCheckBox("Allow local offline use and sync when a connection returns");self.offline_enabled_check.setChecked(True);form.addWidget(self.offline_enabled_check)
        connection_feedback=QHBoxLayout();self.status_label = QLabel("Settings loaded. Test the connection before continuing."); self.status_label.setObjectName("status");self.retry_connection_button=QPushButton("Retry");self.retry_connection_button.hide();self.retry_connection_button.clicked.connect(self.test_connection);connection_feedback.addWidget(self.status_label,1);connection_feedback.addWidget(self.retry_connection_button);form.addLayout(connection_feedback);self.connection_busy=_busy_bar();form.addWidget(self.connection_busy)
        actions = QHBoxLayout(); actions.addStretch()
        self.save_button = QPushButton("Save Settings"); self.test_button = QPushButton("Test Connection"); self.test_button.setObjectName("primary")
        self.save_button.clicked.connect(self.save_settings); self.test_button.clicked.connect(self.test_connection)
        actions.addWidget(self.save_button); actions.addWidget(self.test_button); form.addLayout(actions)
        body.addWidget(card); body.addStretch()
        note = QLabel("Connection order: shop LAN, then Cloud HTTPS, then local storage under this Windows user profile. Pending offline changes sync automatically when a server returns.")
        note.setObjectName("muted"); note.setWordWrap(True); body.addWidget(note)
        self.pages=QStackedWidget();self.pages.addWidget(self._build_dashboard_page());self.pages.addWidget(self._build_input_page());self.pages.addWidget(self._build_records_page());self.pages.addWidget(self._build_print_page());self.pages.addWidget(content);shell.addWidget(self.pages,1)
        self.dashboard_nav.clicked.connect(lambda:self._show_page(0));self.input_nav.clicked.connect(lambda:self._show_page(1));self.records_nav.clicked.connect(lambda:self._show_page(2));self.print_nav.clicked.connect(lambda:self._show_page(3));self.connection_nav.clicked.connect(lambda:self._show_page(4));self._show_page(0)
        QTimer.singleShot(0,self.refresh_dashboard)

    def _build_dashboard_page(self):
        page=QWidget();outer=QVBoxLayout(page);outer.setContentsMargins(0,0,0,0);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.Shape.NoFrame);content=QWidget();body=QVBoxLayout(content);body.setContentsMargins(34,30,34,28);body.setSpacing(16);scroll.setWidget(content);outer.addWidget(scroll)
        heading=QHBoxLayout();titles=QVBoxLayout();title=QLabel("Dashboard");title.setObjectName("pageTitle");description=QLabel("Car Management overview and service health.");description.setObjectName("muted");titles.addWidget(title);titles.addWidget(description);heading.addLayout(titles);heading.addStretch()
        self.dashboard_settings_button=QPushButton("Settings");self.dashboard_settings_button.clicked.connect(self.open_dashboard_settings);heading.addWidget(self.dashboard_settings_button);self.dashboard_refresh_button=QPushButton("Refresh");self.dashboard_refresh_button.setObjectName("primary");self.dashboard_refresh_button.clicked.connect(self.refresh_dashboard);heading.addWidget(self.dashboard_refresh_button);body.addLayout(heading)
        status_card=QFrame();status_card.setObjectName("card");status_layout=QVBoxLayout(status_card);status_layout.setContentsMargins(22,18,22,18);status_layout.setSpacing(10)
        status_header=QHBoxLayout();status_title=QLabel("Server & Database");status_title.setStyleSheet("font-size: 12pt; font-weight: 700;");self.dashboard_connection_badge=QLabel("Not checked");self.dashboard_connection_badge.setObjectName("status");status_header.addWidget(status_title);status_header.addStretch();status_header.addWidget(self.dashboard_connection_badge);status_layout.addLayout(status_header)
        self.dashboard_status=QLabel("Checking the Car Management service...");self.dashboard_status.setObjectName("muted");self.dashboard_status.setWordWrap(True);status_layout.addWidget(self.dashboard_status)
        retry_row=QHBoxLayout();retry_row.addStretch();self.dashboard_retry_button=QPushButton("Retry");self.dashboard_retry_button.clicked.connect(self.refresh_dashboard);self.dashboard_retry_button.hide();retry_row.addWidget(self.dashboard_retry_button);status_layout.addLayout(retry_row)
        self.dashboard_busy=_busy_bar();status_layout.addWidget(self.dashboard_busy);body.addWidget(status_card)
        quick_title=QLabel("Quick Actions");quick_title.setStyleSheet("font-size: 12pt; font-weight: 700;");body.addWidget(quick_title);quick_actions=QGridLayout();quick_actions.setHorizontalSpacing(8);quick_actions.setVerticalSpacing(8)
        quick_definitions=(("Add New Car",self.dashboard_add_new),("Existing Car · New Driver",self.dashboard_add_driver),("Search Records",self.dashboard_search_records),("Auto Fill Forms",self.dashboard_open_forms),("Open Print Page",lambda:self._show_page(3)),("Refresh Dashboard",self.refresh_dashboard))
        for index,(label,callback) in enumerate(quick_definitions):button=QPushButton(label);button.clicked.connect(callback);quick_actions.addWidget(button,index//3,index%3)
        for column in range(3):quick_actions.setColumnStretch(column,1)
        body.addLayout(quick_actions)
        cards=QGridLayout();cards.setHorizontalSpacing(14);cards.setVerticalSpacing(14)
        self.dashboard_values={};self.dashboard_cards={}
        card_definitions=(("total_records","Total Records","All car-driver records"),("unique_cars","Unique Cars","Counted by Car Number"),("total_drivers","Total Drivers","Unique NRC or name/phone"),("multiple_driver_cars","Multiple-driver Cars","Cars used by 2+ drivers"),("added_today","Added Today","Records created today"),("missing_information","Missing Information","Records needing completion"))
        for index,(key,label,hint) in enumerate(card_definitions):
            card=QFrame();card.setObjectName("card");layout=QVBoxLayout(card);layout.setContentsMargins(20,18,20,18);caption=QLabel(label);caption.setStyleSheet("font-weight: 700;");value=QLabel("—");value.setStyleSheet("font-size: 22pt; font-weight: 700;");note=QLabel(hint);note.setObjectName("muted");layout.addWidget(caption);layout.addWidget(value);layout.addWidget(note);cards.addWidget(card,index//2,index%2);self.dashboard_values[key]=value;self.dashboard_cards[key]=card;card.setVisible(self.store.settings.value(f"dashboard/cards/{key}",True,type=bool))
        cards.setColumnStretch(0,1);cards.setColumnStretch(1,1);body.addLayout(cards)
        alerts_title=QLabel("Data Quality & Alerts");alerts_title.setStyleSheet("font-size: 12pt; font-weight: 700;");body.addWidget(alerts_title)
        alerts_grid=QGridLayout();alerts_grid.setHorizontalSpacing(8);alerts_grid.setVerticalSpacing(8);self.dashboard_alert_buttons={}
        alert_definitions=(("missing_age","Missing Age"),("missing_phone","Missing Phone"),("missing_address","Missing Address"),("missing_engine","Missing Engine"),("missing_frame","Missing Frame"),("possible_duplicates","Possible Duplicates"),("vehicle_conflicts","Vehicle Conflicts"))
        for index,(key,label) in enumerate(alert_definitions):
            button=QPushButton(f"{label}  —");button.clicked.connect(lambda _checked=False,alert_key=key,alert_title=label:self.open_dashboard_alert(alert_key,alert_title));alerts_grid.addWidget(button,index//4,index%4);self.dashboard_alert_buttons[key]=button
        for column in range(4):alerts_grid.setColumnStretch(column,1)
        body.addLayout(alerts_grid)
        activity_header=QHBoxLayout();activity_title=QLabel("Recent Activity");activity_title.setStyleSheet("font-size: 12pt; font-weight: 700;");activity_header.addWidget(activity_title);activity_header.addStretch();activity_header.addWidget(QLabel("Show:"));self.dashboard_activity_limit=QComboBox();self.dashboard_activity_limit.addItems(["5","10","20"]);saved_limit=str(self.store.settings.value("dashboard/activity_limit","10"));self.dashboard_activity_limit.setCurrentText(saved_limit if saved_limit in {"5","10","20"} else "10");self.dashboard_activity_limit.currentTextChanged.connect(self._dashboard_activity_limit_changed);activity_header.addWidget(self.dashboard_activity_limit);self.dashboard_view_button=QPushButton("View Record");self.dashboard_view_button.clicked.connect(self.view_dashboard_record);activity_header.addWidget(self.dashboard_view_button);body.addLayout(activity_header)
        activity_headers=("Updated","Car Number","Driver","Vehicle","Phone")
        self.dashboard_activity_table=QTableWidget(0,len(activity_headers));self.dashboard_activity_table.setHorizontalHeaderLabels(activity_headers);self.dashboard_activity_table.setAlternatingRowColors(True);self.dashboard_activity_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.dashboard_activity_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.dashboard_activity_table.verticalHeader().setVisible(False);self.dashboard_activity_table.doubleClicked.connect(self.view_dashboard_record)
        activity_table_header=self.dashboard_activity_table.horizontalHeader();activity_table_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents);activity_table_header.setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch);activity_table_header.setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch);self.dashboard_activity_table.setFixedHeight(235);body.addWidget(self.dashboard_activity_table)
        insights_header=QHBoxLayout();insights_title=QLabel("Charts & Insights");insights_title.setStyleSheet("font-size: 12pt; font-weight: 700;");insights_header.addWidget(insights_title);insights_header.addStretch();insights_header.addWidget(QLabel("Date:"));self.dashboard_period=QComboBox();self.dashboard_period.addItem("All Time","all");self.dashboard_period.addItem("Today","today");self.dashboard_period.addItem("This Week","week");self.dashboard_period.addItem("This Month","month");self.dashboard_period.addItem("This Year","year");self.dashboard_period.addItem("Custom Range","custom");saved_period=str(self.store.settings.value("dashboard/period","all"));saved_period_index=self.dashboard_period.findData(saved_period);self.dashboard_period.setCurrentIndex(saved_period_index if saved_period_index>=0 else 0);self.dashboard_period.currentIndexChanged.connect(self._dashboard_period_changed);insights_header.addWidget(self.dashboard_period)
        saved_start=QDate.fromString(str(self.store.settings.value("dashboard/start_date","")),Qt.DateFormat.ISODate);saved_end=QDate.fromString(str(self.store.settings.value("dashboard/end_date","")),Qt.DateFormat.ISODate);self.dashboard_start_date=QDateEdit(saved_start if saved_start.isValid() else QDate.currentDate().addMonths(-1));self.dashboard_end_date=QDateEdit(saved_end if saved_end.isValid() else QDate.currentDate());self.dashboard_start_date.setCalendarPopup(True);self.dashboard_end_date.setCalendarPopup(True);self.dashboard_start_date.setDisplayFormat("dd MMM yyyy");self.dashboard_end_date.setDisplayFormat("dd MMM yyyy");self.dashboard_start_date.dateChanged.connect(self._dashboard_dates_changed);self.dashboard_end_date.dateChanged.connect(self._dashboard_dates_changed);custom=saved_period=="custom";self.dashboard_start_date.setVisible(custom);self.dashboard_end_date.setVisible(custom);insights_header.addWidget(self.dashboard_start_date);insights_header.addWidget(self.dashboard_end_date);body.addLayout(insights_header)
        charts=QGridLayout();charts.setHorizontalSpacing(14);charts.setVerticalSpacing(14)
        def chart_card(title_text,widget,row,column,column_span=1):
            card=QFrame();card.setObjectName("card");layout=QVBoxLayout(card);layout.setContentsMargins(16,14,16,14);caption=QLabel(title_text);caption.setStyleSheet("font-weight: 700;");layout.addWidget(caption);layout.addWidget(widget,1);charts.addWidget(card,row,column,1,column_span)
        self.monthly_chart=HorizontalBarChart("#5865f2");self.type_chart=HorizontalBarChart("#3ba5d8");self.kind_chart=HorizontalBarChart("#e89b18");self.reused_chart=HorizontalBarChart("#9b7bf2");self.completeness_chart=CompletenessChart()
        chart_card("Records Added by Month",self.monthly_chart,0,0);chart_card("Cars by Type",self.type_chart,0,1);chart_card("Cars by Kind",self.kind_chart,1,0);chart_card("Most Reused Cars · Drivers",self.reused_chart,1,1);chart_card("Complete vs Incomplete",self.completeness_chart,2,0,2);charts.setColumnStretch(0,1);charts.setColumnStretch(1,1);body.addLayout(charts)
        return page

    def _set_dashboard_status(self,text,status="",retry=False):
        self.dashboard_status.setText(text);self.dashboard_connection_badge.setText("Connected" if status=="success" else "Unavailable" if status=="error" else "Checking...")
        self.dashboard_connection_badge.setProperty("status",status);self.dashboard_connection_badge.style().unpolish(self.dashboard_connection_badge);self.dashboard_connection_badge.style().polish(self.dashboard_connection_badge)
        self.dashboard_busy.setVisible(status=="working");self.dashboard_retry_button.setVisible(bool(retry and status=="error"))

    def refresh_dashboard(self):
        if self.dashboard_thread and self.dashboard_thread.isRunning():return
        try:settings=self.store.load()
        except ValueError as exc:self._set_dashboard_status(str(exc),"error",True);return
        self.dashboard_refresh_button.setEnabled(False);self._set_dashboard_status(f"Connecting to {settings.host}:{settings.port}...","working")
        self.dashboard_thread=LoadCarsThread(settings,"",self);self.dashboard_thread.succeeded.connect(self._dashboard_ready);self.dashboard_thread.failed.connect(self._dashboard_failed);self.dashboard_thread.finished.connect(self._dashboard_thread_finished);self.dashboard_thread.start()

    def _dashboard_ready(self,records,mode="lan"):
        self.dashboard_all_records=list(records or [])
        summary=calculate_dashboard_summary(records)
        for key,label in self.dashboard_values.items():label.setText(f"{summary[key]:,}")
        self.dashboard_alert_records=calculate_dashboard_alerts(records)
        for key,button in self.dashboard_alert_buttons.items():
            count=len(self.dashboard_alert_records.get(key,[]));base=button.text().rsplit("  ",1)[0];button.setText(f"{base}  {count:,}");button.setEnabled(count>0)
        self.dashboard_recent_records=list(records or []);self._render_dashboard_activity();self._update_dashboard_charts();self.dashboard_needs_refresh=False
        source="local offline cache" if mode=="offline" else f"{mode.upper()} database"
        self._set_dashboard_status(f"Dashboard loaded {summary['total_records']:,} record(s) from {source}.","success")

    def open_dashboard_alert(self,key,title):
        records=self.dashboard_alert_records.get(key,[])
        if records:DashboardAlertDialog(title,records,self).exec()

    def open_dashboard_settings(self):
        current={key:not card.isHidden() for key,card in self.dashboard_cards.items()};dialog=DashboardSettingsDialog(current,self)
        if not dialog.exec():return
        for key,visible in dialog.visibility.items():self.dashboard_cards[key].setVisible(visible);self.store.settings.setValue(f"dashboard/cards/{key}",visible)
        self.store.settings.sync()

    def dashboard_add_new(self):
        self._show_page(1);self.entry_mode.setCurrentIndex(self.entry_mode.findData("new"));self.car_inputs["car_number"].setFocus()

    def dashboard_add_driver(self):
        self._show_page(1);self.entry_mode.setCurrentIndex(self.entry_mode.findData("existing"));self.existing_car_combo.setFocus()

    def dashboard_search_records(self):
        self._show_page(2);self.record_search.setFocus();self.record_search.selectAll()

    def dashboard_open_forms(self):
        self._show_page(2)
        if self.records_loaded:self._set_records_status("Select a record, then click Auto Fill Forms.","success")

    def _dashboard_period_changed(self,*_args):
        custom=self.dashboard_period.currentData()=="custom";self.dashboard_start_date.setVisible(custom);self.dashboard_end_date.setVisible(custom);self.store.settings.setValue("dashboard/period",self.dashboard_period.currentData());self.store.settings.sync();self._update_dashboard_charts()

    def _dashboard_dates_changed(self,*_args):
        self.store.settings.setValue("dashboard/start_date",self.dashboard_start_date.date().toString(Qt.DateFormat.ISODate));self.store.settings.setValue("dashboard/end_date",self.dashboard_end_date.date().toString(Qt.DateFormat.ISODate));self.store.settings.sync();self._update_dashboard_charts()

    def _dashboard_activity_limit_changed(self,*_args):
        self.store.settings.setValue("dashboard/activity_limit",self.dashboard_activity_limit.currentText());self.store.settings.sync();self._render_dashboard_activity()

    def _update_dashboard_charts(self,*_args):
        if not hasattr(self,"monthly_chart"):return
        records=filter_dashboard_records(self.dashboard_all_records,self.dashboard_period.currentData(),start=self.dashboard_start_date.date().toPyDate(),end=self.dashboard_end_date.date().toPyDate());insights=calculate_dashboard_insights(records)
        self.monthly_chart.set_data(insights["monthly"]);self.type_chart.set_data(insights["types"]);self.kind_chart.set_data(insights["kinds"]);self.reused_chart.set_data(insights["reused"]);self.completeness_chart.set_data(insights["complete"],insights["incomplete"])

    def _render_dashboard_activity(self,*_args):
        if not hasattr(self,"dashboard_activity_table"):return
        limit=int(self.dashboard_activity_limit.currentText());visible=recent_dashboard_records(self.dashboard_recent_records,limit);self.dashboard_visible_activity=visible;self.dashboard_activity_table.setRowCount(len(visible))
        for row,record in enumerate(visible):
            vehicle=" ".join(part for part in (str(record.get("kind_of_car") or "").strip(),str(record.get("type_of_car") or "").strip()) if part)
            values=(record.get("timestamp"),record.get("car_number"),record.get("driver_name"),vehicle,record.get("phone_number"))
            for column,value in enumerate(values):self.dashboard_activity_table.setItem(row,column,QTableWidgetItem(str(value or "")))
        self.dashboard_view_button.setEnabled(bool(visible))

    def view_dashboard_record(self,*_args):
        row=self.dashboard_activity_table.currentRow()
        if row<0 or row>=len(getattr(self,"dashboard_visible_activity",[])):
            QMessageBox.information(self,"Recent Activity","Select a record first.");return
        CarRecordDialog(self.dashboard_visible_activity[row],self,False).exec()

    def _dashboard_failed(self,message):
        self._set_dashboard_status(message,"error",True)

    def _dashboard_thread_finished(self):
        self.dashboard_refresh_button.setEnabled(True);thread=self.dashboard_thread;self.dashboard_thread=None
        if thread:thread.deleteLater()

    def _build_print_page(self):
        page=QWidget();body=QVBoxLayout(page);body.setContentsMargins(38,32,38,32);body.setSpacing(14)
        title=QLabel("Print");title.setObjectName("pageTitle");description=QLabel("Set the default form page order and Windows printer preferences. These settings are reused for every selected car record.");description.setObjectName("muted");description.setWordWrap(True)
        body.addWidget(title);body.addWidget(description)
        self.print_settings_panel=FormPrintSettingsDialog(None,page,embedded=True);self.print_settings_panel.setObjectName("card");body.addWidget(self.print_settings_panel)
        agent_card=QFrame();agent_card.setObjectName("card");agent_layout=QVBoxLayout(agent_card);agent_layout.setContentsMargins(22,18,22,18)
        self.print_agent_enabled=QCheckBox("Enable automatic Owner Web print jobs");self.print_agent_enabled.setChecked(self.store.settings.value("print_agent/enabled",True,type=bool));agent_layout.addWidget(self.print_agent_enabled)
        agent_row=QHBoxLayout();self.print_agent_status=QLabel("Print Agent is starting...");self.print_agent_status.setObjectName("status");self.print_agent_status.setWordWrap(True);self.print_agent_poll_button=QPushButton("Check Queue Now");agent_row.addWidget(self.print_agent_status,1);agent_row.addWidget(self.print_agent_poll_button);agent_layout.addLayout(agent_row);body.addWidget(agent_card);body.addStretch()
        self.print_agent_enabled.toggled.connect(self._print_agent_toggled);self.print_agent_poll_button.clicked.connect(self.poll_print_agent)
        note=QLabel("Automatic jobs use the saved Windows printer and the page sequence attached to each server job.");note.setObjectName("muted");note.setWordWrap(True);body.addWidget(note)
        return page

    def _print_agent_toggled(self,enabled):
        self.store.settings.setValue("print_agent/enabled",bool(enabled));self.store.settings.sync()
        if enabled:QTimer.singleShot(0,self.poll_print_agent)
        else:self._set_print_agent_status("Automatic Print Agent is disabled.")

    def _set_print_agent_status(self,text,status=""):
        self.print_agent_status.setText(text);self.print_agent_status.setProperty("status",status)
        self.print_agent_status.style().unpolish(self.print_agent_status);self.print_agent_status.style().polish(self.print_agent_status)

    def poll_print_agent(self):
        if not self.print_agent_enabled.isChecked():return
        if self.print_agent_thread and self.print_agent_thread.isRunning():return
        printers=available_printer_names()
        if not printers:
            self._set_print_agent_status("No Windows printers are available on this computer.","error");return
        default_printer=saved_printer_name(self.store.settings)
        try:settings=self.store.load()
        except ValueError as exc:self._set_print_agent_status(str(exc),"error");return
        if self.pending_print_status:
            action="status";payload=dict(self.pending_print_status);message=f"Updating job {payload['job_id'][:8]} status..."
        else:
            action="poll";payload={"printers":printers,"default_printer":default_printer,"client_name":os.getenv("COMPUTERNAME","Car Client")};message=f"Checking print queue · {default_printer or str(len(printers))+' available printer(s)'}"
        self.print_agent_poll_button.setEnabled(False);self._set_print_agent_status(message,"working")
        self.print_agent_thread=PrintAgentNetworkThread(settings,action,payload,self)
        self.print_agent_thread.succeeded.connect(lambda result,mode:self._print_agent_network_succeeded(action,result,mode))
        self.print_agent_thread.failed.connect(self._print_agent_network_failed)
        self.print_agent_thread.finished.connect(self._print_agent_thread_finished);self.print_agent_thread.start()

    def _print_agent_network_succeeded(self,action,result,mode):
        if action=="status":
            completed_status=str((result or {}).get("status") or "")
            self.pending_print_status=None
            self._set_print_agent_status(f"Job {(result or {}).get('job_id','')[:8]} · {completed_status.upper()} via {mode.upper()}.","success" if completed_status=="completed" else "error")
            QTimer.singleShot(1200,self.poll_print_agent);return
        if not result:
            self._set_print_agent_status(f"Queue is ready · no pending jobs · {mode.upper()}.","success");return
        job=dict(result);job_id=str(job.get("job_id") or "")
        self._set_print_agent_status(f"Printing job {job_id[:8]} · {job.get('car_number') or ''}...","working")
        QApplication.processEvents()
        try:
            printer=print_record_pages(job.get("record") or {},job.get("page_sequence") or [],job.get("copies",1),self.store.settings,job.get("printer_name") or "")
            self.pending_print_status={"job_id":job_id,"status":"completed","error_message":""}
            self._set_print_agent_status(f"Sent job {job_id[:8]} to {printer}; confirming completion...","working")
        except Exception as exc:
            self.pending_print_status={"job_id":job_id,"status":"failed","error_message":str(exc)}
            self._set_print_agent_status(f"Print failed · {exc}","error")

    def _print_agent_network_failed(self,message):
        self._set_print_agent_status(f"Print Agent: {message}","error")
        if self.pending_print_status:self.print_agent_retry_delay=5000

    def _print_agent_thread_finished(self):
        self.print_agent_poll_button.setEnabled(True);thread=self.print_agent_thread;self.print_agent_thread=None
        if thread:thread.deleteLater()
        if self.pending_print_status:
            delay=getattr(self,"print_agent_retry_delay",100);self.print_agent_retry_delay=100;QTimer.singleShot(delay,self.poll_print_agent)

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

    def _existing_cars_received(self,records,mode="lan"):
        unique={}
        for record in records or []:
            key=str(record.get("car_number") or "").strip().casefold()
            if key and key not in unique:unique[key]=record
        self.existing_car_combo.blockSignals(True);self.existing_car_combo.clear();self.existing_car_combo.addItem("Select or type a car number...",None)
        for record in sorted(unique.values(),key=lambda item:str(item.get("car_number") or "").casefold()):
            detail=str(record.get("type_of_car") or record.get("kind_of_car") or "").strip();label=f"{record.get('car_number')} — {detail}" if detail else str(record.get("car_number"));self.existing_car_combo.addItem(label,record)
        self.existing_car_combo.setCurrentIndex(0);self.existing_car_combo.blockSignals(False);self._set_input_status(f"Loaded {len(unique):,} unique car(s) via {mode.upper()}. Choose one, then enter the new driver information.","success")

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
        record_actions=QHBoxLayout();record_actions.addStretch();self.form_record_button=QPushButton("Auto Fill Forms");self.form_record_button.setObjectName("primary");self.qr_record_button=QPushButton("QR Code");self.view_record_button=QPushButton("View");self.edit_record_button=QPushButton("Edit");self.delete_record_button=QPushButton("Delete")
        self.form_record_button.clicked.connect(self.open_selected_forms);self.qr_record_button.clicked.connect(self.open_selected_qr);self.view_record_button.clicked.connect(self.view_selected_record);self.edit_record_button.clicked.connect(self.edit_selected_record);self.delete_record_button.clicked.connect(self.delete_selected_record);self.records_table.doubleClicked.connect(self.view_selected_record)
        record_actions.addWidget(self.form_record_button);record_actions.addWidget(self.qr_record_button);record_actions.addWidget(self.view_record_button);record_actions.addWidget(self.edit_record_button);record_actions.addWidget(self.delete_record_button);body.addLayout(record_actions)
        footer=QHBoxLayout();self.record_count=QLabel("0 records");self.record_count.setObjectName("muted");footer.addWidget(self.record_count);footer.addStretch();footer.addWidget(QLabel("Rows:"))
        self.rows_per_page=QComboBox();self.rows_per_page.addItems(["10","25","50","100"]);self.rows_per_page.setCurrentText("25");self.rows_per_page.currentTextChanged.connect(self._page_size_changed);footer.addWidget(self.rows_per_page)
        self.previous_button=QPushButton("Previous");self.next_button=QPushButton("Next");self.page_label=QLabel("Page 1 / 1");self.previous_button.clicked.connect(lambda:self._change_page(-1));self.next_button.clicked.connect(lambda:self._change_page(1))
        footer.addWidget(self.previous_button);footer.addWidget(self.page_label);footer.addWidget(self.next_button);body.addLayout(footer)
        records_feedback=QHBoxLayout();self.records_status=QLabel("Open this page to load records.");self.records_status.setObjectName("status");self.retry_records_button=QPushButton("Retry");self.retry_records_button.hide();self.retry_records_button.clicked.connect(lambda:self._load_records(self.last_record_term));records_feedback.addWidget(self.records_status,1);records_feedback.addWidget(self.retry_records_button);body.addLayout(records_feedback);self.records_busy=_busy_bar();body.addWidget(self.records_busy)
        return page

    def _show_page(self,index):
        self.pages.setCurrentIndex(index);self.dashboard_nav.setChecked(index==0);self.input_nav.setChecked(index==1);self.records_nav.setChecked(index==2);self.print_nav.setChecked(index==3);self.connection_nav.setChecked(index==4)
        if index==0 and self.dashboard_needs_refresh:self.refresh_dashboard()
        if index==2 and not self.records_loaded:self.refresh_records()

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

    def _records_received(self,records,mode="lan"):
        self.records=list(records or []);self.current_page=1;self.records_loaded=True;self._render_records_page();self._set_records_status(f"Loaded {len(self.records):,} record(s) via {mode.upper()}.","success")

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

    def open_selected_qr(self):
        record=self._selected_record()
        if not record:return
        if self.qr_thread and self.qr_thread.isRunning():return
        try:settings=self.store.load()
        except ValueError as exc:self._set_records_status(str(exc),"error");return
        self.qr_record_button.setEnabled(False);self._set_records_status("Issuing secure owner QR code...","working")
        self.qr_thread=IssueQrThread(settings,int(record.get("id") or 0),self)
        self.qr_thread.succeeded.connect(lambda result,mode:self._qr_issued(record,settings,result,mode))
        self.qr_thread.failed.connect(lambda message:self._set_records_status(message,"error"))
        self.qr_thread.finished.connect(self._qr_thread_finished);self.qr_thread.start()

    def _qr_issued(self,record,settings,result,mode):
        token=str(result.get("token") or "")
        url=qr_access_url(token,settings.host,settings.owner_web_url)
        self._set_records_status(f"Secure owner QR ready via {mode.upper()}.","success")
        CarQrDialog(record,url,self).exec()

    def _qr_thread_finished(self):
        self.qr_record_button.setEnabled(True);thread=self.qr_thread;self.qr_thread=None
        if thread:thread.deleteLater()

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
        for button in (self.form_record_button,self.qr_record_button,self.view_record_button,self.edit_record_button,self.delete_record_button):button.setEnabled(enabled)

    def _start_record_action(self,action,payload):
        if self.record_action_thread and self.record_action_thread.isRunning():return
        try:settings=self.store.load()
        except ValueError as exc:self._set_records_status(str(exc),"error");return
        self._set_record_actions_enabled(False);self._set_records_status("Updating the server..." if action=="update" else "Deleting record...","working")
        self.record_action_thread=RecordActionThread(settings,action,payload,self);self.record_action_thread.succeeded.connect(lambda mode:self._record_action_succeeded(action,mode));self.record_action_thread.failed.connect(lambda message:self._set_records_status(message,"error"));self.record_action_thread.finished.connect(self._record_action_finished);self.record_action_thread.start()

    def _record_action_succeeded(self,action,mode="lan"):
        verb="updated" if action=="update" else "deleted";message=f"Record {verb} successfully via {mode.upper()}." if mode!="offline" else f"Record {verb} locally; pending automatic sync."
        self._set_records_status(message,"success");self.records_loaded=False;self.dashboard_needs_refresh=True

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

    def _car_saved(self,mode="lan"):
        if self.entry_mode.currentData()=="existing":
            for field in DRIVER_FIELDS:self.car_inputs[field].clear()
            self._existing_car_selected(self.existing_car_combo.currentIndex());focus=self.car_inputs["driver_name"]
        else:
            for editor in self.car_inputs.values():editor.clear()
            focus=self.car_inputs["car_number"]
        message=f"Car record saved successfully via {mode.upper()}." if mode!="offline" else "Car record saved offline; pending automatic sync."
        self.records_loaded=False;self.dashboard_needs_refresh=True;self._set_input_status(message,"success");focus.setFocus()

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
        self.cloud_url_input.setText(value.cloud_url);self.cloud_api_key_input.setText(value.cloud_api_key);self.offline_enabled_check.setChecked(value.offline_enabled)
        self.owner_web_url_input.setText(value.owner_web_url)

    def current_settings(self) -> ServerSettings:
        return ServerSettings(
            self.host_input.text(), self.port_input.value(), self.timeout_input.value(),
            self.cloud_url_input.text(), self.cloud_api_key_input.text(),
            self.offline_enabled_check.isChecked(), self.owner_web_url_input.text(),
        ).validated()

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
        self.connection_thread.succeeded.connect(lambda mode: self._connection_finished(True, mode))
        self.connection_thread.failed.connect(lambda message: self._connection_finished(False, message))
        self.connection_thread.finished.connect(self._thread_finished)
        self.connection_thread.start()

    def _connection_finished(self, success: bool, message: str):
        if success:
            self._set_status(f"Connected successfully via {message.upper()}. Car Management service and database are ready.", "success")
        else:
            self._set_status(message, "error", True)

    def _thread_finished(self):
        self.test_button.setEnabled(True); self.save_button.setEnabled(True)
        thread = self.connection_thread; self.connection_thread = None
        if thread: thread.deleteLater()

    def closeEvent(self, event: QCloseEvent):
        if ((self.connection_thread and self.connection_thread.isRunning()) or
                (self.dashboard_thread and self.dashboard_thread.isRunning()) or
                (self.save_thread and self.save_thread.isRunning()) or
                (self.records_thread and self.records_thread.isRunning()) or
                (self.car_picker_thread and self.car_picker_thread.isRunning()) or
                (self.record_action_thread and self.record_action_thread.isRunning()) or
                (self.qr_thread and self.qr_thread.isRunning()) or
                (self.print_agent_thread and self.print_agent_thread.isRunning()) or
                (self.duplicate_thread and self.duplicate_thread.isRunning())):
            if self.pages.currentIndex()==0:self._set_dashboard_status("A server request is still running. Please wait before closing.","working")
            elif self.pages.currentIndex()==1:self._set_input_status("A server request is still running. Please wait before closing.","working")
            elif self.pages.currentIndex()==2:self._set_records_status("A server request is still running. Please wait before closing.","working")
            else:self._set_status("A server request is still running. Please wait before closing.", "working")
            event.ignore(); return
        super().closeEvent(event)


def apply_app_identity(app: QApplication):
    app.setApplicationName("KAY Car Management")
    app.setOrganizationName("KAY POS")
    icon_path = Path(__file__).resolve().parents[1] / "assets" / "kay" / "kay_multi.ico"
    if icon_path.exists(): app.setWindowIcon(QIcon(str(icon_path)))
