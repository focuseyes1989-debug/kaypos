# ui/expense_budget_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QDoubleSpinBox, QPushButton, QMessageBox, 
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QProgressBar, QGroupBox, QScrollArea, QWidget
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIcon, QColor
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from ui.widgets.modern_button import ModernButton
from ui.widgets.summary_card_widget import SummaryCardWidget
from ui.widgets.no_wheel_spinbox import NoWheelDoubleSpinBox  # ✅ Import custom spinbox
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme


class ExpenseBudgetDialog(QDialog):
    """Budget Settings Dialog - Theme-aware with SVG icons and Modern Buttons"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dark = is_dark_theme()
        
        self.setWindowTitle("Budget Settings")
        
        self.setWindowFlags(
            self.windowFlags() | 
            Qt.WindowType.WindowMinimizeButtonHint | 
            Qt.WindowType.WindowMaximizeButtonHint
        )
        
        self.setMinimumSize(1100, 700)
        self.resize(1200, 750)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setModal(True)
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # ========== MONTH/YEAR SELECTION ==========
        selection_layout = QHBoxLayout()
        selection_layout.setSpacing(15)
        
        select_label = QLabel("Select Month/Year:")
        select_label.setStyleSheet(self._get_label_style())
        selection_layout.addWidget(select_label)

        self.month_combo = QComboBox()
        months = ["January", "February", "March", "April", "May", "June", 
                  "July", "August", "September", "October", "November", "December"]
        self.month_combo.addItems(months)
        self.month_combo.setCurrentIndex(QDate.currentDate().month() - 1)
        self.month_combo.setMinimumWidth(150)
        self.month_combo.setStyleSheet(self._get_combobox_style())
        selection_layout.addWidget(self.month_combo)

        self.year_spin = QDoubleSpinBox()
        self.year_spin.setRange(2020, 2030)
        self.year_spin.setDecimals(0)
        self.year_spin.setValue(QDate.currentDate().year())
        self.year_spin.setFixedWidth(100)
        self.year_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.year_spin.setStyleSheet(self._get_spinbox_style())
        selection_layout.addWidget(self.year_spin)

        # ✅ ModernButton with SVG icon
        self.btn_load = ModernButton("Load", ModernButton.PRIMARY)
        self.btn_load.set_compact(False)
        self.btn_load.set_icon("refresh", size=(18, 18))  # ✅ SVG icon
        self.btn_load.clicked.connect(self.load_budgets)
        selection_layout.addWidget(self.btn_load)

        selection_layout.addStretch()
        layout.addLayout(selection_layout)

        # ========== SUMMARY CARDS (Using SummaryCardWidget with SVG Icons) ==========
        card_layout = QHBoxLayout()
        card_layout.setSpacing(12)
        
        # Total Budget Card - Using SVG icon
        self.total_card = SummaryCardWidget(
            title="Total Budget",
            value="0",
            icon="attach_money",    # SVG file: attach_money.svg
            color="#3498db",
            icon_is_svg=True        # ✅ Enable SVG mode
        )
        card_layout.addWidget(self.total_card)
        
        # Total Actual Card - Using SVG icon
        self.actual_card = SummaryCardWidget(
            title="Total Actual",
            value="0",
            icon="bar_chart",       # SVG file: bar_chart.svg
            color="#e74c3c",
            icon_is_svg=True        # ✅ Enable SVG mode
        )
        card_layout.addWidget(self.actual_card)
        
        # Remaining Card - Using SVG icon
        self.remaining_card = SummaryCardWidget(
            title="Remaining",
            value="0",
            icon="savings",         # SVG file: savings.svg
            color="#2ecc71",
            icon_is_svg=True        # ✅ Enable SVG mode
        )
        card_layout.addWidget(self.remaining_card)
        
        # Used Percentage Card - Using SVG icon
        self.used_card = SummaryCardWidget(
            title="Overall Used",
            value="0%",
            icon="trending_up",     # SVG file: trending_up.svg
            color="#f39c12",
            icon_is_svg=True        # ✅ Enable SVG mode
        )
        card_layout.addWidget(self.used_card)
        
        card_layout.addStretch()
        layout.addLayout(card_layout)

        # ========== TABLE WITH SCROLL AREA (Reduced scroll bar) ==========
        # ✅ Wrap table in scroll area with smaller scroll bar
        table_container = QWidget()
        table_container_layout = QVBoxLayout(table_container)
        table_container_layout.setContentsMargins(0, 0, 0, 0)
        table_container_layout.setSpacing(0)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet(self._get_scroll_area_style())
        
        # Create table widget
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Category", "Budget", "Actual", "Used %", "Remaining", "Status", "Notes"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(400)
        
        # Apply table style
        self._update_table_style()
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(1, 160)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(50)
        
        self.scroll_area.setWidget(self.table)
        table_container_layout.addWidget(self.scroll_area)
        layout.addWidget(table_container, 1)

        # ========== BUTTONS ==========
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        btn_layout.addStretch()
        
        # ✅ ModernButton with SVG icon
        self.btn_close = ModernButton("Close", ModernButton.TERTIARY)
        self.btn_close.set_compact(False)
        self.btn_close.set_icon("close", size=(18, 18))  # ✅ SVG icon
        self.btn_close.clicked.connect(self.accept)
        
        # ✅ ModernButton with SVG icon
        self.btn_save = ModernButton("Save Budgets", ModernButton.PRIMARY)
        self.btn_save.set_compact(False)
        self.btn_save.set_icon("save", size=(18, 18))  # ✅ SVG icon
        self.btn_save.clicked.connect(self.save_budgets)
        
        btn_layout.addWidget(self.btn_close)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        
        # Apply initial theme
        self._apply_theme()
        
        self.load_budgets()
        self.retranslateUi()

    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
        self.load_budgets()
    
    def _apply_theme(self):
        """Apply theme-aware styles"""
        colors = get_theme_colors()
        
        # Dialog background
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
            }}
        """)
        
        # Update table
        self._update_table_style()
        
        # Update combobox
        if hasattr(self, 'month_combo'):
            self.month_combo.setStyleSheet(self._get_combobox_style())
        
        # Update spinbox
        if hasattr(self, 'year_spin'):
            self.year_spin.setStyleSheet(self._get_spinbox_style())
        
        # Update labels
        for child in self.findChildren(QLabel):
            if child.text() in ["Select Month/Year:", "လ/နှစ် ရွေးပါ:"]:
                child.setStyleSheet(self._get_label_style())
        
        # Update scroll area
        if hasattr(self, 'scroll_area'):
            self.scroll_area.setStyleSheet(self._get_scroll_area_style())
        
        # Update summary cards
        for card in [self.total_card, self.actual_card, self.remaining_card, self.used_card]:
            if hasattr(card, 'update_theme'):
                card.update_theme()
        
        # ✅ Update ModernButtons theme
        for btn in [self.btn_load, self.btn_close, self.btn_save]:
            if hasattr(btn, 'update_theme'):
                btn.update_theme()
    
    def _get_label_style(self):
        colors = get_theme_colors()
        return f"color: {colors['text']}; font-size: 10pt; font-weight: 500;"
    
    def _get_combobox_style(self):
        colors = get_theme_colors()
        return f"""
            QComboBox {{
                padding: 6px 12px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
                min-height: 28px;
            }}
            QComboBox:focus {{
                border-color: #5865f2;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                color: {colors['text']};
                selection-background-color: #5865f2;
                selection-color: white;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 4px 8px;
                border-radius: 2px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {colors['bg_hover']};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: #5865f2;
                color: white;
            }}
        """
    
    def _get_spinbox_style(self):
        colors = get_theme_colors()
        return f"""
            QDoubleSpinBox {{
                padding: 6px 12px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
                min-height: 28px;
            }}
            QDoubleSpinBox:focus {{
                border-color: #5865f2;
            }}
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                background-color: transparent;
                border: none;
                width: 14px;
            }}
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
                background-color: {colors['bg_hover']};
                border-radius: 2px;
            }}
        """
    
    def _get_scroll_area_style(self):
        """✅ Reduced scroll bar style"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        if is_dark:
            return """
                QScrollArea {
                    background: transparent;
                    border: none;
                }
                QScrollBar:vertical {
                    background: transparent;
                    width: 6px;
                    border-radius: 3px;
                }
                QScrollBar::handle:vertical {
                    background: #40444b;
                    border-radius: 3px;
                    min-height: 20px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #5865f2;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    border: none;
                    background: none;
                    height: 0px;
                }
                QScrollBar:horizontal {
                    background: transparent;
                    height: 6px;
                    border-radius: 3px;
                }
                QScrollBar::handle:horizontal {
                    background: #40444b;
                    border-radius: 3px;
                    min-width: 20px;
                }
                QScrollBar::handle:horizontal:hover {
                    background: #5865f2;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    border: none;
                    background: none;
                    width: 0px;
                }
            """
        else:
            return """
                QScrollArea {
                    background: transparent;
                    border: none;
                }
                QScrollBar:vertical {
                    background: transparent;
                    width: 6px;
                    border-radius: 3px;
                }
                QScrollBar::handle:vertical {
                    background: #ced4da;
                    border-radius: 3px;
                    min-height: 20px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #5865f2;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    border: none;
                    background: none;
                    height: 0px;
                }
                QScrollBar:horizontal {
                    background: transparent;
                    height: 6px;
                    border-radius: 3px;
                }
                QScrollBar::handle:horizontal {
                    background: #ced4da;
                    border-radius: 3px;
                    min-width: 20px;
                }
                QScrollBar::handle:horizontal:hover {
                    background: #5865f2;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    border: none;
                    background: none;
                    width: 0px;
                }
            """
    
    def _update_table_style(self):
        """Update table style based on theme"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        if is_dark:
            table_style = """
                QTableWidget {
                    background-color: #2f3136;
                    alternate-background-color: #36393f;
                    selection-background-color: #40444b;
                    selection-color: #dcddde;
                    gridline-color: #40444b;
                    border: 1px solid #40444b;
                    border-radius: 6px;
                    color: #dcddde;
                }
                QTableWidget::item {
                    padding: 8px 12px;
                    color: #dcddde;
                }
                QTableWidget::item:selected {
                    background-color: #40444b;
                    color: #dcddde;
                }
                QHeaderView::section {
                    background-color: #202225;
                    padding: 8px 12px;
                    border: none;
                    border-bottom: 2px solid #40444b;
                    font-weight: 600;
                    font-size: 10pt;
                    color: #b9bbbe;
                }
                QTableWidget::item:hover {
                    background-color: #40444b;
                }
                QTableWidget QTableCornerButton::section {
                    background: #202225;
                    border: none;
                }
            """
        else:
            table_style = """
                QTableWidget {
                    background-color: white;
                    alternate-background-color: #f8f9fa;
                    selection-background-color: #e9ecef;
                    selection-color: #212529;
                    gridline-color: #dee2e6;
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                    color: #212529;
                }
                QTableWidget::item {
                    padding: 8px 12px;
                    color: #212529;
                }
                QTableWidget::item:selected {
                    background-color: #e9ecef;
                    color: #212529;
                }
                QHeaderView::section {
                    background-color: #f8f9fa;
                    padding: 8px 12px;
                    border: none;
                    border-bottom: 2px solid #dee2e6;
                    font-weight: 600;
                    font-size: 10pt;
                    color: #2c3e50;
                }
                QTableWidget::item:hover {
                    background-color: #f1f3f5;
                }
                QTableWidget QTableCornerButton::section {
                    background: #f8f9fa;
                    border: none;
                }
            """
        
        self.table.setStyleSheet(table_style)

    def get_lang(self):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='language'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "en"
        except:
            return "en"

    def retranslateUi(self):
        lang = self.get_lang()
        symbol = get_currency_symbol()
        colors = get_theme_colors()
        
        if lang == "my":
            self.setWindowTitle("ဘတ်ဂျက်သတ်မှတ်ချက်များ")
            
            # ✅ Update ModernButtons text
            self.btn_load.setText("ဖွင့်မည်")
            self.btn_save.setText("သိမ်းဆည်းမည်")
            self.btn_close.setText("ပိတ်မည်")
            
            # Update summary cards
            self.total_card.set_title("စုစုပေါင်းဘတ်ဂျက်")
            self.actual_card.set_title("စုစုပေါင်းအသုံးစရိတ်")
            self.remaining_card.set_title("ကျန်ငွေ")
            self.used_card.set_title("အသုံးပြုမှုနှုန်း")
            
            self.table.setHorizontalHeaderLabels([
                "အမျိုးအစား", "ဘတ်ဂျက်", "အသုံးစရိတ်", 
                "အသုံးပြုမှု", "ကျန်ငွေ", "အခြေအနေ", "မှတ်ချက်"
            ])
            
            # Update month names to Myanmar
            months = ["ဇန်နဝါရီ", "ဖေဖော်ဝါရီ", "မတ်", "ဧပြီ", "မေ", "ဇွန်", 
                      "ဇူလိုင်", "ဩဂုတ်", "စက်တင်ဘာ", "အောက်တိုဘာ", "နိုဝင်ဘာ", "ဒီဇင်ဘာ"]
            self.month_combo.blockSignals(True)
            self.month_combo.clear()
            self.month_combo.addItems(months)
            self.month_combo.setCurrentIndex(QDate.currentDate().month() - 1)
            self.month_combo.blockSignals(False)
            
            # Update label style for Myanmar
            for child in self.findChildren(QLabel):
                if child.text() == "Select Month/Year:":
                    child.setText("လ/နှစ် ရွေးပါ:")
                    child.setStyleSheet(self._get_label_style())
        else:
            self.setWindowTitle("Budget Settings")
            
            # ✅ Update ModernButtons text
            self.btn_load.setText("Load")
            self.btn_save.setText("Save Budgets")
            self.btn_close.setText("Close")
            
            # Update summary cards
            self.total_card.set_title("Total Budget")
            self.actual_card.set_title("Total Actual")
            self.remaining_card.set_title("Remaining")
            self.used_card.set_title("Overall Used")
            
            self.table.setHorizontalHeaderLabels([
                "Category", "Budget", "Actual", 
                "Used %", "Remaining", "Status", "Notes"
            ])
            
            # Reset month names to English
            months = ["January", "February", "March", "April", "May", "June", 
                      "July", "August", "September", "October", "November", "December"]
            self.month_combo.blockSignals(True)
            self.month_combo.clear()
            self.month_combo.addItems(months)
            self.month_combo.setCurrentIndex(QDate.currentDate().month() - 1)
            self.month_combo.blockSignals(False)
            
            # Update label style for English
            for child in self.findChildren(QLabel):
                if child.text() == "လ/နှစ် ရွေးပါ:":
                    child.setText("Select Month/Year:")
                    child.setStyleSheet(self._get_label_style())
        
        # Apply theme after language change
        self._apply_theme()

    def load_budgets(self):
        month = self.month_combo.currentIndex() + 1
        year = int(self.year_spin.value())
        symbol = get_currency_symbol()
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        # Color definitions
        red_color = "#ed4245" if is_dark else "#dc3545"
        orange_color = "#faa81a" if is_dark else "#f39c12"
        green_color = "#3ba55d" if is_dark else "#28a745"
        gray_color = "#72767d" if is_dark else "#6c757d"
        text_color = "#dcddde" if is_dark else "#212529"

        conn = connect_db()
        cursor = conn.cursor()

        # Get all expense categories
        cursor.execute("SELECT id, name FROM expense_categories ORDER BY name")
        categories = cursor.fetchall()

        # Get budgets for selected month/year
        cursor.execute("""
            SELECT category, budget_amount, notes 
            FROM expense_budgets 
            WHERE month = ? AND year = ?
        """, (month, year))
        budgets = {row[0]: {"amount": row[1], "notes": row[2] or ""} for row in cursor.fetchall()}

        # Get actual expenses for selected month/year
        month_start = f"{year}-{month:02d}-01"
        if month == 12:
            month_end = f"{year+1}-01-01"
        else:
            month_end = f"{year}-{month+1:02d}-01"
        
        cursor.execute("""
            SELECT category, COALESCE(SUM(amount), 0) as total
            FROM expenses
            WHERE expense_date >= ? AND expense_date < ?
            GROUP BY category
        """, (month_start, month_end))
        actuals = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()

        self.table.setRowCount(0)
        total_budget = 0
        total_actual = 0

        for cat_id, cat_name in categories:
            budget = budgets.get(cat_name, {}).get("amount", 0)
            actual = actuals.get(cat_name, 0)
            total_budget += budget
            total_actual += actual
            
            used_percent = (actual / budget * 100) if budget > 0 else 0
            remaining = budget - actual
            notes = budgets.get(cat_name, {}).get("notes", "")
            
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setRowHeight(row, 50)
            
            # Category (read-only)
            cat_item = QTableWidgetItem(cat_name)
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            cat_item.setForeground(QColor(text_color))
            self.table.setItem(row, 0, cat_item)
            
            # ✅ Budget amount (editable) - Using NoWheelDoubleSpinBox with vertical alignment fix
            budget_spin = NoWheelDoubleSpinBox()
            budget_spin.setRange(0, 999999999)
            budget_spin.setDecimals(0)
            budget_spin.setPrefix(f"{symbol} ")
            budget_spin.setValue(budget)
            budget_spin.setMinimumWidth(145)
            # ✅ Fix: Reduce top/bottom padding to center the spinbox vertically in the cell
            budget_spin.setStyleSheet(f"""
                QDoubleSpinBox {{
                    padding: 2px 8px;
                    border: 1px solid {colors['border']};
                    border-radius: 4px;
                    background: {colors['card_bg']};
                    color: {colors['text']};
                    font-size: 10pt;
                    min-height: 24px;
                    max-height: 28px;
                }}
                QDoubleSpinBox:focus {{
                    border-color: #5865f2;
                }}
                QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                    background-color: transparent;
                    border: none;
                    width: 12px;
                }}
                QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
                    background-color: {colors['bg_hover']};
                    border-radius: 2px;
                }}
            """)
            budget_spin.valueChanged.connect(self.update_summary)
            self.table.setCellWidget(row, 1, budget_spin)
            
            # Actual amount (read-only)
            actual_item = QTableWidgetItem(format_money(actual, symbol))
            actual_item.setFlags(actual_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            actual_item.setForeground(QColor(text_color))
            if actual > budget and budget > 0:
                actual_item.setForeground(QColor(red_color))
            self.table.setItem(row, 2, actual_item)
            
            # Used percentage
            used_text = f"{used_percent:.1f}%"
            percent_item = QTableWidgetItem(used_text)
            percent_item.setFlags(percent_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if used_percent >= 100:
                percent_item.setForeground(QColor(red_color))
            elif used_percent >= 80:
                percent_item.setForeground(QColor(orange_color))
            elif used_percent > 0:
                percent_item.setForeground(QColor(green_color))
            else:
                percent_item.setForeground(QColor(text_color))
            self.table.setItem(row, 3, percent_item)
            
            # Remaining amount
            remaining_item = QTableWidgetItem(format_money(remaining, symbol))
            remaining_item.setFlags(remaining_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if remaining < 0:
                remaining_item.setForeground(QColor(red_color))
            elif remaining > 0:
                remaining_item.setForeground(QColor(green_color))
            else:
                remaining_item.setForeground(QColor(text_color))
            self.table.setItem(row, 4, remaining_item)
            
            # Status
            if budget == 0:
                status_text = "No Budget"
                status_color = QColor(gray_color)
            elif actual >= budget:
                status_text = "⚠️ Exceeded"
                status_color = QColor(red_color)
            elif actual >= budget * 0.8:
                status_text = "⚠️ Warning"
                status_color = QColor(orange_color)
            else:
                status_text = "✓ OK"
                status_color = QColor(green_color)
            
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(status_color)
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 5, status_item)
            
            # Notes
            notes_item = QTableWidgetItem(notes)
            notes_item.setForeground(QColor(text_color))
            self.table.setItem(row, 6, notes_item)
        
        # Update summary cards
        self.total_card.set_value(format_money(total_budget, symbol))
        self.actual_card.set_value(format_money(total_actual, symbol))
        
        remaining_total = total_budget - total_actual
        self.remaining_card.set_value(format_money(remaining_total, symbol))
        if remaining_total < 0:
            self.remaining_card.set_color(red_color)
        else:
            self.remaining_card.set_color(green_color)
        
        overall_percent = (total_actual / total_budget * 100) if total_budget > 0 else 0
        self.used_card.set_value(f"{overall_percent:.1f}%")
        if overall_percent >= 100:
            self.used_card.set_color(red_color)
        elif overall_percent >= 80:
            self.used_card.set_color(orange_color)
        else:
            self.used_card.set_color(green_color)

    def update_summary(self):
        """Update summary when budget values change"""
        total_budget = 0
        for row in range(self.table.rowCount()):
            budget_widget = self.table.cellWidget(row, 1)
            if budget_widget:
                total_budget += budget_widget.value()
        
        total_actual = 0
        symbol = get_currency_symbol()
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        # Color definitions
        red_color = "#ed4245" if is_dark else "#dc3545"
        orange_color = "#faa81a" if is_dark else "#f39c12"
        green_color = "#3ba55d" if is_dark else "#28a745"
        
        for row in range(self.table.rowCount()):
            actual_item = self.table.item(row, 2)
            if actual_item:
                text = actual_item.text().replace(symbol, "").replace(",", "")
                try:
                    total_actual += float(text)
                except:
                    pass
        
        self.total_card.set_value(format_money(total_budget, symbol))
        self.actual_card.set_value(format_money(total_actual, symbol))
        
        remaining = total_budget - total_actual
        self.remaining_card.set_value(format_money(remaining, symbol))
        if remaining < 0:
            self.remaining_card.set_color(red_color)
        else:
            self.remaining_card.set_color(green_color)
        
        overall_percent = (total_actual / total_budget * 100) if total_budget > 0 else 0
        self.used_card.set_value(f"{overall_percent:.1f}%")
        if overall_percent >= 100:
            self.used_card.set_color(red_color)
        elif overall_percent >= 80:
            self.used_card.set_color(orange_color)
        else:
            self.used_card.set_color(green_color)
        
        # Update individual row statuses
        for row in range(self.table.rowCount()):
            budget_widget = self.table.cellWidget(row, 1)
            budget = budget_widget.value() if budget_widget else 0
            
            actual_item = self.table.item(row, 2)
            actual_text = actual_item.text().replace(symbol, "").replace(",", "") if actual_item else "0"
            try:
                actual = float(actual_text)
            except:
                actual = 0
            
            used_percent = (actual / budget * 100) if budget > 0 else 0
            remaining_row = budget - actual
            
            # Update used percentage
            percent_item = self.table.item(row, 3)
            if percent_item:
                percent_item.setText(f"{used_percent:.1f}%")
                if used_percent >= 100:
                    percent_item.setForeground(QColor(red_color))
                elif used_percent >= 80:
                    percent_item.setForeground(QColor(orange_color))
                elif used_percent > 0:
                    percent_item.setForeground(QColor(green_color))
                else:
                    percent_item.setForeground(QColor(colors['text']))
            
            # Update remaining amount
            remaining_item = self.table.item(row, 4)
            if remaining_item:
                remaining_item.setText(format_money(remaining_row, symbol))
                if remaining_row < 0:
                    remaining_item.setForeground(QColor(red_color))
                elif remaining_row > 0:
                    remaining_item.setForeground(QColor(green_color))
                else:
                    remaining_item.setForeground(QColor(colors['text']))
            
            # Update status
            status_item = self.table.item(row, 5)
            if status_item:
                if budget == 0:
                    status_item.setText("No Budget")
                    status_item.setForeground(QColor("#72767d" if is_dark else "#6c757d"))
                elif actual >= budget:
                    status_item.setText("⚠️ Exceeded")
                    status_item.setForeground(QColor(red_color))
                elif actual >= budget * 0.8:
                    status_item.setText("⚠️ Warning")
                    status_item.setForeground(QColor(orange_color))
                else:
                    status_item.setText("✓ OK")
                    status_item.setForeground(QColor(green_color))

    def save_budgets(self):
        month = self.month_combo.currentIndex() + 1
        year = int(self.year_spin.value())

        conn = connect_db()
        cursor = conn.cursor()
        
        try:
            for row in range(self.table.rowCount()):
                category = self.table.item(row, 0).text()
                budget_widget = self.table.cellWidget(row, 1)
                budget = budget_widget.value() if budget_widget else 0
                notes_item = self.table.item(row, 6)
                notes = notes_item.text() if notes_item else ""
                
                cursor.execute("""
                    INSERT INTO expense_budgets (category, month, year, budget_amount, notes)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(category, month, year) 
                    DO UPDATE SET budget_amount = excluded.budget_amount, notes = excluded.notes, updated_at = CURRENT_TIMESTAMP
                """, (category, month, year, budget, notes))
            
            conn.commit()
            lang = self.get_lang()
            msg = "Budgets saved successfully!" if lang != "my" else "ဘတ်ဂျက်များ သိမ်းဆည်းပြီးပါပြီ။"
            QMessageBox.information(self, "Success" if lang != "my" else "အောင်မြင်ပါပြီ", msg)
            self.load_budgets()
        except Exception as e:
            conn.rollback()
            lang = self.get_lang()
            error_msg = f"Failed to save budgets: {e}" if lang != "my" else f"ဘတ်ဂျက်များ သိမ်းဆည်းမရပါ: {e}"
            QMessageBox.critical(self, "Error" if lang != "my" else "အမှား", error_msg)
        finally:
            conn.close()

    def showEvent(self, event):
        """Refresh data when dialog becomes visible"""
        self.load_budgets()
        super().showEvent(event)
