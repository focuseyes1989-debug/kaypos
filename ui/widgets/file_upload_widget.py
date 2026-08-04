# ui/widgets/file_upload_widget.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QHBoxLayout, QListWidget, QListWidgetItem, QProgressBar
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QDragEnterEvent, QDropEvent


class FileUploadWidget(QWidget):
    """Drag & Drop ဖိုင်တင်ရန် Widget"""
    
    files_uploaded = pyqtSignal(list)  # ဖိုင်လမ်းကြောင်းစာရင်း
    
    def __init__(self, accept_types="All Files (*.*)", max_files=10, parent=None):
        super().__init__(parent)
        self.accept_types = accept_types
        self.max_files = max_files
        self.files = []
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        # Drop zone
        self.drop_zone = QLabel()
        self.drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_zone.setMinimumHeight(150)
        self.drop_zone.setStyleSheet("""
            QLabel {
                border: 2px dashed #ced4da;
                border-radius: 8px;
                background-color: #f8f9fa;
                padding: 20px;
                font-size: 14px;
                color: #6c757d;
            }
            QLabel:hover {
                border-color: #5865f2;
                background-color: #f1f3f5;
            }
        """)
        self.drop_zone.setText("📁\nDrag & drop files here\nor click to browse")
        self.drop_zone.setWordWrap(True)
        self.drop_zone.mousePressEvent = self._browse_files
        self.setAcceptDrops(True)
        layout.addWidget(self.drop_zone)
        
        # File list
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(100)
        self.file_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        layout.addWidget(self.file_list)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ced4da;
                border-radius: 4px;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #5865f2;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        self.btn_browse = QPushButton("📁 Browse Files")
        self.btn_browse.setStyleSheet("""
            QPushButton {
                background-color: #5865f2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #4752c4;
            }
        """)
        self.btn_browse.clicked.connect(self._browse_files)
        btn_layout.addWidget(self.btn_browse)
        
        self.btn_clear = QPushButton("🗑️ Clear All")
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.btn_clear.clicked.connect(self.clear_files)
        btn_layout.addWidget(self.btn_clear)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Drag enter event handler"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            
    def dropEvent(self, event: QDropEvent):
        """Drop event handler"""
        files = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path:
                files.append(file_path)
        if files:
            self.add_files(files)
            
    def _browse_files(self, event=None):
        """ဖိုင်ရွေးချယ်ရန် dialog ဖွင့်ရန်"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, 
            "Select Files",
            "",
            self.accept_types
        )
        if file_paths:
            self.add_files(file_paths)
            
    def add_files(self, file_paths):
        """ဖိုင်များကို စာရင်းထဲထည့်ရန်"""
        remaining = self.max_files - len(self.files)
        if remaining <= 0:
            return
            
        added = 0
        for file_path in file_paths[:remaining]:
            if file_path not in self.files:
                self.files.append(file_path)
                self.file_list.addItem(QListWidgetItem(file_path))
                added += 1
                
        if added > 0:
            self.files_uploaded.emit(self.files)
            self._update_drop_zone()
            
    def clear_files(self):
        """ဖိုင်အားလုံးကို ရှင်းရန်"""
        self.files.clear()
        self.file_list.clear()
        self.progress_bar.setVisible(False)
        self._update_drop_zone()
        
    def remove_file(self, index):
        """ဖိုင်တစ်ခုကို ဖယ်ရှားရန်"""
        if 0 <= index < len(self.files):
            self.files.pop(index)
            self.file_list.takeItem(index)
            self.files_uploaded.emit(self.files)
            self._update_drop_zone()
            
    def _update_drop_zone(self):
        """Drop zone ကို update လုပ်ရန်"""
        if len(self.files) >= self.max_files:
            self.drop_zone.setText(f"📁\nMax files reached ({self.max_files})")
            self.drop_zone.setStyleSheet("""
                QLabel {
                    border: 2px dashed #e74c3c;
                    border-radius: 8px;
                    background-color: #fdf2f2;
                    padding: 20px;
                    font-size: 14px;
                    color: #e74c3c;
                }
            """)
        else:
            self.drop_zone.setText(f"📁\nDrag & drop files here\nor click to browse\n({len(self.files)}/{self.max_files})")
            self.drop_zone.setStyleSheet("""
                QLabel {
                    border: 2px dashed #ced4da;
                    border-radius: 8px;
                    background-color: #f8f9fa;
                    padding: 20px;
                    font-size: 14px;
                    color: #6c757d;
                }
                QLabel:hover {
                    border-color: #5865f2;
                    background-color: #f1f3f5;
                }
            """)
            
    def get_files(self):
        """ဖိုင်လမ်းကြောင်းစာရင်းကို ပြန်ရယူရန်"""
        return self.files.copy()
        
    def retranslateUi(self, lang_code):
        """ဘာသာပြန်ရန်"""
        if lang_code == "my":
            self.drop_zone.setText(f"📁\nဖိုင်များကို ဆွဲချပါ\nသို့မဟုတ် နှိပ်၍ ရွေးပါ\n({len(self.files)}/{self.max_files})")
            self.btn_browse.setText("📁 ဖိုင်ရွေးရန်")
            self.btn_clear.setText("🗑️ အားလုံးရှင်း")
        else:
            self._update_drop_zone()
            self.btn_browse.setText("📁 Browse Files")
            self.btn_clear.setText("🗑️ Clear All")