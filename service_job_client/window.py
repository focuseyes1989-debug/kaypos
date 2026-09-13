from __future__ import annotations

import base64
from collections.abc import Callable

from PyQt6.QtCore import QDate, QObject, QStringListModel, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QCompleter, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QStatusBar, QSystemTrayIcon, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from lite_pos.api import LiteApiClient
from lite_pos.service_jobs import READY_FOR_PICKUP_STATUSES, job_status_style
from service_job_client.config import load_config, save_config
from utils.branded_icons import service_job_icon


class LoginDialog(QDialog):
    def reject(self) -> None:
        if not self.property("busy"):
            super().reject()


class PromptDialog(QDialog):
    def __init__(self, parent=None, prompt: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Design Prompt")
        self.setMinimumSize(560, 420)
        body = QVBoxLayout(self)
        form = QFormLayout()
        self.title_input = QLineEdit(str((prompt or {}).get("title") or ""))
        self.title_input.setPlaceholderText("Prompt name")
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Write the prompt text to reuse with ChatGPT, image AI, etc.")
        self.text_input.setPlainText(str((prompt or {}).get("text") or ""))
        form.addRow("Name", self.title_input)
        form.addRow("Prompt", self.text_input)
        body.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        body.addWidget(buttons)

    def prompt(self) -> dict:
        return {"title": self.title_input.text().strip(), "text": self.text_input.toPlainText().strip()}

    def accept(self) -> None:
        values = self.prompt()
        if not values["title"] or not values["text"]:
            QMessageBox.warning(self, "Design Prompt", "Prompt name and text are required.")
            return
        super().accept()


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
        self.setWindowIcon(service_job_icon())
        self.resize(1080, 680)
        self.setMinimumSize(820, 540)
        self.api: LiteApiClient | None = None
        self.user: dict = {}
        self.jobs: list[dict] = []
        self.selected_job: dict = {}
        self._threads: set[QThread] = set()
        self._workers: set[TaskWorker] = set()
        self._loading = False
        self._updating = False
        self._jobs_revision = 0
        self._known_job_ids: set[int] | None = None
        self.prompts: list[dict] = []
        self.selected_prompt_row = -1
        self.prompt_cards: list[QFrame] = []

        self.pages = QStackedWidget()
        self.login_page = QWidget()
        self.login_dialog = self._build_login_dialog()
        self.jobs_page = self._build_jobs_page()
        self.prompts_page = self._build_prompts_page()
        self.pages.addWidget(self.login_page)
        self.pages.addWidget(self.jobs_page)
        self.pages.addWidget(self.prompts_page)
        self.setCentralWidget(self.pages)
        self.setStatusBar(QStatusBar())
        self.jobs_status = QLabel("")
        self.identity_label = QLabel("")
        self.statusBar().addWidget(self.jobs_status)
        self.statusBar().addPermanentWidget(self.identity_label)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(5000)
        self.refresh_timer.timeout.connect(self.refresh_jobs)
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("KAY Service Job Client")
        self.tray.show()

    def _build_login_dialog(self) -> QDialog:
        dialog = LoginDialog(self)
        dialog.setWindowTitle("Sign in · KAY Service Job Client")
        dialog.setWindowIcon(self.windowIcon())
        dialog.setModal(True)
        dialog.setFixedSize(470, 340)
        dialog.rejected.connect(self.close)
        body = QVBoxLayout(dialog)
        body.setContentsMargins(34, 24, 34, 24)
        body.setSpacing(8)
        brand = QLabel("KAY SERVICE JOB CLIENT", objectName="brand")
        title = QLabel("Welcome back", objectName="title")
        subtitle = QLabel("Sign in to continue to your service jobs.", objectName="muted")
        subtitle.setWordWrap(True)
        brand.setStyleSheet("font-weight: 600;")
        for label in (brand, title, subtitle):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            body.addWidget(label)
        body.addSpacing(4)
        config = load_config()
        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(9)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.server_input = QLineEdit(config["server_url"])
        self.server_input.setMinimumWidth(285)
        self.server_input.setPlaceholderText("https://192.168.1.10:8000")
        self.username_input = QLineEdit(config["remember_username"])
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self.login)
        form.addRow("Server URL", self.server_input)
        form.addRow("Username", self.username_input)
        form.addRow("Password", self.password_input)
        self.insecure_check = QCheckBox("Allow self-signed HTTPS certificate")
        self.insecure_check.setChecked(config["insecure_tls"])
        form.addRow("", self.insecure_check)
        body.addLayout(form)
        self.login_status = QLabel("", objectName="muted")
        self.login_status.setWordWrap(True)
        self.login_status.setMinimumHeight(28)
        self.login_status.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        body.addWidget(self.login_status)
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.test_button = QPushButton("Test Connection")
        self.test_button.setMinimumWidth(128)
        self.test_button.clicked.connect(self.test_connection)
        self.login_button = QPushButton("Sign In", objectName="primary")
        self.login_button.setMinimumWidth(100)
        self.login_button.clicked.connect(self.login)
        buttons.addStretch()
        buttons.addWidget(self.test_button)
        buttons.addWidget(self.login_button)
        body.addLayout(buttons)
        return dialog

    def show_login_dialog(self) -> None:
        if self.api or self.login_dialog.isVisible():
            return
        self.login_dialog.show()
        screen = self.screen() or QApplication.primaryScreen()
        if screen:
            frame = self.login_dialog.frameGeometry()
            frame.moveCenter(screen.availableGeometry().center())
            self.login_dialog.move(frame.topLeft())
        self.login_dialog.raise_()
        self.login_dialog.activateWindow()
        self.username_input.setFocus()

    def _set_login_busy(self, busy: bool, message: str = "") -> None:
        self.login_dialog.setProperty("busy", busy)
        for widget in (self.server_input, self.username_input, self.password_input,
                       self.insecure_check, self.test_button, self.login_button):
            widget.setEnabled(not busy)
        self.login_status.setText(message)

    def test_connection(self) -> None:
        if self.login_dialog.property("busy"):
            return
        self._set_login_busy(True, "Testing server connection…")
        client = LiteApiClient(self.server_input.text(), self.insecure_check.isChecked())

        def operation():
            try:
                return client.health()
            finally:
                client.close()

        def connected(_data):
            self.server_input.setText(client.server_url)
            save_config({"server_url": client.server_url, "insecure_tls": self.insecure_check.isChecked(),
                         "remember_username": self.username_input.text().strip()})
            self._set_login_busy(False, "Server is connected and ready.")

        self._run_task(operation, connected, lambda error: self._set_login_busy(False, error))

    def _build_jobs_page(self) -> QWidget:
        page = QWidget(); outer = QVBoxLayout(page)
        top = QHBoxLayout()
        title = QLabel("Service Jobs"); title.setStyleSheet("font-size: 22px; font-weight: 700;")
        self.search_input = QLineEdit(); self.search_input.setPlaceholderText("Search job name or details…"); self.search_input.returnPressed.connect(self.refresh_jobs)
        self.date_filter_check = QCheckBox("Date")
        self.date_filter_check.toggled.connect(self._date_filter_toggled)
        self.from_date = QDateEdit(QDate.currentDate())
        self.from_date.setCalendarPopup(True)
        self.from_date.setDisplayFormat("yyyy-MM-dd")
        self.from_date.setEnabled(False)
        self.from_date.dateChanged.connect(self.refresh_jobs)
        self.to_date = QDateEdit(QDate.currentDate())
        self.to_date.setCalendarPopup(True)
        self.to_date.setDisplayFormat("yyyy-MM-dd")
        self.to_date.setEnabled(False)
        self.to_date.dateChanged.connect(self.refresh_jobs)
        self.status_filter = QComboBox()
        self.status_filter.addItem("Pending", "pending")
        self.status_filter.addItem("In Progress", "in_progress")
        self.status_filter.addItem("Ready for Pickup", "ready_for_pickup")
        self.status_filter.addItem("Delivered", "delivered")
        self.status_filter.addItem("All", "all")
        self._make_searchable_combo(self.status_filter, "Search status")
        self.status_filter.currentIndexChanged.connect(self.refresh_jobs)
        refresh = QPushButton("Refresh"); refresh.clicked.connect(self.refresh_jobs)
        prompts = QPushButton("Design Prompts"); prompts.clicked.connect(self.show_prompts_page)
        logout = QPushButton("Sign Out"); logout.clicked.connect(self.logout)
        top.addWidget(title); top.addStretch(); top.addWidget(self.search_input, 1)
        top.addWidget(self.date_filter_check); top.addWidget(self.from_date); top.addWidget(self.to_date)
        top.addWidget(self.status_filter); top.addWidget(refresh); top.addWidget(prompts); top.addWidget(logout); outer.addLayout(top)

        body = QHBoxLayout()
        self.job_table = QTableWidget(0, 12)
        self.job_table.setHorizontalHeaderLabels(["Date", "Time", "Job Name", "Details", "Appointment", "Status", "Work Completed By", "Working By", "Started At", "Work Completed At", "Delivered By", "Delivered At"])
        self.job_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.job_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.job_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.job_table.verticalHeader().setVisible(False)
        self.job_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.job_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for column, width in {0:90, 1:65, 4:135, 5:135, 6:145, 7:110, 8:150, 9:150, 10:110, 11:150}.items():
            self.job_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            self.job_table.setColumnWidth(column, width)
        self.job_table.itemSelectionChanged.connect(self.load_selected_job)
        body.addWidget(self.job_table, 3)

        detail = QFrame(); detail.setFrameShape(QFrame.Shape.StyledPanel); detail.setMinimumWidth(300); detail.setMaximumWidth(420)
        detail_layout = QVBoxLayout(detail)
        self.detail_title = QLabel("Select a job"); self.detail_title.setWordWrap(True); self.detail_title.setStyleSheet("font-size: 18px; font-weight: 700;")
        self.detail_status = QLabel(); self.detail_status.hide()
        self.detail_text = QTextEdit(); self.detail_text.setReadOnly(True)
        self.start_button = QPushButton("Start Job"); self.start_button.setEnabled(False); self.start_button.clicked.connect(self.start_job)
        self.complete_button = QPushButton("Complete Job"); self.complete_button.setEnabled(False); self.complete_button.clicked.connect(self.complete_job)
        self.collect_button = QPushButton("Mark as Collected"); self.collect_button.setEnabled(False); self.collect_button.clicked.connect(self.collect_job)
        detail_layout.addWidget(self.detail_title); detail_layout.addWidget(self.detail_status); detail_layout.addWidget(self.detail_text, 1); detail_layout.addWidget(self.start_button); detail_layout.addWidget(self.complete_button); detail_layout.addWidget(self.collect_button)
        body.addWidget(detail, 1); outer.addLayout(body, 1)
        return page

    def _build_prompts_page(self) -> QWidget:
        page = QWidget(); outer = QVBoxLayout(page)
        top = QHBoxLayout()
        title = QLabel("Design Prompts"); title.setStyleSheet("font-size: 22px; font-weight: 700;")
        back = QPushButton("Service Jobs"); back.clicked.connect(self.show_jobs_page)
        logout = QPushButton("Sign Out"); logout.clicked.connect(self.logout)
        top.addWidget(title); top.addStretch(); top.addWidget(back); top.addWidget(logout); outer.addLayout(top)

        body = QHBoxLayout()
        left = QFrame(); left.setFrameShape(QFrame.Shape.StyledPanel); left.setMinimumWidth(520)
        left_layout = QVBoxLayout(left)
        self.copy_prompt_button = QPushButton("Copy Prompt")
        self.copy_prompt_button.clicked.connect(self.copy_prompt)
        self.refresh_prompt_button = QPushButton("Refresh")
        self.refresh_prompt_button.clicked.connect(self.refresh_design_prompts)
        self.prompt_search_input = QLineEdit()
        self.prompt_search_input.setPlaceholderText("Search prompts...")
        self.prompt_search_input.textChanged.connect(self.refresh_prompt_controls)
        left_layout.addWidget(self.prompt_search_input)
        self.prompt_card_area = QScrollArea()
        self.prompt_card_area.setWidgetResizable(True)
        self.prompt_card_area.setFrameShape(QFrame.Shape.NoFrame)
        self.prompt_card_container = QWidget()
        self.prompt_card_layout = QGridLayout(self.prompt_card_container)
        self.prompt_card_layout.setContentsMargins(0, 0, 0, 0)
        self.prompt_card_layout.setSpacing(8)
        self.prompt_card_area.setWidget(self.prompt_card_container)
        left_layout.addWidget(self.prompt_card_area, 1)

        right = QFrame(); right.setFrameShape(QFrame.Shape.StyledPanel); right.setMinimumWidth(280); right.setMaximumWidth(360)
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Preview"))
        self.prompt_preview = QTextEdit()
        self.prompt_preview.setReadOnly(True)
        self.prompt_preview.setPlaceholderText("Save reusable prompts here, then copy them into ChatGPT or another design AI.")
        right_layout.addWidget(self.prompt_preview, 1)
        right_layout.addWidget(QLabel("Sample Image"))
        self.prompt_image = QLabel("No sample image")
        self.prompt_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.prompt_image.setMinimumHeight(180)
        self.prompt_image.setStyleSheet("border: 1px solid #d7e0ed; border-radius: 8px; color: #6b7280;")
        right_layout.addWidget(self.prompt_image)
        prompt_actions = QHBoxLayout()
        prompt_actions.addWidget(self.copy_prompt_button)
        prompt_actions.addWidget(self.refresh_prompt_button)
        right_layout.addLayout(prompt_actions)
        body.addWidget(left, 2)
        body.addWidget(right, 1)
        outer.addLayout(body, 1)
        self.refresh_prompt_controls()
        return page

    def refresh_prompt_controls(self) -> None:
        current = self.selected_prompt_row
        search_text = self.prompt_search_input.text().strip().casefold() if hasattr(self, "prompt_search_input") else ""
        while self.prompt_card_layout.count():
            item = self.prompt_card_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.prompt_cards = []
        visible_rows = []
        for index, prompt in enumerate(self.prompts):
            if search_text and search_text not in self._prompt_search_text(prompt).casefold():
                continue
            visible_rows.append(index)
            card = self._create_prompt_card(prompt, index)
            self.prompt_cards.append(card)
            position = len(visible_rows) - 1
            self.prompt_card_layout.addWidget(card, position // 3, position % 3)
        if not self.prompts or not visible_rows:
            empty = QLabel("No matching prompts" if self.prompts else "No design prompts yet")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #6b7280; padding: 28px 8px;")
            self.prompt_card_layout.addWidget(empty, 0, 0, 1, 3)
        for column in range(3):
            self.prompt_card_layout.setColumnStretch(column, 1)
        self.selected_prompt_row = current if current in visible_rows else (visible_rows[0] if visible_rows else -1)
        self.refresh_prompt_card_styles()
        self.load_prompt_preview()

    @staticmethod
    def _prompt_search_text(prompt: dict) -> str:
        return " ".join(str(prompt.get(key) or "") for key in ("category", "title", "prompt_text", "text", "image_name"))

    def _create_prompt_card(self, prompt: dict, index: int) -> QFrame:
        card = QFrame()
        card.setObjectName("promptCard")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setFixedHeight(236)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setProperty("prompt_index", index)
        card.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(7)
        image = QLabel()
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setFixedHeight(132)
        image.setStyleSheet("background: #f8fafc; border: 1px solid #d7e0ed; border-radius: 6px; color: #64748b;")
        self._set_prompt_card_image(image, str(prompt.get("image_data") or ""))
        title = QLabel(str(prompt.get("title") or f"Prompt {index + 1}"))
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: 700;")
        category = QLabel(str(prompt.get("category") or "General"))
        category.setStyleSheet("color: #2563eb; font-size: 11px; font-weight: 700;")
        meta = QLabel("Sample image attached" if prompt.get("image_data") else "Text prompt")
        meta.setStyleSheet("color: #64748b; font-size: 11px;")
        layout.addWidget(image)
        layout.addWidget(title)
        layout.addWidget(category)
        layout.addWidget(meta)
        card.mousePressEvent = lambda event, row=index: self.select_prompt_card(row)
        return card

    def _set_prompt_card_image(self, label: QLabel, image_data: str) -> None:
        if not image_data:
            label.setPixmap(QPixmap())
            label.setText("No image")
            return
        try:
            encoded = image_data.split(",", 1)[1] if "," in image_data else image_data
            pixmap = QPixmap()
            pixmap.loadFromData(base64.b64decode(encoded))
            if pixmap.isNull():
                raise ValueError("Invalid image")
            label.setPixmap(self._cropped_prompt_pixmap(pixmap, 190, 126))
            label.setText("")
        except Exception:
            label.setPixmap(QPixmap())
            label.setText("Bad image")

    @staticmethod
    def _cropped_prompt_pixmap(pixmap: QPixmap, width: int, height: int) -> QPixmap:
        scaled = pixmap.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        x = max(0, (scaled.width() - width) // 2)
        y = max(0, (scaled.height() - height) // 2)
        cropped = scaled.copy(x, y, width, height)
        canvas = QPixmap(width, height)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.drawPixmap(0, 0, cropped)
        painter.end()
        return canvas

    def select_prompt_card(self, index: int) -> None:
        if not 0 <= index < len(self.prompts):
            return
        self.selected_prompt_row = index
        self.refresh_prompt_card_styles()
        self.load_prompt_preview()

    def refresh_prompt_card_styles(self) -> None:
        for card in self.prompt_cards:
            selected = int(card.property("prompt_index") or -1) == self.selected_prompt_row
            card.setStyleSheet(
                "QFrame#promptCard {"
                f"background: {'#eef6ff' if selected else '#ffffff'};"
                f"border: 2px solid {'#2563eb' if selected else '#d7e0ed'};"
                "border-radius: 8px;"
                "}"
                "QFrame#promptCard:hover { background: #f8fbff; border-color: #60a5fa; }"
            )

    @staticmethod
    def _make_searchable_combo(combo: QComboBox, placeholder: str = "Search") -> None:
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.setMinimumWidth(180)
        combo.setMaxVisibleItems(12)
        line_edit = combo.lineEdit()
        if line_edit:
            line_edit.setPlaceholderText(placeholder)
            line_edit.setClearButtonEnabled(False)
        completer = QCompleter(combo)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        combo.setCompleter(completer)
        ServiceJobClientWindow._refresh_combo_completer(combo)

    @staticmethod
    def _refresh_combo_completer(combo: QComboBox) -> None:
        completer = combo.completer()
        if not completer:
            return
        labels = [combo.itemText(index) for index in range(combo.count())]
        completer.setModel(QStringListModel([label for label in labels if label.strip()], completer))

    def selected_prompt_index(self) -> int:
        index = int(self.selected_prompt_row)
        return index if 0 <= index < len(self.prompts) else -1

    def selected_prompt(self) -> dict:
        index = self.selected_prompt_index()
        return dict(self.prompts[index]) if index >= 0 else {}

    def load_prompt_preview(self) -> None:
        prompt = self.selected_prompt()
        self.prompt_preview.setPlainText(self.render_prompt_text(str(prompt.get("prompt_text") or prompt.get("text") or "")))
        self.load_prompt_image(str(prompt.get("image_data") or ""))
        has_prompt = bool(prompt)
        self.copy_prompt_button.setEnabled(has_prompt)

    def load_prompt_image(self, image_data: str) -> None:
        if not image_data:
            self.prompt_image.setPixmap(QPixmap())
            self.prompt_image.setText("No sample image")
            return
        try:
            encoded = image_data.split(",", 1)[1] if "," in image_data else image_data
            pixmap = QPixmap()
            pixmap.loadFromData(base64.b64decode(encoded))
            if pixmap.isNull():
                raise ValueError("Invalid image")
            self.prompt_image.setPixmap(pixmap.scaled(420, 220, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.prompt_image.setText("")
        except Exception:
            self.prompt_image.setPixmap(QPixmap())
            self.prompt_image.setText("Could not preview image")

    def prompt_context(self) -> dict:
        job = self.selected_job or {}
        return {
            "job_title": str(job.get("job_title") or ""),
            "details": str(job.get("complaint") or ""),
            "notes": str(job.get("internal_notes") or ""),
            "appointment": str(job.get("expected_at") or ""),
            "status": str(job.get("status") or ""),
        }

    def render_prompt_text(self, text: str) -> str:
        values = self.prompt_context()
        result = str(text or "")
        for key, value in values.items():
            result = result.replace("{" + key + "}", value)
        return result

    def copy_prompt(self) -> None:
        prompt = self.selected_prompt()
        if not prompt:
            return
        text = self.render_prompt_text(str(prompt.get("prompt_text") or prompt.get("text") or ""))
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage("Prompt copied to clipboard.", 3500)

    def refresh_design_prompts(self) -> None:
        if not self.api:
            return
        client = self.api
        self.refresh_prompt_button.setEnabled(False)

        def loaded(prompts):
            if self.api is not client:
                return
            self.prompts = list(prompts or []) if isinstance(prompts, list) else []
            self.refresh_prompt_controls()
            self.refresh_prompt_button.setEnabled(True)
            self.statusBar().showMessage(f"{len(self.prompts)} prompt(s) loaded.", 3500)

        self._run_task(
            client.service_order_design_prompts,
            loaded,
            lambda error: (self.refresh_prompt_button.setEnabled(True), QMessageBox.warning(self, "Design Prompts", error)),
        )

    def show_jobs_page(self) -> None:
        self.pages.setCurrentWidget(self.jobs_page)
        self.refresh_jobs()

    def show_prompts_page(self) -> None:
        self.load_prompt_preview()
        self.pages.setCurrentWidget(self.prompts_page)

    def _date_filter_toggled(self, checked: bool) -> None:
        self.from_date.setEnabled(checked)
        self.to_date.setEnabled(checked)
        self.refresh_jobs()

    def _selected_date_range(self) -> tuple[str, str]:
        if not self.date_filter_check.isChecked():
            return "", ""
        if self.from_date.date() > self.to_date.date():
            self.to_date.blockSignals(True)
            self.to_date.setDate(self.from_date.date())
            self.to_date.blockSignals(False)
        return self.from_date.date().toString("yyyy-MM-dd"), self.to_date.date().toString("yyyy-MM-dd")

    def _run_task(self, operation: Callable, success: Callable, failure: Callable) -> None:
        thread = QThread(self); worker = TaskWorker(operation); worker.moveToThread(thread)
        self._threads.add(thread); self._workers.add(worker)
        thread.started.connect(worker.run); worker.succeeded.connect(success); worker.failed.connect(failure)
        worker.finished.connect(thread.quit); worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._threads.discard(thread)); thread.finished.connect(lambda: self._workers.discard(worker))
        thread.start()

    def login(self) -> None:
        if self.login_dialog.property("busy"):
            return
        username = self.username_input.text().strip(); password = self.password_input.text()
        if not username or not password:
            self.login_status.setText("Username and password are required."); return
        self._set_login_busy(True, "Signing in…")
        client = LiteApiClient(self.server_input.text(), self.insecure_check.isChecked())

        def accepted(user):
            self.api = client; self.user = dict(user); self.password_input.clear(); self._set_login_busy(False)
            save_config({"server_url": client.server_url, "insecure_tls": self.insecure_check.isChecked(), "remember_username": username})
            name = self.user.get("full_name") or self.user.get("username") or "User"
            self.identity_label.setText(f"Signed in: {name}")
            self.pages.setCurrentWidget(self.jobs_page); self.show(); self.login_dialog.accept(); self._known_job_ids = None; self.refresh_timer.start(); self.refresh_jobs()
            self.refresh_design_prompts()

        def authenticate():
            try:
                user = client.login(username, password)
                return client.current_user() or user
            except Exception:
                client.close()
                raise

        self._run_task(authenticate, accepted, lambda error: self._set_login_busy(False, error))

    def logout(self) -> None:
        self.refresh_timer.stop(); self.api = None; self.user = {}; self.jobs = []; self.selected_job = {}; self._known_job_ids = None
        self.job_table.setRowCount(0); self.detail_title.setText("Select a job"); self.detail_text.clear(); self.complete_button.setEnabled(False)
        self.detail_status.hide()
        self.start_button.setEnabled(False)
        self.collect_button.setEnabled(False)
        self.pages.setCurrentWidget(self.login_page); self.password_input.clear(); self._set_login_busy(False)
        self.show_login_dialog(); self.hide()

    def refresh_jobs(self) -> None:
        if not self.api or self._loading or self._updating:
            return
        client = self.api
        revision = self._jobs_revision
        self._loading = True; query = self.search_input.text().strip(); mode = str(self.status_filter.currentData() or "pending")
        from_date, to_date = self._selected_date_range()

        def operation():
            # Always fetch the shared board so notifications are independent of
            # the operator's current search or status filter.
            all_rows = client.service_orders(query="", status="", limit=200)
            rows = client.service_orders(query=query, status="", limit=200, from_date=from_date, to_date=to_date)
            needle = query.casefold()
            if needle:
                rows = [row for row in rows if needle in " ".join(str(row.get(key) or "") for key in ("job_title", "complaint", "internal_notes")).casefold()]
            if mode == "ready_for_pickup":
                rows = [row for row in rows if str(row.get("status") or "") in READY_FOR_PICKUP_STATUSES]
            elif mode in {"delivered", "in_progress"}:
                rows = [row for row in rows if str(row.get("status") or "") == mode]
            elif mode != "all":
                rows = [row for row in rows if str(row.get("status") or "") not in READY_FOR_PICKUP_STATUSES | {"delivered", "cancelled"}]
            return all_rows, rows

        def loaded(result):
            self._loading = False; all_jobs, jobs = result; jobs = list(jobs); current_ids = {int(job.get("id") or 0) for job in all_jobs}
            if self.api is not client:
                return
            if revision != self._jobs_revision:
                self.refresh_jobs()
                return
            selected_id = self.selected_job.get("id")
            if self._known_job_ids is not None:
                username = str(self.user.get("username") or "").casefold()
                for job in reversed([job for job in all_jobs if int(job.get("id") or 0) not in self._known_job_ids]):
                    if str(job.get("created_by") or "").casefold() != username:
                        self.tray.showMessage("New Service Job", str(job.get("job_title") or "New Job"), QSystemTrayIcon.MessageIcon.Information, 8000)
            self._known_job_ids = (self._known_job_ids or set()) | current_ids
            self.jobs = jobs; self.job_table.blockSignals(True); self.job_table.setRowCount(len(jobs))
            for row, job in enumerate(jobs):
                received = str(job.get("received_at") or ""); status = str(job.get("status") or "received")
                status_label, background, foreground = job_status_style(status)
                values = (received[:10], received[11:16], job.get("job_title") or "—", job.get("complaint") or "—",
                          job.get("expected_at") or "—", status_label, job.get("completed_by") or "—",
                          job.get("started_by") or "—", job.get("started_at") or "—",
                          job.get("completed_at") or "—", job.get("delivered_by") or "—", job.get("delivered_at") or "—")
                for column, value in enumerate(values):
                    item = QTableWidgetItem(str(value)); item.setData(Qt.ItemDataRole.UserRole, int(job.get("id") or 0)); self.job_table.setItem(row, column, item)
                    item.setBackground(QColor(background)); item.setForeground(QColor(foreground))
                    if column == 5:
                        font = item.font(); font.setBold(True); item.setFont(font)
            self.job_table.blockSignals(False); self.jobs_status.setText(f"{len(jobs)} job(s)")
            if jobs:
                selected_row = next((index for index, job in enumerate(jobs) if job.get("id") == selected_id), 0)
                self.job_table.selectRow(selected_row)
            self.load_selected_job()

        self._run_task(operation, loaded, lambda error: (setattr(self, "_loading", False), self.statusBar().showMessage(error)))

    def load_selected_job(self) -> None:
        row = self.job_table.currentRow(); item = self.job_table.item(row, 0) if row >= 0 else None
        job_id = int(item.data(Qt.ItemDataRole.UserRole) or 0) if item else 0
        job = next((entry for entry in self.jobs if int(entry.get("id") or 0) == job_id), {})
        self.selected_job = dict(job)
        self.start_button.setEnabled(False)
        self.collect_button.setEnabled(False)
        if not job:
            self.detail_title.setText("Select a job"); self.detail_text.clear(); self.detail_status.hide(); self.complete_button.setEnabled(False); self.load_prompt_preview(); return
        status = str(job.get("status") or "received")
        status_label, background, foreground = job_status_style(status)
        self.detail_status.setText(status_label)
        self.detail_status.setStyleSheet(f"background-color: {background}; color: {foreground}; padding: 6px 10px; border-radius: 6px; font-weight: 700;")
        self.detail_status.show()
        self.detail_title.setText(str(job.get("job_title") or "Service Job"))
        self.detail_text.setPlainText(
            f"Date/Time: {job.get('received_at') or '—'}\n\nDetails:\n{job.get('complaint') or '—'}\n\n"
            f"Appointment: {job.get('expected_at') or '—'}\n\nNotes:\n{job.get('internal_notes') or '—'}\n\n"
            f"Working By: {job.get('started_by') or '—'}\nStarted At: {job.get('started_at') or '—'}\n\n"
            f"Created By: {job.get('created_by') or '—'}\nWork Completed By: {job.get('completed_by') or '—'}\n"
            f"Work Completed At: {job.get('completed_at') or '—'}\n\n"
            f"Delivered By: {job.get('delivered_by') or '—'}\nDelivered At: {job.get('delivered_at') or '—'}"
        )
        owner = str(job.get("started_by") or "")
        self.start_button.setEnabled(not self._updating and status in {"received", "assigned", "on_hold", "waiting_parts"}
                                     and (not owner or owner == self.user.get("username")))
        self.complete_button.setEnabled(not self._updating and status not in READY_FOR_PICKUP_STATUSES | {"delivered", "cancelled"})
        self.collect_button.setEnabled(not self._updating and status in READY_FOR_PICKUP_STATUSES)
        self.load_prompt_preview()

    def start_job(self) -> None:
        if not self.api or not self.selected_job or self._updating:
            return
        self._change_job_status("in_progress", "Started from Service Job Client")

    def _change_job_status(self, status: str, note: str) -> None:
        client = self.api
        job_id = int(self.selected_job["id"])
        self._updating = True
        self._jobs_revision += 1
        self.start_button.setEnabled(False); self.complete_button.setEnabled(False)
        self.collect_button.setEnabled(False)

        def finished(job=None, error=None):
            self._updating = False
            if self.api is not client:
                return
            if job:
                self.jobs = [dict(job) if entry.get("id") == job_id else entry for entry in self.jobs]
            self.load_selected_job()
            self.refresh_jobs()
            if error:
                if (status == "ready_for_pickup"
                        and str(error).startswith("Cannot change service order from ")
                        and str(error).endswith(" to ready_for_pickup")):
                    error = (f"{error}\n\n"
                             "The POS Server may be running an older service-job workflow. "
                             "Update the POS Server code and restart the process serving this client's server address, "
                             "then refresh and try Complete Job again. Updating only this client is not enough.\n\n"
                             "No alternative completion or collection request was sent.")
                QMessageBox.warning(self, "Service Job", error)

        self._run_task(lambda: client.change_service_order_status(job_id, status, note),
                       finished, lambda error: finished(error=error))

    def complete_job(self) -> None:
        if not self.api or not self.selected_job or self._updating:
            return
        if str(self.selected_job.get("status")) in READY_FOR_PICKUP_STATUSES | {"delivered", "cancelled"}:
            return
        if QMessageBox.question(self, "Complete Job", "Mark the work as finished and ready for customer pickup?") != QMessageBox.StandardButton.Yes:
            return
        self._change_job_status("ready_for_pickup", "Work completed from Service Job Client")

    def collect_job(self) -> None:
        if not self.api or not self.selected_job or self._updating:
            return
        if str(self.selected_job.get("status")) not in READY_FOR_PICKUP_STATUSES:
            return
        notes = str(self.selected_job.get("internal_notes") or "—")
        if QMessageBox.question(self, "Customer Collection", f"Notes:\n{notes}\n\nHas the customer collected this job?") != QMessageBox.StandardButton.Yes:
            return
        self._change_job_status("delivered", "Customer collected job from Service Job Client")
