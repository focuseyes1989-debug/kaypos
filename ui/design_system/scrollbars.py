"""Application-wide scrollbar styling, including legacy locally styled views."""

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtWidgets import QScrollBar

from ui.design_system.metrics import SCROLLBAR_WIDTH, SCROLLBAR_MIN_HANDLE


def scrollbar_stylesheet(colors):
    handle = colors['text_secondary']
    hover = colors['progress_bg']
    track = colors['bg']
    return f"""
        QScrollBar {{ background: {track}; border: none; padding: 0px; margin: 0px; }}
        QScrollBar:vertical {{ width: {SCROLLBAR_WIDTH}px; min-width: {SCROLLBAR_WIDTH}px; max-width: {SCROLLBAR_WIDTH}px; }}
        QScrollBar:horizontal {{ height: {SCROLLBAR_WIDTH}px; min-height: {SCROLLBAR_WIDTH}px; max-height: {SCROLLBAR_WIDTH}px; }}
        QScrollBar::handle {{ background: {handle}; border: none; border-radius: 4px; }}
        QScrollBar::handle:vertical {{ min-height: {SCROLLBAR_MIN_HANDLE}px; margin: 2px; }}
        QScrollBar::handle:horizontal {{ min-width: {SCROLLBAR_MIN_HANDLE}px; margin: 2px; }}
        QScrollBar::handle:hover, QScrollBar::handle:pressed {{ background: {hover}; }}
        QScrollBar::handle:disabled {{ background: {colors['border']}; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ width: 0px; height: 0px; border: none; background: transparent; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; border: none; }}
        QScrollBar::up-arrow, QScrollBar::down-arrow,
        QScrollBar::left-arrow, QScrollBar::right-arrow {{ image: none; width: 0px; height: 0px; }}
    """


class _ScrollbarStyleController(QObject):
    def __init__(self, app):
        super().__init__(app)
        self.stylesheet = ""
        self._applying = False
        app.installEventFilter(self)

    def apply(self, bar):
        if self._applying or bar.styleSheet() == self.stylesheet:
            return
        self._applying = True
        try:
            # A scrollbar-local rule wins over legacy styles on its ancestors.
            bar.setStyleSheet(self.stylesheet)
        finally:
            self._applying = False

    def eventFilter(self, obj, event):
        if isinstance(obj, QScrollBar) and event.type() in (
            QEvent.Type.Polish, QEvent.Type.Show, QEvent.Type.StyleChange,
        ):
            self.apply(obj)
        return False


def install_scrollbar_style(app, colors):
    controller = getattr(app, "_kay_scrollbar_styles", None)
    if controller is None:
        controller = _ScrollbarStyleController(app)
        app._kay_scrollbar_styles = controller
    controller.stylesheet = scrollbar_stylesheet(colors)
    for widget in app.allWidgets():
        if isinstance(widget, QScrollBar):
            controller.apply(widget)
