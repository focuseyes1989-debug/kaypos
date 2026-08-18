# ui/lazy_loading_widget.py
"""
Lazy Loading Widget - Asynchronous Page Loading
✅ Module not found error ကို ကောင်းမွန်စွာ ကိုင်တွယ်နိုင်သည်
"""

from typing import Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, 
    QPushButton, QLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from loguru import logger
import re


class LazyLoadingWidget(QWidget):
    """
    Lazy Loading Widget - Shows loading indicator while page loads
    """
    
    page_loaded = pyqtSignal(object)  # Emits the loaded widget
    page_error = pyqtSignal(str)      # Emits error message
    
    def __init__(self, parent=None, load_delay=100):
        super().__init__(parent)
        # ✅ Ensure load_delay is int
        try:
            self._load_delay = int(load_delay) if load_delay is not None else 100
        except (ValueError, TypeError):
            self._load_delay = 100
        
        self._loaded_widget = None
        self._is_loading = False
        self._is_loaded = False
        self._load_func = None
        self._load_args = ()
        self._load_kwargs = {}
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the loading UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Loading container
        self.loading_container = QWidget()
        loading_layout = QVBoxLayout(self.loading_container)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.setSpacing(15)
        
        # Loading label
        self.loading_label = QLabel("Loading...")
        self.loading_label.setStyleSheet("""
            font-size: 14pt;
            color: #5865f2;
            font-weight: 500;
        """)
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.loading_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedWidth(250)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #e9ecef;
                border: none;
                border-radius: 6px;
                height: 8px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #5865f2;
                border-radius: 6px;
            }
        """)
        loading_layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("Initializing...")
        self.status_label.setStyleSheet("""
            font-size: 10pt;
            color: #6c757d;
        """)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(self.status_label)
        
        # Retry button (hidden by default)
        self.retry_btn = QPushButton("Retry")
        self.retry_btn.setStyleSheet("""
            QPushButton {
                background-color: #5865f2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: 500;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #4752c4;
            }
            QPushButton:pressed {
                background-color: #3c45a3;
            }
        """)
        self.retry_btn.setFixedHeight(36)
        self.retry_btn.setFixedWidth(100)
        self.retry_btn.hide()
        self.retry_btn.clicked.connect(self.retry_load)
        loading_layout.addWidget(self.retry_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.loading_container)
        
        # Start with loading visible
        self.loading_container.show()
        
        # Connect signals
        self.page_loaded.connect(self._on_page_loaded)
        self.page_error.connect(self._on_page_error)
    
    def load_page(self, load_func, *args, **kwargs):
        """
        Load a page using the provided function
        
        Args:
            load_func: Function that creates the page widget
            *args, **kwargs: Arguments to pass to load_func
        """
        if self._is_loading:
            logger.warning("Page is already loading")
            return
        
        self._is_loading = True
        self._is_loaded = False
        self._load_func = load_func
        self._load_args = args
        self._load_kwargs = kwargs if isinstance(kwargs, dict) else {}
        
        # Show loading, hide retry button
        self.loading_container.show()
        if self.layout():
            self.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.retry_btn.hide()
        self.status_label.setStyleSheet("color: #6c757d;")
        
        if self._loaded_widget:
            self._loaded_widget.hide()
            layout = self.layout()
            if layout:
                layout.removeWidget(self._loaded_widget)
        
        # Reset progress
        self.progress_bar.setValue(0)
        self.status_label.setText("Initializing...")
        self.loading_label.setText("Loading...")
        self.loading_label.setStyleSheet("""
            font-size: 14pt;
            color: #5865f2;
            font-weight: 500;
        """)
        
        # Load with delay (to allow UI to update)
        delay = self._load_delay if isinstance(self._load_delay, int) else 100
        QTimer.singleShot(delay, self._do_load)
    
    def _do_load(self):
        """Execute the actual loading with proper error handling"""
        try:
            if not self._load_func:
                self._on_loading_error("No load function provided")
                return
            
            self.status_label.setText("Loading page...")
            self.progress_bar.setValue(20)
            
            # ✅ Call the load function with better error handling
            widget = None
            error_msg = None
            
            try:
                widget = self._load_func(*self._load_args, **self._load_kwargs)
            except ImportError as e:
                # ✅ Module not found error - handle gracefully
                error_msg = str(e)
                logger.warning(f"Import error in lazy loading: {error_msg}")
                
                # Extract module name from error message
                module_name = "unknown"
                if "No module named" in error_msg:
                    match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_msg)
                    if match:
                        module_name = match.group(1)
                
                # Create a fallback widget showing the error
                widget = self._create_fallback_widget(
                    f"Module '{module_name}' is not installed.\n"
                    f"Please install it using: pip install {module_name}"
                )
                self.page_error.emit(f"Missing module: {module_name}")
                
            except Exception as e:
                # ✅ Other errors - also handle gracefully
                error_msg = str(e)
                logger.error(f"Error loading page: {error_msg}")
                widget = self._create_fallback_widget(
                    f"Error loading page:\n{error_msg}"
                )
                self.page_error.emit(error_msg)
            
            if widget is not None:
                self._loaded_widget = widget
                
                layout = self.layout()
                if layout is None:
                    layout = QVBoxLayout(self)
                    self.setLayout(layout)
                    # Move loading container to new layout
                    layout.addWidget(self.loading_container)
                
                layout.addWidget(widget)
                widget.hide()
                
                self.progress_bar.setValue(80)
                self.status_label.setText("Finalizing...")
                
                QTimer.singleShot(50, self._show_loaded_widget)
            else:
                self._on_loading_error("Failed to create page widget (returned None)")
                
        except Exception as e:
            logger.error(f"Lazy loading error: {e}")
            self._on_loading_error(str(e))
    
    def _create_fallback_widget(self, message: str) -> QWidget:
        """
        Create a fallback widget when loading fails
        
        Args:
            message: Error message to display
        
        Returns:
            QWidget: Fallback widget with error message
        """
        widget = QWidget()
        widget.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)
        
        # Warning icon
        icon_label = QLabel("⚠️")
        icon_label.setStyleSheet("font-size: 48px; background: transparent;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)
        
        # Error title
        title_label = QLabel("Unable to Load Page")
        title_label.setStyleSheet("""
            font-size: 14pt;
            font-weight: 600;
            color: #dc3545;
            background: transparent;
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Error message
        error_label = QLabel(message)
        error_label.setStyleSheet("""
            font-size: 10pt;
            color: #6c757d;
            background: transparent;
        """)
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setWordWrap(True)
        error_label.setMaximumWidth(400)
        layout.addWidget(error_label)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button_layout.setSpacing(12)
        
        # Retry button
        retry_btn = QPushButton("🔄 Retry")
        retry_btn.setStyleSheet("""
            QPushButton {
                background-color: #5865f2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 500;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #4752c4;
            }
            QPushButton:pressed {
                background-color: #3c45a3;
            }
        """)
        retry_btn.setFixedHeight(36)
        retry_btn.clicked.connect(self.retry_load)
        button_layout.addWidget(retry_btn)
        
        layout.addLayout(button_layout)
        
        return widget
    
    def _show_loaded_widget(self):
        """Show the loaded widget"""
        if self._loaded_widget:
            layout = self.layout()
            if layout:
                # AlignCenter is only for the temporary loading indicator. If it
                # remains active, real pages collapse to their size hint and sit
                # in the middle of a large empty area.
                layout.setAlignment(Qt.AlignmentFlag(0))
                layout.setStretchFactor(self.loading_container, 0)
                layout.setStretchFactor(self._loaded_widget, 1)
            self._loaded_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            self._loaded_widget.show()
            self.loading_container.hide()
            self._is_loaded = True
            self._is_loading = False
            self.page_loaded.emit(self._loaded_widget)
            logger.info("Page loaded successfully")
    
    def _on_page_loaded(self, widget):
        """Handle page loaded signal"""
        self.progress_bar.setValue(100)
        self.status_label.setText("✅ Ready")
        self.status_label.setStyleSheet("color: #28a745;")
    
    def _on_page_error(self, error_msg):
        """Handle page error signal"""
        # Error is already handled in _do_load
        pass
    
    def _on_loading_error(self, error_msg):
        """Handle loading error"""
        self._is_loading = False
        self.status_label.setText(f"❌ Error: {error_msg}")
        self.status_label.setStyleSheet("color: #dc3545;")
        self.progress_bar.setValue(0)
        self.loading_label.setText("⚠️ Loading Failed")
        self.loading_label.setStyleSheet("""
            font-size: 14pt;
            color: #dc3545;
            font-weight: 500;
        """)
        self.retry_btn.show()
        self.page_error.emit(error_msg)
        logger.error(f"Lazy loading error: {error_msg}")
    
    def get_loaded_widget(self):
        """Get the loaded widget"""
        return self._loaded_widget
    
    def is_loaded(self):
        """Check if page is loaded"""
        return self._is_loaded
    
    def is_loading(self):
        """Check if page is loading"""
        return self._is_loading
    
    def retry_load(self):
        """Retry loading the page"""
        self.retry_btn.hide()
        self.loading_label.setText("Loading...")
        self.loading_label.setStyleSheet("""
            font-size: 14pt;
            color: #5865f2;
            font-weight: 500;
        """)
        if self._load_func:
            self.load_page(
                self._load_func,
                *(self._load_args or []),
                **(self._load_kwargs or {})
            )
    
    def clear(self):
        """Clear the loaded widget"""
        if self._loaded_widget:
            layout = self.layout()
            if layout:
                layout.removeWidget(self._loaded_widget)
            self._loaded_widget.deleteLater()
            self._loaded_widget = None
        self._is_loaded = False
        self._is_loading = False
        self.loading_container.show()
        self.retry_btn.hide()
        self.progress_bar.setValue(0)
        self.status_label.setText("Ready to load")
        self.status_label.setStyleSheet("color: #6c757d;")
        self.loading_label.setText("Loading...")
        self.loading_label.setStyleSheet("""
            font-size: 14pt;
            color: #5865f2;
            font-weight: 500;
        """)
    
    def set_load_delay(self, delay_ms: int):
        """Set load delay in milliseconds"""
        try:
            self._load_delay = int(delay_ms) if delay_ms is not None else 100
        except (ValueError, TypeError):
            self._load_delay = 100
