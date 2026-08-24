# ui/inventory_page/warehouse_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QInputDialog, QHeaderView, QLineEdit,
    QLabel, QGroupBox, QFrame, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QColor, QPixmap, QPainter
from models.database import connect_db
from utils.language import lang
from ui.widgets.modern_button import ModernButton
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
from loguru import logger
import os


class WarehouseDialog(QDialog):
    """Manage warehouse/location for products - Theme-aware with SVG icons"""
    warehouses_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dark = is_dark_theme()
        
        self.setWindowTitle("Manage Locations")
        self.setMinimumSize(700, 500)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setModal(True)
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Top section: Add new location
        top_group = QGroupBox("Add New Location")
        colors = get_theme_colors()
        top_group.setStyleSheet(self._get_groupbox_style(colors))
        
        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)
        top_layout.setContentsMargins(15, 10, 15, 10)
        
        self.location_name = QLineEdit()
        self.location_name.setPlaceholderText("Enter location name (e.g., Shelf A1, Warehouse 1)")
        self.location_name.setStyleSheet(self._get_line_edit_style(colors))
        top_layout.addWidget(self.location_name, 2)
        
        # ✅ Add Location button with SVG icon
        self.btn_add_location = ModernButton("", ModernButton.PRIMARY)
        self.btn_add_location.set_icon("add", size=(16, 16))
        self.btn_add_location.set_compact(False)
        self.btn_add_location.clicked.connect(self.add_location)
        top_layout.addWidget(self.btn_add_location)
        
        top_group.setLayout(top_layout)
        layout.addWidget(top_group)
        
        # Location table - NO custom style, use PyQt6 default
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Location Name", "Product Count"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setColumnHidden(0, True)
        self.table.setAlternatingRowColors(True)
        
        # ✅ NO custom table style
        # self._update_table_style(colors)  <-- ဒီ line ကို ဖယ်ရှားပါ
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)
        
        # Bottom buttons with SVG icons
        button_frame = QFrame()
        button_frame.setObjectName("button_frame")
        button_frame.setStyleSheet(self._get_button_frame_style(colors))
        
        btn_layout = QHBoxLayout(button_frame)
        btn_layout.setSpacing(12)
        btn_layout.setContentsMargins(15, 8, 15, 8)
        
        # ✅ Edit button with SVG icon
        self.btn_edit = ModernButton("", ModernButton.SECONDARY)
        self.btn_edit.set_icon("edit", size=(16, 16))
        self.btn_edit.set_compact(False)
        self.btn_edit.clicked.connect(self.edit_location)
        btn_layout.addWidget(self.btn_edit)
        
        # ✅ Delete Button with SVG icon - Override with red color
        self.btn_delete = ModernButton("", ModernButton.PRIMARY)
        self.btn_delete.set_icon("delete", size=(16, 16))
        self.btn_delete.set_compact(False)
        self.btn_delete.clicked.connect(self.delete_location)
        self.btn_delete.setStyleSheet(self._get_delete_button_style())
        btn_layout.addWidget(self.btn_delete)
        
        btn_layout.addStretch()
        
        # ✅ Close button with SVG icon
        self.btn_close = ModernButton("Close", ModernButton.SECONDARY)
        self.btn_close.set_icon("close", size=(16, 16))
        self.btn_close.set_compact(False)
        self.btn_close.setFixedSize(112, 38)
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        
        layout.addWidget(button_frame)
        
        self.setLayout(layout)
        
        # Apply initial theme
        self._apply_theme()
        
        self.load_locations()
        self.retranslateUi()
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
        self._update_button_icons()
        self.load_locations()
    
    def _update_button_icons(self):
        """Update button icons when theme changes"""
        self.btn_add_location.set_icon("add", size=(16, 16))
        self.btn_edit.set_icon("edit", size=(16, 16))
        self.btn_delete.set_icon("delete", size=(16, 16))
        self.btn_close.set_icon("close", size=(16, 16))
    
    def _apply_theme(self):
        """Apply theme-aware styles"""
        colors = get_theme_colors()
        
        # Dialog background
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
            }}
        """)
        
        # Update groupbox
        top_group = self.findChild(QGroupBox)
        if top_group:
            top_group.setStyleSheet(self._get_groupbox_style(colors))
        
        # Update button frame
        button_frame = self.findChild(QFrame, "button_frame")
        if button_frame:
            button_frame.setStyleSheet(self._get_button_frame_style(colors))
        
        # Update input
        if hasattr(self, 'location_name'):
            self.location_name.setStyleSheet(self._get_line_edit_style(colors))
        
        # ✅ NO table style update - use PyQt6 default
        # self._update_table_style(colors)  <-- ဒီ line ကို ဖယ်ရှားပါ
        
        # Update delete button
        self.btn_delete.setStyleSheet(self._get_delete_button_style())
        
        # Update button icons
        self._update_button_icons()
    
    def _get_groupbox_style(self, colors):
        return f"""
            QGroupBox {{
                font-weight: 600;
                font-size: 10pt;
                border: 1px solid {colors['border']};
                border-radius: 8px;
                padding-top: 10px;
                margin-top: 5px;
                color: {colors['text']};
                background-color: {colors['card_bg']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: {colors['text']};
            }}
        """
    
    def _get_button_frame_style(self, colors):
        return f"""
            QFrame#button_frame {{
                background: {colors['bg_hover']};
                border-radius: 8px;
                padding: 5px;
            }}
        """
    
    def _get_line_edit_style(self, colors):
        return f"""
            QLineEdit {{
                padding: 8px 12px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
            }}
            QLineEdit:focus {{
                border-color: #5865f2;
            }}
            QLineEdit::placeholder {{
                color: {colors['text_secondary']};
            }}
        """
    
    def _get_delete_button_style(self):
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        if is_dark:
            return """
                QPushButton {
                    background-color: #ed4245;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 5px 16px;
                    font-weight: 500;
                    font-size: 9pt;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
                QPushButton:pressed {
                    background-color: #a93226;
                }
            """
        else:
            return """
                QPushButton {
                    background-color: #e74c3c;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 5px 16px;
                    font-weight: 500;
                    font-size: 9pt;
                }
                QPushButton:hover {
                    background-color: #c0392b;
                }
                QPushButton:pressed {
                    background-color: #a93226;
                }
            """
    
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
        lang_code = self.get_lang()
        colors = get_theme_colors()
        
        if lang_code == "my":
            self.setWindowTitle("ပစ္စည်းထားရာနေရာများ စီမံရန်")
            self.location_name.setPlaceholderText("နေရာအမည်ထည့်ပါ (ဥပမာ - စင်တန်း A1၊ ဂိုဒေါင် ၁)")
            self.btn_add_location.setText(" နေရာအသစ်ထည့်")
            self.btn_edit.setText(" ပြင်ဆင်")
            self.btn_delete.setText(" ဖျက်")
            self.btn_close.setText(" ပိတ်မည်")
            self.table.setHorizontalHeaderLabels(["ID", "နေရာအမည်", "ပစ္စည်းအရေအတွက်"])
        else:
            self.setWindowTitle("Manage Locations")
            self.location_name.setPlaceholderText("Enter location name (e.g., Shelf A1, Warehouse 1)")
            self.btn_add_location.setText(" Add Location")
            self.btn_edit.setText(" Edit")
            self.btn_delete.setText(" Delete")
            self.btn_close.setText(" Close")
            self.table.setHorizontalHeaderLabels(["ID", "Location Name", "Product Count"])
        
        # Update button icons
        self._update_button_icons()
        
        # Update styles after language change
        self._apply_theme()
        self.load_locations()
    
    def load_locations(self):
        """Load locations from product_locations table with theme-aware styling"""
        conn = connect_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT location FROM product_locations 
            WHERE location IS NOT NULL AND location != ''
            ORDER BY location
        """)
        rows = cursor.fetchall()
        conn.close()
        
        self.table.setRowCount(0)
        for row in rows:
            location_name = row[0]
            
            conn2 = connect_db()
            cursor2 = conn2.cursor()
            cursor2.execute("SELECT COUNT(*) FROM product_locations WHERE location = ?", (location_name,))
            count = cursor2.fetchone()[0]
            conn2.close()
            
            r = self.table.rowCount()
            self.table.insertRow(r)
            
            # ✅ Use PyQt6 default colors - no custom text color
            # ID (hidden)
            id_item = QTableWidgetItem(location_name)
            self.table.setItem(r, 0, id_item)
            
            # Location Name
            name_item = QTableWidgetItem(location_name)
            self.table.setItem(r, 1, name_item)
            
            # Product Count
            count_item = QTableWidgetItem(str(count))
            if count > 0:
                count_item.setForeground(QColor("#28a745"))  # Green
            self.table.setItem(r, 2, count_item)
    
    def add_location(self):
        """Add a new location to product_locations table"""
        name = self.location_name.text().strip()
        if not name:
            lang_code = self.get_lang()
            msg = "Please enter a location name." if lang_code != "my" else "နေရာအမည်ထည့်ပါ။"
            QMessageBox.warning(self, "Error", msg)
            return
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM product_locations WHERE location = ?", (name,))
        exists = cursor.fetchone()[0] > 0
        conn.close()
        
        if exists:
            lang_code = self.get_lang()
            msg = f"Location '{name}' already exists!" if lang_code != "my" else f"နေရာ '{name}' ရှိပြီးသားပါ။"
            QMessageBox.warning(self, "Error", msg)
            return
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM products LIMIT 1")
        product = cursor.fetchone()
        
        if product:
            lang_code = self.get_lang()
            msg = f"Location '{name}' added successfully!\n\nTo assign products to this location, use the 'Add to Location' button in product location dialog." if lang_code != "my" else f"နေရာ '{name}' ထည့်သွင်းပြီးပါပြီ။\n\nပစ္စည်းများကို ဤနေရာသို့ သတ်မှတ်ရန် ပစ္စည်းနေရာပြင်ဆင်ရေးမှ 'နေရာသို့ထည့်' ခလုတ်ကို သုံးပါ။"
            QMessageBox.information(self, "Success", msg)
        else:
            lang_code = self.get_lang()
            msg = "No products found. Please add a product first to use locations." if lang_code != "my" else "ပစ္စည်းမရှိပါ။ နေရာအသုံးပြုရန် ပစ္စည်းအရင်ထည့်ပါ။"
            QMessageBox.warning(self, "Warning", msg)
        
        conn.close()
        
        self.location_name.clear()
        self.load_locations()
        self.warehouses_changed.emit()
    
    def edit_location(self):
        """Edit location name in product_locations, stock_movements, and products tables"""
        current_row = self.table.currentRow()
        if current_row < 0:
            lang_code = self.get_lang()
            msg = "Please select a location to edit." if lang_code != "my" else "ပြင်ဆင်လိုသော နေရာကိုရွေးပါ။"
            QMessageBox.warning(self, "No Selection", msg)
            return
        
        old_name = self.table.item(current_row, 1).text()
        
        lang_code = self.get_lang()
        new_name, ok = QInputDialog.getText(
            self, 
            "Edit Location" if lang_code != "my" else "နေရာပြင်ဆင်ရန်",
            "Enter new name:" if lang_code != "my" else "အမည်အသစ်ထည့်ပါ:",
            text=old_name
        )
        
        if ok and new_name.strip():
            new_name = new_name.strip()
            if new_name == old_name:
                return
            
            conn = connect_db()
            cursor = conn.cursor()
            try:
                cursor.execute("BEGIN IMMEDIATE")
                
                cursor.execute("UPDATE product_locations SET location = ? WHERE location = ?", (new_name, old_name))
                cursor.execute("UPDATE stock_movements SET location = ? WHERE location = ?", (new_name, old_name))
                cursor.execute("UPDATE products SET warehouse = ? WHERE warehouse = ?", (new_name, old_name))
                
                conn.commit()
                
                self.load_locations()
                self.warehouses_changed.emit()
                
                lang_code = self.get_lang()
                msg = f"Location renamed to '{new_name}' and updated in all records!" if lang_code != "my" else f"နေရာအမည် '{new_name}' သို့ ပြောင်းလဲပြီး မှတ်တမ်းအားလုံးတွင် ပြင်ဆင်ပြီးပါပြီ။"
                QMessageBox.information(self, "Success", msg)
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to rename location: {e}")
                lang_code = self.get_lang()
                msg = f"Failed to rename location: {e}" if lang_code != "my" else f"နေရာအမည်ပြောင်းလဲရာတွင် အမှားရှိသည်: {e}"
                QMessageBox.critical(self, "Error", msg)
            finally:
                conn.close()
    
    def delete_location(self):
        """Delete location from product_locations, stock_movements, and products tables"""
        current_row = self.table.currentRow()
        if current_row < 0:
            lang_code = self.get_lang()
            msg = "Please select a location to delete." if lang_code != "my" else "ဖျက်လိုသော နေရာကိုရွေးပါ။"
            QMessageBox.warning(self, "No Selection", msg)
            return
        
        name = self.table.item(current_row, 1).text()
        count = int(self.table.item(current_row, 2).text())
        
        if count > 0:
            lang_code = self.get_lang()
            msg = f"Location '{name}' has {count} products. Please move or remove them first." if lang_code != "my" else f"နေရာ '{name}' တွင် ပစ္စည်း {count} ခုရှိပါသည်။ ဦးစွာရွှေ့ပြောင်းပါ။"
            QMessageBox.warning(self, "Cannot Delete", msg)
            return
        
        lang_code = self.get_lang()
        reply = QMessageBox.question(
            self, 
            "Confirm Delete" if lang_code != "my" else "အတည်ပြုဖျက်ရန်",
            f"Delete location '{name}' permanently?" if lang_code != "my" else f"နေရာ '{name}' ကို အပြီးတိုင်ဖျက်မည်လား?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            conn = connect_db()
            cursor = conn.cursor()
            try:
                cursor.execute("BEGIN IMMEDIATE")
                
                cursor.execute("DELETE FROM product_locations WHERE location = ?", (name,))
                cursor.execute("UPDATE stock_movements SET location = '' WHERE location = ?", (name,))
                cursor.execute("UPDATE products SET warehouse = '' WHERE warehouse = ?", (name,))
                
                conn.commit()
                
                self.load_locations()
                self.warehouses_changed.emit()
                
                lang_code = self.get_lang()
                msg = "Location deleted successfully!" if lang_code != "my" else "နေရာဖျက်ပြီးပါပြီ။"
                QMessageBox.information(self, "Success", msg)
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Failed to delete location: {e}")
                lang_code = self.get_lang()
                msg = f"Failed to delete location: {e}" if lang_code != "my" else f"နေရာဖျက်ရာတွင် အမှားရှိသည်: {e}"
                QMessageBox.critical(self, "Error", msg)
            finally:
                conn.close()
    
    def showEvent(self, event):
        """Update button icons when shown"""
        self._update_button_icons()
        super().showEvent(event)
