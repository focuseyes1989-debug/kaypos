from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QVBoxLayout,
)

from ui.widgets.numeric_keypad_dialog import NumericKeypadDialog
from ui.widgets.dialog_backdrop import exec_with_blurred_backdrop
from ui.themes.theme_manager import get_theme_colors, get_icon_with_color


class ServicePriceDialog(NumericKeypadDialog):
    DIGIT_KEY_HEIGHT = 92
    CLEAR_KEY_HEIGHT = 72
    ACTION_KEY_HEIGHT = 72
    DISPLAY_HEIGHT = 62
    DIALOG_HEIGHT = 880

    def __init__(self, product_name, parent=None):
        self._configure_metrics(parent)
        super().__init__(product_name, parent=parent, decimals=2)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(420, self.DIALOG_HEIGHT)

    def _configure_metrics(self, parent):
        parent_height = 0
        if parent is not None:
            window = parent.window()
            parent_height = max(parent.height(), window.height())
        if parent_height and parent_height < 760:
            self.DIGIT_KEY_HEIGHT = 58
            self.CLEAR_KEY_HEIGHT = 54
            self.ACTION_KEY_HEIGHT = 54
            self.DISPLAY_HEIGHT = 52
            self.DIALOG_HEIGHT = max(600, parent_height - 40)
        elif parent_height and parent_height < 860:
            self.DIGIT_KEY_HEIGHT = 72
            self.CLEAR_KEY_HEIGHT = 60
            self.ACTION_KEY_HEIGHT = 60
            self.DISPLAY_HEIGHT = 58
            self.DIALOG_HEIGHT = max(620, parent_height - 40)

    def _setup_ui(self, title, value):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)
        header.setContentsMargins(0, 0, 0, 0)
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        header_text.setContentsMargins(0, 0, 0, 0)
        name = QLabel(title)
        name.setObjectName("titleLabel")
        name.setWordWrap(True)
        name.setToolTip(title)
        name.setFixedHeight(22)
        name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        subtitle = QLabel("Enter service price")
        subtitle.setObjectName("subtitleLabel")
        subtitle.setFixedHeight(18)
        subtitle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header_text.addWidget(name)
        header_text.addWidget(subtitle)
        header.addLayout(header_text, 1)
        close = QPushButton()
        close.setObjectName("closeKey")
        close.setIcon(get_icon_with_color("close", get_theme_colors()["text"], (20, 20)))
        close.setToolTip("Close")
        close.setFixedSize(38, 38)
        close.clicked.connect(self.reject)
        header.addWidget(close)
        layout.addLayout(header)

        divider = QFrame()
        divider.setObjectName("headerDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFixedHeight(1)
        layout.addWidget(divider)

        price_label = QLabel("Price")
        price_label.setObjectName("fieldLabel")
        price_label.setFixedHeight(20)
        layout.addWidget(price_label)

        self.display = QLineEdit("0")
        self.display.setReadOnly(True)
        self.display.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.display.setFixedHeight(self.DISPLAY_HEIGHT)
        layout.addWidget(self.display)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "00", "0", "\u232b"]
        for index, key in enumerate(keys):
            button = QPushButton(key)
            button.setObjectName("digitKey")
            button.setFixedHeight(self.DIGIT_KEY_HEIGHT)
            button.setMinimumHeight(self.DIGIT_KEY_HEIGHT)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda checked=False, value=key: self._handle_key(value))
            grid.addWidget(button, index // 3, index % 3)
        for row in range(4):
            grid.setRowMinimumHeight(row, self.DIGIT_KEY_HEIGHT)
        layout.addLayout(grid)

        clear = QPushButton("Clear")
        clear.setObjectName("clearKey")
        clear.setFixedHeight(self.CLEAR_KEY_HEIGHT)
        clear.clicked.connect(lambda: self._handle_key("C"))
        layout.addWidget(clear)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("cancelKey")
        cancel.clicked.connect(self.reject)
        add = QPushButton("Add")
        add.setObjectName("addKey")
        add.clicked.connect(lambda: self._handle_key("OK"))
        for button in (cancel, add):
            button.setFixedHeight(self.ACTION_KEY_HEIGHT)
            actions.addWidget(button)
        layout.addLayout(actions)

    def _apply_theme(self):
        colors = get_theme_colors()
        surface = colors.get("card_bg", "#ffffff")
        border = colors.get("border", "#d9e1ee")
        text = colors.get("text", "#111827")
        muted = colors.get("text_secondary", "#667085")
        hover = colors.get("bg_hover", "#f3f6fb")
        self.setStyleSheet(f"""
            QDialog {{
                background: {surface};
                border: 1px solid {border};
                border-radius: 14px;
            }}
            QLabel {{
                color: {text};
                background: transparent;
                font-family: 'Segoe UI', 'Myanmar Text', 'Pyidaungsu', 'Noto Sans Myanmar';
                font-size: 14px;
            }}
            QLabel#titleLabel {{
                font-size: 17px;
                font-weight: 800;
            }}
            QLabel#subtitleLabel, QLabel#fieldLabel {{
                color: {muted};
                font-size: 14px;
            }}
            QFrame#headerDivider {{
                background: {border};
                border: none;
            }}
            QLineEdit {{
                background: {surface};
                color: {text};
                border: 2px solid {text};
                border-radius: 9px;
                padding: 4px 10px;
                font-size: 28px;
                font-weight: 500;
            }}
            QPushButton {{
                background: {surface};
                color: {text};
                border: 1px solid {border};
                border-radius: 9px;
                font-size: 16px;
                font-weight: 600;
                min-width: 0;
                padding: 0 12px;
                text-align: center;
            }}
            QPushButton:hover {{
                background: {hover};
                border-color: #9aa8c7;
            }}
            QPushButton#closeKey {{
                border-radius: 10px;
            }}
            QPushButton#digitKey {{
                min-height: {self.DIGIT_KEY_HEIGHT - 2}px;
                max-height: {self.DIGIT_KEY_HEIGHT - 2}px;
                font-size: 20px;
                font-weight: 700;
            }}
            QPushButton#clearKey {{
                min-height: {self.CLEAR_KEY_HEIGHT - 2}px;
                max-height: {self.CLEAR_KEY_HEIGHT - 2}px;
                color: #dc2626;
                font-size: 16px;
            }}
            QPushButton#cancelKey {{
                min-height: {self.ACTION_KEY_HEIGHT - 2}px;
                max-height: {self.ACTION_KEY_HEIGHT - 2}px;
                font-size: 16px;
                font-weight: 500;
            }}
            QPushButton#addKey {{
                min-height: {self.ACTION_KEY_HEIGHT}px;
                max-height: {self.ACTION_KEY_HEIGHT}px;
                background: #2563eb;
                color: white;
                border: none;
                font-weight: 700;
            }}
            QPushButton#addKey:hover {{ background: #1d4ed8; }}
        """)

    def exec(self):
        return exec_with_blurred_backdrop(self)
