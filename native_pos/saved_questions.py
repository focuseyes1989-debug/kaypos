"""Explicit, encrypted machine-local question bookmarks."""
import hashlib
import json
import os
import tempfile
from pathlib import Path
from PyQt6.QtCore import QLockFile
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QLineEdit, QPlainTextEdit, QPushButton, QMessageBox
from native_pos.config import config_path
from native_pos.protected_journal import protect


class QuestionStore:
    def __init__(self, root, scope):
        self.path = Path(root) / ('questions-' + hashlib.sha256(scope.encode()).hexdigest() + '.dat')
        self.snapshot = self.path.read_bytes() if self.path.exists() else None

    def read(self):
        if not self.path.exists(): return []
        try:
            raw = self.path.read_bytes()
            rows = json.loads(protect(raw, decrypt=True))
            self.validate(rows)
            self.snapshot = raw
            return rows
        except (ValueError, OSError, TypeError, KeyError) as exc:
            raise ValueError('Saved questions could not be opened with this Windows account. The existing file has been preserved.') from exc

    @staticmethod
    def validate(rows):
        if not isinstance(rows, list) or len(rows) > 50: raise ValueError('Save at most 50 questions.')
        names = set()
        for row in rows:
            if not isinstance(row, dict): raise ValueError('Invalid saved question.')
            for key, limit in [('name', 80), ('query', 1000)]:
                value = row.get(key)
                if not isinstance(value, str) or not value.strip() or len(value) > limit:
                    raise ValueError(f'{key.title()} must contain 1–{limit} characters.')
            name = row['name'].strip().casefold()
            if name in names: raise ValueError('Choose a different name for this question.')
            names.add(name)

    def write(self, rows):
        self.validate(rows)
        data = protect(json.dumps(rows, ensure_ascii=False).encode())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(self.path) + '.lock')
        if not lock.tryLock(0): raise ValueError('Another window is saving questions. Try again shortly.')
        name = None
        try:
            current = self.path.read_bytes() if self.path.exists() else None
            if current != self.snapshot: raise ValueError('Saved questions changed in another window. Close and reopen this dialog before editing.')
            fd, name = tempfile.mkstemp(dir=self.path.parent, prefix='.questions-', suffix='.tmp')
            with os.fdopen(fd, 'wb') as stream: stream.write(data)
            os.replace(name, self.path)
            self.snapshot = data
        finally:
            if name and os.path.exists(name): os.unlink(name)
            lock.unlock()


class SavedQuestionsDialog(QDialog):
    def __init__(self, store, query='', parent=None):
        super().__init__(parent); self.store = store; self.chosen = None
        self.setWindowTitle('Saved questions · this PC'); self.resize(700, 540)
        body = QVBoxLayout(self)
        note = QLabel('Saved separately for this server and POS account, encrypted with your Windows account. Loading only fills the question box; press Ask to run with current permissions. Dates written in a question stay fixed.'); note.setWordWrap(True); body.addWidget(note)
        self.list = QListWidget(); body.addWidget(self.list)
        self.name = QLineEdit(); self.name.setMaxLength(80); self.name.setPlaceholderText('Question name'); body.addWidget(self.name)
        self.query = QPlainTextEdit(); self.query.setPlainText(query); body.addWidget(self.query)
        row = QHBoxLayout(); body.addLayout(row)
        for label, callback in [('New', self.new), ('Save', self.save), ('Delete', self.delete), ('Load question', self.load), ('Close', self.reject)]:
            button = QPushButton(label); button.clicked.connect(callback); row.addWidget(button)
        self.rows = store.read(); self.refresh()
        self.list.currentRowChanged.connect(self.select)

    def refresh(self):
        self.list.blockSignals(True); self.list.clear(); self.list.addItems([r['name'] for r in self.rows]); self.list.blockSignals(False)

    def select(self, index):
        if 0 <= index < len(self.rows):
            self.name.setText(self.rows[index]['name']); self.query.setPlainText(self.rows[index]['query'])

    def new(self):
        self.list.setCurrentRow(-1); self.name.clear(); self.query.clear()

    def save(self):
        rows = list(self.rows); item = dict(name=self.name.text().strip(), query=self.query.toPlainText().strip())
        index = self.list.currentRow()
        if index < 0: rows.append(item); index = len(rows) - 1
        else: rows[index] = item
        try: self.store.write(rows)
        except (ValueError, OSError) as exc: QMessageBox.warning(self, 'Saved questions', str(exc)); return
        self.rows = rows; self.refresh(); self.list.setCurrentRow(index)

    def delete(self):
        index = self.list.currentRow()
        if index < 0: return
        if QMessageBox.question(self, 'Delete question', 'Delete the selected saved question?') != QMessageBox.StandardButton.Yes: return
        rows = self.rows[:index] + self.rows[index + 1:]
        try: self.store.write(rows)
        except (ValueError, OSError) as exc: QMessageBox.warning(self, 'Saved questions', str(exc)); return
        self.rows = rows; self.refresh(); self.new()

    def load(self):
        index = self.list.currentRow()
        if index >= 0: self.chosen = self.rows[index]['query']; self.accept()


def store_for(host):
    config = host.config
    scope = json.dumps([config['backend'], config['server_url'].rstrip('/'), config.get('database', ''), config.get('schema', ''), host.session.user_id, host.session.username])
    return QuestionStore(Path(host.settings_path or config_path()).parent / 'saved_questions', scope)
