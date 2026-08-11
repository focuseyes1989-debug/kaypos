# ui/inventory_page/stock_movement_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QMessageBox, QLabel, QComboBox,
    QLineEdit, QFrame, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate, QTimer
from PyQt6.QtGui import QIcon, QColor
from models.database import connect_db
from models.database.queries import reverse_stock_movement, get_stock_movement
from utils.currency import get_currency_symbol, format_money
from utils.translations import tr
from ui.widgets.pagination_widget import PaginationWidget
from ui.widgets.modern_button import ModernButton
from ui.widgets.date_range_widget import DateRangeWidget
from ui.widgets.status_badge_widget import StatusBadgeWidget
from ui.inventory_page.stock_in_widgets import HeaderFrame
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
from datetime import datetime
import os


class StockMovementDialog(QDialog):
    """Dialog to view and reverse stock movements for a product - Theme-aware with SVG Icons"""
    
    movement_reversed = pyqtSignal()
    
    def __init__(self, product_id, parent=None):
        super().__init__(parent)
        self.product_id = product_id
        self.current_page = 1
        self.page_size = 25
        self._is_dark = is_dark_theme()
        
        self.setWindowTitle("Stock Movements")
        self.setMinimumSize(1000, 650)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setModal(True)
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Setup header
        self._setup_header(main_layout)
        
        # Setup filters
        self._setup_filters(main_layout)
        
        # Setup table
        self._setup_table(main_layout)
        
        # Setup pagination
        self.pagination = PaginationWidget()
        self.pagination.page_changed.connect(self.on_page_changed)
        main_layout.addWidget(self.pagination)
        
        # Setup buttons
        self._setup_buttons(main_layout)
        
        self.setLayout(main_layout)
        
        # Apply initial theme
        self._apply_theme()
        
        # Load data
        self.load_movements()
        self.retranslateUi()
    
    def _load_svg_icon(self, icon_name, size=(16, 16)):
        """Load SVG icon from assets/icons folder"""
        # Try SVG first
        svg_path = f"assets/icons/{icon_name}.svg"
        if os.path.exists(svg_path):
            try:
                pixmap = QPixmap(svg_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        size[0], size[1],
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    return QIcon(scaled)
            except Exception as e:
                pass
        
        # Try PNG fallback
        png_path = f"assets/icons/{icon_name}.png"
        if os.path.exists(png_path):
            try:
                pixmap = QPixmap(png_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        size[0], size[1],
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    return QIcon(scaled)
            except Exception as e:
                pass
        
        return None
    
    def _update_button_icons(self):
        """Update button icons when theme changes"""
        if hasattr(self, 'btn_reverse'):
            self.btn_reverse.set_icon("undo", size=(16, 16))
        if hasattr(self, 'btn_refresh'):
            self.btn_refresh.set_icon("refresh", size=(16, 16))
        if hasattr(self, 'btn_close'):
            self.btn_close.set_icon("close", size=(16, 16))
    
    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
        self._update_button_icons()
        self.load_movements()
    
    def _apply_theme(self):
        """Apply theme-aware styles to all widgets"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        # Dialog background
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
            }}
        """)
        
        # Update filter frame
        for child in self.findChildren(QFrame):
            if child.objectName() == "filter_frame":
                child.setStyleSheet(self._get_filter_frame_style(colors))
            elif child.objectName() == "button_frame":
                child.setStyleSheet(self._get_button_frame_style(colors))
        
        # Update table
        self._update_table_style(colors)
        
        # Update filter widgets
        self._update_filter_styles(colors)
        
        # Update button icons
        self._update_button_icons()
    
    def _get_filter_frame_style(self, colors):
        return f"""
            QFrame#filter_frame {{
                background: {colors['bg_hover']};
                border-radius: 8px;
                padding: 5px;
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
    
    def _update_table_style(self, colors):
        """Update table style based on theme"""
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
            """
        
        self.table.setStyleSheet(table_style)
    
    def _update_filter_styles(self, colors):
        """Update filter widget styles"""
        # Type filter combo
        if hasattr(self, 'type_filter'):
            self.type_filter.setStyleSheet(self._get_combobox_style(colors))
        
        # Label styles
        for child in self.findChildren(QLabel):
            if child.parent() and child.parent().objectName() == "filter_frame":
                child.setStyleSheet(f"color: {colors['text']}; font-size: 10pt;")
    
    def _get_combobox_style(self, colors):
        return f"""
            QComboBox {{
                padding: 6px 12px;
                border: 1px solid {colors['border']};
                border-radius: 6px;
                background: {colors['card_bg']};
                color: {colors['text']};
                font-size: 10pt;
                min-width: 120px;
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
    
    def _setup_header(self, parent_layout):
        """Setup the header section"""
        header_frame = HeaderFrame()
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 10, 20, 10)
        
        # Get product info
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT name, sku, stock FROM products WHERE id = ?", (self.product_id,))
        product = cursor.fetchone()
        conn.close()
        
        # ✅ Header with SVG icon
        icon = self._load_svg_icon("history", size=(24, 24))
        if icon and not icon.isNull():
            icon_label = QLabel()
            icon_label.setPixmap(icon.pixmap(24, 24))
            icon_label.setStyleSheet("background: transparent; border: none;")
            header_layout.addWidget(icon_label)
        
        if product:
            title_text = f" Stock Movements - {product[0]}"
            info_text = f"SKU: {product[1] or 'N/A'}  |  Current Stock: {product[2] or 0}"
        else:
            title_text = " Stock Movements"
            info_text = ""
        
        title_label = QLabel(title_text)
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 16pt;
                font-weight: 600;
            }
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        if info_text:
            info_label = QLabel(info_text)
            info_label.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 10pt;")
            header_layout.addWidget(info_label)
        
        parent_layout.addWidget(header_frame)
    
    def _setup_filters(self, parent_layout):
        """Setup the filter section with DateRangeWidget"""
        filter_frame = QFrame()
        filter_frame.setObjectName("filter_frame")
        colors = get_theme_colors()
        filter_frame.setStyleSheet(self._get_filter_frame_style(colors))
        
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setSpacing(12)
        filter_layout.setContentsMargins(15, 8, 15, 8)
        
        # Type filter
        type_label = QLabel("📌 Type:")
        type_label.setStyleSheet(f"color: {colors['text']}; font-size: 10pt;")
        filter_layout.addWidget(type_label)
        
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All", "Stock In", "Stock Out", "Adjustment", "Sale"])
        self.type_filter.currentTextChanged.connect(self.on_filter_changed)
        self.type_filter.setStyleSheet(self._get_combobox_style(colors))
        filter_layout.addWidget(self.type_filter)
        
        # Date range widget
        date_label = QLabel("📅 Date:")
        date_label.setStyleSheet(f"color: {colors['text']}; font-size: 10pt;")
        filter_layout.addWidget(date_label)
        
        self.date_range = DateRangeWidget()
        self.date_range.date_range_changed.connect(self.on_filter_changed)
        filter_layout.addWidget(self.date_range)
        
        filter_layout.addStretch()
        
        # ✅ Refresh button with SVG icon
        self.btn_refresh = ModernButton(" Refresh", ModernButton.SECONDARY)
        self.btn_refresh.set_icon("refresh", size=(16, 16))
        self.btn_refresh.set_compact(True)
        self.btn_refresh.clicked.connect(self.load_movements)
        filter_layout.addWidget(self.btn_refresh)
        
        parent_layout.addWidget(filter_frame)
    
    def _setup_table(self, parent_layout):
        """Setup the table widget"""
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ID", "Type", "Qty", "From Stock", "To Stock", "Location", 
            "Reference", "Created By", "Date"
        ])
        self.table.setColumnHidden(0, True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        # Apply initial table style
        colors = get_theme_colors()
        self._update_table_style(colors)
        
        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        
        self.table.verticalHeader().setDefaultSectionSize(40)
        parent_layout.addWidget(self.table)
    
    def _setup_buttons(self, parent_layout):
        """Setup the action buttons"""
        button_frame = QFrame()
        button_frame.setObjectName("button_frame")
        colors = get_theme_colors()
        button_frame.setStyleSheet(self._get_button_frame_style(colors))
        
        button_layout = QHBoxLayout(button_frame)
        button_layout.setSpacing(12)
        button_layout.setContentsMargins(15, 8, 15, 8)
        
        # ✅ Reverse button with SVG icon (red)
        self.btn_reverse = ModernButton(" Reverse Selected", ModernButton.PRIMARY)
        self.btn_reverse.set_icon("undo", size=(16, 16))
        self.btn_reverse.set_compact(False)
        self.btn_reverse.setMinimumHeight(32)
        self.btn_reverse.setMinimumWidth(160)
        self.btn_reverse.clicked.connect(self.reverse_selected)
        self.btn_reverse.setStyleSheet(self.btn_reverse.styleSheet() + """
            QPushButton {
                background-color: #e74c3c;
                font-size: 10pt;
                font-weight: 600;
                padding: 8px 24px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
        """)
        button_layout.addWidget(self.btn_reverse)
        
        button_layout.addStretch()
        
        # ✅ Close button with SVG icon
        self.btn_close = ModernButton(" Close", ModernButton.TERTIARY)
        self.btn_close.set_icon("close", size=(16, 16))
        self.btn_close.set_compact(False)
        self.btn_close.setMinimumHeight(32)
        self.btn_close.setMinimumWidth(120)
        self.btn_close.clicked.connect(self.accept)
        self.btn_close.setStyleSheet(self.btn_close.styleSheet() + """
            QPushButton {
                font-size: 10pt;
                padding: 8px 20px;
                border-radius: 6px;
            }
        """)
        button_layout.addWidget(self.btn_close)
        
        parent_layout.addWidget(button_frame)
    
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
        
        # Update button icons
        self._update_button_icons()
        
        if lang == "my":
            self.setWindowTitle("စတော့လှုပ်ရှားမှုများ")
            self.table.setHorizontalHeaderLabels([
                "ID", "အမျိုးအစား", "ပမာဏ", "မပြောင်းမီ", "ပြောင်းပြီး", 
                "နေရာ", "ကိုးကား", "ဖန်တီးသူ", "ရက်စွဲ"
            ])
            self.btn_reverse.setText(" ရွေးထားသော လှုပ်ရှားမှုကို ပြန်ဖျက်မည်")
            self.btn_refresh.setText(" ပြန်လည်")
            self.btn_close.setText(" ပိတ်မည်")
            self.type_filter.setItemText(0, "အားလုံး")
            self.type_filter.setItemText(1, "စတော့ဝင်")
            self.type_filter.setItemText(2, "စတော့ထွက်")
            self.type_filter.setItemText(3, "ပြင်ဆင်ချက်")
            self.type_filter.setItemText(4, "ရောင်းချမှု")
            self.date_range.retranslateUi("my")
        else:
            self.setWindowTitle("Stock Movements")
            self.table.setHorizontalHeaderLabels([
                "ID", "Type", "Qty", "From Stock", "To Stock", "Location", 
                "Reference", "Created By", "Date"
            ])
            self.btn_reverse.setText(" Reverse Selected")
            self.btn_refresh.setText(" Refresh")
            self.btn_close.setText(" Close")
            self.type_filter.setItemText(0, "All")
            self.type_filter.setItemText(1, "Stock In")
            self.type_filter.setItemText(2, "Stock Out")
            self.type_filter.setItemText(3, "Adjustment")
            self.type_filter.setItemText(4, "Sale")
            self.date_range.retranslateUi("en")
        
        # Update table with theme
        colors = get_theme_colors()
        self._update_table_style(colors)
    
    def on_filter_changed(self):
        self.current_page = 1
        self.load_movements()
    
    def on_page_changed(self, page: int, page_size: int):
        self.current_page = page
        self.page_size = page_size
        self.load_movements()
    
    def load_movements(self):
        """Load stock movements for the product."""
        from_date = self.date_range.get_from_date()
        to_date = self.date_range.get_to_date()
        type_filter = self.type_filter.currentText()
        
        # Map display type to DB type
        type_map = {
            "Stock In": "in",
            "Stock Out": "out",
            "Adjustment": "adjustment",
            "Sale": "sale"
        }
        db_type = type_map.get(type_filter) if type_filter != "All" else None
        
        conn = connect_db()
        cursor = conn.cursor()
        
        # Count total
        count_query = """
            SELECT COUNT(*) FROM stock_movements
            WHERE product_id = ? AND date(created_at) BETWEEN ? AND ?
        """
        count_params = [self.product_id, from_date, to_date]
        
        if db_type:
            count_query += " AND type = ?"
            count_params.append(db_type)
        
        cursor.execute(count_query, count_params)
        total_items = cursor.fetchone()[0]
        self.pagination.set_total_items(total_items, emit_signal=False)
        
        # Main query
        offset = (self.current_page - 1) * self.page_size
        data_query = """
            SELECT id, type, quantity, old_stock, new_stock, location, 
                   reference, created_by, created_at, notes
            FROM stock_movements
            WHERE product_id = ? AND date(created_at) BETWEEN ? AND ?
        """
        data_params = [self.product_id, from_date, to_date]
        
        if db_type:
            data_query += " AND type = ?"
            data_params.append(db_type)
        
        data_query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        data_params.extend([self.page_size, offset])
        
        cursor.execute(data_query, data_params)
        rows = cursor.fetchall()
        conn.close()
        
        self.table.setRowCount(0)
        
        # Display type mapping
        display_type = {
            "in": "Stock In",
            "out": "Stock Out",
            "adjustment": "Adjustment",
            "sale": "Sale"
        }
        
        lang = self.get_lang()
        if lang == "my":
            display_type_my = {
                "in": "စတော့ဝင်",
                "out": "စတော့ထွက်",
                "adjustment": "ပြင်ဆင်ချက်",
                "sale": "ရောင်းချမှု"
            }
        
        # Color mapping for types
        type_colors = {
            "in": QColor(46, 204, 113),      # Green
            "out": QColor(231, 76, 60),      # Red
            "sale": QColor(231, 76, 60),     # Red
            "adjustment": QColor(230, 126, 34)  # Orange
        }
        
        # Theme colors
        is_dark = is_dark_theme()
        text_color = "#dcddde" if is_dark else "#212529"
        
        for row in rows:
            mov_id, mov_type, qty, old_stock, new_stock, location, reference, created_by, created_at, notes = row
            
            # Check if this is a reversal
            is_reversal = notes and "REVERSAL" in notes
            
            r = self.table.rowCount()
            self.table.insertRow(r)
            
            # ID (hidden)
            id_item = QTableWidgetItem(str(mov_id))
            id_item.setForeground(QColor(text_color))
            self.table.setItem(r, 0, id_item)
            
            # Type
            type_display = display_type.get(mov_type, mov_type)
            if lang == "my":
                type_display = display_type_my.get(mov_type, mov_type)
            
            type_item = QTableWidgetItem(type_display)
            
            # Color code
            color = type_colors.get(mov_type, QColor(108, 117, 125))
            type_item.setForeground(color)
            
            if is_reversal:
                type_item.setText(f"{type_item.text()} (↩️)")
                type_item.setForeground(QColor(128, 128, 128))  # Gray
            
            self.table.setItem(r, 1, type_item)
            
            # Qty
            qty_display = f"{'+' if mov_type == 'in' else '-'}{abs(qty)}"
            qty_item = QTableWidgetItem(qty_display)
            if mov_type == "in":
                qty_item.setForeground(QColor(46, 204, 113))
            else:
                qty_item.setForeground(QColor(231, 76, 60))
            self.table.setItem(r, 2, qty_item)
            
            # From Stock
            from_item = QTableWidgetItem(str(old_stock) if old_stock is not None else "-")
            from_item.setForeground(QColor(text_color))
            self.table.setItem(r, 3, from_item)
            
            # To Stock
            to_item = QTableWidgetItem(str(new_stock) if new_stock is not None else "-")
            to_item.setForeground(QColor(text_color))
            self.table.setItem(r, 4, to_item)
            
            # Location
            loc_item = QTableWidgetItem(location or "-")
            loc_item.setForeground(QColor(text_color))
            self.table.setItem(r, 5, loc_item)
            
            # Reference
            ref_item = QTableWidgetItem(reference or "-")
            ref_item.setForeground(QColor(text_color))
            self.table.setItem(r, 6, ref_item)
            
            # Created By
            user_item = QTableWidgetItem(created_by or "-")
            user_item.setForeground(QColor(text_color))
            self.table.setItem(r, 7, user_item)
            
            # Date
            date_str = created_at[:16] if created_at else ""
            date_item = QTableWidgetItem(date_str)
            date_item.setForeground(QColor(text_color))
            self.table.setItem(r, 8, date_item)
        
        # Disable reverse button if no rows
        self.btn_reverse.setEnabled(self.table.rowCount() > 0)
    
    def reverse_selected(self):
        """Reverse the selected stock movement."""
        current_row = self.table.currentRow()
        if current_row < 0:
            lang = self.get_lang()
            msg = "Please select a movement to reverse." if lang != "my" else "ပြန်ဖျက်မည့် လှုပ်ရှားမှုကို ရွေးပါ။"
            QMessageBox.warning(self, "No Selection" if lang != "my" else "မရွေးရသေး", msg)
            return
        
        id_item = self.table.item(current_row, 0)
        if not id_item:
            return
        
        movement_id = int(id_item.text())
        
        # Get movement details
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT type, quantity, reference, created_by, created_at, notes
            FROM stock_movements WHERE id = ?
        """, (movement_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            QMessageBox.warning(self, "Error", "Movement not found.")
            return
        
        mov_type, qty, reference, created_by, created_at, notes = row
        
        # Check if already reversed
        if notes and "REVERSED" in notes:
            lang = self.get_lang()
            msg = "This movement has already been reversed." if lang != "my" else "ဤလှုပ်ရှားမှုကို ပြန်ဖျက်ပြီးသားဖြစ်သည်။"
            QMessageBox.warning(self, "Already Reversed" if lang != "my" else "ပြန်ဖျက်ပြီးသား", msg)
            return
        
        lang = self.get_lang()
        
        # Confirm reversal
        type_display = {
            "in": "Stock In",
            "out": "Stock Out",
            "adjustment": "Adjustment",
            "sale": "Sale"
        }.get(mov_type, mov_type)
        
        if lang == "my":
            msg = (f"ဤလှုပ်ရှားမှုကို ပြန်ဖျက်မည်လား?\n\n"
                   f"အမျိုးအစား: {type_display}\n"
                   f"ပမာဏ: {qty}\n"
                   f"ရက်စွဲ: {created_at}\n"
                   f"ဖန်တီးသူ: {created_by or 'System'}\n\n"
                   f"ဤလုပ်ဆောင်ချက်ကို နောက်ပြန်မလှန်နိုင်ပါ။")
        else:
            msg = (f"Reverse this movement?\n\n"
                   f"Type: {type_display}\n"
                   f"Quantity: {qty}\n"
                   f"Date: {created_at}\n"
                   f"Created by: {created_by or 'System'}\n\n"
                   f"This action cannot be undone.")
        
        reply = QMessageBox.question(
            self, 
            "Confirm Reversal" if lang != "my" else "အတည်ပြုရန်",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Perform reversal
        main_window = self.window()
        current_user = main_window.current_user['username'] if hasattr(main_window, 'current_user') else 'System'
        
        result = reverse_stock_movement(movement_id, reason="User requested reversal", created_by=current_user)
        
        if result['success']:
            lang = self.get_lang()
            msg = result['message'] if lang != "my" else "လှုပ်ရှားမှုကို အောင်မြင်စွာ ပြန်ဖျက်ပြီးပါပြီ။"
            QMessageBox.information(self, "Success" if lang != "my" else "အောင်မြင်ပြီး", msg)
            self.load_movements()
            self.movement_reversed.emit()
        else:
            QMessageBox.critical(self, "Error", result['message'])
    
    def showEvent(self, event):
        """Update button icons when dialog becomes visible"""
        self._update_button_icons()
        super().showEvent(event)