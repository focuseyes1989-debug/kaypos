# ui/sales_page/pagination_widget.py
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QComboBox, QPushButton, QButtonGroup
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont
from ui.themes.theme_manager import get_theme_colors, theme_manager


class PaginationWidget(QWidget):
    page_changed = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._total_items = 0
        self._current_page = 1
        self._page_size = 25  # ✅ int
        self._total_pages = 1
        self._page_buttons = []

        # Main Layout
        layout = QHBoxLayout()
        layout.setSpacing(4)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.addStretch()

        # --- Rows per page (Left side) ---
        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["25", "50", "100", "200"])
        self.page_size_combo.setCurrentText(str(self._page_size))
        self.page_size_combo.currentTextChanged.connect(self._on_page_size_changed)
        self.page_size_combo.setMinimumWidth(55)
        self.page_size_combo.setMaximumWidth(70)
        
        rows_label = QLabel("Rows:")
        rows_label.setStyleSheet("font-size: 10px;")
        layout.addWidget(rows_label)
        layout.addWidget(self.page_size_combo)

        layout.addSpacing(6)

        # --- Previous Button ---
        self.btn_prev = QPushButton("‹")
        self.btn_prev.setFixedSize(32, 32)
        self.btn_prev.clicked.connect(self._prev_page)
        layout.addWidget(self.btn_prev)

        # --- Page Number Buttons (Dynamic) ---
        self.page_button_group = QButtonGroup(self)
        self.page_button_group.buttonClicked.connect(self._on_page_button_clicked)
        
        self.page_numbers_layout = QHBoxLayout()
        self.page_numbers_layout.setSpacing(3)
        layout.addLayout(self.page_numbers_layout)

        # --- Next Button ---
        self.btn_next = QPushButton("›")
        self.btn_next.setFixedSize(32, 32)
        self.btn_next.clicked.connect(self._next_page)
        layout.addWidget(self.btn_next)

        layout.addStretch()
        self.setLayout(layout)

        # Apply theme-aware style
        self._apply_style()

        # Connect theme change signal
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _apply_style(self):
        """Apply theme-aware stylesheet"""
        colors = get_theme_colors()
        border_color = colors['border']
        text_color = colors['text']
        text_secondary = colors['text_secondary']
        hover_bg = colors['bg_hover']
        active_bg = colors['progress_bg']
        active_hover = colors['border_hover']
        disabled_color = colors['text_secondary']
        combo_bg = colors['input_bg']
        combo_text = colors['text']

        # Apply stylesheet
        self.setStyleSheet(f"""
            QWidget {{
                background-color: transparent;
            }}
            
            QLabel {{
                color: {text_secondary};
                font-size: 10px;
                background-color: transparent;
            }}
            
            QComboBox {{
                background-color: {combo_bg};
                border: 1px solid {border_color};
                border-radius: 7px;
                padding: 3px 8px;
                font-size: 10px;
                color: {combo_text};
                min-height: 22px;
                max-height: 26px;
            }}
            QComboBox:hover {{
                border-color: {active_bg};
            }}
            QComboBox:focus {{
                border-color: {active_bg};
                border-width: 2px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 16px;
                background: transparent;
            }}
            QComboBox QAbstractItemView {{
                background-color: {combo_bg};
                border: 1px solid {border_color};
                border-radius: 7px;
                selection-background-color: {active_bg};
                selection-color: white;
                color: {combo_text};
                font-size: 10px;
                padding: 2px;
            }}
            
            QPushButton {{
                background-color: transparent;
                border: 1px solid {border_color};
                border-radius: 7px;
                color: {text_color};
                font-size: 13px;
                font-weight: 500;
                padding: 0px 4px;
                min-width: 24px;
                max-width: 32px;
                min-height: 28px;
                max-height: 32px;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
                border-color: {active_bg};
            }}
            QPushButton:pressed {{
                background-color: {active_bg};
                color: white;
            }}
            QPushButton:disabled {{
                color: {disabled_color};
                border-color: {border_color};
                background-color: transparent;
            }}
            
            /* Active page button */
            QPushButton[active="true"] {{
                background-color: {active_bg};
                border-color: {active_bg};
                color: white;
                font-weight: 600;
            }}
            QPushButton[active="true"]:hover {{
                background-color: {active_hover};
                border-color: {active_hover};
            }}
        """)

    def _get_button_style(self, is_active):
        """Return stylesheet for a single page button"""
        colors = get_theme_colors()
        border_color = colors['border']
        text_color = colors['text']
        hover_bg = colors['bg_hover']
        active_bg = colors['progress_bg']
        active_hover = colors['border_hover']

        if is_active:
            return f"""
                QPushButton {{
                    background-color: {active_bg};
                    border: 1px solid {active_bg};
                    color: white;
                    border-radius: 7px;
                    font-weight: 600;
                    font-size: 11px;
                    padding: 0px 4px;
                    min-width: 24px;
                    max-width: 32px;
                    min-height: 28px;
                    max-height: 32px;
                }}
                QPushButton:hover {{
                    background-color: {active_hover};
                    border-color: {active_hover};
                }}
            """
        else:
            return f"""
                QPushButton {{
                    background-color: transparent;
                    border: 1px solid {border_color};
                    border-radius: 7px;
                    color: {text_color};
                    font-size: 11px;
                    padding: 0px 4px;
                    min-width: 24px;
                    max-width: 32px;
                    min-height: 28px;
                    max-height: 32px;
                }}
                QPushButton:hover {{
                    background-color: {hover_bg};
                    border-color: {active_bg};
                }}
            """

    def _update_page_buttons(self):
        """Create or update page number buttons (compact style)"""
        # Remove existing buttons
        for button in self._page_buttons:
            self.page_numbers_layout.removeWidget(button)
            button.deleteLater()
        self._page_buttons.clear()

        # ✅ Ensure _total_pages is int
        if not isinstance(self._total_pages, int):
            self._total_pages = 1

        # Show max 5 pages
        max_visible = 5
        start_page = max(1, self._current_page - 2)
        end_page = min(self._total_pages, start_page + max_visible - 1)

        if end_page - start_page < max_visible - 1:
            start_page = max(1, end_page - max_visible + 1)

        # First page button
        if start_page > 1:
            self._add_page_button(1)
            if start_page > 2:
                self._add_ellipsis_button()

        # Page number buttons
        for page_num in range(start_page, end_page + 1):
            self._add_page_button(page_num)

        # Last page button
        if end_page < self._total_pages:
            if end_page < self._total_pages - 1:
                self._add_ellipsis_button()
            self._add_page_button(self._total_pages)

    def _add_page_button(self, page_num):
        """Add a single page number button"""
        # ✅ Ensure page_num is int
        try:
            page_num = int(page_num) if page_num is not None else 1
        except (ValueError, TypeError):
            page_num = 1
            
        button = QPushButton(str(page_num))
        button.setFixedSize(32, 32)
        button.setProperty("active", page_num == self._current_page)
        
        button.page_number = page_num
        self.page_button_group.addButton(button)
        self._page_buttons.append(button)
        self.page_numbers_layout.addWidget(button)

        # Apply dynamic style
        button.setStyleSheet(self._get_button_style(page_num == self._current_page))

    def _add_ellipsis_button(self):
        """Add an ellipsis button"""
        ellipsis_btn = QPushButton("…")
        ellipsis_btn.setFixedSize(22, 28)
        ellipsis_btn.setEnabled(False)
        
        colors = get_theme_colors()
        text_color = colors['text_secondary']
        
        ellipsis_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: {text_color};
                font-size: 14px;
                padding: 0px;
            }}
        """)
        self._page_buttons.append(ellipsis_btn)
        self.page_numbers_layout.addWidget(ellipsis_btn)

    def _on_page_button_clicked(self, button):
        """Handle page number button click"""
        if hasattr(button, 'page_number'):
            self.set_current_page(button.page_number)

    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._apply_style()
        # Refresh buttons with new style
        for button in self._page_buttons:
            if hasattr(button, 'page_number'):
                is_active = button.page_number == self._current_page
                button.setStyleSheet(self._get_button_style(is_active))
            else:
                # Ellipsis button
                colors = get_theme_colors()
                text_color = colors['text_secondary']
                button.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        border: none;
                        color: {text_color};
                        font-size: 14px;
                        padding: 0px;
                    }}
                """)

    def set_total_items(self, total_items: int, emit_signal: bool = True):
        """Set total number of items"""
        # ✅ Ensure total_items is int
        if isinstance(total_items, str):
            try:
                total_items = int(total_items)
            except ValueError:
                total_items = 0
        elif not isinstance(total_items, (int, float)):
            total_items = 0
        
        self._total_items = int(total_items)
        old_pages = self._total_pages
        
        # ✅ Calculate total pages - ensure page_size is int
        if self._page_size > 0:
            self._total_pages = max(1, (self._total_items + self._page_size - 1) // self._page_size)
        else:
            self._total_pages = 1
        
        if self._current_page > self._total_pages:
            self._current_page = self._total_pages
        self._update_controls()
        
        if emit_signal and old_pages != self._total_pages:
            self._emit_page_changed()

    def set_current_page(self, page: int, emit_signal: bool = True):
        """Set current page"""
        # ✅ Ensure page is int
        if isinstance(page, str):
            try:
                page = int(page)
            except ValueError:
                page = 1
        elif not isinstance(page, int):
            page = 1
        
        # ✅ Ensure _total_pages is int
        if not isinstance(self._total_pages, int):
            self._total_pages = 1
        
        if 1 <= page <= self._total_pages and page != self._current_page:
            self._current_page = page
            self._update_controls()
            if emit_signal:
                self._emit_page_changed()

    def set_page_size(self, size: int, emit_signal: bool = True):
        """Set page size"""
        # ✅ Ensure size is int
        if isinstance(size, str):
            try:
                size = int(size)
            except ValueError:
                size = 25
        elif not isinstance(size, int):
            size = 25
        
        if size != self._page_size:
            self._page_size = size
            self._current_page = 1
            self._total_pages = max(1, (self._total_items + size - 1) // size)
            if self.page_size_combo.currentText() != str(size):
                self.page_size_combo.blockSignals(True)
                self.page_size_combo.setCurrentText(str(size))
                self.page_size_combo.blockSignals(False)
            self._update_controls()
            if emit_signal:
                self._emit_page_changed()

    def _update_controls(self):
        """Update all controls based on current state"""
        self.btn_prev.setEnabled(self._current_page > 1)
        self.btn_next.setEnabled(self._current_page < self._total_pages)
        self._update_page_buttons()

    def _emit_page_changed(self):
        self.page_changed.emit(self._current_page, self._page_size)

    def _on_page_size_changed(self, value: str):
        self.set_page_size(int(value) if value else 25)

    def _prev_page(self):
        if self._current_page > 1:
            self.set_current_page(self._current_page - 1)

    def _next_page(self):
        if self._current_page < self._total_pages:
            self.set_current_page(self._current_page + 1)
