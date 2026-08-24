# ui/expense/expense_table.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from ui.widgets.pagination_widget import PaginationWidget
from utils.currency import format_money, get_currency_symbol


class ExpenseTable(QWidget):
    """Expense table with pagination"""
    
    expense_selected = pyqtSignal(int)
    expense_double_clicked = pyqtSignal(int, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_page = 1
        self.page_size = 25
        self.selected_expense_id = None
        self.total_amount = 0
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "ID", "Expense No", "Date", "Category", "Description", 
            "Amount", "Payment Method", "Reference", "Notes", "Attachments"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.cellClicked.connect(self.on_cell_clicked)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        self.table.setColumnHidden(0, True)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.ResizeToContents)
        
        layout.addWidget(self.table)
        
        self.pagination = PaginationWidget()
        self.pagination.page_changed.connect(self.on_page_changed)
        layout.addWidget(self.pagination)
        
        self.setLayout(layout)
    
    def on_cell_clicked(self, row, col):
        """Handle cell click - ignore summary row"""
        id_item = self.table.item(row, 0)
        if id_item:
            id_text = id_item.text()
            # Skip summary row (TOTAL row)
            if id_text == "TOTAL":
                return
            try:
                self.selected_expense_id = int(id_text)
                self.expense_selected.emit(self.selected_expense_id)
            except ValueError:
                # If not a valid integer, ignore
                pass
    
    def on_cell_double_clicked(self, row, col):
        """Handle cell double click - ignore summary row"""
        id_item = self.table.item(row, 0)
        if id_item:
            id_text = id_item.text()
            # Skip summary row (TOTAL row)
            if id_text == "TOTAL":
                return
            try:
                expense_id = int(id_text)
                expense_no_item = self.table.item(row, 1)
                expense_no = expense_no_item.text() if expense_no_item else ""
                self.expense_double_clicked.emit(expense_id, expense_no)
            except ValueError:
                # If not a valid integer, ignore
                pass
    
    def on_page_changed(self, page, page_size):
        self.current_page = page
        self.page_size = page_size
        if hasattr(self.parent(), 'load_expenses'):
            self.parent().load_expenses(page, page_size)
    
    def get_selected_id(self):
        return self.selected_expense_id
    
    def clear_selection(self):
        self.selected_expense_id = None
        self.table.clearSelection()
    
    def set_total_amount(self, total):
        """Set the total amount for the summary row"""
        self.total_amount = total
    
    def add_summary_row(self, row_count, symbol=None):
        """Add a summary row at the bottom of the table"""
        if symbol is None:
            symbol = get_currency_symbol()
        
        # Check if summary row already exists and remove it
        if self.table.rowCount() > 0:
            last_row = self.table.rowCount() - 1
            id_item = self.table.item(last_row, 0)
            if id_item and id_item.text() == "TOTAL":
                self.table.removeRow(last_row)
        
        # Add summary row
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Create bold font
        bold_font = QFont()
        bold_font.setBold(True)
        
        # ID column (hidden) - use "TOTAL" to identify summary row
        id_item = QTableWidgetItem("TOTAL")
        id_item.setFont(bold_font)
        self.table.setItem(row, 0, id_item)
        
        # Empty columns
        for col in [1, 2, 3, 6, 7, 8, 9]:
            item = QTableWidgetItem("")
            item.setFont(bold_font)
            self.table.setItem(row, col, item)
        
        # Description column
        lang_code = self._get_lang()
        if lang_code == "my":
            desc_item = QTableWidgetItem("စုစုပေါင်း")
        else:
            desc_item = QTableWidgetItem("TOTAL")
        desc_item.setFont(bold_font)
        desc_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, 4, desc_item)
        
        # Amount column - normal color (no red/green)
        amount_item = QTableWidgetItem(format_money(self.total_amount, symbol))
        amount_item.setFont(bold_font)
        amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, 5, amount_item)
        
        # Make the summary row non-selectable
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
    
    def _get_lang(self):
        """Get current language"""
        try:
            from models.database import connect_db
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='language'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "en"
        except:
            return "en"
    
    def retranslateUi(self, lang_code):
        if lang_code == "my":
            self.table.setHorizontalHeaderLabels([
                "ID", "အမှတ်", "ရက်စွဲ", "အမျိုးအစား", "ဖော်ပြချက်", 
                "ပမာဏ", "ငွေပေးချေမှုနည်းလမ်း", "ကိုးကားအမှတ်", "မှတ်ချက်", "ပူးတွဲဖိုင်"
            ])
        else:
            self.table.setHorizontalHeaderLabels([
                "ID", "Expense No", "Date", "Category", "Description", 
                "Amount", "Payment Method", "Reference", "Notes", "Attachments"
            ])
        
        # Update summary row if exists
        if self.table.rowCount() > 0:
            last_row = self.table.rowCount() - 1
            id_item = self.table.item(last_row, 0)
            if id_item and id_item.text() == "TOTAL":
                desc_item = self.table.item(last_row, 4)
                if desc_item:
                    if lang_code == "my":
                        desc_item.setText("စုစုပေါင်း")
                    else:
                        desc_item.setText("TOTAL")
