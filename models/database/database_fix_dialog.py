# ui/dialogs/database_fix_dialog.py
"""
Simple dialog to show database fix progress.
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon


class DatabaseFixWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)
    
    def run(self):
        try:
            from models.database.auto_fix import run_auto_fix
            
            self.progress.emit(10, "Checking database...")
            
            self.progress.emit(30, "Fixing category columns...")
            success = run_auto_fix()
            
            self.progress.emit(90, "Verifying fixes...")
            
            self.progress.emit(100, "Fix completed!")
            self.finished.emit(True, "Database fix completed successfully!")
            
        except Exception as e:
            self.finished.emit(False, str(e))


class DatabaseFixDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Database Fix")
        self.setModal(True)
        self.resize(500, 200)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        # Title
        title = QLabel("🔧 Fixing Database...")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Status
        self.status_label = QLabel("Starting...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        # Button
        self.btn_close = QPushButton("Close")
        self.btn_close.setEnabled(False)
        self.btn_close.clicked.connect(self.accept)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        # Start worker
        self.worker = DatabaseFixWorker()
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()
    
    def update_progress(self, value, status):
        self.progress_bar.setValue(value)
        self.status_label.setText(status)
    
    def on_finished(self, success, message):
        self.btn_close.setEnabled(True)
        if success:
            self.status_label.setText("✅ " + message)
        else:
            self.status_label.setText("❌ " + message)