# ui/widgets/date_range_widget.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QFrame, QGridLayout, QButtonGroup,
                             QDialog, QApplication, QSizePolicy, QComboBox)
from PyQt6.QtCore import pyqtSignal, QDate, Qt
from PyQt6.QtGui import QFont, QIntValidator, QMouseEvent

from ui.themes import theme_manager, get_theme_colors, is_dark_theme, get_current_theme
from ui.widgets.modern_button import ModernButton


class DatePickerDialog(QDialog):
    """သီးသန့် Dialog အနေနဲ့ ပွင့်တဲ့ ရက်စွဲရွေးချယ်ရေး - Wider Layout with Smaller Elements"""
    
    date_selected = pyqtSignal(QDate, QDate)
    
    def __init__(self, parent=None, initial_from=None, initial_to=None):
        super().__init__(parent)
        self.setWindowTitle("Select Date")
        self.setModal(True)
        self.setFixedSize(480, 520)
        
        # Set Today as default if no initial date provided
        if initial_from is None:
            initial_from = QDate.currentDate()
            initial_to = QDate.currentDate()
        
        self.temp_from = initial_from
        self.temp_to = initial_to
        self.current_month = initial_from
        
        self.setup_ui()
        self._apply_theme_style()
        
        # Update selection info for default date
        if self.temp_from == self.temp_to:
            self.selection_info.setText(f"Selected: {self.temp_from.toString('d MMM yyyy')}")
        else:
            self.selection_info.setText(
                f"Range: {self.temp_from.toString('d MMM yyyy')} - {self.temp_to.toString('d MMM yyyy')}"
            )
        
        # Update calendar after UI is set up
        self._update_calendar()
        
        # Connect to theme changes
        theme_manager.theme_changed.connect(self._on_theme_changed)
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._apply_theme_style()
        # Force update calendar to refresh colors
        self._update_calendar()
    
    def _apply_theme_style(self):
        """Apply theme-specific styles"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        # Dialog background
        bg_color = colors['bg']
        border_color = colors['border']
        text_color = colors['text']
        text_secondary = colors['text_secondary']
        card_bg = colors['card_bg']
        card_hover = colors['card_hover']
        input_border = colors['input_border']
        
        # Range background and text colors for dark/light theme
        if is_dark:
            range_bg = "#2a4a6a"  # Darker blue background for range
            range_text = "#ffffff"  # White text for dark theme
            range_bg_hover = "#3a5a7a"
            selected_bg = "#5865f2"  # Primary color for selected
            selected_text = "#ffffff"
            hover_bg = "#4a6a8a"
            hover_text = "#ffffff"
        else:
            range_bg = "#d4e0ff"  # Light blue for range
            range_text = "#1a1a2e"  # Dark text for light theme
            range_bg_hover = "#c0d0f0"
            selected_bg = "#5865f2"  # Primary color for selected
            selected_text = "#ffffff"
            hover_bg = "#e8edfd"
            hover_text = "#1a1a2e"
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            
            QLabel {{
                color: {text_color};
                background-color: transparent;
            }}
            
            /* Quick buttons - using ModernButton styling */
            QPushButton#quickBtn {{
                background-color: {card_bg};
                border: 1px solid {input_border};
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 500;
                color: {text_color};
            }}
            QPushButton#quickBtn:hover {{
                background-color: {card_hover};
            }}
            QPushButton#quickBtn:pressed {{
                background-color: {input_border};
            }}
            
            /* Navigation buttons */
            QPushButton#navBtn {{
                border: none;
                border-radius: 4px;
                font-size: 16px;
                padding: 4px 16px;
                color: #5865f2;
                background-color: transparent;
            }}
            QPushButton#navBtn:hover {{
                background-color: {card_hover};
            }}
            
            /* Month/Year ComboBox */
            QComboBox {{
                border: 1px solid {input_border};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 14px;
                font-weight: 600;
                color: {text_color};
                background-color: {card_bg};
                min-width: 70px;
            }}
            QComboBox:hover {{
                border-color: #5865f2;
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {card_bg};
                border: 1px solid {input_border};
                border-radius: 4px;
                selection-background-color: #5865f2;
                selection-color: white;
                color: {text_color};
            }}
            
            /* Day buttons - Default state */
            QPushButton#dayBtn {{
                border: none;
                border-radius: 17px;
                font-size: 12px;
                color: {text_color};
                background-color: transparent;
                padding: 0px;
                margin: 1px;
            }}
            QPushButton#dayBtn:hover {{
                background-color: {hover_bg};
                color: {hover_text};
                border-radius: 17px;
            }}
            
            /* Day buttons - Selected (start/end) state */
            QPushButton#dayBtn:checked {{
                background-color: {selected_bg};
                color: {selected_text};
                border-radius: 17px;
                font-weight: 600;
            }}
            QPushButton#dayBtn:checked:hover {{
                background-color: #4752c4;
                color: {selected_text};
                border-radius: 17px;
            }}
            
            /* Day buttons - Range (in between) state */
            QPushButton#dayBtn[range="true"] {{
                background-color: {range_bg};
                color: {range_text};
                border-radius: 0px;
            }}
            QPushButton#dayBtn[range="true"]:hover {{
                background-color: {range_bg_hover};
                color: {range_text};
                border-radius: 0px;
            }}
            
            /* Day buttons - Range start/end with rounded corners */
            QPushButton#dayBtn[range="true"][range-start="true"] {{
                border-radius: 17px 0px 0px 17px;
            }}
            QPushButton#dayBtn[range="true"][range-end="true"] {{
                border-radius: 0px 17px 17px 0px;
            }}
            QPushButton#dayBtn[range="true"][range-start="true"][range-end="true"] {{
                border-radius: 17px;
            }}
            
            /* Day of week headers */
            QLabel#dowLabel {{
                font-weight: 600;
                color: {text_secondary};
                font-size: 12px;
                padding: 6px 0;
            }}
            
            /* Selection info */
            QLabel#selectionInfo {{
                font-size: 12px;
                color: {text_secondary};
                padding: 6px 0;
                background-color: {card_bg};
                border-radius: 6px;
            }}
            
            /* Action buttons */
            QPushButton#actionBtn {{
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton#clearBtn {{
                color: {text_color};
                background-color: {card_bg};
                border: 1px solid {input_border};
            }}
            QPushButton#clearBtn:hover {{
                background-color: {card_hover};
            }}
            QPushButton#cancelBtn {{
                color: {text_color};
                background-color: {card_bg};
                border: 1px solid {input_border};
            }}
            QPushButton#cancelBtn:hover {{
                background-color: {card_hover};
            }}
            QPushButton#applyBtn {{
                color: white;
                background-color: #5865f2;
                border: 1px solid #5865f2;
            }}
            QPushButton#applyBtn:hover {{
                background-color: #4752c4;
            }}
        """)
        
        # Update button object names for styling
        for btn in [self.btn_today, self.btn_week, self.btn_month, self.btn_year]:
            btn.setObjectName("quickBtn")
        
        self.btn_prev_month.setObjectName("navBtn")
        self.btn_next_month.setObjectName("navBtn")
        
        for btn in self.day_buttons:
            btn.setObjectName("dayBtn")
        
        self.selection_info.setObjectName("selectionInfo")
        
        self.btn_clear.setObjectName("actionBtn")
        self.btn_clear.setObjectName("clearBtn")
        self.btn_cancel.setObjectName("actionBtn")
        self.btn_cancel.setObjectName("cancelBtn")
        self.btn_apply.setObjectName("actionBtn")
        self.btn_apply.setObjectName("applyBtn")
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(24, 16, 24, 16)
        main_layout.setSpacing(12)

        # --- Quick Range Buttons (Row 1) - Using ModernButton with Icons (18x18) ---
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(8)
        
        # Use ModernButton for quick range buttons with icons - 18x18 size
        self.btn_today = ModernButton("Today", ModernButton.SECONDARY)
        self.btn_today.set_icon("today", size=(18, 18))
        self.btn_today.set_compact(True)
        self._set_button_height(self.btn_today)
        
        self.btn_week = ModernButton("This Week", ModernButton.SECONDARY)
        self.btn_week.set_icon("calendar", size=(18, 18))
        self.btn_week.set_compact(True)
        self._set_button_height(self.btn_week)
        
        self.btn_month = ModernButton("This Month", ModernButton.SECONDARY)
        self.btn_month.set_icon("calendar_month", size=(18, 18))
        self.btn_month.set_compact(True)
        self._set_button_height(self.btn_month)
        
        self.btn_year = ModernButton("This Year", ModernButton.SECONDARY)
        self.btn_year.set_icon("date", size=(18, 18))
        self.btn_year.set_compact(True)
        self._set_button_height(self.btn_year)
        
        self.btn_today.clicked.connect(lambda: self._set_quick_range("today"))
        self.btn_week.clicked.connect(lambda: self._set_quick_range("week"))
        self.btn_month.clicked.connect(lambda: self._set_quick_range("month"))
        self.btn_year.clicked.connect(lambda: self._set_quick_range("year"))
        
        quick_layout.addWidget(self.btn_today)
        quick_layout.addWidget(self.btn_week)
        quick_layout.addWidget(self.btn_month)
        quick_layout.addWidget(self.btn_year)
        quick_layout.addStretch()
        
        main_layout.addLayout(quick_layout)

        # --- Month/Year Navigation (Row 2) - With Dropdowns ---
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(8)
        
        # Use ModernButton for navigation with icons - 18x18 size
        self.btn_prev_month = ModernButton("", ModernButton.TERTIARY)
        self.btn_prev_month.set_icon("arrow_circle_left", size=(18, 18))
        self.btn_prev_month.set_compact(True)
        self.btn_prev_month.setFixedSize(32, 32)
        
        self.btn_next_month = ModernButton("", ModernButton.TERTIARY)
        self.btn_next_month.set_icon("arrow_circle_right", size=(18, 18))
        self.btn_next_month.set_compact(True)
        self.btn_next_month.setFixedSize(32, 32)
        
        # Month ComboBox
        self.month_combo = QComboBox()
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for month in month_names:
            self.month_combo.addItem(month)
        self.month_combo.currentIndexChanged.connect(self._on_month_changed)
        
        # Year ComboBox
        self.year_combo = QComboBox()
        current_year = QDate.currentDate().year()
        # Keep a useful DOB history in the dropdown while also allowing any
        # QDate-supported year to be typed directly.
        for year in range(current_year - 100, current_year + 11):
            self.year_combo.addItem(str(year))
        self.year_combo.setEditable(True)
        self.year_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.year_combo.lineEdit().setValidator(QIntValidator(1, 9999, self.year_combo))
        self.year_combo.lineEdit().setPlaceholderText("Year")
        self.year_combo.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.year_combo.setCurrentText(str(current_year))
        self.year_combo.textActivated.connect(self._on_year_changed)
        self.year_combo.lineEdit().editingFinished.connect(
            lambda: self._on_year_changed(self.year_combo.currentText())
        )
        
        self.btn_prev_month.clicked.connect(self._prev_month)
        self.btn_next_month.clicked.connect(self._next_month)
        
        nav_layout.addWidget(self.btn_prev_month)
        nav_layout.addWidget(self.month_combo)
        nav_layout.addWidget(self.year_combo)
        nav_layout.addWidget(self.btn_next_month)
        nav_layout.addStretch()
        main_layout.addLayout(nav_layout)

        # --- Day of Week Headers (Row 3) ---
        dow_layout = QHBoxLayout()
        dow_layout.setSpacing(4)
        for dow in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            label = QLabel(dow)
            label.setObjectName("dowLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedWidth(48)
            dow_layout.addWidget(label)
        main_layout.addLayout(dow_layout)

        # --- Day Grid (Row 4) ---
        self.day_grid = QGridLayout()
        self.day_grid.setSpacing(3)
        self.day_buttons = []
        self.day_group = QButtonGroup(self)
        self.day_group.buttonClicked.connect(self._select_day)
        
        for i in range(42):
            btn = QPushButton()
            btn.setFixedSize(34, 34)
            btn.setCheckable(True)
            self.day_group.addButton(btn, i)
            self.day_buttons.append(btn)
            row = i // 7
            col = i % 7
            self.day_grid.addWidget(btn, row, col)
        
        main_layout.addLayout(self.day_grid)

        # --- Selection Info (Row 5) ---
        self.selection_info = QLabel("Select a date")
        self.selection_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.selection_info)

        # --- Action Buttons (Row 6) - Using ModernButton with Icons (18x18) ---
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)
        
        self.btn_clear = ModernButton("Clear", ModernButton.SECONDARY)
        self.btn_clear.set_icon("close", size=(18, 18))
        self.btn_clear.set_compact(True)
        self._set_button_height(self.btn_clear)
        
        self.btn_cancel = ModernButton("Cancel", ModernButton.SECONDARY)
        self.btn_cancel.set_icon("cancel", size=(18, 18))
        self.btn_cancel.set_compact(True)
        self._set_button_height(self.btn_cancel)
        
        self.btn_apply = ModernButton("Apply", ModernButton.PRIMARY)
        self.btn_apply.set_icon("check_circle", size=(18, 18))
        self.btn_apply.set_compact(True)
        self._set_button_height(self.btn_apply)
        
        self.btn_clear.clicked.connect(self._clear_selection)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply.clicked.connect(self._apply_selection)
        
        action_layout.addWidget(self.btn_clear)
        action_layout.addStretch()
        action_layout.addWidget(self.btn_cancel)
        action_layout.addWidget(self.btn_apply)
        main_layout.addLayout(action_layout)

        self.setLayout(main_layout)

    def _set_button_height(self, button, minimum=32, maximum=36):
        """Keep compact icon buttons from clipping text descenders."""
        button.setMinimumHeight(minimum)
        button.setMaximumHeight(maximum)
    
    def _on_month_changed(self, index):
        """Handle month combo box change"""
        if index >= 0:
            new_month = index + 1
            if new_month != self.current_month.month():
                self.current_month = QDate(self.current_month.year(), new_month, 1)
                self._update_calendar()
    
    def _on_year_changed(self, year_text):
        """Handle year combo box change"""
        text = str(year_text or "").strip()
        if not text.isdigit():
            return
        new_year = int(text)
        if not 1 <= new_year <= 9999 or new_year == self.current_month.year():
            return
        candidate = QDate(new_year, self.current_month.month(), 1)
        if candidate.isValid():
            self.current_month = candidate
            self._update_calendar()
    
    def _set_quick_range(self, range_type):
        """Handle quick range button clicks"""
        today = QDate.currentDate()
        
        if range_type == "today":
            self.temp_from = today
            self.temp_to = today
        elif range_type == "week":
            start = today.addDays(-(today.dayOfWeek() - 1))
            self.temp_from = start
            self.temp_to = start.addDays(6)
        elif range_type == "month":
            self.temp_from = QDate(today.year(), today.month(), 1)
            self.temp_to = today
        elif range_type == "year":
            self.temp_from = QDate(today.year(), 1, 1)
            self.temp_to = today
        
        # Update info label
        if self.temp_from == self.temp_to:
            self.selection_info.setText(f"Selected: {self.temp_from.toString('d MMM yyyy')}")
        else:
            self.selection_info.setText(
                f"Range: {self.temp_from.toString('d MMM yyyy')} - {self.temp_to.toString('d MMM yyyy')}"
            )
        
        self.current_month = self.temp_from
        self._update_calendar()
    
    def _update_calendar(self):
        """Update the calendar display with rounded range styling"""
        # Update combo boxes to match current_month
        self.month_combo.blockSignals(True)
        self.month_combo.setCurrentIndex(self.current_month.month() - 1)
        self.month_combo.blockSignals(False)
        
        self.year_combo.blockSignals(True)
        self.year_combo.setEditText(str(self.current_month.year()))
        self.year_combo.blockSignals(False)
        
        first_day = QDate(self.current_month.year(), self.current_month.month(), 1)
        days_in_month = self.current_month.daysInMonth()
        start_offset = first_day.dayOfWeek()
        
        # Get theme colors for range highlighting
        is_dark = is_dark_theme()
        if is_dark:
            range_bg = "#2a4a6a"
            range_text = "#ffffff"
            range_bg_hover = "#3a5a7a"
            hover_bg = "#4a6a8a"
            hover_text = "#ffffff"
        else:
            range_bg = "#d4e0ff"
            range_text = "#1a1a2e"
            range_bg_hover = "#c0d0f0"
            hover_bg = "#e8edfd"
            hover_text = "#1a1a2e"
        
        for i, btn in enumerate(self.day_buttons):
            day_num = i - (start_offset - 1) + 1
            
            if 1 <= day_num <= days_in_month:
                date = QDate(self.current_month.year(), self.current_month.month(), day_num)
                btn.setText(str(day_num))
                btn.setEnabled(True)
                btn.setVisible(True)
                
                # Check if date is in range
                is_in_range = self._is_date_in_selection(date)
                
                # Check if it's start or end of range
                is_start = self.temp_from is not None and date == self.temp_from
                is_end = self.temp_to is not None and date == self.temp_to
                
                # Set range properties for styling
                btn.setProperty("range", "true" if is_in_range else "false")
                btn.setProperty("range-start", "true" if is_start else "false")
                btn.setProperty("range-end", "true" if is_end else "false")
                
                # Set checked state for selected dates
                if self.temp_from and self.temp_to:
                    btn.setChecked(date == self.temp_from or date == self.temp_to)
                elif self.temp_from:
                    btn.setChecked(date == self.temp_from)
                else:
                    btn.setChecked(False)
                
                # Apply dynamic styles for range with rounded corners
                if is_in_range:
                    if is_start and is_end:
                        # Single date selected - fully rounded
                        btn.setStyleSheet(f"""
                            QPushButton#dayBtn {{
                                background-color: {range_bg};
                                color: {range_text};
                                border-radius: 17px;
                            }}
                            QPushButton#dayBtn:hover {{
                                background-color: {range_bg_hover};
                                color: {range_text};
                                border-radius: 17px;
                            }}
                        """)
                    elif is_start:
                        # Start of range - left rounded
                        btn.setStyleSheet(f"""
                            QPushButton#dayBtn {{
                                background-color: {range_bg};
                                color: {range_text};
                                border-radius: 17px 0px 0px 17px;
                            }}
                            QPushButton#dayBtn:hover {{
                                background-color: {range_bg_hover};
                                color: {range_text};
                                border-radius: 17px 0px 0px 17px;
                            }}
                        """)
                    elif is_end:
                        # End of range - right rounded
                        btn.setStyleSheet(f"""
                            QPushButton#dayBtn {{
                                background-color: {range_bg};
                                color: {range_text};
                                border-radius: 0px 17px 17px 0px;
                            }}
                            QPushButton#dayBtn:hover {{
                                background-color: {range_bg_hover};
                                color: {range_text};
                                border-radius: 0px 17px 17px 0px;
                            }}
                        """)
                    else:
                        # Middle of range - no rounding
                        btn.setStyleSheet(f"""
                            QPushButton#dayBtn {{
                                background-color: {range_bg};
                                color: {range_text};
                                border-radius: 0px;
                            }}
                            QPushButton#dayBtn:hover {{
                                background-color: {range_bg_hover};
                                color: {range_text};
                                border-radius: 0px;
                            }}
                        """)
                else:
                    # Not in range - clear styles
                    btn.setStyleSheet("")
                
                btn.style().unpolish(btn)
                btn.style().polish(btn)
            else:
                btn.setText("")
                btn.setEnabled(False)
                btn.setVisible(False)
                btn.setChecked(False)
                btn.setProperty("range", "false")
                btn.setProperty("range-start", "false")
                btn.setProperty("range-end", "false")
                btn.setStyleSheet("")
    
    def _is_date_in_selection(self, date):
        """Check if a date is within the selected range"""
        if not self.temp_from:
            return False
        if not self.temp_to:
            return date == self.temp_from
        return self.temp_from <= date <= self.temp_to
    
    def _select_day(self, button):
        """Handle day selection"""
        if not button.text():
            return
        
        day = int(button.text())
        selected_date = QDate(self.current_month.year(), self.current_month.month(), day)
        
        if not self.temp_from:
            # First selection
            self.temp_from = selected_date
            self.temp_to = None
            self.selection_info.setText(f"From: {selected_date.toString('d MMM yyyy')} - Select end date")
        else:
            if not self.temp_to and selected_date >= self.temp_from:
                # Second selection after first date
                self.temp_to = selected_date
                self.selection_info.setText(
                    f"Range: {self.temp_from.toString('d MMM yyyy')} - {self.temp_to.toString('d MMM yyyy')}"
                )
            else:
                # Start new selection
                self.temp_from = selected_date
                self.temp_to = None
                self.selection_info.setText(f"From: {selected_date.toString('d MMM yyyy')} - Select end date")
        
        self._update_calendar()
    
    def _prev_month(self):
        self.current_month = self.current_month.addMonths(-1)
        self._update_calendar()
    
    def _next_month(self):
        self.current_month = self.current_month.addMonths(1)
        self._update_calendar()
    
    def _clear_selection(self):
        """Clear current selection"""
        self.temp_from = None
        self.temp_to = None
        self.selection_info.setText("Select a date")
        self._update_calendar()
    
    def _apply_selection(self):
        """Apply the selected date range and close dialog"""
        if self.temp_from:
            from_date = self.temp_from
            to_date = self.temp_to if self.temp_to else self.temp_from
            self.date_selected.emit(from_date, to_date)
            self.accept()
        else:
            self.reject()
    
    def closeEvent(self, event):
        """Clean up theme connection on close"""
        try:
            theme_manager.theme_changed.disconnect(self._on_theme_changed)
        except:
            pass
        event.accept()


