"""Native attachment preview and explicit upload/download controls."""
import base64
import hashlib
import os
from pathlib import Path
import tempfile
from urllib.parse import urlencode

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox
from native_pos.catalog import CatalogSession

MAX_BYTES = 8 * 1024 * 1024


def atomic_download(path, data):
    path = Path(path); descriptor, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        Path(temporary).replace(path)
    finally: Path(temporary).unlink(missing_ok=True)


class AttachmentDialog(QDialog):
    def __init__(self, host, kind, record_id, data, parent=None):
        super().__init__(parent); self.host = host; self.kind = kind; self.record_id = record_id; self.data = data; self.change = None
        self.setWindowTitle({'photo': 'Employee photo', 'document': 'Employee document', 'logo': 'Receipt logo', 'qr': 'Receipt QR image'}[kind])
        self.resize(620, 460)
        self.bytes = base64.b64decode(data.get('content') or '', validate=True)
        if len(self.bytes) != data['size'] or hashlib.sha256(self.bytes).hexdigest() != data['sha256']: raise ValueError('Attachment checksum mismatch')
        body = QVBoxLayout(self)
        self.info = QLabel((data.get('name') or data.get('reference') or 'No uploaded file') + f" · {data['size']:,} bytes")
        self.info.setTextFormat(Qt.TextFormat.PlainText); self.info.setWordWrap(True); body.addWidget(self.info)
        preview = QLabel(); preview.setAlignment(Qt.AlignmentFlag.AlignCenter); preview.setMinimumHeight(230)
        if data.get('mime', '').startswith('image/') and self.bytes:
            pixmap = QPixmap(); pixmap.loadFromData(self.bytes)
            preview.setPixmap(pixmap.scaled(540, 290, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else: preview.setText('Download to view this PDF.' if self.bytes else 'No file has been uploaded. Existing local references are not read from the server filesystem.')
        preview.setWordWrap(True); body.addWidget(preview, 1)
        row = QHBoxLayout()
        upload = QPushButton('Upload / Replace…'); upload.clicked.connect(self.upload)
        remove = QPushButton('Remove…'); remove.clicked.connect(self.remove)
        download = QPushButton('Download…'); download.clicked.connect(self.download); download.setEnabled(bool(self.bytes))
        close = QPushButton('Close'); close.clicked.connect(self.reject)
        permission = 'edit_settings' if kind in ('logo', 'qr') else 'manage_employees'
        allowed = host.session.can(permission) and not host.files_session.pending and not host.files_session.error
        upload.setEnabled(allowed); remove.setEnabled(allowed and bool(self.bytes or data.get('reference')))
        for control in (upload, remove, download, close): row.addWidget(control)
        body.addLayout(row)

    def values(self, **extra):
        return dict(kind=self.kind, id=self.record_id, revision=self.data['revision'], **extra)

    def upload(self):
        filter = 'PDF / images (*.pdf *.png *.jpg *.jpeg *.webp)' if self.kind == 'document' else 'Images (*.png *.jpg *.jpeg *.webp)'
        path, _ = QFileDialog.getOpenFileName(self, 'Choose attachment', '', filter)
        if not path: return
        try:
            with open(path, 'rb') as stream: data = stream.read(MAX_BYTES + 1)
            if not data or len(data) > MAX_BYTES: raise ValueError('Choose a non-empty file of at most 8 MB')
            if QMessageBox.question(self, 'Upload attachment', f'Upload {Path(path).name} ({len(data):,} bytes) and replace the current attachment?') != QMessageBox.StandardButton.Yes: return
            self.change = self.values(filename=Path(path).name, content=base64.b64encode(data).decode()); self.accept()
        except (OSError, ValueError) as exc: QMessageBox.warning(self, 'Attachment', str(exc))

    def remove(self):
        if QMessageBox.question(self, 'Remove attachment', 'Remove this uploaded file/reference? The employee/document record is retained.') == QMessageBox.StandardButton.Yes:
            self.change = self.values(remove=True); self.accept()

    def download(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Download attachment', self.data['name'])
        if path:
            try: atomic_download(path, self.bytes)
            except OSError as exc: QMessageBox.warning(self, 'Download failed', str(exc))


def open_attachment(page, kind, record_id=0):
    host = page.host
    if host.runner.busy or host.closing: return
    if not getattr(host, 'files_session', None): host.files_session = CatalogSession(host, 'files')
    channel = host.files_session
    if channel.pending:
        channel.recover(); return
    def received(data):
        dialog = AttachmentDialog(host, kind, record_id, data, page)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.change:
            operation = 'receipt_image.save' if kind in ('logo', 'qr') else kind + '.save'
            channel.submit(operation, dialog.change)
    channel.run(lambda: channel.api._request('GET', '/api/native/files?' + urlencode(dict(kind=kind, record_id=record_id))), received, 'Loading attachment…')
