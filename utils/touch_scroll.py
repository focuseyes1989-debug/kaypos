"""Project-wide kinetic touch scrolling for item views."""

from PyQt6.QtCore import QObject, QEvent, QTimer, Qt
from PyQt6.QtWidgets import QApplication, QAbstractItemView, QScroller, QScrollerProperties


def enable_touch_scroll_for_view(view):
    """Enable finger/mouse drag scrolling for a table/list/tree view."""
    if not isinstance(view, QAbstractItemView):
        return
    if view.property("_zay_touch_scroll_enabled"):
        return

    view.setProperty("_zay_touch_scroll_enabled", True)
    view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    view.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)

    viewport = view.viewport()
    if viewport is None:
        return
    viewport.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)

    QScroller.grabGesture(viewport, QScroller.ScrollerGestureType.TouchGesture)
    QScroller.grabGesture(viewport, QScroller.ScrollerGestureType.LeftMouseButtonGesture)

    scroller = QScroller.scroller(viewport)
    properties = scroller.scrollerProperties()
    properties.setScrollMetric(
        QScrollerProperties.ScrollMetric.VerticalOvershootPolicy,
        QScrollerProperties.OvershootPolicy.OvershootAlwaysOff,
    )
    properties.setScrollMetric(
        QScrollerProperties.ScrollMetric.HorizontalOvershootPolicy,
        QScrollerProperties.OvershootPolicy.OvershootAlwaysOff,
    )
    properties.setScrollMetric(
        QScrollerProperties.ScrollMetric.FrameRate,
        QScrollerProperties.FrameRates.Fps60,
    )
    properties.setScrollMetric(QScrollerProperties.ScrollMetric.DragStartDistance, 0.006)
    properties.setScrollMetric(QScrollerProperties.ScrollMetric.DecelerationFactor, 0.08)
    properties.setScrollMetric(QScrollerProperties.ScrollMetric.MaximumClickThroughVelocity, 0.01)
    scroller.setScrollerProperties(properties)


class TouchScrollInstaller(QObject):
    """Apply touch scrolling to existing and newly-created item views."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app

    def apply_to_existing(self):
        for widget in self.app.allWidgets():
            self.apply_to_widget_tree(widget)

    def apply_to_widget_tree(self, widget):
        try:
            if isinstance(widget, QAbstractItemView):
                enable_touch_scroll_for_view(widget)
            for child in widget.findChildren(QAbstractItemView):
                enable_touch_scroll_for_view(child)
        except RuntimeError:
            pass

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.ChildAdded:
            child = event.child()
            QTimer.singleShot(0, lambda child=child: self.apply_to_widget_tree(child))
        return False


def install_global_touch_scrolling(app=None):
    """Install project-wide touch drag scrolling for tables/lists/tree views."""
    app = app or QApplication.instance()
    if app is None:
        return None

    installer = getattr(app, "_zay_touch_scroll_installer", None)
    if installer is not None:
        installer.apply_to_existing()
        return installer

    installer = TouchScrollInstaller(app)
    app._zay_touch_scroll_installer = installer
    app.installEventFilter(installer)
    QTimer.singleShot(0, installer.apply_to_existing)
    return installer