class DateRangeWidget(QWidget):
    """ရက်စွဲရွေးချယ်ရေး Widget - Horizontal Layout with ModernButton"""
    
    date_range_changed = pyqtSignal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_from = None
        self.selected_to = None
        self.setup_ui()
        self._apply_theme_style()
        
        # Set default to today if no selection
        if self.selected_from is None:
            today = QDate.currentDate()
            self.selected_from = today
            self.selected_to = today
            self._update_display()
        
        # Connect to theme changes
        theme_manager.theme_changed.connect(self._on_theme_changed)
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._apply_theme_style()
    
    def _apply_theme_style(self):
        """Apply theme-specific styles"""
        colors = get_theme_colors()
        
        text_color = colors['text']
        card_bg = colors['card_bg']
        input_border = colors['input_border']
        
        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
        
        # ModernButton already handles its own styling
        # Just style the date display
        self.date_display.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: {text_color};
                padding: 7px 14px;
                background-color: {colors['input_bg']};
                border-radius: 8px;
                border: 1px solid {input_border};
                min-width: 140px;
            }}
        """)
    
    def _update_display(self):
        """Update the display with current selection"""
        if self.selected_from and self.selected_to:
            if self.selected_from == self.selected_to:
                display_text = self.selected_from.toString("d MMM yyyy")
            else:
                display_text = f"{self.selected_from.toString('d MMM yyyy')} - {self.selected_to.toString('d MMM yyyy')}"
            
            self.date_display.setText(display_text)
            self.choose_btn.setText("Change")
            self.choose_btn.set_icon("edit", size=(18, 18))
            
            # Emit signal
            self.date_range_changed.emit(
                self.selected_from.toString("yyyy-MM-dd"),
                self.selected_to.toString("yyyy-MM-dd")
            )
    
    def setup_ui(self):
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # --- Choose Date Button - Using ModernButton with Icon (18x18) ---
        self.choose_btn = ModernButton("Choose Date", ModernButton.PRIMARY)
        self.choose_btn.set_icon("calendar", size=(18, 18))
        self.choose_btn.set_compact(True)
        self.choose_btn.setFixedHeight(38)
        self.choose_btn.clicked.connect(self.show_date_picker)
        main_layout.addWidget(self.choose_btn)

        # --- Selected Date Display ---
        self.date_display = QLabel("No date selected")
        self.date_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.date_display.setMinimumHeight(38)
        main_layout.addWidget(self.date_display)
        
        main_layout.addStretch()
        self.setLayout(main_layout)
        self.setMinimumHeight(38)
    
    def show_date_picker(self):
        """Open the date picker dialog"""
        dialog = DatePickerDialog(
            self,
            initial_from=self.selected_from,
            initial_to=self.selected_to
        )
        dialog.date_selected.connect(self._on_date_selected)
        dialog.exec()
    
    def _on_date_selected(self, from_date, to_date):
        """Handle date selection from dialog"""
        self.selected_from = from_date
        self.selected_to = to_date
        self._update_display()
    
    def get_from_date(self):
        """Get from date as yyyy-MM-dd"""
        if self.selected_from:
            return self.selected_from.toString("yyyy-MM-dd")
        return QDate.currentDate().toString("yyyy-MM-dd")
    
    def get_to_date(self):
        """Get to date as yyyy-MM-dd"""
        if self.selected_to:
            return self.selected_to.toString("yyyy-MM-dd")
        return QDate.currentDate().toString("yyyy-MM-dd")
    
    def set_range(self, from_date_str, to_date_str=None):
        """Set date range programmatically (yyyy-MM-dd format)"""
        from_date = QDate.fromString(from_date_str, "yyyy-MM-dd")
        if from_date.isValid():
            self.selected_from = from_date
            if to_date_str:
                to_date = QDate.fromString(to_date_str, "yyyy-MM-dd")
                self.selected_to = to_date if to_date.isValid() else from_date
            else:
                self.selected_to = from_date
            
            self._update_display()
    
    def retranslateUi(self, lang_code):
        """ဘာသာပြန်ရန်"""
        if lang_code == "my":
            self.choose_btn.setText("ရက်စွဲရွေးရန်")
            if not self.selected_from:
                self.date_display.setText("ရက်စွဲမရွေးရသေး")
        else:
            self.choose_btn.setText("Choose Date")
            if not self.selected_from:
                self.date_display.setText("No date selected")
    
    def closeEvent(self, event):
        """Clean up theme connection on close"""
        try:
            theme_manager.theme_changed.disconnect(self._on_theme_changed)
        except:
            pass
        event.accept()
