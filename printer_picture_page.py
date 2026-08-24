"""Windows Print Pictures-inspired page for the KAY Printer Agent."""

from __future__ import annotations

import os
import json
import tempfile
import uuid
from pathlib import Path

from PyQt6.QtCore import QSize, QSettings, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
    QInputDialog, QLabel, QListWidget, QListWidgetItem, QMessageBox, QProgressBar, QPushButton,
    QDoubleSpinBox, QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from printer_picture_print import (
    LAYOUTS, PAPER_SIZES_MM, PictureItem, export_picture_pdf, layout_capacity,
    load_picture, paginate, paper_api_key, preview_page,
)


class PictureQueueWorker(QThread):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, request, target: dict, items: list[PictureItem], options: dict, parent=None):
        super().__init__(parent)
        self.request = request
        self.target = dict(target)
        self.items = [PictureItem(item.path, item.rotation) for item in items]
        self.options = dict(options)

    def run(self) -> None:
        output_path = ""
        try:
            self.progress.emit(5, "Confirming printer availability…")
            agents = self.request("GET", "/api/printer/agents") or []
            available = any(
                agent.get("agent_id") == self.target.get("agent_id")
                and agent.get("is_online") and agent.get("is_enabled", True)
                and any(
                    printer.get("printer_name") == self.target.get("printer_name")
                    and printer.get("status") == "online" and printer.get("is_enabled", True)
                    for printer in agent.get("printers") or []
                )
                for agent in agents
            )
            if not available:
                raise RuntimeError("The selected printer is offline. Refresh printers and choose an online target.")
            self.progress.emit(15, "Composing print-ready pages…")
            with tempfile.NamedTemporaryFile(prefix="kay-print-pictures-", suffix=".pdf", delete=False) as stream:
                output_path = stream.name
            pages = export_picture_pdf(output_path, self.items, **self.options)
            asset_size = Path(output_path).stat().st_size
            if asset_size > 25 * 1024 * 1024:
                raise RuntimeError(
                    "The composed PDF exceeds the 25 MB queue limit. Use Normal/Draft quality, fewer pictures, or smaller source images."
                )
            self.progress.emit(45, f"Uploading {pages} page(s) to Printer Server…")
            with Path(output_path).open("rb") as stream:
                job = self.request(
                    "POST", "/api/printer/jobs/upload",
                    files={"file": ("KAY Print Pictures.pdf", stream, "application/pdf")},
                    data={
                        "target_agent_id": self.target["agent_id"],
                        "printer_name": self.target["printer_name"],
                        "request_key": f"agent-pictures-{uuid.uuid4()}",
                        # Copies are already composed per picture in the PDF.
                        "copies": 1,
                        "paper_size": paper_api_key(self.options["paper"]),
                        "custom_width_mm": self.options.get("custom_width_mm", 210.0),
                        "custom_height_mm": self.options.get("custom_height_mm", 297.0),
                        "borderless": str(self.options.get("borderless", False)).lower(),
                        "orientation": self.options["orientation"].lower(),
                        "quality": self.options["quality"].lower(),
                        "paper_type": self.options["paper_type"].lower(),
                        "color_mode": self.options["color_mode"].lower(),
                        "source_agent_id": "printer-agent-picture-ui",
                    },
                )
            result = dict(job or {})
            result["composed_pages"] = pages
            self.progress.emit(100, "Print job queued successfully.")
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if output_path:
                try:
                    os.unlink(output_path)
                except OSError:
                    pass


