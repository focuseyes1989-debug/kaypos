"""A compact toolbar layout that wraps controls without hiding actions."""

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtWidgets import QLayout


class WrappingToolbar(QLayout):
    def __init__(self, parent=None, minimum_item_width=None):
        super().__init__(parent)
        self._items = []
        self.minimum_item_width = minimum_item_width
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(8)

    def addItem(self, item):
        self._items.append(item)

    def addWidget(self, widget, stretch=0, alignment=Qt.AlignmentFlag(0)):
        super().addWidget(widget)

    def addStretch(self, stretch=0):
        # Rows already reserve all remaining space after their last control.
        pass

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QRect(0, 0, width, 0), False)

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            if not item.isEmpty():
                size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def sizeHint(self):
        return self.minimumSize()

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, True)

    def _arrange(self, rect, apply):
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y, row_height = area.x(), area.y(), 0
        uniform_width = None
        if self.minimum_item_width:
            columns = max(1, (area.width() + self.spacing()) // (self.minimum_item_width + self.spacing()))
            uniform_width = (area.width() - (columns - 1) * self.spacing()) // columns
        for item in self._items:
            if item.isEmpty():
                continue
            size = item.sizeHint().expandedTo(item.minimumSize())
            width = max(item.minimumSize().width(), min(uniform_width or size.width(), area.width()))
            if x > area.x() and x + width > area.right() + 1:
                x = area.x()
                y += row_height + self.spacing()
                row_height = 0
            height = item.heightForWidth(width) if item.hasHeightForWidth() else size.height()
            if apply:
                item.setGeometry(QRect(x, y, width, height))
            x += width + self.spacing()
            row_height = max(row_height, height)
        return y + row_height - rect.y() + margins.bottom()
