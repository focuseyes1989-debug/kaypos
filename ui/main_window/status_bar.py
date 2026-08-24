# ui/main_window/status_bar.py
"""
Main Window Status Bar Component
"""

from PyQt6.QtWidgets import QStatusBar, QWidget, QHBoxLayout, QLabel, QProgressBar, QSizePolicy
from PyQt6.QtCore import Qt
from ui.themes.theme_manager import get_theme_colors


class StatusBar(QStatusBar):
    """Main Window Status Bar with background activity indicator"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent = parent
        self._background_activity_counts = {}
        self._setup_ui()
    
    def _setup_ui(self):
        colors = get_theme_colors()
        
        self.setStyleSheet(f"""
            QStatusBar {{
                background-color: {colors['card_bg']};
                color: {colors['text_secondary']};
                border-top: 1px solid {colors['border']};
                padding: 3px 16px;
            }}
        """)
        if hasattr(self, "ready_label"):
            self.ready_label.setStyleSheet(f"""
                color: {colors['text_secondary']};
                font-size: 9pt;
                background: transparent;
            """)
        self.clearMessage()
        self.setSizeGripEnabled(False)
        
        # Background activity indicator
        self._setup_activity_indicator()
    
    def _setup_activity_indicator(self):
        """Setup background activity indicator"""
        status_left = QWidget()
        status_layout = QHBoxLayout(status_left)
        status_layout.setContentsMargins(16, 0, 0, 0)
        status_layout.setSpacing(8)

        self.ready_label = QLabel("Ready")
        colors = get_theme_colors()
        self.ready_label.setStyleSheet(f"""
            color: {colors['text_secondary']};
            font-size: 9pt;
            background: transparent;
        """)
        status_layout.addWidget(self.ready_label)
        
        self.background_activity_progress = QProgressBar()
        self.background_activity_progress.setRange(0, 0)
        self.background_activity_progress.setTextVisible(False)
        self.background_activity_progress.setFixedSize(80, 5)
        self.background_activity_progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {colors['border']};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {colors['progress_bg']};
                border-radius: 3px;
            }}
        """)
        status_layout.addWidget(self.background_activity_progress)
        
        self.background_activity_label = QLabel("Background working...")
        self.background_activity_label.setStyleSheet(f"""
            color: {colors['progress_bg']};
            font-weight: 500;
            font-size: 9pt;
            background: transparent;
        """)
        status_layout.addWidget(self.background_activity_label)

        status_layout.addStretch()

        self.addPermanentWidget(status_left, 1)
        self.background_activity_progress.hide()
        self.background_activity_label.hide()
    
    def begin_background_activity(self, key: str, message: str = "Background working..."):
        self._background_activity_counts[key] = message
        self._refresh_activity_indicator()
    
    def end_background_activity(self, key: str):
        self._background_activity_counts.pop(key, None)
        self._refresh_activity_indicator()
    
    def set_background_activity(self, key: str, message: str = ""):
        if message:
            self.begin_background_activity(key, message)
        else:
            self.end_background_activity(key)
    
    def _refresh_activity_indicator(self):
        if self._background_activity_counts:
            latest_message = list(self._background_activity_counts.values())[-1]
            self.background_activity_label.setText(latest_message)
            self.background_activity_progress.show()
            self.background_activity_label.show()
        else:
            self.background_activity_progress.hide()
            self.background_activity_label.hide()
    
    def update_theme(self, theme_name):
        """Update status bar theme"""
        colors = get_theme_colors()
        
        self.setStyleSheet(f"""
            QStatusBar {{
                background-color: {colors['card_bg']};
                color: {colors['text_secondary']};
                border-top: 1px solid {colors['border']};
                padding: 3px 16px;
            }}
        """)
        self.ready_label.setStyleSheet(
            f"color: {colors['text_secondary']}; font-size: 9pt; background: transparent;"
        )
        self.background_activity_progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {colors['border']};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {colors['progress_bg']};
                border-radius: 3px;
            }}
        """)
        self.background_activity_label.setStyleSheet(
            f"color: {colors['progress_bg']}; font-weight: 500; font-size: 9pt; background: transparent;"
        )
