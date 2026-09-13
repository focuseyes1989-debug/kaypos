from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QMessageBox, 
    QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from models.database import connect_db
from utils.branded_icons import pos_icon


class ExpenseCategoriesDialog(QDialog):
    # Add signal to notify parent that categories have changed
    categories_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Expense Categories")
        self.setWindowIcon(pos_icon())
        self.setMinimumSize(400, 500)
        self.setModal(True)

        layout = QVBoxLayout()

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search category...")
        self.search_input.textChanged.connect(self.filter_categories)
        layout.addWidget(self.search_input)

        # Category list
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Add Category")
        self.btn_edit = QPushButton("Edit")
        self.btn_delete = QPushButton("Delete")
        self.btn_add.clicked.connect(self.add_category)
        self.btn_edit.clicked.connect(self.edit_category)
        self.btn_delete.clicked.connect(self.delete_category)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        
        self.load_categories()
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
        if lang == "my":
            self.setWindowTitle("အသုံးစရိတ်အမျိုးအစားများ စီမံရန်")
            self.search_input.setPlaceholderText("အမျိုးအစားရှာရန်...")
            self.btn_add.setText("အသစ်ထည့်")
            self.btn_edit.setText("ပြင်ဆင်")
            self.btn_delete.setText("ဖျက်")
        else:
            self.setWindowTitle("Manage Expense Categories")
            self.search_input.setPlaceholderText("Search category...")
            self.btn_add.setText("Add Category")
            self.btn_edit.setText("Edit")
            self.btn_delete.setText("Delete")

    def load_categories(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM expense_categories ORDER BY name")
        self.all_categories = cursor.fetchall()
        conn.close()
        self.filter_categories()

    def filter_categories(self):
        search_text = self.search_input.text().strip().lower()
        
        self.list_widget.clear()
        
        for cat_id, name in self.all_categories:
            if search_text and search_text not in name.lower():
                continue
            
            item = QListWidgetItem(name)
            item.setData(1, cat_id)
            item.setData(2, name)
            self.list_widget.addItem(item)

    def get_current_category(self):
        current = self.list_widget.currentItem()
        if current:
            cat_id = current.data(1)
            name = current.data(2)
            return cat_id, name
        return None, None

    def add_category(self):
        name, ok = QInputDialog.getText(self, "Add Category", "Category name:")
        if ok and name.strip():
            conn = connect_db()
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO expense_categories (name) VALUES (?)", (name.strip(),))
                conn.commit()
                QMessageBox.information(self, "Success", "Category added successfully.")
                self.load_categories()
                # Emit signal to notify parent
                self.categories_changed.emit()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Cannot add: {e}")
            finally:
                conn.close()

    def edit_category(self):
        cat_id, old_name = self.get_current_category()
        if not cat_id:
            QMessageBox.warning(self, "No Selection", "Please select a category to edit.")
            return
        
        new_name, ok = QInputDialog.getText(self, "Edit Category", "New name:", text=old_name)
        if ok and new_name.strip():
            conn = connect_db()
            cursor = conn.cursor()
            try:
                cursor.execute("UPDATE expense_categories SET name = ? WHERE id = ?", (new_name.strip(), cat_id))
                conn.commit()
                QMessageBox.information(self, "Success", "Category updated successfully.")
                self.load_categories()
                # Emit signal to notify parent
                self.categories_changed.emit()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Cannot update: {e}")
            finally:
                conn.close()

    def delete_category(self):
        cat_id, name = self.get_current_category()
        if not cat_id:
            QMessageBox.warning(self, "No Selection", "Please select a category to delete.")
            return
        
        # Check if category has expenses
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM expenses WHERE category = ?", (name,))
        count = cursor.fetchone()[0]
        conn.close()
        
        if count > 0:
            lang = self.get_lang()
            msg = f"This category has {count} expense(s). Please delete them first." if lang != "my" else f"ဤအမျိုးအစားတွင် အသုံးစရိတ် {count} ခုရှိပါသည်။ ဦးစွာဖျက်ပါ။"
            QMessageBox.warning(self, "Cannot Delete", msg)
            return
        
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete '{name}' permanently?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            conn = connect_db()
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM expense_categories WHERE id = ?", (cat_id,))
                conn.commit()
                self.load_categories()
                # Emit signal to notify parent
                self.categories_changed.emit()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Cannot delete: {e}")
            finally:
                conn.close()
