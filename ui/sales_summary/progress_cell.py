from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QProgressBar, QWidget


def progress_color(percentage: float, warning_threshold: float = 50, danger_threshold: float = 80) -> str:
    if percentage >= danger_threshold:
        return "#dc4765"
    if percentage >= warning_threshold:
        return "#df8b28"
    return "#2fc879"


def create_progress_cell(percentage: float, color: str | None = None) -> QWidget:
    value = max(0, min(100, int(percentage)))
    bar_color = color or progress_color(percentage)

    cell = QWidget()
    cell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    cell.setStyleSheet("QWidget { background: transparent; border: none; }")

    layout = QHBoxLayout(cell)
    layout.setContentsMargins(8, 0, 8, 0)
    layout.setSpacing(0)

    progress_bar = QProgressBar()
    progress_bar.setRange(0, 100)
    progress_bar.setValue(value)
    progress_bar.setFormat("")
    progress_bar.setTextVisible(False)
    progress_bar.setFixedHeight(13)
    progress_bar.setStyleSheet(f"""
        QProgressBar {{
            background: transparent;
            border: none;
            border-radius: 3px;
        }}
        QProgressBar::chunk {{
            background-color: {bar_color};
            border-radius: 3px;
        }}
    """)

    layout.addWidget(progress_bar)
    return cell
