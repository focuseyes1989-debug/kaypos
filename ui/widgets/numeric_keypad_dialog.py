from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator, QKeyEvent
from PyQt6.QtWidgets import QDialog, QGridLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QVBoxLayout

from ui.themes.theme_manager import get_icon_with_color, get_theme_colors, is_dark_theme


class NumericKeypadDialog(QDialog):
    """Touch-friendly numeric keypad for amount and quantity inputs."""

    def __init__(
        self,
        title: str,
        value: float | int = 0,
        parent=None,
        *,
        decimals: int = 0,
        minimum: float = 0,
        maximum: float = 999999999,
    ):
        super().__init__(parent)
        title_key = str(title or "").strip().lower()
        force_integer = title_key in {"quantity", "received amount", "received"}
        self.decimals = 0 if force_integer else max(0, int(decimals))
        self._show_decimal_key = self.decimals > 0
        self.minimum = float(minimum)
        self.maximum = float(maximum)
        self._value = float(value or 0)

        self.setWindowTitle(title)
        self.setModal(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(400, 575)
        self._setup_ui(title, value)
        self._apply_theme()
        self.setFocus()

    def value(self) -> float:
        text = self.display.text().replace(",", "").strip()
        if not text or text == ".":
            return self.minimum
        try:
            value = float(text)
        except ValueError:
            value = self.minimum
        return max(self.minimum, min(self.maximum, value))

    def _setup_ui(self, title: str, value: float | int) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 8, 18, 12)
        layout.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFixedHeight(24)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.title_label)

        self.display = QLineEdit(self._format_initial_value(value))
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.display.setFixedHeight(54)
        self.display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.display.setReadOnly(True)
        self.display.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.display)

        grid = QGridLayout()
        grid.setSpacing(8)
        buttons = [
            ("7", 0, 0), ("8", 0, 1), ("9", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("1", 2, 0), ("2", 2, 1), ("3", 2, 2),
            ("00", 3, 0), ("0", 3, 1), ("⌫", 3, 2),
        ]
        if self._show_decimal_key:
            buttons.append((".", 4, 0))
            buttons.append(("C", 4, 1))
            buttons.append(("OK", 4, 2))
        else:
            buttons.append(("C", 4, 0))
            buttons.append(("OK", 4, 1))

        for text, row, col in buttons:
            button = QPushButton(text)
            if text == "OK":
                button.setObjectName("ok_key")
            if text == "OK" and not self._show_decimal_key:
                button.setFixedSize(232, 82)
            else:
                button.setFixedSize(112, 82)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda _checked=False, key=text: self._handle_key(key))
            grid.addWidget(button, row, col, 1, 2 if text == "OK" and self.decimals == 0 else 1)
        layout.addLayout(grid, stretch=0)

    def _format_initial_value(self, value: float | int) -> str:
        number = float(value or 0)
        if self.decimals <= 0:
            return str(int(round(number)))
        return f"{number:.{self.decimals}f}".rstrip("0").rstrip(".") or "0"

    def _backspace(self) -> None:
        text = self.display.text()
        self.display.setText(text[:-1] if len(text) > 1 else "0")

    def _handle_key(self, key: str) -> None:
        if key == "OK":
            self._value = self.value()
            self.accept()
            return
        if key == "C":
            self.display.setText("0")
            return
        if key == "⌫":
            text = self.display.text()
            self.display.setText(text[:-1] if len(text) > 1 else "0")
            return
        if key == "." and (not self._show_decimal_key or "." in self.display.text()):
            return

        text = self.display.text()
        if text == "0" and key != ".":
            text = ""
        candidate = f"{text}{key}"
        if "." in candidate:
            _, fraction = candidate.split(".", 1)
            if len(fraction) > self.decimals:
                return
        try:
            if float(candidate or 0) > self.maximum:
                return
        except ValueError:
            return
        self.display.setText(candidate)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        text = event.text()

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._handle_key("OK")
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            self.reject()
            event.accept()
            return
        if key == Qt.Key.Key_Backspace:
            self._backspace()
            event.accept()
            return
        if key == Qt.Key.Key_Delete:
            self._handle_key("C")
            event.accept()
            return
        if text in {"c", "C"}:
            self._handle_key("C")
            event.accept()
            return
        if text.isdigit():
            self._handle_key(text)
            event.accept()
            return
        if text in {".", ","}:
            self._handle_key(".")
            event.accept()
            return

        super().keyPressEvent(event)

    def _apply_theme(self) -> None:
        colors = get_theme_colors()
        dark = is_dark_theme()
        bg = colors.get("card_bg", "#ffffff")
        text = colors.get("text", "#212529")
        border = colors.get("border", "#d0d3d9")
        hover = colors.get("bg_hover", "#eef0ff")
        accent = colors.get("border_hover", "#5865f2")
        button_bg = "#40444b" if dark else "#f1f3f5"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
            }}
            QLabel {{
                color: {text};
                background: transparent;
                font-size: 15px;
                font-weight: 600;
            }}
            QLineEdit {{
                background-color: {bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 26px;
                font-weight: 700;
            }}
            QPushButton {{
                background-color: {button_bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 8px;
                font-size: 21px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {hover};
                border-color: {accent};
            }}
            QPushButton:pressed {{
                background-color: {accent};
                color: white;
            }}
            QPushButton#ok_key {{
                background-color: #2f9e44;
                color: white;
                border-color: #2b8a3e;
            }}
            QPushButton#ok_key:hover {{
                background-color: #37b24d;
                border-color: #2f9e44;
            }}
            QPushButton#ok_key:pressed {{
                background-color: #2b8a3e;
                color: white;
            }}
        """)


def get_numeric_keypad_value(
    parent,
    title: str,
    value: float | int = 0,
    *,
    decimals: int = 0,
    minimum: float = 0,
    maximum: float = 999999999,
) -> tuple[float, bool]:
    dialog = NumericKeypadDialog(
        title,
        value,
        parent,
        decimals=decimals,
        minimum=minimum,
        maximum=maximum,
    )
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.value(), True
    return float(value or 0), False


class NumericInputDialog(QDialog):
    """Keyboard-friendly numeric input with an optional touch keypad."""

    def __init__(
        self,
        title: str,
        label: str,
        value: float | int = 0,
        parent=None,
        *,
        decimals: int = 0,
        minimum: float = 0,
        maximum: float = 999999999,
    ):
        super().__init__(parent)
        self.decimals = max(0, int(decimals))
        self.minimum = float(minimum)
        self.maximum = float(maximum)

        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(360, 180)
        self._setup_ui(label, value)
        self._apply_theme()

    def value(self) -> float:
        text = self.input.text().replace(",", "").strip()
        if not text or text == ".":
            return self.minimum
        try:
            value = float(text)
        except ValueError:
            value = self.minimum
        return max(self.minimum, min(self.maximum, value))

    def _setup_ui(self, label: str, value: float | int) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        self.label = QLabel(label)
        layout.addWidget(self.label)

        validator = QDoubleValidator(self.minimum, self.maximum, self.decimals, self)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)

        self.input = QLineEdit(self._format_value(value))
        self.input.setValidator(validator)
        self.input.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.input.setFixedHeight(44)
        self.input.returnPressed.connect(self.accept)
        self.input.selectAll()
        layout.addWidget(self.input)

        self.keypad_action = self.input.addAction(
            get_icon_with_color("keyboard", get_theme_colors().get("text_secondary", "#6c757d"), (18, 18)),
            QLineEdit.ActionPosition.TrailingPosition,
        )
        self.keypad_action.triggered.connect(self._open_keypad)

        self.ok_button = QPushButton("OK")
        self.ok_button.setFixedHeight(36)
        self.ok_button.clicked.connect(self.accept)
        layout.addWidget(self.ok_button)

    def _format_value(self, value: float | int) -> str:
        number = float(value or 0)
        if self.decimals <= 0:
            return str(int(round(number)))
        return f"{number:.{self.decimals}f}".rstrip("0").rstrip(".") or "0"

    def _open_keypad(self) -> None:
        dialog = NumericKeypadDialog(
            self.windowTitle(),
            self.value(),
            self,
            decimals=self.decimals,
            minimum=self.minimum,
            maximum=self.maximum,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.input.setText(self._format_value(dialog.value()))
            self.input.setFocus()
            self.input.selectAll()

    def _apply_theme(self) -> None:
        colors = get_theme_colors()
        dark = is_dark_theme()
        bg = colors.get("card_bg", "#ffffff")
        text = colors.get("text", "#212529")
        secondary = colors.get("text_secondary", "#6c757d")
        border = colors.get("input_border", colors.get("border", "#d0d3d9"))
        focus = colors.get("border_hover", "#5865f2")
        button_bg = "#40444b" if dark else "#f1f3f5"

        self.keypad_action.setIcon(get_icon_with_color("keyboard", secondary, (18, 18)))
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
            }}
            QLabel {{
                color: {text};
                background: transparent;
                font-size: 13px;
                font-weight: 600;
            }}
            QLineEdit {{
                background-color: {bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 6px 28px 6px 10px;
                font-size: 17pt;
                font-weight: 700;
            }}
            QLineEdit:focus {{
                border: 1px solid {focus};
            }}
            QPushButton {{
                background-color: {button_bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                border-color: {focus};
            }}
            QPushButton:pressed {{
                background-color: {focus};
                color: white;
            }}
        """)


def get_numeric_input_value(
    parent,
    title: str,
    label: str,
    value: float | int = 0,
    *,
    decimals: int = 0,
    minimum: float = 0,
    maximum: float = 999999999,
) -> tuple[float, bool]:
    dialog = NumericKeypadDialog(
        title,
        value,
        parent,
        decimals=decimals,
        minimum=minimum,
        maximum=maximum,
    )
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.value(), True
    return float(value or 0), False