class PrintPicturesPage(QWidget):
    job_queued = pyqtSignal(dict)

    def __init__(self, request=None, parent=None):
        super().__init__(parent)
        self.request = request
        self.settings = QSettings("KAY POS", "Printer Agent")
        self.items: list[PictureItem] = []
        self.current_page = 0
        self.queue_worker = None
        self._loading_preset = False
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        toolbar = QHBoxLayout()
        add = QPushButton("Add Pictures…")
        add.clicked.connect(self.add_pictures)
        remove = QPushButton("Remove Selected")
        remove.clicked.connect(self.remove_selected)
        rotate_left = QPushButton("Rotate Left")
        rotate_left.clicked.connect(lambda: self.rotate_selected(-90))
        rotate_right = QPushButton("Rotate Right")
        rotate_right.clicked.connect(lambda: self.rotate_selected(90))
        clear = QPushButton("Clear All")
        clear.clicked.connect(self.clear_all)
        toolbar.addWidget(add)
        toolbar.addWidget(remove)
        toolbar.addWidget(rotate_left)
        toolbar.addWidget(rotate_right)
        toolbar.addWidget(clear)
        toolbar.addStretch()
        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.thumbnail_list = QListWidget()
        self.thumbnail_list.setObjectName("PictureThumbnails")
        self.thumbnail_list.setIconSize(QSize(72, 58))
        self.thumbnail_list.setMinimumWidth(170)
        self.thumbnail_list.setMaximumWidth(230)
        self.thumbnail_list.currentRowChanged.connect(self._thumbnail_selected)
        splitter.addWidget(self.thumbnail_list)

        preview_card = QFrame()
        preview_card.setObjectName("PicturePreviewCard")
        preview_layout = QVBoxLayout(preview_card)
        self.preview = QLabel("Add one or more pictures to begin")
        self.preview.setObjectName("PicturePreview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(300, 320)
        preview_layout.addWidget(self.preview, 1)
        navigation = QHBoxLayout()
        self.previous_button = QPushButton("‹ Previous")
        self.previous_button.clicked.connect(lambda: self.change_page(-1))
        self.page_label = QLabel("0 of 0 pages")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_button = QPushButton("Next ›")
        self.next_button.clicked.connect(lambda: self.change_page(1))
        navigation.addStretch()
        navigation.addWidget(self.previous_button)
        navigation.addWidget(self.page_label)
        navigation.addWidget(self.next_button)
        navigation.addStretch()
        preview_layout.addLayout(navigation)
        splitter.addWidget(preview_card)

        options_card = QFrame()
        options_card.setObjectName("PictureOptionsCard")
        options_card.setMinimumWidth(210)
        options = QFormLayout(options_card)
        self.preset = QComboBox()
        self.preset.addItem("Custom", "")
        preset_actions = QWidget()
        preset_layout = QHBoxLayout(preset_actions)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        preset_layout.setSpacing(6)
        save_preset = QPushButton("Save")
        save_preset.clicked.connect(self.save_preset)
        delete_preset = QPushButton("Delete")
        delete_preset.clicked.connect(self.delete_preset)
        preset_layout.addWidget(self.preset, 1)
        preset_layout.addWidget(save_preset)
        preset_layout.addWidget(delete_preset)
        self.paper = QComboBox()
        self.paper.addItems(PAPER_SIZES_MM.keys())
        self.paper.addItem("Custom Size")
        custom_size = QWidget()
        custom_layout = QHBoxLayout(custom_size)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        self.custom_width = QDoubleSpinBox()
        self.custom_width.setRange(20.0, 1000.0)
        self.custom_width.setValue(210.0)
        self.custom_width.setSuffix(" mm W")
        self.custom_height = QDoubleSpinBox()
        self.custom_height.setRange(20.0, 1000.0)
        self.custom_height.setValue(297.0)
        self.custom_height.setSuffix(" mm H")
        custom_layout.addWidget(self.custom_width)
        custom_layout.addWidget(self.custom_height)
        self.printer = QComboBox()
        self.printer.setMinimumContentsLength(20)
        self.printer.addItem("Refresh to load online printers", None)
        refresh_printers = QPushButton("Refresh Printers")
        refresh_printers.clicked.connect(self.refresh_printers)
        self.orientation = QComboBox()
        self.orientation.addItems(["Portrait", "Landscape"])
        self.layout = QComboBox()
        self.layout.addItems(LAYOUTS.keys())
        self.copies = QSpinBox()
        self.copies.setRange(1, 99)
        self.margin = QSpinBox()
        self.margin.setRange(0, 30)
        self.margin.setValue(5)
        self.margin.setSuffix(" mm")
        self.fit_to_frame = QCheckBox("Fit picture to frame")
        self.fit_to_frame.setChecked(True)
        self.quality = QComboBox()
        self.quality.addItems(["Draft", "Normal", "High"])
        self.quality.setCurrentText("Normal")
        self.paper_type = QComboBox()
        self.paper_type.addItems(["Automatic", "Plain", "Photo", "Glossy", "Matte"])
        self.color_mode = QComboBox()
        self.color_mode.addItems(["Color", "Grayscale"])
        self.borderless = QCheckBox("Borderless (printer support required)")
        options.addRow("Preset", preset_actions)
        options.addRow("Printer", self.printer)
        options.addRow("", refresh_printers)
        options.addRow("Paper", self.paper)
        options.addRow("Custom size", custom_size)
        options.addRow("Orientation", self.orientation)
        options.addRow("Layout", self.layout)
        options.addRow("Copies of each", self.copies)
        options.addRow("Margins", self.margin)
        options.addRow("", self.borderless)
        options.addRow("Quality", self.quality)
        options.addRow("Paper type", self.paper_type)
        options.addRow("Output", self.color_mode)
        options.addRow("", self.fit_to_frame)
        hint = QLabel("Fit fills each frame and may crop picture edges. Turn it off to keep the entire picture.")
        hint.setWordWrap(True)
        hint.setObjectName("AgentSubtitle")
        options.addRow(hint)
        splitter.addWidget(options_card)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        root.addWidget(splitter, 1)

        footer = QHBoxLayout()
        self.status = QLabel("Ready · local PDF export and Printer Server queue")
        self.status.setObjectName("AgentStatus")
        self.queue_progress = QProgressBar()
        self.queue_progress.setRange(0, 100)
        self.queue_progress.setTextVisible(False)
        self.queue_progress.hide()
        export = QPushButton("Save Print PDF…")
        export.clicked.connect(self.export_pdf)
        self.queue_button = QPushButton("Queue Print Job")
        self.queue_button.clicked.connect(self.queue_print_job)
        footer.addWidget(self.status, 1)
        footer.addWidget(self.queue_progress)
        footer.addWidget(export)
        footer.addWidget(self.queue_button)
        root.addLayout(footer)

        for control in (self.paper, self.orientation, self.layout, self.quality, self.paper_type, self.color_mode):
            control.currentIndexChanged.connect(self.refresh_preview)
            control.currentIndexChanged.connect(self._mark_custom_preset)
        self.copies.valueChanged.connect(self.refresh_preview)
        self.copies.valueChanged.connect(self._mark_custom_preset)
        self.margin.valueChanged.connect(self.refresh_preview)
        self.margin.valueChanged.connect(self._mark_custom_preset)
        for custom_control in (self.custom_width, self.custom_height):
            custom_control.valueChanged.connect(self.refresh_preview)
            custom_control.valueChanged.connect(self._mark_custom_preset)
        self.paper.currentIndexChanged.connect(self._update_custom_size_state)
        self.borderless.toggled.connect(self._update_borderless_state)
        self.borderless.toggled.connect(self.refresh_preview)
        self.borderless.toggled.connect(self._mark_custom_preset)
        self.fit_to_frame.toggled.connect(self.refresh_preview)
        self.fit_to_frame.toggled.connect(self._mark_custom_preset)
        self.preset.currentIndexChanged.connect(self.load_preset)
        self._reload_presets()
        self._update_custom_size_state()
        self.refresh_preview()

    def _presets(self) -> dict:
        try:
            value = json.loads(str(self.settings.value("picture_print/presets", "{}") or "{}"))
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

    def _reload_presets(self, select_name: str = "") -> None:
        self.preset.blockSignals(True)
        self.preset.clear()
        self.preset.addItem("Custom", "")
        for name in sorted(self._presets(), key=str.casefold):
            self.preset.addItem(name, name)
        index = self.preset.findData(select_name)
        self.preset.setCurrentIndex(index if index >= 0 else 0)
        self.preset.blockSignals(False)

    def save_preset(self) -> None:
        suggested = str(self.preset.currentData() or "Photo preset")
        name, accepted = QInputDialog.getText(self, "Save Picture Preset", "Preset name", text=suggested)
        name = str(name or "").strip()[:60]
        if not accepted or not name:
            return
        presets = self._presets()
        presets[name] = self._preset_values()
        self.settings.setValue("picture_print/presets", json.dumps(presets, ensure_ascii=False))
        self.settings.sync()
        self._reload_presets(name)
        self.status.setText(f"Preset saved · {name}")

    def delete_preset(self) -> None:
        name = str(self.preset.currentData() or "")
        if not name:
            return
        presets = self._presets()
        presets.pop(name, None)
        self.settings.setValue("picture_print/presets", json.dumps(presets, ensure_ascii=False))
        self.settings.sync()
        self._reload_presets()
        self.status.setText(f"Preset deleted · {name}")

    def _preset_values(self) -> dict:
        return {
            "paper": self.paper.currentText(), "orientation": self.orientation.currentText(),
            "layout": self.layout.currentText(), "copies": self.copies.value(),
            "margin": self.margin.value(), "fit": self.fit_to_frame.isChecked(),
            "quality": self.quality.currentText(), "paper_type": self.paper_type.currentText(),
            "color_mode": self.color_mode.currentText(),
            "custom_width": self.custom_width.value(), "custom_height": self.custom_height.value(),
            "borderless": self.borderless.isChecked(),
        }

    def _mark_custom_preset(self, _value=None) -> None:
        if not self._loading_preset and self.preset.currentData():
            self.preset.setCurrentIndex(0)

    def load_preset(self, _index: int) -> None:
        name = str(self.preset.currentData() or "")
        values = self._presets().get(name) if name else None
        if not isinstance(values, dict):
            return
        self._loading_preset = True
        controls = (
            (self.paper, values.get("paper")),
            (self.orientation, values.get("orientation")),
            (self.layout, values.get("layout")),
            (self.quality, values.get("quality")),
            (self.paper_type, values.get("paper_type")),
            (self.color_mode, values.get("color_mode")),
        )
        try:
            for control, value in controls:
                if value is not None and control.findText(str(value)) >= 0:
                    control.setCurrentText(str(value))
            self.copies.setValue(max(1, min(99, int(values.get("copies", 1)))))
            self.margin.setValue(max(0, min(30, int(values.get("margin", 5)))))
            self.fit_to_frame.setChecked(bool(values.get("fit", True)))
            self.custom_width.setValue(float(values.get("custom_width", 210.0)))
            self.custom_height.setValue(float(values.get("custom_height", 297.0)))
            self.borderless.setChecked(bool(values.get("borderless", False)))
        finally:
            self._loading_preset = False
        self.refresh_preview()

    def _update_custom_size_state(self, _value=None) -> None:
        enabled = self.paper.currentText() == "Custom Size"
        self.custom_width.setEnabled(enabled)
        self.custom_height.setEnabled(enabled)

    def _update_borderless_state(self, checked: bool) -> None:
        self.margin.setEnabled(not checked)

    def set_printer_agents(self, agents: list[dict]) -> None:
        previous = self.printer.currentData() or {}
        previous_key = (previous.get("agent_id"), previous.get("printer_name"))
        self.printer.clear()
        selected_index = -1
        default_index = -1
        for agent in agents or []:
            if not agent.get("is_online") or not agent.get("is_enabled", True):
                continue
            for printer in agent.get("printers") or []:
                if (
                    printer.get("status") != "online"
                    or not printer.get("is_enabled", True)
                    or not printer.get("printer_name")
                ):
                    continue
                target = {
                    "agent_id": agent.get("agent_id"),
                    "computer_name": agent.get("computer_name"),
                    "printer_name": printer.get("printer_name"),
                }
                label = f"{agent.get('computer_name') or 'PC'} · {printer.get('printer_name')}"
                index = self.printer.count()
                self.printer.addItem(label, target)
                if (target["agent_id"], target["printer_name"]) == previous_key:
                    selected_index = index
                if default_index < 0 and printer.get("is_default"):
                    default_index = index
        if not self.printer.count():
            self.printer.addItem("No online printers available", None)
            self.queue_button.setEnabled(False)
            return
        self.printer.setCurrentIndex(selected_index if selected_index >= 0 else max(0, default_index))
        self.queue_button.setEnabled(True)

    def refresh_printers(self, _checked=False, *, silent: bool = False) -> None:
        if not self.request:
            self.set_printer_agents([])
            return
        try:
            self.status.setText("Loading online printers…")
            agents = self.request("GET", "/api/printer/agents") or []
            self.set_printer_agents(agents)
            available = sum(1 for index in range(self.printer.count()) if self.printer.itemData(index))
            self.status.setText(f"{available} online printer(s) available")
        except Exception as exc:
            self.set_printer_agents([])
            self.status.setText(f"Printer refresh failed: {exc}")
            if not silent:
                QMessageBox.warning(self, "Print Pictures", str(exc))

    def add_pictures(self) -> None:
        filenames, _ = QFileDialog.getOpenFileNames(
            self, "Select Pictures", "", "Pictures (*.jpg *.jpeg *.png *.bmp)"
        )
        self.add_picture_paths(filenames)

    def add_picture_paths(self, paths: list[str]) -> None:
        if len(self.items) >= 100:
            QMessageBox.warning(self, "Print Pictures", "A maximum of 100 pictures can be composed in one job.")
            return
        existing = {str(Path(item.path).resolve()).casefold() for item in self.items}
        skipped = 0
        for path in paths[:max(0, 100 - len(self.items))]:
            resolved = str(Path(path).resolve())
            if resolved.casefold() in existing:
                continue
            pixmap = QPixmap(resolved)
            if pixmap.isNull():
                skipped += 1
                continue
            picture = PictureItem(resolved)
            self.items.append(picture)
            entry = QListWidgetItem(QIcon(pixmap), picture.name)
            entry.setToolTip(resolved)
            self.thumbnail_list.addItem(entry)
            existing.add(resolved.casefold())
        if self.thumbnail_list.count() and self.thumbnail_list.currentRow() < 0:
            self.thumbnail_list.setCurrentRow(0)
        self.current_page = 0
        self.refresh_preview()
        if skipped:
            self.status.setText(f"Skipped {skipped} unreadable picture(s)")

    def remove_selected(self) -> None:
        row = self.thumbnail_list.currentRow()
        if row < 0:
            return
        self.thumbnail_list.takeItem(row)
        self.items.pop(row)
        if self.items:
            self.thumbnail_list.setCurrentRow(min(row, len(self.items) - 1))
        self.current_page = 0
        self.refresh_preview()

    def clear_all(self) -> None:
        self.items.clear()
        self.thumbnail_list.clear()
        self.current_page = 0
        self.refresh_preview()

    def rotate_selected(self, degrees: int) -> None:
        row = self.thumbnail_list.currentRow()
        if row < 0:
            return
        self.items[row].rotation = (self.items[row].rotation + degrees) % 360
        pixmap = QPixmap.fromImage(load_picture(self.items[row]))
        self.thumbnail_list.item(row).setIcon(QIcon(pixmap))
        self.refresh_preview()

    def _thumbnail_selected(self, row: int) -> None:
        if row < 0:
            return
        pages = self._pages()
        capacity = layout_capacity(self.layout.currentText())
        self.current_page = min(len(pages) - 1, row // capacity) if pages else 0
        self.refresh_preview()

    def _pages(self) -> list[list[PictureItem]]:
        return paginate(self.items, self.layout.currentText(), self.copies.value())

    def change_page(self, offset: int) -> None:
        pages = self._pages()
        if pages:
            self.current_page = max(0, min(len(pages) - 1, self.current_page + offset))
        self.refresh_preview()

    def refresh_preview(self) -> None:
        pages = self._pages()
        if not pages:
            self.preview.clear()
            self.preview.setText("Add one or more pictures to begin")
            self.page_label.setText("0 of 0 pages")
            self.previous_button.setEnabled(False)
            self.next_button.setEnabled(False)
            return
        self.current_page = max(0, min(self.current_page, len(pages) - 1))
        pixmap = preview_page(
            pages[self.current_page], paper=self.paper.currentText(),
            orientation=self.orientation.currentText(), layout=self.layout.currentText(),
            margin_mm=float(self.margin.value()), fit_to_frame=self.fit_to_frame.isChecked(),
            custom_width_mm=self.custom_width.value(), custom_height_mm=self.custom_height.value(),
            borderless=self.borderless.isChecked(),
            max_size=QSize(max(300, self.preview.width() - 20), max(300, self.preview.height() - 20)),
        )
        self.preview.setPixmap(pixmap)
        self.page_label.setText(f"{self.current_page + 1} of {len(pages)} pages")
        self.previous_button.setEnabled(self.current_page > 0)
        self.next_button.setEnabled(self.current_page + 1 < len(pages))
        self.status.setText(f"{len(self.items)} picture(s) · {len(pages)} print page(s)")

    def export_pdf(self) -> None:
        if not self.items:
            QMessageBox.warning(self, "Print Pictures", "Add at least one picture first.")
            return
        filename, _ = QFileDialog.getSaveFileName(self, "Save Print PDF", "KAY Print Pictures.pdf", "PDF (*.pdf)")
        if not filename:
            return
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
        try:
            pages = export_picture_pdf(filename, self.items, **self._composition_options())
            self.status.setText(f"Saved {pages} print-ready page(s) · {filename}")
            QMessageBox.information(self, "Print Pictures", f"Print-ready PDF saved successfully.\n\n{filename}")
        except Exception as exc:
            QMessageBox.critical(self, "Print Pictures", str(exc))

    def _composition_options(self) -> dict:
        return {
            "paper": self.paper.currentText(),
            "orientation": self.orientation.currentText(),
            "layout": self.layout.currentText(),
            "copies": self.copies.value(),
            "margin_mm": float(self.margin.value()),
            "fit_to_frame": self.fit_to_frame.isChecked(),
            "quality": self.quality.currentText(),
            "paper_type": self.paper_type.currentText(),
            "color_mode": self.color_mode.currentText(),
            "custom_width_mm": self.custom_width.value(),
            "custom_height_mm": self.custom_height.value(),
            "borderless": self.borderless.isChecked(),
        }

    def queue_print_job(self) -> None:
        if not self.items:
            QMessageBox.warning(self, "Print Pictures", "Add at least one picture first.")
            return
        target = self.printer.currentData()
        if not isinstance(target, dict):
            QMessageBox.warning(self, "Print Pictures", "Refresh and select an online printer first.")
            return
        if not self.request:
            QMessageBox.warning(self, "Print Pictures", "Printer Server connection is unavailable.")
            return
        if self.queue_worker and self.queue_worker.isRunning():
            return
        self.queue_button.setEnabled(False)
        self.queue_progress.setValue(0)
        self.queue_progress.show()
        self.queue_worker = PictureQueueWorker(
            self.request, target, self.items, self._composition_options(), self,
        )
        self.queue_worker.progress.connect(self._queue_progress)
        self.queue_worker.succeeded.connect(self._queue_succeeded)
        self.queue_worker.failed.connect(self._queue_failed)
        self.queue_worker.finished.connect(self._queue_finished)
        self.queue_worker.start()

    def _queue_progress(self, value: int, message: str) -> None:
        self.queue_progress.setValue(value)
        self.status.setText(message)

    def _queue_succeeded(self, job: dict) -> None:
        job_id = str(job.get("job_id") or "")
        pages = int(job.get("composed_pages") or 0)
        self.status.setText(f"Queued {pages} page(s) · Job {job_id[:8]}")
        self.job_queued.emit(job)
        QMessageBox.information(self, "Print Pictures", f"Print job queued successfully.\n\nJob ID: {job_id}")

    def _queue_failed(self, message: str) -> None:
        self.status.setText(f"Queue failed: {message}")
        QMessageBox.critical(self, "Print Pictures", message)

    def _queue_finished(self) -> None:
        worker = self.queue_worker
        self.queue_worker = None
        self.queue_progress.hide()
        self.queue_button.setEnabled(any(self.printer.itemData(i) for i in range(self.printer.count())))
        if worker:
            worker.deleteLater()
