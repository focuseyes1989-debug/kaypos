from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QDialog, QGraphicsBlurEffect, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout,
)

from ui.widgets.numeric_keypad_dialog import NumericKeypadDialog
from ui.themes.theme_manager import get_theme_colors, get_icon_with_color


class ServicePriceDialog(NumericKeypadDialog):
    def __init__(self, product_name, parent=None):
        super().__init__(product_name, parent=parent, decimals=2)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(340, 470)

    def _setup_ui(self, title, value):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        header = QHBoxLayout()
        name = QLabel(title)
        name.setWordWrap(True)
        name.setToolTip(title)
        name.setStyleSheet("font-weight: 600;")
        header.addWidget(name, 1)
        close = QPushButton()
        close.setIcon(get_icon_with_color("close", get_theme_colors()["text"], (16, 16)))
        close.setToolTip("Close")
        close.setFixedSize(36, 36)
        close.clicked.connect(self.reject)
        header.addWidget(close)
        layout.addLayout(header)
        self.display = QLineEdit("0")
        self.display.setReadOnly(True)
        self.display.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.display.setFixedHeight(46)
        layout.addWidget(self.display)
        grid = QGridLayout()
        grid.setSpacing(8)
        keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "00", "0", "\u232b"]
        for index, key in enumerate(keys):
            button = QPushButton(key)
            button.setFixedHeight(52)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda checked=False, value=key: self._handle_key(value))
            grid.addWidget(button, index // 3, index % 3)
        layout.addLayout(grid)
        utilities = QHBoxLayout()
        decimal = QPushButton(".")
        decimal.setFixedHeight(38)
        decimal.clicked.connect(lambda: self._handle_key("."))
        clear = QPushButton("Clear")
        clear.setObjectName("clearKey")
        clear.setFixedHeight(38)
        clear.clicked.connect(lambda: self._handle_key("C"))
        utilities.addWidget(decimal, 1)
        utilities.addWidget(clear, 2)
        layout.addLayout(utilities)
        actions = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        add = QPushButton("Add")
        add.setObjectName("addKey")
        add.clicked.connect(lambda: self._handle_key("OK"))
        for button in (cancel, add):
            button.setFixedHeight(44)
            actions.addWidget(button)
        layout.addLayout(actions)

    def _apply_theme(self):
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QDialog {{ background: {colors['card_bg']}; border: 1px solid {colors['border']}; }}
            QLabel {{ color: {colors['text']}; background: transparent; font-family: 'Segoe UI'; font-size: 13px; }}
            QLineEdit {{ background: {colors['card_bg']}; color: {colors['text']};
                border: 2px solid {colors['text']}; border-radius: 8px; padding: 4px 10px; font-size: 22px; }}
            QPushButton {{ background: {colors['card_bg']}; color: {colors['text']};
                border: 1px solid {colors['border']}; border-radius: 8px; font-size: 14px; min-width: 0; padding: 0; }}
            QPushButton:hover {{ background: {colors['bg_hover']}; }}
            QPushButton#addKey {{ background: #2563eb; color: white; border: none; }}
            QPushButton#addKey:hover {{ background: #1d4ed8; }}
            QPushButton#clearKey {{ color: #dc3545; }}
        """)

    def exec(self):
        window = self.parentWidget().window() if self.parentWidget() else None
        overlay = None
        try:
            if window and window.isVisible():
                snapshot = window.grab()
                painter = QPainter(snapshot)
                painter.fillRect(snapshot.rect(), QColor(0, 0, 0, 85))
                painter.end()
                overlay = QLabel(window)
                overlay.setPixmap(snapshot)
                overlay.setScaledContents(True)
                overlay.setGeometry(window.rect())
                blur = QGraphicsBlurEffect(overlay)
                blur.setBlurRadius(10)
                overlay.setGraphicsEffect(blur)
                overlay.show()
                overlay.raise_()
                self.move(window.mapToGlobal(window.rect().center()) - self.rect().center())
            return QDialog.exec(self)
        finally:
            if overlay:
                overlay.hide()
                overlay.deleteLater()
