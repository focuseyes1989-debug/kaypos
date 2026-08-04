"""
Reusable loading overlay for long UI actions.
"""

from typing import Optional

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from ui.themes.theme_manager import get_theme_colors, is_dark_theme


class LoadingOverlay(QWidget):
    """Centered progress overlay that also manages the wait cursor it starts."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._cursor_active = False
        self.setObjectName("globalLoadingOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self._setup_ui()
        self.hide()

        if parent:
            parent.installEventFilter(self)
            self._sync_geometry()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()

        self.card = QFrame(self)
        self.card.setObjectName("loadingOverlayCard")
        self.card.setFixedWidth(360)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(14)

        self.message_label = QLabel("Loading...")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)

        card_layout.addWidget(self.message_label)
        card_layout.addWidget(self.progress_bar)

        layout.addWidget(self.card, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()

    def eventFilter(self, watched, event):
        if watched is self.parent() and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self._sync_geometry()
        return super().eventFilter(watched, event)

    def _sync_geometry(self) -> None:
        parent = self.parentWidget()
        if parent:
            self.setGeometry(parent.rect())

    def _apply_theme(self) -> None:
        colors = get_theme_colors()
        overlay_bg = "rgba(15, 23, 42, 95)" if is_dark_theme() else "rgba(15, 23, 42, 45)"
        progress_track = colors.get("bg_hover", colors.get("input_border", "#e9ecef"))
        self.setStyleSheet(f"""
            QWidget#globalLoadingOverlay {{
                background-color: {overlay_bg};
            }}
            QFrame#loadingOverlayCard {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
            }}
            QLabel {{
                color: {colors['text']};
                font-size: 11pt;
                font-weight: 600;
                background: transparent;
            }}
            QProgressBar {{
                background-color: {progress_track};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {colors['progress_bg']};
                border-radius: 4px;
            }}
        """)

    def show_loading(self, message: str = "Loading...", progress: Optional[int] = None) -> None:
        self._sync_geometry()
        self._apply_theme()
        self.message_label.setText(message)
        self.update_progress(progress)
        self.show()
        self.raise_()

        app = QApplication.instance()
        if app and not self._cursor_active:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self._cursor_active = True
        if app:
            app.processEvents()

    def update_loading(self, message: Optional[str] = None, progress: Optional[int] = None) -> None:
        if message:
            self.message_label.setText(message)
        self.update_progress(progress)
        app = QApplication.instance()
        if app:
            app.processEvents()

    def update_progress(self, progress: Optional[int]) -> None:
        if progress is None:
            self.progress_bar.setRange(0, 0)
            return

        value = max(0, min(100, int(progress)))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(value)

    def hide_loading(self) -> None:
        self.hide()
        app = QApplication.instance()
        if app and self._cursor_active:
            QApplication.restoreOverrideCursor()
            self._cursor_active = False
        if app:
            app.processEvents()
