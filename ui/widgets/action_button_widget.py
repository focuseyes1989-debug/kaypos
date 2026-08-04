# ui/widgets/action_button_widget.py
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QVBoxLayout
from PyQt6.QtCore import pyqtSignal


class ActionButtonWidget(QWidget):
    """Reusable action buttons with consistent styling"""
    
    add_clicked = pyqtSignal()
    edit_clicked = pyqtSignal()
    delete_clicked = pyqtSignal()
    refresh_clicked = pyqtSignal()
    
    def __init__(self, show_add=True, show_edit=True, show_delete=True, 
                 show_refresh=True, parent=None):
        super().__init__(parent)
        self.show_add = show_add
        self.show_edit = show_edit
        self.show_delete = show_delete
        self.show_refresh = show_refresh
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Add button
        if self.show_add:
            self.btn_add = QPushButton("➕ Add")
            self.btn_add.setStyleSheet(self._button_style("#2ecc71", "#27ae60"))
            self.btn_add.clicked.connect(self.add_clicked.emit)
            layout.addWidget(self.btn_add)
        
        # Edit button
        if self.show_edit:
            self.btn_edit = QPushButton("✏️ Edit")
            self.btn_edit.setStyleSheet(self._button_style("#3498db", "#2980b9"))
            self.btn_edit.clicked.connect(self.edit_clicked.emit)
            layout.addWidget(self.btn_edit)
        
        # Delete button
        if self.show_delete:
            self.btn_delete = QPushButton("🗑️ Delete")
            self.btn_delete.setStyleSheet(self._button_style("#e74c3c", "#c0392b"))
            self.btn_delete.clicked.connect(self.delete_clicked.emit)
            layout.addWidget(self.btn_delete)
        
        # Refresh button
        if self.show_refresh:
            self.btn_refresh = QPushButton("🔄 Refresh")
            self.btn_refresh.setStyleSheet(self._button_style("#95a5a6", "#7f8c8d"))
            self.btn_refresh.clicked.connect(self.refresh_clicked.emit)
            layout.addWidget(self.btn_refresh)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def _button_style(self, bg_color, hover_color):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
        """
    
    def set_add_enabled(self, enabled):
        if hasattr(self, 'btn_add'):
            self.btn_add.setEnabled(enabled)
    
    def set_edit_enabled(self, enabled):
        if hasattr(self, 'btn_edit'):
            self.btn_edit.setEnabled(enabled)
    
    def set_delete_enabled(self, enabled):
        if hasattr(self, 'btn_delete'):
            self.btn_delete.setEnabled(enabled)
    
    def retranslateUi(self, lang_code):
        """Update language"""
        if lang_code == "my":
            if hasattr(self, 'btn_add'):
                self.btn_add.setText("➕ အသစ်")
            if hasattr(self, 'btn_edit'):
                self.btn_edit.setText("✏️ ပြင်ဆင်")
            if hasattr(self, 'btn_delete'):
                self.btn_delete.setText("🗑️ ဖျက်")
            if hasattr(self, 'btn_refresh'):
                self.btn_refresh.setText("🔄 ပြန်လည်")
        else:
            if hasattr(self, 'btn_add'):
                self.btn_add.setText("➕ Add")
            if hasattr(self, 'btn_edit'):
                self.btn_edit.setText("✏️ Edit")
            if hasattr(self, 'btn_delete'):
                self.btn_delete.setText("🗑️ Delete")
            if hasattr(self, 'btn_refresh'):
                self.btn_refresh.setText("🔄 Refresh")