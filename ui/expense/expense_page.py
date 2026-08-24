# ui/expense/expense_page.py

from loguru import logger
logger.info("=== Loading ExpensePage from ui/expense/expense_page.py ===")

import os  # âœ… Add this import

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox, 
    QTabWidget, QTableWidgetItem, QLabel, QComboBox,
    QFrame
)
from PyQt6.QtCore import Qt, QDate, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from utils.language import lang
from ui.expense.expense_table import ExpenseTable
from ui.expense.expense_export import ExpenseExport
from ui.expense.expense_category_tab import ExpenseCategoryTab
from ui.expense_dialog import ExpenseDialog
from ui.expense_categories_dialog import ExpenseCategoriesDialog
from ui.expense_budget_dialog import ExpenseBudgetDialog
from ui.expense_notification_dialog import ExpenseNotificationDialog
from ui.expense_comparison_dialog import ExpenseComparisonDialog

# âœ… Import widgets
from ui.widgets import (
    DateRangeWidget,
    ToastNotificationWidget,
    LoadingSpinnerWidget,
    SummaryCardWidget,
    SearchWidget
)
from ui.widgets.modern_button import ModernButton
from ui.widgets.action_toolbar import ActionToolbar
from ui.themes.theme_manager import theme_manager, is_dark_theme, get_theme_colors


