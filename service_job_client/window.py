from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QFormLayout, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QStackedWidget, QStatusBar, QSystemTrayIcon, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from lite_pos.api import LiteApiClient
from service_job_client.config import load_config, save_config


class TaskWorker(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, operation: Callable):
        super().__init__()
        self.operation = operation

    def run(self) -> None:
        try:
            self.succeeded.emit(self.operation())
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class ServiceJobClientWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KAY Service Job Client")
        self.resize(1080, 680)
        self.setMinimumSize(820, 540)
        self.api: LiteApiClient | None = None
        self.user: dict = {}
        self.jobs: list[dict] = []
        self.selected_job: dict = {}
        self._threads: set[QThread] = set()
        self._workers: set[TaskWorker] = set()
        self._loading = False
        self._known_job_ids: set[int] | None = None

        self.pages = QStackedWidget()
        self.login_page = self._build_login_page()
        self.jobs_page = self._build_jobs_page()
        self.pages.addWidget(self.login_page)
        self.pages.addWidget(self.jobs_page)
        self.setCentralWidget(self.pages)
        self.setStatusBar(QStatusBar())

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(5000)
        self.refresh_timer.timeout.connect(self.refresh_jobs)
        self.tray = QSystemTrayIcon(QApplication.instance().windowIcon(), self)
        self.tray.setToolTip("KAY Service Job Client")
        self.tray.show()

    def _build_login_page(self) -> QWidget:
        config = load_config()
        page = QWidget(); outer = QVBoxLayout(page); outer.addStretch()
        card = QFrame(); card.setFrameShape(QFrame.Shape.StyledPanel); card.setMaximumWidth(480)
        layout = QVBoxLayout(card)
        title = QLabel("KAY Service Job Client"); title.setStyleSheet("font-size: 24px; font-weight: 700;")
        subtitle = QLabel("Sign in to view and complete service jobs.")
        form = QFormLayout()
        self.server_input = QLineEdit(config["server_url"])
        self.username_input = QLineEdit(config["remember_username"])
        self.password_input = QLineEdit(); self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.insecure_check = QCheckBox("Allow self-signed HTTPS certificate"); self.insecure_check.setChecked(config["insecure_tls"])
        form.addRow("Server URL", self.server_input); form.addRow("Username", self.username_input); form.addRow("Password", self.password_input)
        self.login_button = QPushButton("Sign In"); self.login_button.clicked.connect(self.login)
        self.password_input.returnPressed.connect(self.login)
        self.login_status = QLabel(""); self.login_status.setWordWrap(True)
        layout.addWidget(title); layout.addWidget(subtitle); layout.addSpacing(12); layout.addLayout(form)
        layout.addWidget(self.insecure_check); layout.addWidget(self.login_button); layout.addWidget(self.login_status)
        row = QHBoxLayout(); row.addStretch(); row.addWidget(card); row.addStretch()
        outer.addLayout(row); outer.addStretch()
        return page

    def _build_jobs_page(self) -> QWidget:
        page = QWidget(); outer = QVBoxLayout(page)
        top = QHBoxLayout()
        title = QLabel("Service Jobs"); title.setStyleSheet("font-size: 22px; font-weight: 700;")
        self.identity_label = QLabel("")
        self.search_input = QLineEdit(); self.search_input.setPlaceholderText("Search job name or details…"); self.search_input.returnPressed.connect(self.refresh_jobs)
        self.status_filter = QComboBox()
        self.status_filter.addItem("Pending", "pending")
        self.status_filter.addItem("Completed", "completed")
        self.status_filter.addItem("All", "all")
        self.status_filter.currentIndexChanged.connect(self.refresh_jobs)
        refresh = QPushButton("Refresh"); refresh.clicked.connect(self.refresh_jobs)
        logout = QPushButton("Sign Out"); logout.clicked.connect(self.logout)
        top.addWidget(title); top.addWidget(self.identity_label); top.addStretch(); top.addWidget(self.search_input, 1)
        top.addWidget(self.status_filter); top.addWidget(refresh); top.addWidget(logout); outer.addLayout(top)

        body = QHBoxLayout()
        self.job_table = QTableWidget(0, 7)
        self.job_table.setHorizontalHeaderLabels(["Date", "Time", "Job Name", "Details", "Appointment", "Status", "Completed By"])
        self.job_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.job_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.job_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.job_table.verticalHeader().setVisible(False)
        self.job_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.job_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for column, width in {0:90, 1:65, 4:135, 5:105, 6:110}.items():
            self.job_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            self.job_table.setColumnWidth(column, width)
        self.job_table.itemSelectionChanged.connect(self.load_selected_job)
        body.addWidget(self.job_table, 3)

        detail = QFrame(); detail.setFrameShape(QFrame.Shape.StyledPanel); detail.setMinimumWidth(300); detail.setMaximumWidth(420)
        detail_layout = QVBoxLayout(detail)
        self.detail_title = QLabel("Select a job"); self.detail_title.setWordWrap(True); self.detail_title.setStyleSheet("font-size: 18px; font-weight: 700;")
        self.detail_text = QTextEdit(); self.detail_text.setReadOnly(True)
        self.complete_button = QPushButton("Complete Job"); self.complete_button.setEnabled(False); self.complete_button.clicked.connect(self.complete_job)
        detail_layout.addWidget(self.detail_title); detail_layout.addWidget(self.detail_text, 1); detail_layout.addWidget(self.complete_button)
        body.addWidget(detail, 1); outer.addLayout(body, 1)
        self.jobs_status = QLabel(""); outer.addWidget(self.jobs_status)
        return page

    def _run_task(self, operation: Callable, success: Callable, failure: Callable) -> None:
        thread = QThread(self); worker = TaskWorker(operation); worker.moveToThread(thread)
        self._threads.add(thread); self._workers.add(worker)
        thread.started.connect(worker.run); worker.succeeded.connect(success); worker.failed.connect(failure)
        worker.finished.connect(thread.quit); worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._threads.discard(thread)); thread.finished.connect(lambda: self._workers.discard(worker))
        thread.start()

    def login(self) -> None:
        username = self.username_input.text().strip(); password = self.password_input.text()
        if not username or not password:
            self.login_status.setText("Username and password are required."); return
        self.login_button.setEnabled(False); self.login_status.setText("Signing in…")
        client = LiteApiClient(self.server_input.text(), self.insecure_check.isChecked())

        def accepted(user):
            self.api = client; self.user = dict(user); self.password_input.clear(); self.login_button.setEnabled(True); self.login_status.clear()
            save_config({"server_url": client.server_url, "insecure_tls": self.insecure_check.isChecked(), "remember_username": username})
            name = self.user.get("full_name") or self.user.get("username") or "User"
            self.identity_label.setText(f"Signed in: {name}")
            self.pages.setCurrentWidget(self.jobs_page); self._known_job_ids = None; self.refresh_timer.start(); self.refresh_jobs()

        self._run_task(lambda: (client.login(username, password), client.current_user())[1], accepted,
                       lambda error: (self.login_button.setEnabled(True), self.login_status.setText(error)))

    def logout(self) -> None:
        self.refresh_timer.stop(); self.api = None; self.user = {}; self.jobs = []; self.selected_job = {}; self._known_job_ids = None
        self.job_table.setRowCount(0); self.detail_title.setText("Select a job"); self.detail_text.clear(); self.complete_button.setEnabled(False)
        self.pages.setCurrentWidget(self.login_page); self.password_input.setFocus()

    def refresh_jobs(self) -> None:
        if not self.api or self._loading:
            return
        self._loading = True; query = self.search_input.text().strip(); mode = str(self.status_filter.currentData() or "pending")

        def operation():
            # Always fetch the shared board so notifications are independent of
            # the operator's current search or status filter.
            all_rows = self.api.service_orders(query="", status="", limit=200)
            rows = list(all_rows)
            needle = query.casefold()
            if needle:
                rows = [row for row in rows if needle in " ".join(str(row.get(key) or "") for key in ("job_title", "complaint", "internal_notes")).casefold()]
            if mode == "completed":
                rows = [row for row in rows if str(row.get("status") or "") == "completed"]
            elif mode != "all":
                rows = [row for row in rows if str(row.get("status") or "") not in {"completed", "delivered", "cancelled"}]
            return all_rows, rows

        def loaded(result):
            self._loading = False; all_jobs, jobs = result; jobs = list(jobs); current_ids = {int(job.get("id") or 0) for job in all_jobs}
            if self._known_job_ids is not None:
                username = str(self.user.get("username") or "").casefold()
                for job in reversed([job for job in all_jobs if int(job.get("id") or 0) not in self._known_job_ids]):
                    if str(job.get("created_by") or "").casefold() != username:
                        self.tray.showMessage("New Service Job", str(job.get("job_title") or "New Job"), QSystemTrayIcon.MessageIcon.Information, 8000)
            self._known_job_ids = (self._known_job_ids or set()) | current_ids
            self.jobs = jobs; self.job_table.blockSignals(True); self.job_table.setRowCount(len(jobs))
            for row, job in enumerate(jobs):
                received = str(job.get("received_at") or ""); status = str(job.get("status") or "received")
                values = (received[:10], received[11:16], job.get("job_title") or "—", job.get("complaint") or "—",
                          job.get("expected_at") or "—", "Completed" if status == "completed" else "Pending", job.get("completed_by") or "—")
                for column, value in enumerate(values):
                    item = QTableWidgetItem(str(value)); item.setData(Qt.ItemDataRole.UserRole, int(job.get("id") or 0)); self.job_table.setItem(row, column, item)
            self.job_table.blockSignals(False); self.jobs_status.setText(f"{len(jobs)} job(s)")
            if jobs: self.job_table.selectRow(0)
            else: self.selected_job = {}; self.detail_title.setText("Select a job"); self.detail_text.clear(); self.complete_button.setEnabled(False)

        self._run_task(operation, loaded, lambda error: (setattr(self, "_loading", False), self.statusBar().showMessage(error)))

    def load_selected_job(self) -> None:
        row = self.job_table.currentRow(); item = self.job_table.item(row, 0) if row >= 0 else None
        job_id = int(item.data(Qt.ItemDataRole.UserRole) or 0) if item else 0
        job = next((entry for entry in self.jobs if int(entry.get("id") or 0) == job_id), {})
        self.selected_job = dict(job)
        if not job:
            self.detail_title.setText("Select a job"); self.detail_text.clear(); self.complete_button.setEnabled(False); return
        status = str(job.get("status") or "received")
        self.detail_title.setText(str(job.get("job_title") or "Service Job"))
        self.detail_text.setPlainText(
            f"Date/Time: {job.get('received_at') or '—'}\n\nDetails:\n{job.get('complaint') or '—'}\n\n"
            f"Appointment: {job.get('expected_at') or '—'}\n\nNotes:\n{job.get('internal_notes') or '—'}\n\n"
            f"Created By: {job.get('created_by') or '—'}\nCompleted By: {job.get('completed_by') or '—'}"
        )
        self.complete_button.setEnabled(status not in {"completed", "delivered", "cancelled"})

    def complete_job(self) -> None:
        if not self.api or not self.selected_job:
            return
        if QMessageBox.question(self, "Complete Job", "Mark this job as completed?") != QMessageBox.StandardButton.Yes:
            return
        job_id = int(self.selected_job.get("id") or 0); self.complete_button.setEnabled(False)
        self._run_task(lambda: self.api.change_service_order_status(job_id, "completed", "Completed from Service Job Client"),
                       lambda _job: self.refresh_jobs(),
                       lambda error: (self.complete_button.setEnabled(True), QMessageBox.critical(self, "Complete Job", error)))
