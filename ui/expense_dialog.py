from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLabel, QLineEdit, QComboBox, 
    QDoubleSpinBox, QDateEdit, QTextEdit, QPushButton, 
    QMessageBox, QVBoxLayout, QHBoxLayout, QListWidget, 
    QListWidgetItem, QWidget, QFrame
)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QIcon
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from datetime import datetime
from utils.branded_icons import pos_icon


class ExpenseDialog(QDialog):
    def __init__(self, expense_id=None, parent=None):
        super().__init__(parent)
        self.expense_id = expense_id
        self.setWindowTitle("Edit Expense" if expense_id else "Add Expense")
        self.setMinimumWidth(800)
        self.setMinimumHeight(550)
        self.setWindowIcon(pos_icon())
        self.setModal(True)

        main_layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("Expense Information")
        title_label.setStyleSheet("font-size: 14pt; font-weight: bold; margin-bottom: 10px;")
        main_layout.addWidget(title_label)
        
        # Two column layout
        two_column_layout = QHBoxLayout()
        two_column_layout.setSpacing(20)
        
        # ========== LEFT COLUMN: Category Selection ==========
        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        
        # Category section title
        category_title = QLabel("Select Category")
        category_title.setStyleSheet("font-size: 12pt; font-weight: bold; margin-bottom: 5px;")
        left_layout.addWidget(category_title)
        
        # Search box for category
        self.category_search = QLineEdit()
        self.category_search.setPlaceholderText("Search category...")
        self.category_search.textChanged.connect(self.filter_categories)
        left_layout.addWidget(self.category_search)
        
        # Category list widget
        self.category_list = QListWidget()
        self.category_list.setMinimumHeight(350)
        self.category_list.itemClicked.connect(self.on_category_selected)
        left_layout.addWidget(self.category_list, 1)
        
        # Selected category display (no border)
        self.selected_category_label = QLabel("Selected Category: None")
        self.selected_category_label.setStyleSheet("color: #27ae60; font-weight: bold; margin-top: 5px;")
        left_layout.addWidget(self.selected_category_label)
        
        # ========== RIGHT COLUMN: Form ==========
        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)
        
        # Form section title
        form_title = QLabel("Expense Details")
        form_title.setStyleSheet("font-size: 12pt; font-weight: bold; margin-bottom: 5px;")
        right_layout.addWidget(form_title)
        
        # Form layout
        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Expense Number (auto-generated)
        self.expense_no = QLineEdit()
        self.expense_no.setReadOnly(True)
        if not expense_id:
            self.expense_no.setText(f"EXP-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        form_layout.addRow(QLabel("Expense No:"), self.expense_no)

        # Description
        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("What was this expense for?")
        form_layout.addRow(QLabel("Description:"), self.description_input)

        # Amount
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0, 99999999)
        self.amount_input.setDecimals(0)
        symbol = get_currency_symbol()
        self.amount_input.setPrefix(f"{symbol} ")
        form_layout.addRow(QLabel("Amount:"), self.amount_input)

        # Expense Date
        self.expense_date = QDateEdit()
        self.expense_date.setCalendarPopup(True)
        self.expense_date.setDate(QDate.currentDate())
        form_layout.addRow(QLabel("Expense Date:"), self.expense_date)

        # Payment Method
        self.payment_method = QComboBox()
        self.payment_method.addItems(["Cash", "Bank Transfer", "Cheque", "Mobile Money", "Credit Card"])
        form_layout.addRow(QLabel("Payment Method:"), self.payment_method)

        # Reference Number
        self.reference_no = QLineEdit()
        self.reference_no.setPlaceholderText("Receipt/Invoice/Cheque number")
        form_layout.addRow(QLabel("Reference No:"), self.reference_no)

        # Notes
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        form_layout.addRow(QLabel("Notes:"), self.notes)
        
        right_layout.addLayout(form_layout)
        right_layout.addStretch()
        
        # ========== Buttons (Discord Style) ==========
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_save = QPushButton("Save")
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #5865f2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 25px;
                font-weight: 500;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #4752c4;
            }
        """)
        self.btn_save.clicked.connect(self.save_expense)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #40444b;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 25px;
                font-weight: 500;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #5865f2;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        
        right_layout.addLayout(btn_layout)
        
        # ========== Add both columns ==========
        two_column_layout.addWidget(left_column, 1)
        two_column_layout.addWidget(right_column, 1)
        
        main_layout.addLayout(two_column_layout)
        
        self.setLayout(main_layout)

        # Load categories
        self.all_categories = []
        self.selected_category = None
        self.load_categories()
        
        if expense_id:
            self.load_expense_data()
        
        self.retranslateUi()

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
        
        if lang == "my":
            self.setWindowTitle("အသုံးစရိတ်ပြင်ဆင်ရန်" if self.expense_id else "အသုံးစရိတ်အသစ်")
            self.category_search.setPlaceholderText("အမျိုးအစားရှာရန်...")
            self.amount_input.setPrefix(f"{symbol} ")
            self.btn_save.setText("သိမ်းဆည်းမည်")
            self.btn_cancel.setText("မလုပ်တော့")
            self.selected_category_label.setText(f"ရွေးထားသောအမျိုးအစား: {self.selected_category if self.selected_category else 'မရှိပါ'}")
        else:
            self.setWindowTitle("Edit Expense" if self.expense_id else "Add Expense")
            self.category_search.setPlaceholderText("Search category...")
            self.amount_input.setPrefix(f"{symbol} ")
            self.btn_save.setText("Save")
            self.btn_cancel.setText("Cancel")
            self.selected_category_label.setText(f"Selected Category: {self.selected_category if self.selected_category else 'None'}")

    def load_categories(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM expense_categories ORDER BY name")
        self.all_categories = cursor.fetchall()
        conn.close()
        self.filter_categories()

    def filter_categories(self):
        search_text = self.category_search.text().strip().lower()
        self.category_list.clear()
        
        for cat_id, name in self.all_categories:
            if search_text and search_text not in name.lower():
                continue
            
            item = QListWidgetItem(name)
            item.setData(1, cat_id)
            item.setData(2, name)
            self.category_list.addItem(item)

    def on_category_selected(self, item):
        cat_id = item.data(1)
        cat_name = item.data(2)
        self.selected_category = cat_name
        lang = self.get_lang()
        if lang == "my":
            self.selected_category_label.setText(f"ရွေးထားသောအမျိုးအစား: {cat_name}")
        else:
            self.selected_category_label.setText(f"Selected Category: {cat_name}")
        self.selected_category_label.setStyleSheet("color: #27ae60; font-weight: bold; margin-top: 5px;")

    def load_expense_data(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT expense_no, category, description, amount, expense_date, 
                   payment_method, reference_no, notes
            FROM expenses WHERE id = ?
        """, (self.expense_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            self.expense_no.setText(row[0])
            self.selected_category = row[1]
            lang = self.get_lang()
            if lang == "my":
                self.selected_category_label.setText(f"ရွေးထားသောအမျိုးအစား: {row[1] if row[1] else 'မရှိပါ'}")
            else:
                self.selected_category_label.setText(f"Selected Category: {row[1] if row[1] else 'None'}")
            self.description_input.setText(row[2] or "")
            self.amount_input.setValue(row[3] if row[3] else 0)
            self.expense_date.setDate(QDate.fromString(row[4], "yyyy-MM-dd"))
            idx = self.payment_method.findText(row[5] if row[5] else "Cash")
            if idx >= 0:
                self.payment_method.setCurrentIndex(idx)
            self.reference_no.setText(row[6] or "")
            self.notes.setPlainText(row[7] or "")

    def check_budget_warning(self, category, amount, expense_date):
        """Check if expense exceeds budget and show warning"""
        expense_qdate = QDate.fromString(expense_date, "yyyy-MM-dd")
        month = expense_qdate.month()
        year = expense_qdate.year()
        
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT budget_amount FROM expense_budgets 
            WHERE category = ? AND month = ? AND year = ?
        """, (category, month, year))
        row = cursor.fetchone()
        
        if row and row[0] > 0:
            budget = row[0]
            
            month_start = f"{year}-{month:02d}-01"
            if month == 12:
                month_end = f"{year+1}-01-01"
            else:
                month_end = f"{year}-{month+1:02d}-01"
            
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM expenses
                WHERE category = ? AND expense_date >= ? AND expense_date < ?
            """, (category, month_start, month_end))
            total_before = cursor.fetchone()[0]
            conn.close()
            
            total_after = total_before + amount
            
            if total_after > budget:
                symbol = get_currency_symbol()
                lang = self.get_lang()
                used_percent = (total_after / budget) * 100
                
                if lang == "my":
                    msg = (f"⚠️ ဘတ်ဂျက်သတိပေးချက်!\n\n"
                           f"အမျိုးအစား: {category}\n"
                           f"ဘတ်ဂျက်: {format_money(budget, symbol)}\n"
                           f"လက်ရှိစုစုပေါင်း: {format_money(total_before, symbol)}\n"
                           f"ဤအသုံးစရိတ်: {format_money(amount, symbol)}\n"
                           f"အသစ်စုစုပေါင်း: {format_money(total_after, symbol)}\n"
                           f"အသုံးပြုမှု: {used_percent:.1f}%\n\n"
                           f"ဆက်လုပ်မည်လား?")
                else:
                    msg = (f"⚠️ Budget Warning!\n\n"
                           f"Category: {category}\n"
                           f"Budget: {format_money(budget, symbol)}\n"
                           f"Current Total: {format_money(total_before, symbol)}\n"
                           f"This expense: {format_money(amount, symbol)}\n"
                           f"New Total: {format_money(total_after, symbol)}\n"
                           f"Usage: {used_percent:.1f}%\n\n"
                           f"Are you sure you want to proceed?")
                
                reply = QMessageBox.warning(self, "Budget Warning", msg,
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                return reply == QMessageBox.StandardButton.Yes
        
        return True

    def save_expense(self):
        category = self.selected_category
        description = self.description_input.text().strip()
        amount = self.amount_input.value()
        expense_date = self.expense_date.date().toString("yyyy-MM-dd")
        payment_method = self.payment_method.currentText()
        reference_no = self.reference_no.text().strip()
        notes = self.notes.toPlainText().strip()
        lang = self.get_lang()

        if not category:
            QMessageBox.warning(self, "Error", "Please select a category.")
            return
        
        if amount <= 0:
            QMessageBox.warning(self, "Error", "Please enter a valid amount.")
            return

        # Check budget warning
        if not self.check_budget_warning(category, amount, expense_date):
            return

        conn = connect_db()
        cursor = conn.cursor()
        try:
            if self.expense_id:
                # Update existing expense
                cursor.execute("""
                    UPDATE expenses 
                    SET category = ?, description = ?, amount = ?, expense_date = ?,
                        payment_method = ?, reference_no = ?, notes = ?
                    WHERE id = ?
                """, (category, description, amount, expense_date, payment_method, reference_no, notes, self.expense_id))
                msg = "Expense updated successfully." if lang != "my" else "အသုံးစရိတ် ပြင်ဆင်ပြီးပါပြီ။"
            else:
                # Insert new expense
                expense_no = self.expense_no.text()
                cursor.execute("""
                    INSERT INTO expenses (expense_no, category, description, amount, expense_date, 
                                         payment_method, reference_no, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (expense_no, category, description, amount, expense_date, payment_method, reference_no, notes))
                msg = "Expense recorded successfully." if lang != "my" else "အသုံးစရိတ် သိမ်းဆည်းပြီးပါပြီ။"
            
            conn.commit()
            QMessageBox.information(self, "Success", msg)
            self.accept()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save expense: {e}")
        finally:
            conn.close()

