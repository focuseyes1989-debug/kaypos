# ui/expense/expense_categories_dialog.py
"""
Expense Categories Management Dialog
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
    QTableWidget, QTableWidgetItem, QMessageBox, 
    QHeaderView, QLineEdit, QWidget, QLabel,
    QFrame, QInputDialog, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QIcon

from models.database import connect_db
from utils.language import lang
from loguru import logger

# ✅ Import components
from ui.widgets.modern_button import ModernButton
from ui.expense.add_category_dialog import AddCategoryDialog
from ui.expense.edit_category_dialog import EditCategoryDialog

# ✅ Import theme icon helpers
from ui.themes.theme_manager import get_themed_icon, get_active_themed_icon, theme_manager


class ExpenseCategoriesDialog(QDialog):
    """
    Dialog for managing expense categories.
    """
    
    categories_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Expense Categories" if lang.get_current() != "my" else "အသုံးစရိတ်အမျိုးအစားများ စီမံခန့်ခွဲရန်")
        self.setMinimumSize(700, 550)
        self.resize(750, 550)
        self.setModal(True)
        
        self._setup_ui()
        self._load_categories()
        self._apply_theme()
        
        # Connect theme change
        try:
            theme_manager.theme_changed.connect(self._on_theme_changed)
        except:
            pass
        
        # Connect language change
        lang.language_changed.connect(self._on_language_changed)
    
    def _get_icon(self, icon_name, use_active_color=False, size=(24, 24)):
        """Get themed SVG icon"""
        try:
            if use_active_color:
                return get_active_themed_icon(icon_name, size=size)
            else:
                return get_themed_icon(icon_name, size=size)
        except Exception as e:
            return QIcon()
    
    def _setup_ui(self):
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # ========== Header ==========
        self._setup_header(main_layout)
        
        # ========== Separator ==========
        self.sep_line = QFrame()
        self.sep_line.setFrameShape(QFrame.Shape.HLine)
        self.sep_line.setFrameShadow(QFrame.Shadow.Sunken)
        self.sep_line.setStyleSheet("background-color: #dee2e6; margin: 0px 0px 10px 0px;")
        main_layout.addWidget(self.sep_line)
        
        # ========== Categories Table ==========
        self._setup_table(main_layout)
        
        # ========== Bottom Buttons ==========
        self._setup_bottom_buttons(main_layout)
        
        self.setLayout(main_layout)
    
    def _setup_header(self, parent_layout):
        """Setup header section"""
        self.header_container = QWidget()
        self.header_container.setObjectName("header_container")
        self.header_container.setStyleSheet("""
            QWidget#header_container {
                background: transparent;
                padding: 8px 0px;
                margin-bottom: 2px;
            }
        """)
        
        header_layout = QHBoxLayout(self.header_container)
        header_layout.setContentsMargins(5, 5, 5, 5)
        
        # Left side - Icon and text
        left_layout = QVBoxLayout()
        left_layout.setSpacing(2)
        
        # Title with icon
        title_layout = QHBoxLayout()
        title_layout.setSpacing(10)
        
        # ✅ Icon using themed SVG
        self.header_icon_label = QLabel()
        icon = self._get_icon("category")
        if not icon.isNull():
            self.header_icon_label.setPixmap(icon.pixmap(QSize(24, 24)))
        else:
            self.header_icon_label.setText("📊")
            self.header_icon_label.setStyleSheet("font-size: 22px; background: transparent;")
        title_layout.addWidget(self.header_icon_label)
        
        self.header_title = QLabel("Manage Expense Categories" if lang.get_current() != "my" else "အသုံးစရိတ်အမျိုးအစားများ စီမံခန့်ခွဲရန်")
        self.header_title.setStyleSheet("""
            font-size: 15pt;
            font-weight: bold;
            color: #2c3e50;
            background: transparent;
        """)
        title_layout.addWidget(self.header_title)
        title_layout.addStretch()
        
        left_layout.addLayout(title_layout)
        
        self.header_subtitle = QLabel("Add, edit or delete expense categories" if lang.get_current() != "my" else "အသုံးစရိတ်အမျိုးအစားများ ထည့်ရန်၊ ပြင်ရန် သို့မဟုတ် ဖျက်ရန်")
        self.header_subtitle.setStyleSheet("""
            color: #6c757d;
            font-size: 9pt;
            padding-left: 34px;
            background: transparent;
        """)
        left_layout.addWidget(self.header_subtitle)
        
        header_layout.addLayout(left_layout, 1)
        
        # Right side - Category count
        self.count_label = QLabel()
        self.count_label.setStyleSheet("""
            background-color: #3498db;
            color: white;
            padding: 4px 14px;
            border-radius: 16px;
            font-size: 10pt;
            font-weight: 600;
        """)
        header_layout.addWidget(self.count_label)
        
        parent_layout.addWidget(self.header_container)
    
    def _setup_table(self, parent_layout):
        """Setup categories table"""
        table_container = QWidget()
        table_container.setStyleSheet("QWidget { background-color: transparent; border: none; }")
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels([
            "Category Name" if lang.get_current() != "my" else "အမျိုးအစားအမည်",
            "Actions" if lang.get_current() != "my" else "လုပ်ဆောင်ချက်များ"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 230)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.verticalHeader().setVisible(False)
        
        # Table style
        self._update_table_style()
        
        table_layout.addWidget(self.table)
        parent_layout.addWidget(table_container, 1)
    
    def _setup_bottom_buttons(self, parent_layout):
        """Setup bottom buttons - Compact with themed icons"""
        self.bottom_bar = QWidget()
        self.bottom_bar.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border-top: 1px solid #dee2e6;
                padding-top: 8px;
            }
        """)
        bottom_layout = QHBoxLayout(self.bottom_bar)
        bottom_layout.setContentsMargins(0, 8, 0, 0)
        bottom_layout.setSpacing(10)
        
        # ✅ Add Category Button - Primary (White icon in both themes)
        self.btn_add = ModernButton(
            " Add Category" if lang.get_current() != "my" else " အမျိုးအစားအသစ်ထည့်မည်", 
            ModernButton.PRIMARY
        )
        self.btn_add.set_icon("add", size=(16, 16))
        self.btn_add.set_compact(True)
        self.btn_add.setFixedSize(160, 32)
        self.btn_add.clicked.connect(self._show_add_category_dialog)
        bottom_layout.addWidget(self.btn_add)
        
        bottom_layout.addStretch()
        
        # ✅ Close Button - Secondary (Gray in Light, White in Dark)
        self.btn_close = ModernButton(
            " Close" if lang.get_current() != "my" else " ပိတ်မည်", 
            ModernButton.SECONDARY
        )
        self.btn_close.set_icon("close", size=(16, 16))
        self.btn_close.set_compact(True)
        self.btn_close.clicked.connect(self.accept)
        self.btn_close.setFixedSize(100, 32)
        bottom_layout.addWidget(self.btn_close)
        
        parent_layout.addWidget(self.bottom_bar)
    
    def _update_count_label(self):
        """Update the category count label"""
        count = self.table.rowCount()
        lang_code = lang.get_current()
        
        if lang_code == "my":
            self.count_label.setText(f"စုစုပေါင်း {count} မျိုး")
        else:
            self.count_label.setText(f"Total {count}")
    
    def _show_add_category_dialog(self):
        """Show the add category dialog"""
        dialog = AddCategoryDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            category_name = dialog.get_category_name()
            if category_name:
                self._add_category_to_db(category_name)
    
    def _add_category_to_db(self, name):
        """Add category to database"""
        conn = connect_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute("INSERT INTO expense_categories (name) VALUES (?)", (name,))
            conn.commit()
            
            self._load_categories()
            self.categories_changed.emit()
            
            logger.info(f"Added expense category: {name}")
            
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error" if lang.get_current() != "my" else "အမှား",
                               f"Could not add category: {e}" if lang.get_current() != "my" else f"အမျိုးအစားထည့်မရပါ: {e}")
        finally:
            conn.close()
        
        self._apply_theme()
    
    def _update_table_style(self):
        try:
            from ui.themes.theme_manager import is_dark_theme
            is_dark = is_dark_theme()
        except:
            is_dark = False
        
        if is_dark:
            self.table.setStyleSheet("""
                QTableWidget {
                    background-color: #2f3136;
                    alternate-background-color: #36393f;
                    selection-background-color: #40444b;
                    selection-color: #dcddde;
                    gridline-color: transparent;
                    border: 1px solid #40444b;
                    border-radius: 8px;
                    color: #dcddde;
                }
                QTableWidget::item {
                    padding: 6px 12px;
                    color: #dcddde;
                    border: none;
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
                    font-size: 9pt;
                    color: #b9bbbe;
                }
                QTableWidget::item:hover {
                    background-color: #40444b;
                }
            """)
            if hasattr(self, 'bottom_bar'):
                self.bottom_bar.setStyleSheet("""
                    QWidget {
                        background-color: transparent;
                        border-top: 1px solid #40444b;
                        padding-top: 8px;
                    }
                """)
            if hasattr(self, 'sep_line'):
                self.sep_line.setStyleSheet("background-color: #40444b; margin: 0px 0px 8px 0px;")
        else:
            self.table.setStyleSheet("""
                QTableWidget {
                    background-color: white;
                    alternate-background-color: #f8f9fa;
                    selection-background-color: #e3f2fd;
                    selection-color: #2c3e50;
                    gridline-color: transparent;
                    border: 1px solid #e9ecef;
                    border-radius: 8px;
                    color: #2c3e50;
                }
                QTableWidget::item {
                    padding: 6px 12px;
                    color: #2c3e50;
                    border: none;
                }
                QTableWidget::item:selected {
                    background-color: #e3f2fd;
                    color: #2c3e50;
                }
                QHeaderView::section {
                    background-color: #f8f9fa;
                    padding: 8px 12px;
                    border: none;
                    border-bottom: 2px solid #dee2e6;
                    font-weight: 600;
                    font-size: 9pt;
                    color: #2c3e50;
                }
                QTableWidget::item:hover {
                    background-color: #f1f3f5;
                }
            """)
            if hasattr(self, 'bottom_bar'):
                self.bottom_bar.setStyleSheet("""
                    QWidget {
                        background-color: transparent;
                        border-top: 1px solid #dee2e6;
                        padding-top: 8px;
                    }
                """)
            if hasattr(self, 'sep_line'):
                self.sep_line.setStyleSheet("background-color: #dee2e6; margin: 0px 0px 8px 0px;")
    
    def _apply_theme(self):
        """Apply theme to entire dialog"""
        self._update_table_style()
        
        try:
            from ui.themes.theme_manager import is_dark_theme
            is_dark = is_dark_theme()
        except:
            is_dark = False
        
        # Update header icon
        if hasattr(self, 'header_icon_label'):
            icon = self._get_icon("category")
            if not icon.isNull():
                self.header_icon_label.setPixmap(icon.pixmap(QSize(24, 24)))
            else:
                self.header_icon_label.setText("📊")
        
        # Header
        self.header_container.setStyleSheet("""
            QWidget#header_container {
                background: transparent;
                padding: 8px 0px;
                margin-bottom: 2px;
            }
        """)
        
        if is_dark:
            self.header_title.setStyleSheet("""
                font-size: 15pt;
                font-weight: bold;
                color: #dcddde;
                background: transparent;
            """)
            self.header_subtitle.setStyleSheet("""
                color: #b9bbbe;
                font-size: 9pt;
                padding-left: 34px;
                background: transparent;
            """)
            self.count_label.setStyleSheet("""
                background-color: #7289da;
                color: white;
                padding: 4px 14px;
                border-radius: 16px;
                font-size: 10pt;
                font-weight: 600;
            """)
        else:
            self.header_title.setStyleSheet("""
                font-size: 15pt;
                font-weight: bold;
                color: #2c3e50;
                background: transparent;
            """)
            self.header_subtitle.setStyleSheet("""
                color: #6c757d;
                font-size: 9pt;
                padding-left: 34px;
                background: transparent;
            """)
            self.count_label.setStyleSheet("""
                background-color: #3498db;
                color: white;
                padding: 4px 14px;
                border-radius: 16px;
                font-size: 10pt;
                font-weight: 600;
            """)
        
        self._update_count_label()
        
        # Update buttons - Compact
        if hasattr(self, 'btn_add'):
            self.btn_add.update_theme()
            self.btn_add.set_compact(True)
            self.btn_add.setFixedSize(160, 32)
        
        if hasattr(self, 'btn_close'):
            self.btn_close.update_theme()
            self.btn_close.set_compact(True)
            self.btn_close.setFixedSize(100, 32)
        
        # Update buttons in table cells
        for row in range(self.table.rowCount()):
            cell_widget = self.table.cellWidget(row, 1)
            if cell_widget:
                for child in cell_widget.findChildren(ModernButton):
                    if child:
                        child.update_theme()
                        child.set_compact(True)
        
        self.repaint()
        self.update()
    
    def _on_theme_changed(self, theme_name):
        self._apply_theme()
    
    def _on_language_changed(self, lang_code):
        self.retranslate_ui()
    
    def retranslate_ui(self):
        lang_code = lang.get_current()
        
        if lang_code == "my":
            self.setWindowTitle("အသုံးစရိတ်အမျိုးအစားများ စီမံခန့်ခွဲရန်")
            self.header_title.setText("အသုံးစရိတ်အမျိုးအစားများ စီမံခန့်ခွဲရန်")
            self.header_subtitle.setText("အသုံးစရိတ်အမျိုးအစားများ ထည့်ရန်၊ ပြင်ရန် သို့မဟုတ် ဖျက်ရန်")
            self.btn_add.setText(" အမျိုးအစားအသစ်ထည့်မည်")
            self.btn_close.setText(" ပိတ်မည်")
            self.table.setHorizontalHeaderLabels(["အမျိုးအစားအမည်", "လုပ်ဆောင်ချက်များ"])
        else:
            self.setWindowTitle("Manage Expense Categories")
            self.header_title.setText("Manage Expense Categories")
            self.header_subtitle.setText("Add, edit or delete expense categories")
            self.btn_add.setText(" Add Category")
            self.btn_close.setText(" Close")
            self.table.setHorizontalHeaderLabels(["Category Name", "Actions"])
        
        self._update_count_label()
        
        # Update buttons - Compact
        self.btn_add.update_theme()
        self.btn_add.set_compact(True)
        self.btn_add.setFixedSize(160, 32)
        self.btn_close.update_theme()
        self.btn_close.set_compact(True)
        self.btn_close.setFixedSize(100, 32)
        
        # Update buttons in table cells
        for row in range(self.table.rowCount()):
            cell_widget = self.table.cellWidget(row, 1)
            if cell_widget:
                for child in cell_widget.findChildren(ModernButton):
                    if child:
                        child.update_theme()
                        child.set_compact(True)
        
        self._load_categories()
        self.repaint()
        self.update()
    
    def _load_categories(self):
        """Load categories into table - Compact buttons with themed SVG icons"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM expense_categories ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        
        self.table.setRowCount(0)
        
        for row_idx, (cat_id, name) in enumerate(rows):
            self.table.insertRow(row_idx)
            
            # Category name with numbering
            name_item = QTableWidgetItem(f"{row_idx + 1}. {name}")
            name_item.setData(Qt.ItemDataRole.UserRole, cat_id)
            self.table.setItem(row_idx, 0, name_item)
            
            # Actions widget - Compact
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)
            
            # ✅ Edit button - Secondary (Gray in Light, White in Dark)
            btn_edit = ModernButton(
                " Edit" if lang.get_current() != "my" else " ပြင်ဆင်", 
                ModernButton.SECONDARY
            )
            btn_edit.set_icon("edit", size=(14, 14))
            btn_edit.set_compact(True)
            btn_edit.setFixedSize(72, 30)
            btn_edit.clicked.connect(lambda checked, cid=cat_id, cname=name: self._edit_category(cid, cname))
            actions_layout.addWidget(btn_edit)
            
            # ✅ Delete button - Primary (White icon in both themes)
            btn_delete = ModernButton(
                " Delete" if lang.get_current() != "my" else " ဖျက်", 
                ModernButton.PRIMARY
            )
            btn_delete.set_icon("delete", size=(14, 14))
            btn_delete.set_compact(True)
            btn_delete.setFixedSize(76, 30)
            # Keep delete button red
            btn_delete.setStyleSheet("""
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    font-size: 9pt;
                    font-weight: 500;
                    padding: 4px 10px;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
                QPushButton:pressed {
                    background-color: #a93226;
                }
            """)
            btn_delete.clicked.connect(lambda checked, cid=cat_id: self._delete_category(cid))
            actions_layout.addWidget(btn_delete)
            
            actions_layout.addStretch()
            self.table.setCellWidget(row_idx, 1, actions_widget)
        
        self._update_count_label()
    
    def _edit_category(self, cat_id, old_name):
        """Edit category using custom dialog"""
        dialog = EditCategoryDialog(cat_id, old_name, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name = dialog.get_category_name()
            if new_name:
                self._update_category_in_db(cat_id, old_name, new_name)
    
    def _update_category_in_db(self, cat_id, old_name, new_name):
        """Update category in database"""
        conn = connect_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute("UPDATE expense_categories SET name = ? WHERE id = ?", (new_name, cat_id))
            conn.commit()
            
            self._load_categories()
            self.categories_changed.emit()
            
            logger.info(f"Updated expense category: {old_name} -> {new_name}")
            
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error" if lang.get_current() != "my" else "အမှား",
                               f"Could not update category: {e}" if lang.get_current() != "my" else f"အမျိုးအစား ပြင်ဆင်မရပါ: {e}")
        finally:
            conn.close()
        
        self._apply_theme()
    
    def _delete_category(self, cat_id):
        """Delete category"""
        lang_code = lang.get_current()
        
        if lang_code == "my":
            confirm = QMessageBox.question(
                self, "ဖျက်ရန် အတည်ပြုပါ",
                "ဤအမျိုးအစားကို ဖျက်မည်လား?\nဤအမျိုးအစားသုံးထားသော အသုံးစရိတ်များကိုလည်း ဖျက်ပစ်မည်။",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
        else:
            confirm = QMessageBox.question(
                self, "Confirm Delete",
                "Delete this category?\nExpenses using this category will also be deleted.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
        
        if confirm != QMessageBox.StandardButton.Yes:
            return
        
        conn = connect_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT name FROM expense_categories WHERE id = ?", (cat_id,))
            row = cursor.fetchone()
            cat_name = row[0] if row else "Unknown"
            
            cursor.execute("DELETE FROM expenses WHERE category = ?", (cat_name,))
            cursor.execute("DELETE FROM expense_categories WHERE id = ?", (cat_id,))
            conn.commit()
            
            self._load_categories()
            self.categories_changed.emit()
            
            logger.info(f"Deleted expense category: {cat_name}")
            
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error" if lang_code != "my" else "အမှား",
                               f"Could not delete category: {e}" if lang_code != "my" else f"အမျိုးအစား ဖျက်မရပါ: {e}")
        finally:
            conn.close()
        
        self._apply_theme()