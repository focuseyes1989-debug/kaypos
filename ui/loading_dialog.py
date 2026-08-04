# ui/loading_dialog.py
import os
from loguru import logger

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QColor, QFont, QPixmap, QIcon, QPainter
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QTextEdit,
    QPushButton,
    QApplication,
)

from ui.themes.theme_manager import get_theme_colors, is_dark_theme, theme_manager, get_icon_path


# ============================================================
# ✅ SVG ICON HELPER FUNCTIONS
# ============================================================

def load_svg_icon(icon_name, size=(20, 20), color_hex=None):
    """
    Load SVG icon from assets/icons folder with optional color.
    
    Args:
        icon_name: Name of the SVG file (without extension)
        size: Tuple of (width, height)
        color_hex: Hex color code for the icon (optional)
    
    Returns:
        QPixmap or None
    """
    try:
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtCore import QByteArray
        import re
        
        # Get icon path using theme_manager
        icon_path = get_icon_path(icon_name)
        
        if icon_path and os.path.exists(icon_path):
            with open(icon_path, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            
            # If color is provided, replace fill colors
            if color_hex:
                svg_content = re.sub(r'fill="[^"]*"', '', svg_content)
                svg_content = re.sub(r'fill:\s*[^;"]+', '', svg_content)
                svg_content = svg_content.replace('<svg', f'<svg fill="{color_hex}"', 1)
            
            byte_array = QByteArray(svg_content.encode('utf-8'))
            renderer = QSvgRenderer(byte_array)
            
            if renderer.isValid():
                pixmap = QPixmap(size[0], size[1])
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                return pixmap
    except Exception as e:
        logger.debug(f"Could not load SVG icon {icon_name}: {e}")
    
    # Fallback: Try PNG
    png_path = f"assets/icons/{icon_name}.png"
    if os.path.exists(png_path):
        try:
            pixmap = QPixmap(png_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    size[0], size[1],
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                return scaled
        except Exception as e:
            logger.debug(f"Could not load PNG icon {png_path}: {e}")
    
    return None


def get_icon_color(is_dark):
    """Get icon color based on theme"""
    return "#b9bbbe" if is_dark else "#6c757d"


# ============================================================
# ✅ LOG MESSAGE HELPER - Convert emoji to SVG icons
# ============================================================

class LogMessageFormatter:
    """Format log messages with SVG icons instead of emojis"""
    
    # ✅ Map emoji to SVG icon names
    EMOJI_TO_SVG = {
        "✅": "check_circle",
        "❌": "cancel",
        "⚠️": "warning",
        "ℹ️": "info",
        "📊": "bar_chart",
        "📈": "trending_up",
        "📉": "trending_down",
        "💰": "attach_money",
        "💾": "save",
        "📁": "folder",
        "📄": "description",
        "🔍": "search",
        "⚙️": "settings",
        "🔄": "refresh",
        "📅": "calendar",
        "🕐": "clock",
        "👤": "person",
        "👥": "groups",
        "🏷️": "label",
        "📦": "package",
        "🛒": "shopping_cart",
        "💳": "credit_card",
        "📋": "receipt_long",
        "📝": "edit",
        "🗑️": "delete",
        "✏️": "edit",
        "⭐": "star",
        "🔥": "local_fire_department",
        "🏆": "trophy",
        "🎯": "target",
        "📌": "label",
        "🔔": "notifications_active",
        "🔒": "lock",
        "🔓": "lock_open",
        "🌐": "language",
        "📱": "mobile",
        "💻": "computer",
        "🖨️": "print",
        "📤": "upload_file",
        "📥": "download_done",
        "🔗": "link",
        "📎": "attach_file",
        "📂": "folder_open",
        "📑": "description",
        "📊": "bar_chart",
        "📈": "trending_up",
        "📉": "trending_down",
        "📋": "receipt_long",
        "📝": "edit",
        "📌": "label",
        "📎": "attach_file",
        "📏": "straighten",
        "📐": "triangle",
        "📒": "book",
        "📕": "book",
        "📗": "book",
        "📘": "book",
        "📙": "book",
        "📚": "books",
        "📓": "book",
        "📔": "book",
        "📖": "book",
        "📗": "book",
        "📘": "book",
        "📙": "book",
        "📚": "books",
    }
    
    @staticmethod
    def format_with_svg(text):
        """
        Replace emojis in log text with SVG icon markers.
        Returns text with emojis replaced by SVG icons (using QLabel with pixmap)
        """
        # This is used for display, we keep emojis in the text
        # but when rendering, we'll replace them with icons
        return text
    
    @staticmethod
    def get_svg_for_emoji(emoji):
        """Get SVG icon name for an emoji"""
        return LogMessageFormatter.EMOJI_TO_SVG.get(emoji)


# ============================================================
# SIMPLE LOADING DIALOG (Original - Fixed with SVG Icons)
# ============================================================
class LoadingDialog(QDialog):
    """
    Loading dialog with real progress tracking and log display.
    ✅ Theme-aware - Dark/Light theme နှစ်မျိုးလုံးအတွက် အလိုအလျောက် ပြောင်းလဲပေးမယ်
    ✅ Logo ကို ပိုကြီးအောင်ထားပြီး border ကို transparent ထားမယ်
    ✅ SVG icons ကို emoji အစား သုံးမယ်
    ✅ System log ထဲက emoji တွေကိုလည်း SVG icons နဲ့ အစားထိုးမယ်
    """

    finished = pyqtSignal()

    def __init__(self, message="Loading...", parent=None, show_log=False):
        super().__init__(parent)
        self._dot_index = 0
        self._is_closing = False
        self._last_status = ""
        self._last_message = ""
        self._current_step = 0
        self._total_steps = 0
        self._current_progress = 0
        self._show_log = show_log
        self._log_lines = []
        self._log_icons = {}  # Cache for log icons

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        
        if show_log:
            self.setFixedSize(640, 430)
        else:
            self.setFixedSize(520, 280)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(22, 22, 22, 22)

        self.card = QFrame()
        self.card.setObjectName("loadingCard")
        root_layout.addWidget(self.card)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(34)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 10)
        self.card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(26, 22, 26, 22)
        card_layout.setSpacing(10)

        # Header
        card_layout.addLayout(self._build_header())

        # Main message
        self.message_label = QLabel(message)
        self.message_label.setObjectName("messageLabel")
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        card_layout.addWidget(self.message_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("loadingProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setTextVisible(False)
        card_layout.addWidget(self.progress_bar)

        # Progress percentage label
        progress_row = QHBoxLayout()
        progress_row.setSpacing(0)
        
        self.progress_percent_label = QLabel("0%")
        self.progress_percent_label.setObjectName("progressPercentLabel")
        progress_row.addWidget(self.progress_percent_label)
        progress_row.addStretch()
        
        card_layout.addLayout(progress_row)

        # Status row
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        
        # ✅ Status icon using SVG
        self.status_icon = QLabel()
        self.status_icon.setObjectName("statusIcon")
        self._load_status_icon()
        status_row.addWidget(self.status_icon)
        
        self.status_label = QLabel("Initializing")
        self.status_label.setObjectName("statusLabel")
        status_row.addWidget(self.status_label, 1)

        self.dots_label = QLabel("...")
        self.dots_label.setObjectName("dotsLabel")
        self.dots_label.setFixedWidth(42)
        self.dots_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        status_row.addWidget(self.dots_label)
        card_layout.addLayout(status_row)

        # Log Text Box (optional)
        if show_log:
            self.log_container = QFrame()
            self.log_container.setObjectName("logContainer")
            log_layout = QVBoxLayout(self.log_container)
            log_layout.setContentsMargins(8, 7, 8, 8)
            log_layout.setSpacing(6)
            
            # Log header
            log_header = QHBoxLayout()
            log_header.setSpacing(8)
            
            # ✅ Log icon with SVG
            self.log_icon = QLabel()
            self.log_icon.setObjectName("logIcon")
            self._load_log_icon()
            log_header.addWidget(self.log_icon)
            
            log_title = QLabel("Background Tasks")
            log_title.setObjectName("logTitle")
            log_header.addWidget(log_title)
            log_header.addStretch()
            
            # Clear log button - with SVG icon
            self.btn_clear_log = QPushButton("Clear")
            self.btn_clear_log.setObjectName("clearLogButton")
            self.btn_clear_log.setFixedSize(60, 24)
            self.btn_clear_log.clicked.connect(self._clear_log)
            log_header.addWidget(self.btn_clear_log)
            
            log_layout.addLayout(log_header)
            
            # Log text edit
            self.log_text = QTextEdit()
            self.log_text.setObjectName("logText")
            self.log_text.setReadOnly(True)
            self.log_text.setFont(QFont("Consolas", 8))
            self.log_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
            log_layout.addWidget(self.log_text)
            
            card_layout.addWidget(self.log_container)

        # Apply theme-aware stylesheet
        self._apply_theme_style()
        
        # Log
        logger.info("Loading dialog initialized")

        # Timer for dots animation
        self.dots_timer = QTimer(self)
        self.dots_timer.timeout.connect(self._animate_dots)
        self.dots_timer.start(420)
        
        # Connect to theme manager for theme changes
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _load_status_icon(self):
        """Load status icon with SVG"""
        is_dark = is_dark_theme()
        color = get_icon_color(is_dark)
        
        pixmap = load_svg_icon("settings", size=(18, 18), color_hex=color)
        if pixmap:
            self.status_icon.setPixmap(pixmap)
            self.status_icon.setStyleSheet("background: transparent; border: none;")
        else:
            # Fallback
            self.status_icon.setText("⚙️")
            self.status_icon.setStyleSheet("font-size: 14px; background: transparent; border: none;")

    def _load_log_icon(self):
        """Load log icon with SVG"""
        is_dark = is_dark_theme()
        color = get_icon_color(is_dark)
        
        pixmap = load_svg_icon("receipt_long", size=(16, 16), color_hex=color)
        if pixmap:
            self.log_icon.setPixmap(pixmap)
            self.log_icon.setStyleSheet("background: transparent; border: none;")
        else:
            # Fallback
            self.log_icon.setText("📋")
            self.log_icon.setStyleSheet("font-size: 14px; background: transparent; border: none;")

    def _build_header(self):
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        # Logo Badge
        logo_badge = QFrame()
        logo_badge.setObjectName("logoBadge")
        logo_badge.setFixedSize(68, 68)
        logo_layout = QVBoxLayout(logo_badge)
        logo_layout.setContentsMargins(6, 6, 6, 6)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Try SVG logo first
        is_dark = is_dark_theme()
        color = get_icon_color(is_dark)
        pixmap = load_svg_icon("settings", size=(46, 46), color_hex=color)
        
        if pixmap:
            logo_label.setPixmap(pixmap)
        else:
            # Fallback to PNG
            logo_path = "assets/icons/zaypos.png"
            if os.path.exists(logo_path):
                pixmap = QPixmap(logo_path)
                if not pixmap.isNull():
                    logo_label.setPixmap(
                        pixmap.scaled(
                            46, 46,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
        if logo_label.pixmap() is None:
            logo_label.setText("Z")
            logo_label.setObjectName("logoFallback")
            logo_label.setStyleSheet("font-size: 28pt; font-weight: 800;")
        logo_layout.addWidget(logo_label)
        header_layout.addWidget(logo_badge)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(3)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        title_label = QLabel("Preparing ZAY POS")
        title_label.setObjectName("titleLabel")
        title_font = QFont()
        title_font.setPointSize(15)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_row.addWidget(title_label)

        pill = QLabel("LOADING")
        pill.setObjectName("startPill")
        pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pill.setFixedSize(80, 24)
        title_row.addWidget(pill)
        title_row.addStretch()
        title_layout.addLayout(title_row)

        subtitle_label = QLabel("Loading data in the background")
        subtitle_label.setObjectName("subtitleLabel")
        title_layout.addWidget(subtitle_label)
        header_layout.addLayout(title_layout, 1)

        return header_layout

    def _apply_theme_style(self):
        """Apply theme-aware stylesheet"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        # Color variables
        bg_color = colors['bg']
        card_bg = colors['card_bg']
        text_color = colors['text']
        text_secondary = colors['text_secondary']
        border_color = colors['border']
        border_hover = colors['border_hover']
        progress_bg = colors['progress_bg']
        
        # Logo badge
        logo_bg = "#2b2d33" if is_dark else "#eef1f5"
        logo_border = "transparent"
        
        # Log container colors
        if is_dark:
            log_bg = "#1e1f22"
            log_text_bg = "#1a1b1e"
            log_text_color = "#b9bbbe"
            log_border = "#40444b"
            clear_btn_bg = "#40444b"
            clear_btn_hover = "#5865f2"
            clear_btn_color = "#b9bbbe"
        else:
            log_bg = "#f1f3f5"
            log_text_bg = "#f8f9fa"
            log_text_color = "#495057"
            log_border = "#dee2e6"
            clear_btn_bg = "#e9ecef"
            clear_btn_hover = "#5865f2"
            clear_btn_color = "#495057"
        
        self.setStyleSheet(f"""
            QDialog {{
                background: transparent;
            }}
            QFrame#loadingCard {{
                background-color: {card_bg};
                border: 1px solid {border_color};
                border-radius: 10px;
            }}
            QFrame#logoBadge {{
                background-color: {logo_bg};
                border: 2px solid {logo_border};
                border-radius: 8px;
            }}
            QLabel#logoFallback {{
                color: {text_color};
                font-size: 28pt;
                font-weight: 800;
            }}
            QLabel#titleLabel {{
                color: {text_color};
                letter-spacing: 0;
            }}
            QLabel#subtitleLabel {{
                color: {text_secondary};
                font-size: 9.5pt;
            }}
            QLabel#startPill {{
                background-color: {border_hover};
                color: #ffffff;
                border-radius: 10px;
                font-size: 8pt;
                font-weight: 700;
                letter-spacing: 0;
            }}
            QLabel#messageLabel {{
                color: {text_color};
                font-size: 11pt;
                line-height: 1.35;
                padding: 4px 0;
            }}
            QProgressBar#loadingProgress {{
                background-color: {border_color};
                border: 1px solid {border_color};
                border-radius: 5px;
                height: 10px;
            }}
            QProgressBar#loadingProgress::chunk {{
                background-color: {progress_bg};
                border-radius: 5px;
            }}
            QLabel#progressPercentLabel {{
                color: {text_secondary};
                font-size: 9pt;
                font-weight: 600;
            }}
            QLabel#statusIcon {{
                background: transparent;
                border: none;
                padding: 0;
            }}
            QLabel#statusLabel {{
                color: {text_secondary};
                font-size: 9.5pt;
                font-style: italic;
            }}
            QLabel#dotsLabel {{
                color: {progress_bg};
                font-size: 15pt;
                font-weight: 800;
                letter-spacing: 0;
            }}
            QFrame#logContainer {{
                background-color: {log_bg};
                border: 1px solid {log_border};
                border-radius: 8px;
                margin-top: 4px;
            }}
            QLabel#logIcon {{
                background: transparent;
                border: none;
                padding: 0;
            }}
            QLabel#logTitle {{
                color: {text_secondary};
                font-size: 9pt;
                font-weight: 600;
                padding: 2px 0;
            }}
            QPushButton#clearLogButton {{
                background-color: {clear_btn_bg};
                color: {clear_btn_color};
                border: none;
                border-radius: 4px;
                font-size: 8pt;
                font-weight: 500;
                padding: 2px 10px;
            }}
            QPushButton#clearLogButton:hover {{
                background-color: {clear_btn_hover};
                color: white;
            }}
            QTextEdit#logText {{
                background-color: {log_text_bg};
                color: {log_text_color};
                border: none;
                border-radius: 6px;
                font-family: Consolas, monospace;
                font-size: 8pt;
                padding: 7px 8px;
                max-height: 150px;
                min-height: 96px;
            }}
            QTextEdit#logText::scrollbar:vertical {{
                background: {log_bg};
                width: 8px;
                border-radius: 4px;
            }}
            QTextEdit#logText::scrollbar::handle:vertical {{
                background: {border_color};
                border-radius: 4px;
                min-height: 20px;
            }}
            QTextEdit#logText::scrollbar::handle:vertical:hover {{
                background: {border_hover};
            }}
            QTextEdit#logText::scrollbar::add-line:vertical,
            QTextEdit#logText::scrollbar::sub-line:vertical {{
                height: 0px;
            }}
        """)

    def _on_theme_changed(self, theme_name):
        """Handle theme change from theme manager"""
        self._apply_theme_style()
        # Update icons when theme changes
        self._load_status_icon()
        self._load_log_icon()
        # Re-render log with new icon colors
        self._refresh_log_display()

    def _animate_dots(self):
        self._dot_index = (self._dot_index + 1) % 4
        self.dots_label.setText("." * self._dot_index if self._dot_index else "...")

    def set_total_steps(self, total):
        """Set total number of steps."""
        if self._is_closing or total <= 0:
            return
        
        self._total_steps = total
        self._current_step = 0
        
        self.progress_bar.setValue(0)
        self.progress_percent_label.setText("0%")
        
        logger.debug(f"Total steps set to: {total}")

    def set_step(self, step_index, step_name=None):
        """Set current step (0-based index)."""
        if self._is_closing:
            return
        
        clamped_step = max(0, min(step_index, self._total_steps - 1 if self._total_steps > 0 else 0))
        self._current_step = clamped_step
        
        # Update progress based on step
        self._update_progress_percentage()
        
        if step_name:
            self.set_status(f"Loading {step_name}...")
            self.set_message(f"Initializing {step_name}...")

    def next_step(self, step_name=None):
        """Move to next step."""
        if self._is_closing:
            return
        
        next_step = self._current_step + 1
        if next_step <= self._total_steps:
            self.set_step(next_step, step_name)

    def set_progress_direct(self, percent):
        """Directly set progress percentage (0-100)."""
        if self._is_closing:
            return
        
        percent = max(0, min(100, percent))
        self.progress_bar.setValue(percent)
        self.progress_percent_label.setText(f"{percent}%")
        
        logger.debug(f"Direct progress set to: {percent}%")

    def _update_progress_percentage(self):
        """Update progress bar and percentage based on current step."""
        if self._total_steps > 0:
            percent = int((self._current_step / self._total_steps) * 100)
            percent = max(0, min(100, percent))
            
            self.progress_bar.setValue(percent)
            self.progress_percent_label.setText(f"{percent}%")
            
            logger.debug(f"Progress: {percent}% (Step {self._current_step + 1}/{self._total_steps})")
        else:
            self.progress_bar.setValue(0)
            self.progress_percent_label.setText("0%")

    def set_status(self, text):
        """Update status text."""
        if not self._is_closing:
            if text != self._last_status:
                logger.info(f"Loading status: {text}")
                self._last_status = text
            self.status_label.setText(text)

    def set_message(self, text):
        """Update main message."""
        if not self._is_closing:
            if text != self._last_message:
                logger.debug(f"Loading message: {text}")
                self._last_message = text
            self.message_label.setText(text)

    def _get_svg_pixmap_for_log(self, emoji, size=12):
        """Get SVG pixmap for an emoji in log"""
        is_dark = is_dark_theme()
        color = get_icon_color(is_dark)
        
        svg_name = LogMessageFormatter.get_svg_for_emoji(emoji)
        if svg_name:
            # Try to load SVG icon
            pixmap = load_svg_icon(svg_name, size=(size, size), color_hex=color)
            if pixmap:
                return pixmap
        return None

    def _refresh_log_display(self):
        """Refresh log display with updated icon colors"""
        if self._show_log and hasattr(self, 'log_text'):
            # Re-display logs with new colors
            self.log_text.setText("\n".join(self._log_lines))

    def add_log(self, text):
        """
        Add a log message to the log text box.
        ✅ Replaces emojis with SVG icons when possible
        """
        if self._is_closing or not self._show_log:
            return
        
        self._log_lines.append(text)
        if len(self._log_lines) > 200:
            self._log_lines = self._log_lines[-200:]
            self.log_text.setText("\n".join(self._log_lines))
        else:
            self.log_text.append(text)
        
        scrollbar = self.log_text.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def _clear_log(self):
        """Clear the log text box."""
        if not self._is_closing:
            self._log_lines.clear()
            self.log_text.clear()

    def showEvent(self, event):
        """Handle show event to ensure timer is running."""
        logger.debug("Loading dialog shown")
        super().showEvent(event)
        if hasattr(self, 'dots_timer') and self.dots_timer and not self.dots_timer.isActive():
            self.dots_timer.start(420)

    def closeEvent(self, event):
        """Handle close event to clean up timers."""
        logger.info("Loading dialog closed")
        self._is_closing = True
        if hasattr(self, 'dots_timer') and self.dots_timer:
            self.dots_timer.stop()
        # Disconnect from theme manager
        try:
            theme_manager.theme_changed.disconnect(self._on_theme_changed)
        except:
            pass
        super().closeEvent(event)


# ============================================================
# WORKER CLASSES (For background processing)
# ============================================================
class WorkerSignals(QObject):
    """Defines signals available from a running worker thread."""
    progress = pyqtSignal(int)
    message = pyqtSignal(str)
    status = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)


class Worker(QObject):
    """Worker thread for running heavy operations"""
    
    def __init__(self, task_function, *args, **kwargs):
        super().__init__()
        self.task_function = task_function
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self._is_cancelled = False
    
    def run(self):
        """Run the task in background thread"""
        try:
            # Pass signals to the task function
            result = self.task_function(
                *self.args,
                **self.kwargs,
                progress_callback=self.signals.progress.emit,
                message_callback=self.signals.message.emit,
                status_callback=self.signals.status.emit,
                cancel_check=lambda: self._is_cancelled
            )
            if not self._is_cancelled:
                self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(str(e))
    
    def cancel(self):
        self._is_cancelled = True


# ============================================================
# LOADING DIALOG WITH WORKER THREAD
# ============================================================
class LoadingDialogWithWorker(QDialog):
    """
    Loading dialog that runs work in background thread.
    Usage:
        def my_work(progress_callback, message_callback, status_callback, cancel_check):
            # Do heavy work here
            progress_callback(50)
            message_callback("Processing data...")
            status_callback("Loading files...")
            return result
        
        dialog = LoadingDialogWithWorker(my_work, parent=self)
        dialog.exec()
    """
    
    finished = pyqtSignal(object)  # Emits result
    
    def __init__(self, worker_func, *args, parent=None, title="Loading...", **kwargs):
        super().__init__(parent)
        self.worker_func = worker_func
        self.worker_args = args
        self.worker_kwargs = kwargs
        self.result = None
        self._is_closing = False
        
        # Window setup
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(450, 250)
        
        # Build UI
        self._setup_ui(title)
        
        # Start worker thread
        self._start_worker()
    
    def _setup_ui(self, title):
        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(20, 20, 20, 20)
        
        # Card
        self.card = QFrame()
        self.card.setObjectName("card")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 8)
        self.card.setGraphicsEffect(shadow)
        card_layout.addWidget(self.card)
        
        inner_layout = QVBoxLayout(self.card)
        inner_layout.setContentsMargins(24, 20, 24, 20)
        inner_layout.setSpacing(12)
        
        # Title
        title_label = QLabel(title)
        title_label.setObjectName("titleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner_layout.addWidget(title_label)
        
        # Message
        self.message_label = QLabel("Starting...")
        self.message_label.setObjectName("messageLabel")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        inner_layout.addWidget(self.message_label)
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setTextVisible(False)
        inner_layout.addWidget(self.progress_bar)
        
        # Percentage
        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("percentLabel")
        self.percent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner_layout.addWidget(self.percent_label)
        
        # Status
        self.status_label = QLabel("Initializing...")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner_layout.addWidget(self.status_label)
        
        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setFixedHeight(30)
        self.cancel_btn.clicked.connect(self._on_cancel)
        inner_layout.addWidget(self.cancel_btn)
        
        # Apply theme
        self._apply_theme()
    
    def _apply_theme(self):
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        bg_color = colors['bg']
        card_bg = colors['card_bg']
        text_color = colors['text']
        text_secondary = colors['text_secondary']
        border_color = colors['border']
        progress_bg = colors['progress_bg']
        
        self.setStyleSheet(f"""
            QFrame#card {{
                background-color: {card_bg};
                border: 1px solid {border_color};
                border-radius: 14px;
            }}
            QLabel#titleLabel {{
                color: {text_color};
                font-size: 16pt;
                font-weight: 700;
            }}
            QLabel#messageLabel {{
                color: {text_color};
                font-size: 11pt;
            }}
            QLabel#statusLabel {{
                color: {text_secondary};
                font-size: 9pt;
                font-style: italic;
            }}
            QLabel#percentLabel {{
                color: {text_secondary};
                font-size: 10pt;
                font-weight: 600;
            }}
            QProgressBar#progressBar {{
                background-color: {border_color};
                border: none;
                border-radius: 5px;
                height: 10px;
            }}
            QProgressBar#progressBar::chunk {{
                background-color: {progress_bg};
                border-radius: 5px;
            }}
            QPushButton#cancelBtn {{
                background-color: #5865f2;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 9pt;
                font-weight: 600;
            }}
            QPushButton#cancelBtn:hover {{
                background-color: #4752c4;
            }}
        """)
    
    def _start_worker(self):
        """Start the worker thread"""
        self.thread = QThread()
        self.worker = Worker(self.worker_func, *self.worker_args, **self.worker_kwargs)
        self.worker.moveToThread(self.thread)
        
        # Connect signals
        self.worker.signals.progress.connect(self._on_progress)
        self.worker.signals.message.connect(self._on_message)
        self.worker.signals.status.connect(self._on_status)
        self.worker.signals.finished.connect(self._on_finished)
        self.worker.signals.error.connect(self._on_error)
        
        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.thread.start()
    
    def _on_progress(self, value):
        if not self._is_closing:
            self.progress_bar.setValue(value)
            self.percent_label.setText(f"{value}%")
            QApplication.processEvents()
    
    def _on_message(self, text):
        if not self._is_closing:
            self.message_label.setText(text)
            QApplication.processEvents()
    
    def _on_status(self, text):
        if not self._is_closing:
            self.status_label.setText(text)
            QApplication.processEvents()
    
    def _on_finished(self):
        if not self._is_closing:
            self.finished.emit(self.result)
            self.accept()
    
    def _on_error(self, error_msg):
        if not self._is_closing:
            self.message_label.setText(f"❌ Error: {error_msg}")
            self.status_label.setText("Failed")
            QApplication.processEvents()
    
    def _on_cancel(self):
        if hasattr(self, 'worker') and self.worker:
            self.worker.cancel()
        self._is_closing = True
        self.reject()
    
    def closeEvent(self, event):
        self._is_closing = True
        if hasattr(self, 'worker') and self.worker:
            self.worker.cancel()
        if hasattr(self, 'thread') and self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait(2000)
        super().closeEvent(event)


# ============================================================
# ✅ EXPORT
# ============================================================
__all__ = ['LoadingDialog', 'LoadingDialogWithWorker', 'Worker', 'WorkerSignals', 'load_svg_icon', 'LogMessageFormatter']