class ExpensePage(QWidget):
    def __init__(self, user_role=None, parent=None):
        super().__init__(parent)
        self.user_role = user_role
        
        logger.info(f"ExpensePage initializing with user_role: {user_role}")
        
        lang.language_changed.connect(self.on_language_changed)
        theme_manager.theme_changed.connect(self.on_theme_changed)
        
        self.setup_ui()
        self.load_initial_data()
        
        logger.info("ExpensePage initialized successfully")
    
    def on_theme_changed(self, theme_name):
        """Handle theme change"""
        self.apply_card_style()
        self._apply_page_style()
        # âœ… Update tab bar style and icons
        self._apply_tab_bar_style()
        self._update_tab_icons_color()
    
    def _get_themed_icon(self, icon_name, size=(16, 16)):
        """Get themed SVG icon"""
        try:
            from ui.themes.theme_manager import get_themed_icon
            return get_themed_icon(icon_name, size=size)
        except:
            return QIcon()
    
    def _apply_tab_bar_style(self):
        """Apply the shared launcher-style tab treatment."""
        colors = get_theme_colors()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget#expenseTabs::pane {{
                border: 1px solid {colors['border']};
                border-radius: 12px;
                background-color: {colors['card_bg']};
                top: -1px;
            }}
            QTabWidget#expenseTabs QTabBar::tab {{
                background-color: transparent;
                color: {colors['text_secondary']};
                padding: 10px 18px;
                margin: 0 4px 7px 0;
                border: none;
                border-radius: 8px;
                font-weight: 600;
            }}
            QTabWidget#expenseTabs QTabBar::tab:selected {{
                background-color: {colors['bg_hover']};
                color: {colors['text']};
                border-bottom: 2px solid {colors['progress_bg']};
            }}
            QTabWidget#expenseTabs QTabBar::tab:hover:!selected {{
                background-color: {colors['card_hover']};
                color: {colors['text']};
            }}
        """)
        
        # âœ… Update tab icons color
        self._update_tab_icons_color()

    def _update_tab_icons_color(self):
        """âœ… Update all tab icons color based on theme"""
        is_dark = is_dark_theme()
        icon_color = "#ffffff" if is_dark else "#495057"
        
        for index in range(self.tab_widget.count()):
            icon = self._load_colored_tab_icon(index)
            self.tab_widget.setTabIcon(index, icon)

    def _load_colored_tab_icon(self, index):
        """âœ… Load SVG icon with color based on theme for tabs"""
        # âœ… Tab Icons Mapping - matching sales summary pattern
        tab_icons = {
            0: "list_alt",      # List tab - list_alt.svg
            1: "category",      # Categories tab - category.svg
            2: "analytics"      # Charts tab - analytics.svg
        }
        
        icon_name = tab_icons.get(index, "")
        if not icon_name:
            return QIcon()
        
        # Try SVG first, then PNG
        paths = [
            f"assets/icons/{icon_name}.svg",
            f"assets/icons/{icon_name}.png",
        ]
        
        for path in paths:
            if os.path.exists(path):
                try:
                    pixmap = QPixmap(path)
                    if not pixmap.isNull():
                        # Scale to 20x20 for tab icon
                        scaled = pixmap.scaled(
                            20, 20,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        
                        # âœ… Color the icon based on theme
                        is_dark = is_dark_theme()
                        color_hex = "#ffffff" if is_dark else "#495057"
                        
                        # Create colored version
                        colored = scaled.copy()
                        painter = QPainter(colored)
                        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                        painter.fillRect(colored.rect(), QColor(color_hex))
                        painter.end()
                        
                        return QIcon(colored)
                except Exception as e:
                    print(f"Could not load icon {path}: {e}")
        
        return QIcon()
    
    def setup_ui(self):
        self.setObjectName("expensePage")
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(15)
        
        # ========== Cards (Using SummaryCardWidget with SVG icons) ==========
        card_layout = QHBoxLayout()
        card_layout.setSpacing(15)
        
        # âœ… Total Expenses Card - with SVG icon
        self.total_card = SummaryCardWidget(
            title="Total Expenses",
            value="0",
            icon="ðŸ“Š",  # Fallback emoji
            color="#e74c3c"
        )
        self.total_card.set_icon("total", size=(28, 28))  # SVG icon
        card_layout.addWidget(self.total_card, 1)
        
        # âœ… This Month Card - with SVG icon
        self.month_card = SummaryCardWidget(
            title="This Month",
            value="0",
            icon="ðŸ“…",  # Fallback emoji
            color="#f39c12"
        )
        self.month_card.set_icon("calendar_month", size=(28, 28))  # SVG icon
        card_layout.addWidget(self.month_card, 1)
        
        # âœ… Today Card - with SVG icon
        self.today_card = SummaryCardWidget(
            title="Today",
            value="0",
            icon="ðŸ“†",  # Fallback emoji
            color="#3498db"
        )
        self.today_card.set_icon("today", size=(28, 28))  # SVG icon
        card_layout.addWidget(self.today_card, 1)
        
        layout.addLayout(card_layout)
        
        # ========== Main Toolbar (Date + Buttons) ==========
        self.toolbar_card = QFrame()
        self.toolbar_card.setObjectName("expenseToolbarCard")
        toolbar_layout = QHBoxLayout(self.toolbar_card)
        toolbar_layout.setContentsMargins(14, 10, 14, 10)
        toolbar_layout.setSpacing(8)
        
        # âœ… DateRangeWidget
        self.date_range = DateRangeWidget()
        self.date_range.date_range_changed.connect(self.on_filter_changed)
        toolbar_layout.addWidget(self.date_range)
        
        toolbar_layout.addStretch()
        
        # âœ… Add button - Primary with SVG icon
        self.action_toolbar = ActionToolbar(self)
        self.btn_add = self.action_toolbar.add_primary(" Add", self.add_expense, "add", width=86)
        self.btn_edit = self.action_toolbar.add_primary(" Edit", self.edit_expense, "edit", ModernButton.SECONDARY, width=86)
        self.action_delete = self.action_toolbar.add_more_action("Delete", self.delete_expense, "delete")
        self.action_toolbar.add_separator()
        self.action_categories = self.action_toolbar.add_more_action("Categories", self.manage_categories, "category")
        self.action_budget = self.action_toolbar.add_more_action("Budget", self.open_budget_dialog, "savings")
        self.action_notifications = self.action_toolbar.add_more_action("Notifications", self.open_notification_settings, "notifications_active")
        self.action_compare = self.action_toolbar.add_more_action("Compare", self.open_comparison_dialog, "swap_horiz")
        self.action_toolbar.add_separator()
        self.action_export_excel = self.action_toolbar.add_more_action("Export Excel", self.export_to_excel, "file_export")
        self.action_export_category = self.action_toolbar.add_more_action("Export Category", self.export_category, "category")
        self.action_export_monthly = self.action_toolbar.add_more_action("Export Monthly", self.export_monthly, "calendar_month")
        self.action_toolbar.finalize()
        toolbar_layout.addWidget(self.action_toolbar, 0, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.toolbar_card)
        
        # ========== TAB WIDGET with Colored SVG Icons ==========
        logger.info("Creating tab widget for ExpensePage")
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("expenseTabs")
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setUsesScrollButtons(True)
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        self.tab_widget.setMinimumHeight(450)
        
        # âœ… Tab names for retranslation
        self.tab_names = {
            0: "List",
            1: "Categories",
            2: "Charts"
        }
        
        # âœ… Tab Icons Mapping
        self.tab_icons = {
            0: "list_alt",      # list_alt.svg
            1: "category",      # category.svg
            2: "analytics"      # analytics.svg
        }
        
        # === Tab 1: List (Table) ===
        self.table_tab = QWidget()
        table_layout = QVBoxLayout(self.table_tab)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(12)  # âœ… Increased spacing
        
        # âœ… Filter row inside List Tab - Compact layout with more padding
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)
        filter_layout.setContentsMargins(0, 8, 0, 8)  # âœ… Added top/bottom margin
        
        # SearchWidget - stretching 2 parts
        self.search_widget = SearchWidget(
            placeholder="Search by description or reference...",
            show_label=True
        )
        self.search_widget.search_changed.connect(self.on_filter_changed)
        filter_layout.addWidget(self.search_widget, 2)
        
        # âœ… Category filter - Compact with fixed widths
        category_label = QLabel("Category:")
        category_label.setFixedWidth(60)
        filter_layout.addWidget(category_label)
        
        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories")
        self.category_filter.currentTextChanged.connect(self.on_filter_changed)
        self.category_filter.setMaximumWidth(150)
        self.category_filter.setMinimumWidth(100)
        filter_layout.addWidget(self.category_filter, 1)
        
        filter_layout.addStretch()
        table_layout.addLayout(filter_layout)
        
        # Table
        self.table = ExpenseTable(self)
        self.table.expense_selected.connect(self.on_expense_selected)
        self.table.expense_double_clicked.connect(self.on_expense_double_clicked)
        table_layout.addWidget(self.table)
        
        # âœ… Add tab with colored icon
        self.tab_widget.addTab(self.table_tab, self._load_colored_tab_icon(0), self.tab_names[0])
        
        # === Tab 2: Categories ===
        logger.info("Creating category breakdown tab for ExpensePage")
        self.category_tab = ExpenseCategoryTab(self)
        self.category_tab.category_selected.connect(self.on_category_selected_from_tab)
        self.tab_widget.addTab(self.category_tab, self._load_colored_tab_icon(1), self.tab_names[1])
        
        # === Tab 3: Charts ===
        logger.info("Creating chart tab for ExpensePage")
        from ui.expense.expense_chart import ExpenseChartWidget
        self.chart_tab = ExpenseChartWidget(self)
        self.tab_widget.addTab(self.chart_tab, self._load_colored_tab_icon(2), self.tab_names[2])
        
        # âœ… Apply tab bar style for dark theme
        self._apply_tab_bar_style()
        
        # âœ… Add some spacing between tab bar and content
        self.tab_widget.setStyleSheet(self.tab_widget.styleSheet() + """
            QTabWidget::tab-bar {
                alignment: left;
            }
        """)
        
        layout.addWidget(self.tab_widget)
        
        # ========== Toast Notification ==========
        self.toast = ToastNotificationWidget(self)
        
        # ========== Loading Spinner ==========
        self.spinner = LoadingSpinnerWidget("Loading expenses...")
        self.spinner.hide()
        layout.addWidget(self.spinner)
        
        self.setLayout(layout)
        self._apply_page_style()
        logger.info("ExpensePage UI setup complete")

    def _apply_page_style(self):
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QWidget#expensePage {{ background: transparent; }}
            QFrame#expenseToolbarCard {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 12px;
            }}
        """)
    
    def load_initial_data(self):
        self.load_categories()
        self.load_expenses()
        self.update_cards()
        self.apply_card_style()
    
    def load_categories(self):
        """Load categories into filter"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM expense_categories ORDER BY name")
        rows = cursor.fetchall()
        self.category_filter.blockSignals(True)
        current = self.category_filter.currentText()
        self.category_filter.clear()
        self.category_filter.addItem("All Categories")
        for (name,) in rows:
            self.category_filter.addItem(name)
        idx = self.category_filter.findText(current)
        if idx >= 0:
            self.category_filter.setCurrentIndex(idx)
        self.category_filter.blockSignals(False)
        conn.close()
    
    def get_date_range(self):
        """Get date range from DateRangeWidget"""
        return self.date_range.get_from_date(), self.date_range.get_to_date()
    
    def get_search_text(self):
        """Get search text from SearchWidget"""
        return self.search_widget.get_text().lower()
    
    def get_category(self):
        """Get selected category"""
        return self.category_filter.currentText()
    
    def on_filter_changed(self):
        """Handle filter changes"""
        self.table.current_page = 1
        self.load_expenses()
    
    def load_expenses(self, page=1, page_size=25):
        """Load expenses with pagination"""
        self.spinner.start()
        
        search_text = self.get_search_text()
        category = self.get_category()
        from_date, to_date = self.get_date_range()
        symbol = get_currency_symbol()
        
        conn = connect_db()
        cursor = conn.cursor()
        
        base_query = "FROM expenses WHERE expense_date BETWEEN ? AND ?"
        params = [from_date, to_date]
        
        if search_text:
            base_query += " AND (LOWER(description) LIKE ? OR LOWER(reference_no) LIKE ?)"
            like = f'%{search_text}%'
            params.extend([like, like])
        
        if category != "All Categories":
            base_query += " AND category = ?"
            params.append(category)
        
        count_query = f"SELECT COUNT(*){base_query}"
        cursor.execute(count_query, params)
        total_items = cursor.fetchone()[0]
        self.table.pagination.set_total_items(total_items, emit_signal=False)
        
        offset = (page - 1) * page_size
        data_query = f"""
            SELECT id, expense_no, expense_date, category, description, 
                   amount, payment_method, reference_no, notes
            {base_query}
            ORDER BY expense_date DESC LIMIT ? OFFSET ?
        """
        cursor.execute(data_query, params + [page_size, offset])
        rows = cursor.fetchall()
        
        total_amount = sum(float(row[5] or 0) for row in rows) if rows else 0
        
        self.table.table.setRowCount(0)
        
        for row_idx, row_data in enumerate(rows):
            exp_id, exp_no, exp_date, cat, desc, amount, method, ref_no, notes = row_data
            exp_date_text = exp_date.isoformat() if hasattr(exp_date, "isoformat") else str(exp_date or "")
            amount_value = float(amount or 0)
            self.table.table.insertRow(row_idx)
            self.table.table.setItem(row_idx, 0, QTableWidgetItem(str(exp_id)))
            self.table.table.setItem(row_idx, 1, QTableWidgetItem(exp_no or ""))
            self.table.table.setItem(row_idx, 2, QTableWidgetItem(exp_date_text))
            self.table.table.setItem(row_idx, 3, QTableWidgetItem(cat or ""))
            self.table.table.setItem(row_idx, 4, QTableWidgetItem(desc or ""))
            
            amount_item = QTableWidgetItem(format_money(amount_value, symbol))
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.table.setItem(row_idx, 5, amount_item)
            
            self.table.table.setItem(row_idx, 6, QTableWidgetItem(method or ""))
            self.table.table.setItem(row_idx, 7, QTableWidgetItem(ref_no or ""))
            self.table.table.setItem(row_idx, 8, QTableWidgetItem(notes or ""))
            
            cursor.execute("SELECT COUNT(*) FROM expense_attachments WHERE expense_id = ?", (exp_id,))
            att_count = cursor.fetchone()[0]
            attachments_item = QTableWidgetItem(f"ðŸ“Ž {att_count}" if att_count > 0 else "")
            attachments_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.table.setItem(row_idx, 9, attachments_item)
        
        self.table.set_total_amount(total_amount)
        self.table.add_summary_row(len(rows), symbol)
        
        conn.close()
        
        self.update_cards()
        
        # âœ… Refresh chart with main page date range
        if hasattr(self, 'chart_tab') and hasattr(self.chart_tab, 'set_date_range') and hasattr(self.chart_tab, 'load_chart'):
            try:
                self.chart_tab.set_date_range(from_date, to_date)
                self.chart_tab.set_filters(category, search_text)
                self.chart_tab.load_chart()
            except Exception as e:
                logger.error(f"Error refreshing chart: {e}")
        
        # âœ… Refresh category tab with main page date range
        if hasattr(self, 'category_tab'):
            try:
                self.category_tab.set_date_range(from_date, to_date)
                self.category_tab.load_data()
            except Exception as e:
                logger.error(f"Error refreshing category tab: {e}")
        
        self.spinner.stop()
    
    def update_cards(self):
        """Update summary cards"""
        from_date, to_date = self.get_date_range()
        symbol = get_currency_symbol()
        
        conn = connect_db()
        cursor = conn.cursor()
        
        # Total Expenses
        cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses")
        total_all = cursor.fetchone()[0]
        self.total_card.set_value(format_money(total_all, symbol))
        
        # This Month
        today = QDate.currentDate()
        month_start = QDate(today.year(), today.month(), 1)
        month_start_str = month_start.toString("yyyy-MM-dd")
        month_end_str = today.toString("yyyy-MM-dd")
        cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE expense_date BETWEEN ? AND ?", 
                      (month_start_str, month_end_str))
        total_month = cursor.fetchone()[0]
        self.month_card.set_value(format_money(total_month, symbol))
        
        # Today
        today_str = today.toString("yyyy-MM-dd")
        cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE expense_date = ?", (today_str,))
        total_today = cursor.fetchone()[0]
        self.today_card.set_value(format_money(total_today, symbol))
        
        conn.close()
    
    def on_expense_selected(self, expense_id):
        self.table.selected_expense_id = expense_id
    
    def on_expense_double_clicked(self, expense_id, expense_no):
        from ui.expense_attachment_dialog import ExpenseAttachmentDialog
        dialog = ExpenseAttachmentDialog(expense_id, expense_no, self)
        dialog.exec()
    
    def on_category_selected_from_tab(self, category):
        """Handle category selection from category tab"""
        self.tab_widget.setCurrentIndex(0)
        
        if category:
            idx = self.category_filter.findText(category)
            if idx >= 0:
                self.category_filter.setCurrentIndex(idx)
            else:
                idx = self.category_filter.findText("All Categories")
                if idx >= 0:
                    self.category_filter.setCurrentIndex(idx)
        else:
            idx = self.category_filter.findText("All Categories")
            if idx >= 0:
                self.category_filter.setCurrentIndex(idx)
        
        self.on_filter_changed()
    
    def add_expense(self):
        dialog = ExpenseDialog(parent=self)
        if dialog.exec():
            self.load_expenses()
            self.load_categories()
            self.update_cards()
    
    def edit_expense(self):
        expense_id = self.table.get_selected_id()
        if not expense_id:
            QMessageBox.warning(self, "No Selection", "Please select an expense to edit.")
            return
        dialog = ExpenseDialog(expense_id, self)
        if dialog.exec():
            self.load_expenses()
            self.update_cards()
    
    def delete_expense(self):
        expense_id = self.table.get_selected_id()
        if not expense_id:
            QMessageBox.warning(self, "No Selection", "Please select an expense to delete.")
            return
        
        reply = QMessageBox.question(self, "Confirm Delete", "Delete this expense permanently?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            conn = connect_db()
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM expense_attachments WHERE expense_id = ?", (expense_id,))
                cursor.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
                conn.commit()
                self.table.clear_selection()
                self.load_expenses()
                self.update_cards()
                self.toast.show_toast("Expense deleted successfully.", "success")
            except Exception as e:
                conn.rollback()
                self.toast.show_toast(f"Could not delete: {e}", "error")
            finally:
                conn.close()
    
    def manage_categories(self):
        """Open manage categories dialog"""
        from ui.expense.expense_categories_dialog import ExpenseCategoriesDialog
        dialog = ExpenseCategoriesDialog(self)
        dialog.categories_changed.connect(self._on_categories_changed)
        dialog.exec()

    def _on_categories_changed(self):
        """Handle categories changed signal"""
        self.load_categories()
        self.load_expenses()
    
    def open_budget_dialog(self):
        dialog = ExpenseBudgetDialog(self)
        dialog.exec()
    
    def open_notification_settings(self):
        dialog = ExpenseNotificationDialog(self)
        dialog.exec()
    
    def open_comparison_dialog(self):
        dialog = ExpenseComparisonDialog(self)
        dialog.exec()
    
    def export_to_excel(self):
        from_date, to_date = self.get_date_range()
        category = self.get_category()
        search_text = self.get_search_text()
        ExpenseExport.export_expense_report(self, from_date, to_date, category, search_text)
    
    def export_category(self):
        from_date, to_date = self.get_date_range()
        ExpenseExport.export_category_report(self, from_date, to_date)
    
    def export_monthly(self):
        from_date, to_date = self.get_date_range()
        ExpenseExport.export_monthly_report(self, from_date, to_date)
    
    def apply_card_style(self):
        """Update card styles when theme changes"""
        self.total_card.update_theme()
        self.month_card.update_theme()
        self.today_card.update_theme()
    
    def get_current_theme(self):
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='theme'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "Light"
        except:
            return "Light"
    
    def on_language_changed(self, lang_code):
        logger.info(f"ExpensePage language changed to: {lang_code}")
        self.retranslateUi()
        self.load_expenses()
        self.update_cards()
    
    def retranslateUi(self):
        lang_code = lang.get_current()
        logger.info(f"ExpensePage retranslateUi: {lang_code}")
        
        # Retranslate summary cards
        if lang_code == "my":
            self.total_card.set_title("á€…á€¯á€…á€¯á€•á€±á€«á€„á€ºá€¸á€¡á€žá€¯á€¶á€¸á€…á€›á€­á€á€º")
            self.month_card.set_title("á€šá€á€¯á€œá€¡á€á€½á€„á€ºá€¸")
            self.today_card.set_title("á€šá€”á€±á€·")
            
            # Retranslate buttons
            self.btn_add.setText(" á€¡á€žá€…á€º")
            self.btn_edit.setText(" á€•á€¼á€„á€ºá€†á€„á€º")
            
            # Search placeholder
            self.search_widget.search_input.setPlaceholderText("á€–á€±á€¬á€ºá€•á€¼á€á€»á€€á€º á€žá€­á€¯á€·á€™á€Ÿá€¯á€á€º á€€á€­á€¯á€¸á€€á€¬á€¸á€¡á€™á€¾á€á€ºá€–á€¼á€„á€·á€º á€›á€¾á€¬á€›á€”á€º...")
            
            # âœ… Tab titles - Myanmar
            tab_titles_my = {
                0: "á€…á€¬á€›á€„á€ºá€¸",
                1: "á€¡á€™á€»á€­á€¯á€¸á€¡á€…á€¬á€¸á€™á€»á€¬á€¸",
                2: "á€‡á€šá€¬á€¸á€™á€»á€¬á€¸"
            }
            for idx, title in tab_titles_my.items():
                self.tab_widget.setTabText(idx, title)
        else:
            self.total_card.set_title("Total Expenses")
            self.month_card.set_title("This Month")
            self.today_card.set_title("Today")
            
            # Retranslate buttons
            self.btn_add.setText(" Add")
            self.btn_edit.setText(" Edit")
            
            # Search placeholder
            self.search_widget.search_input.setPlaceholderText("Search by description or reference...")
            
            # âœ… Tab titles - English
            for idx, title in self.tab_names.items():
                self.tab_widget.setTabText(idx, title)
        
        self.action_delete.setText("Delete")
        self.action_categories.setText("Categories")
        self.action_budget.setText("Budget")
        self.action_notifications.setText("Notifications")
        self.action_compare.setText("Compare")
        self.action_export_excel.setText("Export Excel")
        self.action_export_category.setText("Export Category")
        self.action_export_monthly.setText("Export Monthly")
        if hasattr(self, "action_toolbar"):
            self.action_toolbar.update_theme()
        
        # Retranslate widgets
        self.search_widget.retranslateUi(lang_code)
        self.date_range.retranslateUi(lang_code)
        self.table.retranslateUi(lang_code)
        
        # Update button icons for language change
        self.btn_add.set_icon("add", size=(14, 14))
        self.btn_edit.set_icon("edit", size=(14, 14))
        
        # âœ… Update tab icons color for language change
        self._update_tab_icons_color()
        
        # Retranslate tabs
        if hasattr(self, 'category_tab'):
            try:
                self.category_tab.retranslateUi()
            except Exception as e:
                logger.error(f"Error retranslating category tab: {e}")
        
        if hasattr(self, 'chart_tab') and hasattr(self.chart_tab, 'retranslateUi'):
            try:
                self.chart_tab.retranslateUi()
            except Exception as e:
                logger.error(f"Error retranslating chart: {e}")
    
    def showEvent(self, event):
        logger.info("ExpensePage showEvent called")
        self.load_expenses()
        self.update_cards()
        self.apply_card_style()
        # âœ… Update tab icons when shown
        self._apply_tab_bar_style()
        super().showEvent(event)


