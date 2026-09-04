"""One short-lived worker at a time; completion is delivered after thread shutdown."""
from PyQt6.QtCore import QObject, QThread, pyqtSignal

class Worker(QObject):
    finished = pyqtSignal()
    def __init__(self, operation):
        super().__init__()
        self.operation = operation
        self.result = None
        self.error = None
    def run(self):
        try:
            self.result = self.operation()
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.operation = None
            self.finished.emit()

class TaskRunner(QObject):
    idle = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.thread = None
    @property
    def busy(self):
        return self.thread is not None
    def start(self, operation, success, failure):
        if self.busy:
            return False
        self.thread = QThread(self)
        self.worker = Worker(operation)
        self.worker.moveToThread(self.thread)
        self.success, self.failure = success, failure
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._finished)
        self.thread.start()
        return True
    def _finished(self):
        result, error = self.worker.result, self.worker.error
        success, failure = self.success, self.failure
        self.thread.deleteLater()
        self.thread = self.worker = None
        self.success = self.failure = None
        if error is None:
            success(result)
        else:
            failure(error)
        self.idle.emit()
