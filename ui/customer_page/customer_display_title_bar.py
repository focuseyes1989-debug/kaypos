# ui/customer_page/customer_display_title_bar.py
from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from .customer_display_theme import get_display_palette


class TitleBar(QWidget):
    """Custom title bar for the customer display."""

    close_clicked = pyqtSignal()
    minimize_clicked = pyqtSignal()
    maximize_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.is_maximized = False
        self.dragging = False
        self.drag_position = QPoint()

        self.setFixedHeight(50)
        self.setup_ui()
        self.apply_theme_style()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 12, 0)
        layout.setSpacing(10)

        self.title_label = QLabel("Customer Display")
        layout.addWidget(self.title_label)

        self.version_badge = QLabel("LIVE SALE")
        layout.addWidget(self.version_badge)
        layout.addStretch()

        self.minimize_btn = QPushButton("-")
        self.minimize_btn.setObjectName("minimize_btn")
        self.minimize_btn.setFixedSize(30, 30)
        self.minimize_btn.clicked.connect(self.minimize_clicked.emit)
        layout.addWidget(self.minimize_btn)

        self.maximize_btn = QPushButton("[]")
        self.maximize_btn.setObjectName("maximize_btn")
        self.maximize_btn.setFixedSize(30, 30)
        self.maximize_btn.clicked.connect(self.toggle_maximize)
        layout.addWidget(self.maximize_btn)

        self.close_btn = QPushButton("x")
        self.close_btn.setObjectName("close_btn")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.clicked.connect(self.close_clicked.emit)
        layout.addWidget(self.close_btn)

    def apply_theme_style(self):
        colors = get_display_palette()
        self.setStyleSheet(f"""
            QWidget {{
                background: {colors['title_bar']};
                border: none;
                border-bottom: 1px solid {colors['title_border']};
            }}
            QPushButton {{
                background-color: transparent;
                color: {colors['muted']};
                border: none;
                padding: 5px 8px;
                font-size: 11pt;
                border-radius: 6px;
                font-weight: 800;
            }}
            QPushButton:hover {{
                background-color: {colors['title_hover']};
                color: {colors['title_text']};
            }}
            QPushButton#close_btn:hover {{
                background-color: {colors['danger']};
                color: #ffffff;
            }}
        """)
        self.title_label.setStyleSheet(f"""
            color: {colors['title_text']};
            font-size: 13pt;
            font-weight: 800;
            background: transparent;
            border: none;
        """)
        self.version_badge.setStyleSheet(f"""
            QLabel {{
                background: {colors['panel_soft']};
                color: {colors['accent']};
                padding: 4px 14px;
                border-radius: 14px;
                font-size: 8.5pt;
                font-weight: 800;
                border: 1px solid {colors['border']};
            }}
        """)

    def toggle_maximize(self):
        self.is_maximized = not self.is_maximized
        self.maximize_btn.setText("[]" if not self.is_maximized else "[ ]")
        self.maximize_clicked.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.parent_window:
            self.dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging and not self.is_maximized and self.parent_window:
            self.parent_window.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            event.accept()

    def retranslateUi(self):
        from utils.translations import tr
        self.title_label.setText(tr("customer_display"))
