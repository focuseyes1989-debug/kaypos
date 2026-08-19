"""Preview and export auto-filled Car Management form templates."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QResizeEvent
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QScrollArea, QVBoxLayout,
)

from car_client.form_templates import PAGE_NUMBERS, export_filled_pdf, render_form_page, save_filled_page
from car_client.form_print_dialog import FormPrintSettingsDialog


class FormPreviewDialog(QDialog):
    def __init__(self,record:dict,parent=None):
        super().__init__(parent);self.record=record;self.rendered_image=None
        self.setWindowTitle("Auto-Filled Car Forms");self.setMinimumSize(760,640);self.resize(940,820)
        layout=QVBoxLayout(self);layout.setContentsMargins(16,14,16,14);layout.setSpacing(10)
        title=QLabel(f"{record.get('car_number') or ''} · {record.get('driver_name') or ''}");title.setStyleSheet("font-size: 15pt; font-weight: 700;");layout.addWidget(title)
        toolbar=QHBoxLayout();toolbar.addWidget(QLabel("Form Page:"));self.page_combo=QComboBox()
        for page in PAGE_NUMBERS:self.page_combo.addItem(f"Page {page}",page)
        toolbar.addWidget(self.page_combo);toolbar.addWidget(QLabel("Zoom:"));self.zoom_combo=QComboBox();self.zoom_combo.addItems(["Fit Width","50%","75%","100%"]);toolbar.addWidget(self.zoom_combo);toolbar.addStretch()
        self.save_image_button=QPushButton("Save Page Image");self.print_button=QPushButton("Print Settings");self.export_pdf_button=QPushButton("Export 4-Page PDF");self.export_pdf_button.setObjectName("primary");toolbar.addWidget(self.save_image_button);toolbar.addWidget(self.print_button);toolbar.addWidget(self.export_pdf_button);layout.addLayout(toolbar)
        self.preview_label=QLabel();self.preview_label.setAlignment(Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignHCenter);self.preview_label.setStyleSheet("background: white;")
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(False);self.scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop);self.scroll.setWidget(self.preview_label);layout.addWidget(self.scroll,1)
        footer=QHBoxLayout();self.status=QLabel("Database data is overlaid on the original image; templates remain unchanged.");self.status.setObjectName("muted");footer.addWidget(self.status,1);close=QPushButton("Close");close.clicked.connect(self.accept);footer.addWidget(close);layout.addLayout(footer)
        self.page_combo.currentIndexChanged.connect(self.refresh_preview);self.zoom_combo.currentIndexChanged.connect(self._display_rendered);self.save_image_button.clicked.connect(self.save_page_image);self.print_button.clicked.connect(self.open_print_settings);self.export_pdf_button.clicked.connect(self.export_pdf)
        self.refresh_preview()

    def refresh_preview(self):
        try:self.rendered_image=render_form_page(self.record,self.page_combo.currentData());self._display_rendered();self.status.setText(f"Page {self.page_combo.currentData()} auto-filled successfully.")
        except Exception as exc:self.rendered_image=None;self.preview_label.clear();self.status.setText(str(exc));QMessageBox.critical(self,"Form Preview",str(exc))

    def _display_rendered(self):
        if self.rendered_image is None:return
        value=self.zoom_combo.currentText()
        if value=="Fit Width":width=max(300,self.scroll.viewport().width()-24)
        else:width=round(self.rendered_image.width()*int(value.rstrip("%"))/100)
        pixmap=QPixmap.fromImage(self.rendered_image).scaledToWidth(width,Qt.TransformationMode.SmoothTransformation)
        self.preview_label.setPixmap(pixmap);self.preview_label.resize(pixmap.size())

    def resizeEvent(self,event:QResizeEvent):
        super().resizeEvent(event)
        if hasattr(self,"zoom_combo") and self.zoom_combo.currentText()=="Fit Width":self._display_rendered()

    def _suggested_name(self,suffix):
        car="".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(self.record.get("car_number") or "car"))
        return f"{car}_forms{suffix}"

    def save_page_image(self):
        page=self.page_combo.currentData();path,_=QFileDialog.getSaveFileName(self,"Save Filled Form Page",self._suggested_name(f"_page_{page}.png"),"PNG Image (*.png);;JPEG Image (*.jpg)")
        if not path:return
        try:save_filled_page(self.record,page,path);self.status.setText(f"Saved: {path}");QMessageBox.information(self,"Form Saved",f"Filled form page saved successfully.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"Could Not Save Form",str(exc))

    def export_pdf(self):
        path,_=QFileDialog.getSaveFileName(self,"Export Filled Forms",self._suggested_name(".pdf"),"PDF Document (*.pdf)")
        if not path:return
        if not Path(path).suffix:path += ".pdf"
        try:export_filled_pdf(self.record,path);self.status.setText(f"Exported: {path}");QMessageBox.information(self,"PDF Exported",f"Four-page form PDF exported successfully.\n{path}")
        except Exception as exc:QMessageBox.critical(self,"Could Not Export PDF",str(exc))

    def open_print_settings(self):
        FormPrintSettingsDialog(self.record, self).exec()
