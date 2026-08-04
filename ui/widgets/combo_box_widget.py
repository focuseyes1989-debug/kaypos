from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QComboBox, QCompleter, QLineEdit

from ui.themes.theme_manager import get_icon_with_color, get_theme_colors, is_dark_theme, theme_manager


class ComboBoxWidget(QComboBox):
    """Theme-aware searchable combo box.

    This intentionally subclasses QComboBox so existing app combo boxes can be
    replaced with minimal code changes while gaining search, clear, and modern
    dark/light styling.
    """

    def __init__(self, placeholder: str = "Select...", parent=None, searchable: bool = True):
        super().__init__(parent)
        self.placeholder = placeholder
        self.searchable = searchable
        self._clear_action: QAction | None = None
        self._user_filtering = False

        self.setEditable(searchable)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumHeight(36)

        if searchable:
            self._setup_line_edit()
            self._setup_completer()

        self.currentIndexChanged.connect(self._sync_selected_text)
        self.apply_theme()
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def addItem(self, text, userData=None):  # noqa: N802 - QComboBox API compatibility
        super().addItem(text, userData)
        self._refresh_completer()
        self._sync_selected_text()

    def addItems(self, texts):  # noqa: N802 - QComboBox API compatibility
        super().addItems(texts)
        self._refresh_completer()
        self._sync_selected_text()

    def clear(self):
        super().clear()
        self._refresh_completer()
        if self.lineEdit():
            self.lineEdit().clear()

    def clear_search(self) -> None:
        if self.lineEdit():
            self._user_filtering = True
            self.lineEdit().clear()
            self.lineEdit().setFocus()
        self.showPopup()

    def setCurrentText(self, text: str) -> None:  # noqa: N802
        index = self.findText(text)
        if index >= 0:
            self.setCurrentIndex(index)
        elif self.lineEdit():
            self.lineEdit().setText(text)
            self._show_clear_action(bool(text))
        else:
            super().setCurrentText(text)

    def focus_combo(self) -> None:
        if self.lineEdit():
            self.lineEdit().setFocus()
            self.lineEdit().selectAll()
        else:
            self.setFocus()

    def setPlaceholderText(self, text: str) -> None:  # noqa: N802
        self.placeholder = text
        if self.lineEdit():
            self.lineEdit().setPlaceholderText(text)

    def placeholderText(self) -> str:  # noqa: N802
        return self.placeholder

    def apply_theme(self) -> None:
        colors = get_theme_colors()
        dark = is_dark_theme()
        bg = colors.get("card_bg", "#ffffff")
        text = colors.get("text", "#212529")
        muted = colors.get("text_secondary", "#6c757d")
        border = colors.get("input_border", colors.get("border", "#ced4da"))
        focus = colors.get("border_hover", "#5865f2")
        hover = colors.get("bg_hover", "#eef0ff")
        selected = "#e7e9ff" if not dark else colors.get("bg_hover", "#40444b")
        disabled_bg = colors.get("bg_hover", bg)

        self.setStyleSheet(f"""
            QComboBox {{
                background-color: {bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 5px 24px 5px 8px;
                min-height: 24px;
                font-size: 13px;
            }}
            QComboBox:focus {{
                border: 1px solid {focus};
            }}
            QComboBox:hover {{
                border: 1px solid {focus};
            }}
            QComboBox:disabled {{
                background-color: {disabled_bg};
                color: {muted};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 26px;
                subcontrol-origin: padding;
                subcontrol-position: top right;
            }}
            QComboBox::down-arrow {{
                image: none;
                width: 0px;
                height: 0px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 4px 0px;
                outline: none;
                selection-background-color: {selected};
                selection-color: {text};
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 30px;
                padding: 6px 10px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {hover};
            }}
            QLineEdit {{
                background: transparent;
                border: none;
                color: {text};
                padding: 0px 2px;
                selection-background-color: {focus};
                selection-color: #ffffff;
            }}
            QLineEdit::placeholder {{
                color: {muted};
            }}
        """)

        if self.searchable and self.lineEdit():
            search_icon = get_icon_with_color("search", muted, (16, 16))
            clear_icon = get_icon_with_color("close", muted, (14, 14))
            if self.lineEdit().actions():
                self.lineEdit().actions()[0].setIcon(search_icon)
            if self._clear_action:
                self._clear_action.setIcon(clear_icon)

    def showPopup(self):  # noqa: N802
        if self.searchable and self.lineEdit():
            self._refresh_completer()
            if self._user_filtering:
                completer = self.completer()
                if completer:
                    completer.complete()
                return
        super().showPopup()

    def eventFilter(self, obj, event):
        if self.searchable and obj == self.lineEdit():
            if event.type() == QEvent.Type.FocusIn:
                self.apply_theme()
                QTimer.singleShot(0, self.showPopup)
            elif event.type() == QEvent.Type.FocusOut:
                self._user_filtering = False
                self._sync_selected_text()
                self.apply_theme()
            elif event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self.hidePopup()
                return True
        return super().eventFilter(obj, event)

    def _setup_line_edit(self) -> None:
        edit = QLineEdit(self)
        edit.setPlaceholderText(self.placeholder)
        self.setLineEdit(edit)
        edit.installEventFilter(self)

        search_icon = get_icon_with_color("search", get_theme_colors().get("text_secondary", "#6c757d"), (16, 16))
        clear_icon = get_icon_with_color("close", get_theme_colors().get("text_secondary", "#6c757d"), (14, 14))
        edit.addAction(search_icon, QLineEdit.ActionPosition.LeadingPosition)
        self._clear_action = edit.addAction(clear_icon, QLineEdit.ActionPosition.TrailingPosition)
        self._clear_action.triggered.connect(self.clear_search)
        self._clear_action.setVisible(False)
        edit.textEdited.connect(self._on_text_edited)

    def _setup_completer(self) -> None:
        completer = QCompleter(self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(completer)
        self._refresh_completer()

    def _refresh_completer(self) -> None:
        if not self.searchable or not self.completer():
            return
        self.completer().setModel(self.model())
        popup = self.completer().popup()
        if popup:
            popup.setStyleSheet(self.view().styleSheet())

    def _on_text_edited(self, text: str) -> None:
        self._user_filtering = True
        self._show_clear_action(bool(text))
        self.hidePopup()
        completer = self.completer()
        if completer:
            completer.setCompletionPrefix(text)
            completer.complete()

    def _show_clear_action(self, visible: bool) -> None:
        if self._clear_action:
            self._clear_action.setVisible(visible and self._user_filtering)

    def _sync_selected_text(self, *_args) -> None:
        if not self.searchable or not self.lineEdit() or self._user_filtering:
            return
        edit = self.lineEdit()
        edit.blockSignals(True)
        edit.setText(self.currentText())
        edit.setCursorPosition(0)
        edit.deselect()
        edit.blockSignals(False)
        self._show_clear_action(False)

    def _on_theme_changed(self, _theme_name: str) -> None:
        self.apply_theme()


ModernComboBoxWidget = ComboBoxWidget
