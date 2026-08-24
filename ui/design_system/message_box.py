"""Global adapter that gives every QMessageBox modern semantic buttons."""

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton


class ModernMessageBoxFilter(QObject):
    """Assign design-system roles to Qt-created QMessageBox buttons."""

    _PRIMARY = {
        QMessageBox.StandardButton.Ok,
        QMessageBox.StandardButton.Yes,
        QMessageBox.StandardButton.Save,
        QMessageBox.StandardButton.SaveAll,
        QMessageBox.StandardButton.Apply,
        QMessageBox.StandardButton.Retry,
        QMessageBox.StandardButton.Open,
    }
    _DANGER = {
        QMessageBox.StandardButton.Abort,
        QMessageBox.StandardButton.Discard,
    }

    def eventFilter(self, watched, event):
        if (
            isinstance(watched, QLabel)
            and watched.objectName() in ("qt_msgbox_label", "qt_msgbox_informativelabel")
            and event.type() in (QEvent.Type.Polish, QEvent.Type.Show)
        ):
            watched.setWordWrap(True)
            watched.setMinimumWidth(260)
        if isinstance(watched, QMessageBox) and event.type() in (
            QEvent.Type.Polish,
            QEvent.Type.Show,
        ):
            self._modernize(watched)
        return super().eventFilter(watched, event)

    @classmethod
    def _modernize(cls, box: QMessageBox) -> None:
        cls._fit_message_text(box)
        for button in box.buttons():
            if not isinstance(button, QPushButton):
                continue
            standard = box.standardButton(button)
            button_role = box.buttonRole(button)
            if standard in cls._DANGER or button_role == QMessageBox.ButtonRole.DestructiveRole:
                role = "Danger"
            elif (
                standard in cls._PRIMARY
                or button is box.defaultButton()
                or button_role in (
                    QMessageBox.ButtonRole.AcceptRole,
                    QMessageBox.ButtonRole.YesRole,
                    QMessageBox.ButtonRole.ApplyRole,
                )
            ):
                role = "Primary"
            else:
                role = "Secondary"
            button.setObjectName(f"modernMessage{role}")
            button.setProperty("modernButtonRole", role.lower())
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(38)

    @staticmethod
    def _fit_message_text(box: QMessageBox) -> None:
        """Keep compact message boxes readable without letting them grow forever."""
        labels = [
            label for label in box.findChildren(QLabel)
            if label.objectName() in ("qt_msgbox_label", "qt_msgbox_informativelabel")
        ]
        if not labels:
            return

        longest_line = 0
        for label in labels:
            label.setMinimumWidth(260)
            lines = label.text().splitlines() or [label.text()]
            line_width = max(label.fontMetrics().horizontalAdvance(line) for line in lines)
            longest_line = max(longest_line, line_width)
            label.setMinimumWidth(max(260, min(520, line_width + 24)))

        # Reserve enough room for icon, text and margins before first paint.
        # Qt retains responsibility for wrapping genuinely long messages.
        target_width = max(360, min(600, longest_line + 120))
        box.setMinimumWidth(target_width)


def install_modern_message_boxes(app: QApplication) -> ModernMessageBoxFilter:
    """Install once and retain the filter for the QApplication lifetime."""
    current = getattr(app, "_modern_message_box_filter", None)
    if isinstance(current, ModernMessageBoxFilter):
        return current
    message_filter = ModernMessageBoxFilter(app)
    app.installEventFilter(message_filter)
    app._modern_message_box_filter = message_filter
    return message_filter
