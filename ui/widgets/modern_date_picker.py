# ui/widgets/modern_date_picker.py
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QFrame)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QPainterPath


class ModernDatePicker(QWidget):
    """Modern date picker with popup calendar"""
    
    date_selected = pyqtSignal(QDate)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_date = QDate.currentDate()
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ========== Input field with icon ==========
        self.input_frame = QFrame()
        self.input_frame.setObjectName("dateInputFrame")
        self.input_frame.setFixedHeight(40)
        # ✅ Set fixed width to accommodate full date
        self.input_frame.setFixedWidth(140)
        self.input_frame.setStyleSheet("""
            QFrame#dateInputFrame {
                background-color: #ffffff;
                border: 1px solid #ced4da;
                border-radius: 6px;
            }
            QFrame#dateInputFrame:hover {
                border-color: #a0a0a0;
            }
            QFrame#dateInputFrame:focus-within {
                border-color: #5865f2;
                border-width: 2px;
            }
        """)
        
        input_layout = QHBoxLayout(self.input_frame)
        input_layout.setContentsMargins(10, 0, 10, 0)
        input_layout.setSpacing(8)
        
        # Calendar icon
        self.icon_label = QLabel("📅")
        self.icon_label.setStyleSheet("font-size: 16px;")
        input_layout.addWidget(self.icon_label)
        
        # Date display with custom format
        self.date_label = QLabel()
        self.date_label.setStyleSheet("""
            font-size: 13px;
            font-weight: 500;
            color: #2c3e50;
        """)
        self.date_label.setFixedWidth(100)  # ✅ Fixed width for date text
        self.date_label.setText(self.selected_date.toString("dd.MM.yyyy"))
        input_layout.addWidget(self.date_label, 1)
        
        # Dropdown arrow
        self.arrow_label = QLabel("▼")
        self.arrow_label.setStyleSheet("""
            color: #95a5a6;
            font-size: 10px;
        """)
        input_layout.addWidget(self.arrow_label)
        
        main_layout.addWidget(self.input_frame)
        
        # ========== Popup Calendar ==========
        self.popup_frame = QFrame()
        self.popup_frame.setObjectName("popupFrame")
        self.popup_frame.setVisible(False)
        self.popup_frame.setStyleSheet("""
            QFrame#popupFrame {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 10px;
                margin-top: 4px;
                padding: 14px;
            }
        """)
        
        popup_layout = QVBoxLayout(self.popup_frame)
        popup_layout.setSpacing(10)
        popup_layout.setContentsMargins(0, 0, 0, 0)
        
        # ========== Month/Year Navigation ==========
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(6)
        
        self.prev_btn = self._create_nav_button("‹")
        nav_layout.addWidget(self.prev_btn)
        
        self.month_label = QLabel()
        self.month_label.setStyleSheet("""
            font-size: 14px;
            font-weight: 600;
            color: #2c3e50;
        """)
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_layout.addWidget(self.month_label, 1)
        
        self.next_btn = self._create_nav_button("›")
        nav_layout.addWidget(self.next_btn)
        
        popup_layout.addLayout(nav_layout)
        
        # ========== Days of Week Header ==========
        days_layout = QHBoxLayout()
        days_layout.setSpacing(2)
        days = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        for day in days:
            label = QLabel(day)
            label.setStyleSheet("""
                font-size: 10px;
                font-weight: 600;
                color: #7f8c8d;
            """)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedHeight(24)
            days_layout.addWidget(label)
        popup_layout.addLayout(days_layout)
        
        # ========== Days Grid ==========
        self.days_grid = QWidget()
        grid_layout = QVBoxLayout(self.days_grid)
        grid_layout.setSpacing(2)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        popup_layout.addWidget(self.days_grid)
        
        # ========== Today Button ==========
        self.today_btn = QPushButton("Today")
        self.today_btn.setStyleSheet("""
            QPushButton {
                background-color: #5865f2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px;
                font-weight: 500;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4752c4;
            }
        """)
        self.today_btn.clicked.connect(lambda: self.set_date(QDate.currentDate()))
        popup_layout.addWidget(self.today_btn)
        
        main_layout.addWidget(self.popup_frame)
        self.setLayout(main_layout)
        
        # ========== Signals ==========
        self.prev_btn.clicked.connect(lambda: self.change_month(-1))
        self.next_btn.clicked.connect(lambda: self.change_month(1))
        self.input_frame.mousePressEvent = self.toggle_popup
        
        # ========== Initialize ==========
        self.update_month_display()
        
    def _create_nav_button(self, text):
        """Create navigation button with modern style"""
        btn = QPushButton(text)
        btn.setFixedSize(30, 30)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f3f5;
                border: none;
                border-radius: 6px;
                color: #2c3e50;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
        """)
        return btn
        
    def update_date_label(self):
        """Update the date display label"""
        self.date_label.setText(self.selected_date.toString("dd MMM yyyy"))
        
    def update_month_display(self):
        """Update month/year display in popup"""
        self.month_label.setText(self.selected_date.toString("MMMM yyyy"))
        self.build_days_grid()
        
    def build_days_grid(self):
        """Build the days grid for current month"""
        # Clear existing grid
        for i in reversed(range(self.days_grid.layout().count())):
            item = self.days_grid.layout().itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()
        
        # Get calendar data
        first_day = QDate(self.selected_date.year(), self.selected_date.month(), 1)
        days_in_month = first_day.daysInMonth()
        first_day_of_week = first_day.dayOfWeek()  # 1=Monday, 7=Sunday
        
        # Calculate starting offset (adjust for Monday start)
        offset = first_day_of_week - 1
        
        # Create rows for each week
        week_row = None
        for day in range(1, days_in_month + 1):
            # Create new row if needed
            if (day - 1 + offset) % 7 == 0:
                week_row = QHBoxLayout()
                week_row.setSpacing(2)
                self.days_grid.layout().addLayout(week_row)
                
            # Create day button
            day_btn = QPushButton(str(day))
            day_btn.setFixedSize(34, 34)
            
            # Style based on selection
            is_selected = (day == self.selected_date.day() and 
                          self.selected_date.month() == first_day.month() and
                          self.selected_date.year() == first_day.year())
            is_today = (day == QDate.currentDate().day() and
                       self.selected_date.month() == QDate.currentDate().month() and
                       self.selected_date.year() == QDate.currentDate().year())
            
            # Apply styling
            if is_selected:
                style = """
                    QPushButton {
                        background-color: #5865f2;
                        border: none;
                        border-radius: 6px;
                        font-size: 12px;
                        font-weight: 600;
                        color: white;
                    }
                    QPushButton:hover {
                        background-color: #4752c4;
                    }
                """
            elif is_today:
                style = """
                    QPushButton {
                        background-color: transparent;
                        border: 2px solid #5865f2;
                        border-radius: 6px;
                        font-size: 12px;
                        font-weight: 500;
                        color: #2c3e50;
                    }
                    QPushButton:hover {
                        background-color: #f1f3f5;
                    }
                """
            else:
                style = """
                    QPushButton {
                        background-color: transparent;
                        border: none;
                        border-radius: 6px;
                        font-size: 12px;
                        font-weight: 500;
                        color: #2c3e50;
                    }
                    QPushButton:hover {
                        background-color: #f1f3f5;
                    }
                """
            
            day_btn.setStyleSheet(style)
            day_btn.clicked.connect(lambda checked, d=day: self.select_day(d))
            week_row.addWidget(day_btn)
            
        # Fill remaining days with empty widgets
        if week_row:
            total_days = days_in_month + offset
            remaining = 7 - (total_days % 7)
            if remaining < 7:
                for _ in range(remaining):
                    empty = QLabel()
                    empty.setFixedSize(34, 34)
                    week_row.addWidget(empty)
                    
    def select_day(self, day):
        """Select a specific day"""
        selected = QDate(self.selected_date.year(), self.selected_date.month(), day)
        self.set_date(selected)
        self.hide_popup()
        
    def set_date(self, date):
        """Set the selected date"""
        self.selected_date = date
        self.update_date_label()
        self.update_month_display()
        self.date_selected.emit(date)
        
    def change_month(self, delta):
        """Change month by delta"""
        self.selected_date = self.selected_date.addMonths(delta)
        self.update_month_display()
        
    def toggle_popup(self, event):
        """Toggle the popup visibility"""
        if self.popup_frame.isVisible():
            self.hide_popup()
        else:
            self.show_popup()
            
    def show_popup(self):
        """Show the popup with animation"""
        self.popup_frame.setVisible(True)
        self.popup_frame.setFixedWidth(max(self.width(), 280))
        self.update_month_display()
        
    def hide_popup(self):
        """Hide the popup"""
        self.popup_frame.setVisible(False)
        
    def get_date(self):
        """Get selected date as QDate"""
        return self.selected_date
        
    def retranslateUi(self, lang_code):
        """Update language"""
        if lang_code == "my":
            self.today_btn.setText("ယနေ့")
        else:
            self.today_btn.setText("Today")
        self.update_date_label()
            
    def paintEvent(self, event):
        """Draw shadow for popup"""
        super().paintEvent(event)
        
        # Draw shadow for popup
        if self.popup_frame.isVisible():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Shadow
            rect = self.popup_frame.geometry()
            shadow_rect = rect.adjusted(4, 4, 4, 4)
            
            path = QPainterPath()
            path.addRoundedRect(shadow_rect, 10, 10)
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 0, 0, 30)))
            painter.drawPath(path)
            
            painter.end()