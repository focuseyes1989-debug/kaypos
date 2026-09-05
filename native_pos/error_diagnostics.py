"""Local, rule-based guidance; pasted errors are never sent or persisted."""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton
from ui.ai_pages.ai_error_diagnostics import AIErrorDiagnostics


def explain_error(text):
    if not text.strip():
        raise ValueError('Paste an error message first.')
    if len(text) > 20000:
        raise ValueError('Use at most 20,000 characters from the relevant error.')
    item = AIErrorDiagnostics.diagnose(text)
    # Rules produce static advice. Never echo arbitrary credentials from a traceback.
    parts = [item['title'], 'Rule-based guidance; verify the actual operation status before retrying.', item['meaning']]
    for title, key in [('Possible causes', 'causes'), ('Checks', 'checks'), ('Suggested fixes', 'fixes')]:
        parts.append(title + '\n' + '\n'.join(f'{i}. {value}' for i, value in enumerate(item[key], 1)))
    parts.extend(['Data risk\n' + item['risk'], 'Retry guidance\n' + item['retry']])
    return '\n\n'.join(parts)


class ErrorDiagnosticsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Error diagnostics · this PC'); self.resize(760, 620)
        body = QVBoxLayout(self)
        note = QLabel('Paste an error or traceback. Analysis uses local rules only; nothing is sent to the server or saved. Suggestions do not execute repairs.'); note.setWordWrap(True); body.addWidget(note)
        self.input = QPlainTextEdit(); self.input.setPlaceholderText('Paste error text here (maximum 20,000 characters)…'); body.addWidget(self.input, 1)
        row = QHBoxLayout()
        self.analyze_button = QPushButton('Analyze'); self.analyze_button.clicked.connect(self.analyze)
        clear = QPushButton('Clear'); clear.clicked.connect(self.clear)
        close = QPushButton('Close'); close.clicked.connect(self.reject)
        for button in (self.analyze_button, clear, close): row.addWidget(button)
        body.addLayout(row)
        self.output = QPlainTextEdit(); self.output.setReadOnly(True); body.addWidget(self.output, 2)
        self.input.textChanged.connect(self.output.clear)

    def analyze(self):
        try: result = explain_error(self.input.toPlainText())
        except ValueError as exc: result = str(exc)
        self.output.setPlainText(result)

    def clear(self):
        self.input.clear(); self.output.clear()
        self.input.document().clearUndoRedoStacks()

    def done(self, result):
        self.clear()
        super().done(result)
