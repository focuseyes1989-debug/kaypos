"""Global adapter that gives every QMessageBox modern semantic buttons."""

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton, QSizePolicy
from ui.design_system.metrics import CONTROL_HEIGHT


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
            if event.type() == QEvent.Type.Show:
                QTimer.singleShot(0, lambda: self._refit_visible(watched))
        return super().eventFilter(watched, event)

    @classmethod
    def _refit_visible(cls, box):
        try:
            if box.isVisible():
                cls._fit_message_text(box)
                box.layout().activate()
                box.adjustSize()
        except RuntimeError:
            pass  # The user may have already dismissed a short-lived message.

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
            button.setMinimumHeight(CONTROL_HEIGHT)
            button.setMaximumHeight(CONTROL_HEIGHT)

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
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
            label.setMinimumWidth(280)
            lines = label.text().splitlines() or [label.text()]
            line_width = max(label.fontMetrics().horizontalAdvance(line) for line in lines)
            longest_line = max(longest_line, line_width)
            label_width = max(280, min(560, line_width + 32))
            label.setMinimumWidth(label_width)
            # Reserve wrapped line height as well as width; Qt's compact
            # native message geometry can otherwise clip subsequent lines.
            text_width = max(label_width, label.width())
            wrapped_rect = label.fontMetrics().boundingRect(
                0,
                0,
                text_width,
                16777215,
                int(Qt.TextFlag.TextWordWrap),
                label.text(),
            )
            required_height = max(
                label.fontMetrics().lineSpacing() * max(1, len(lines)) + 18,
                label.heightForWidth(text_width),
                wrapped_rect.height() + 18,
            )
            # Apply the constraint in QSS too: a later theme polish can reset
            # QWidget.minimumHeight to the global message-label rule (20px).
            label.setStyleSheet(
                f"min-height: {required_height}px; max-height: 16777215px;"
                "padding: 2px 0px; background: transparent;"
            )
            label.setMinimumHeight(required_height)

        # Reserve enough room for icon, text and margins before first paint.
        # Qt retains responsibility for wrapping genuinely long messages.
        target_width = max(380, min(640, longest_line + 140))
        box.setMinimumWidth(target_width)
        box.setMinimumHeight(max(box.minimumHeight(), 150))


def install_modern_message_boxes(app: QApplication) -> ModernMessageBoxFilter:
    """Install once and retain the filter for the QApplication lifetime."""
    current = getattr(app, "_modern_message_box_filter", None)
    if isinstance(current, ModernMessageBoxFilter):
        return current
    message_filter = ModernMessageBoxFilter(app)
    app.installEventFilter(message_filter)
    app._modern_message_box_filter = message_filter
    return message_filter
