# ui/widgets/date_time_widget.py
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QVBoxLayout, QFrame
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QDate, QTime
from PyQt6.QtGui import QFont
from datetime import datetime
from ui.themes.theme_manager import theme_manager, get_theme_colors


class DateTimeWidget(QWidget):
    """Date and Time Widget with day.month.year, hh:mm AM/PM format"""
    
    date_changed = pyqtSignal(str)  # Emits date string when date changes
    time_changed = pyqtSignal(str)  # Emits time string when time changes
    
    def __init__(self, show_date=True, show_time=True, show_seconds=False, parent=None):
        super().__init__(parent)
        self.show_date = show_date
        self.show_time = show_time
        self.show_seconds = show_seconds
        self._is_dark = self._check_theme()
        self.setup_ui()
        self.update_display()
        
        # Update every second
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_display)
        self.timer.start(1000)
        
        # Connect theme change
        theme_manager.theme_changed.connect(self.on_theme_changed)
    
    def _check_theme(self):
        """Check if dark theme is active"""
        try:
            from ui.themes.theme_manager import is_dark_theme
            return is_dark_theme()
        except:
            return False
    
    def _get_theme_colors(self):
        """Get theme-aware colors"""
        if self._is_dark:
            return {
                'bg': 'transparent',
                'text': '#ffffff',
                'date_color': '#b9bbbe',
                'time_color': '#ffffff',
                'separator': '#40444b'
            }
        else:
            return {
                'bg': 'transparent',
                'text': '#212529',
                'date_color': '#6c757d',
                'time_color': '#212529',
                'separator': '#dee2e6'
            }
    
    def setup_ui(self):
        # Main layout
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # Create container for date and time
        self.container = QFrame()
        self.container.setStyleSheet("background: transparent;")
        container_layout = QHBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(8)
        
        # Date label
        if self.show_date:
            self.date_label = QLabel()
            self.date_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            container_layout.addWidget(self.date_label)
        
        # Separator
        if self.show_date and self.show_time:
            self.separator_label = QLabel("|")
            self.separator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            container_layout.addWidget(self.separator_label)
        
        # Time label
        if self.show_time:
            self.time_label = QLabel()
            self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            container_layout.addWidget(self.time_label)
        
        layout.addWidget(self.container)
        self.setLayout(layout)
        
        # Apply theme
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply theme-aware styles"""
        colors = self._get_theme_colors()
        
        # Container
        self.container.setStyleSheet("background: transparent;")
        
        # Date style
        if hasattr(self, 'date_label'):
            self.date_label.setStyleSheet(f"""
                QLabel {{
                    color: {colors['date_color']};
                    font-size: 10pt;
                    font-weight: normal;
                    background: transparent;
                    padding: 2px 0px;
                    border: none;
                }}
            """)
        
        # Separator style
        if hasattr(self, 'separator_label'):
            self.separator_label.setStyleSheet(f"""
                QLabel {{
                    color: {colors['separator']};
                    font-size: 10pt;
                    font-weight: normal;
                    background: transparent;
                    padding: 2px 4px;
                    border: none;
                }}
            """)
        
        # Time style
        if hasattr(self, 'time_label'):
            self.time_label.setStyleSheet(f"""
                QLabel {{
                    color: {colors['time_color']};
                    font-size: 10pt;
                    font-weight: 500;
                    background: transparent;
                    padding: 2px 0px;
                    border: none;
                }}
            """)
    
    def on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = self._check_theme()
        self._apply_theme()
    
    def update_display(self):
        """Update date and time display"""
        now = datetime.now()
        previous_date = None
        
        # Update date (only if changed)
        if self.show_date and hasattr(self, 'date_label'):
            date_str = now.strftime("%d.%m.%Y")
            if hasattr(self, '_last_date') and self._last_date != date_str:
                self.date_changed.emit(date_str)
            self._last_date = date_str
            self.date_label.setText(date_str)
        
        # Update time
        if self.show_time and hasattr(self, 'time_label'):
            if self.show_seconds:
                time_str = now.strftime("%I:%M:%S %p")
            else:
                time_str = now.strftime("%I:%M %p")
            # Remove leading zero from hour (e.g., "09" -> "9")
            if time_str.startswith('0'):
                time_str = time_str[1:]
            if hasattr(self, '_last_time') and self._last_time != time_str:
                self.time_changed.emit(time_str)
            self._last_time = time_str
            self.time_label.setText(time_str)
    
    def set_show_date(self, show):
        """Show or hide date"""
        self.show_date = show
        if hasattr(self, 'date_label'):
            self.date_label.setVisible(show)
        if hasattr(self, 'separator_label'):
            self.separator_label.setVisible(show and self.show_time)
    
    def set_show_time(self, show):
        """Show or hide time"""
        self.show_time = show
        if hasattr(self, 'time_label'):
            self.time_label.setVisible(show)
        if hasattr(self, 'separator_label'):
            self.separator_label.setVisible(show and self.show_date)
    
    def set_show_seconds(self, show):
        """Show or hide seconds"""
        self.show_seconds = show
        self.update_display()
    
    def get_date(self):
        """Get current date as string (day.month.year)"""
        return datetime.now().strftime("%d.%m.%Y")
    
    def get_time(self):
        """Get current time as string (hh:mm AM/PM)"""
        time_str = datetime.now().strftime("%I:%M %p")
        if time_str.startswith('0'):
            time_str = time_str[1:]
        return time_str
    
    def get_datetime(self):
        """Get current date and time as string (day.month.year, hh:mm AM/PM)"""
        date_str = datetime.now().strftime("%d.%m.%Y")
        time_str = datetime.now().strftime("%I:%M %p")
        if time_str.startswith('0'):
            time_str = time_str[1:]
        return f"{date_str}, {time_str}"
    
    def retranslateUi(self, lang_code):
        """Update language"""
        pass  # Date and time don't need translation
    
    def stop(self):
        """Stop the timer (call when widget is closed)"""
        if hasattr(self, 'timer'):
            self.timer.stop()
    
    def start(self):
        """Start the timer"""
        if hasattr(self, 'timer'):
            self.timer.start(1000)