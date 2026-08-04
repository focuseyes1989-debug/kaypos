# ui/sales_page/checkout_handler/checkout_dialogs.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QHeaderView, QPushButton, QDialogButtonBox,
    QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from utils.currency import get_currency_symbol, format_money
from utils.language import lang
from ui.themes.theme_manager import get_theme_colors, is_dark_theme
from loguru import logger


def _set_first_column_stretch(table: QTableWidget) -> None:
    """Apply stretch to the first table column when the header is available."""
    header = table.horizontalHeader()
    if header is not None:
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)


class CompletionDialog(QDialog):
    """Completion dialog with sale details - NO receipt dialog"""
    
    def __init__(self, parent, sale_id, invoice_no, grand_total, payment, change, discount, is_credit_sale):
        super().__init__(parent)
        self._parent_widget = parent
        self.sale_id = sale_id
        self.invoice_no = invoice_no
        self.grand_total = grand_total
        self.payment = payment
        self.change = change
        self.discount = discount
        self.is_credit_sale = is_credit_sale
        
        self._print_receipt_check = None
        self._open_drawer_check = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        symbol = get_currency_symbol()
        lang_code = lang.get_current()
        is_dark = is_dark_theme()
        colors = get_theme_colors()
        
        # Theme-aware colors
        bg_color = colors.get('bg', '#2f3136' if is_dark else '#f2f3f5')
        text_color = colors.get('text', '#dcddde' if is_dark else '#2e3338')
        text_secondary = colors.get('text_secondary', '#b9bbbe' if is_dark else '#4a4f55')
        border_color = colors.get('border', '#40444b' if is_dark else '#d0d3d9')
        card_bg = colors.get('card_bg', '#2f3136' if is_dark else '#ffffff')
        
        if lang_code == "my":
            self.setWindowTitle("✅ ရောင်းချမှုပြီးဆုံးပါပြီ")
        else:
            self.setWindowTitle("✅ Sale Completed")
        
        self.setMinimumSize(450, 420)
        self.setModal(True)
        
        # Apply theme-aware stylesheet
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
            }}
            QLabel {{
                color: {text_color};
                background: transparent;
            }}
            QPushButton {{
                background-color: #5865f2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #4752c4;
            }}
            QPushButton:pressed {{
                background-color: #3c45a3;
            }}
            QCheckBox {{
                color: {text_color};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid {border_color};
                background-color: {card_bg};
            }}
            QCheckBox::indicator:checked {{
                background-color: #5865f2;
                border-color: #5865f2;
            }}
            QCheckBox::indicator:hover {{
                border-color: #5865f2;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Success icon
        icon_label = QLabel("✅")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 48px; background: transparent;")
        layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel("Sale Completed Successfully!" if lang_code != "my" else "ရောင်းချမှုအောင်မြင်ပါသည်!")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: #27ae60; background: transparent;")
        layout.addWidget(title_label)
        
        # Invoice number
        invoice_label = QLabel(f"Invoice: {self.invoice_no}")
        invoice_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        invoice_label.setStyleSheet(f"font-size: 11pt; color: {text_secondary}; background: transparent;")
        layout.addWidget(invoice_label)
        
        # Separator
        sep_label = QLabel("─" * 40)
        sep_label.setStyleSheet(f"color: {border_color}; background: transparent;")
        layout.addWidget(sep_label)
        
        # Details grid
        details_layout = QVBoxLayout()
        details_layout.setSpacing(6)
        
        # Grand Total
        total_row = QHBoxLayout()
        total_row.addWidget(QLabel("Grand Total:" if lang_code != "my" else "စုစုပေါင်း:"))
        total_row.addStretch()
        total_label = QLabel(format_money(self.grand_total, symbol))
        total_label.setStyleSheet(f"font-size: 14pt; font-weight: bold; color: {text_color}; background: transparent;")
        total_row.addWidget(total_label)
        details_layout.addLayout(total_row)
        
        # Payment
        payment_row = QHBoxLayout()
        payment_row.addWidget(QLabel("Payment:" if lang_code != "my" else "လက်ခံငွေ:"))
        payment_row.addStretch()
        payment_label = QLabel(format_money(self.payment, symbol))
        payment_label.setStyleSheet("font-size: 12pt; color: #2980b9; background: transparent;")
        payment_row.addWidget(payment_label)
        details_layout.addLayout(payment_row)
        
        # Change
        change_row = QHBoxLayout()
        change_row.addWidget(QLabel("Change:" if lang_code != "my" else "ပြန်အမ်းငွေ:"))
        change_row.addStretch()
        change_label = QLabel(format_money(self.change, symbol))
        change_color = "#27ae60" if self.change >= 0 else "#e74c3c"
        change_label.setStyleSheet(f"font-size: 12pt; color: {change_color}; background: transparent;")
        change_row.addWidget(change_label)
        details_layout.addLayout(change_row)
        
        # Discount
        if self.discount > 0:
            discount_row = QHBoxLayout()
            discount_row.addWidget(QLabel("Discount:" if lang_code != "my" else "လျှော့စျေး:"))
            discount_row.addStretch()
            discount_label = QLabel(format_money(self.discount, symbol))
            discount_label.setStyleSheet("font-size: 11pt; color: #e67e22; background: transparent;")
            discount_row.addWidget(discount_label)
            details_layout.addLayout(discount_row)
        
        # Credit sale note
        if self.is_credit_sale:
            note_label = QLabel("🔵 Credit Sale - Balance due" if lang_code != "my" else "🔵 အကြွေးရောင်းချမှု - ကျန်ရှိငွေ")
            note_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            note_label.setStyleSheet("font-size: 10pt; color: #6c5ce7; font-weight: bold; background: transparent;")
            details_layout.addWidget(note_label)
        
        layout.addLayout(details_layout)
        
        # Separator
        sep_label2 = QLabel("─" * 40)
        sep_label2.setStyleSheet(f"color: {border_color}; background: transparent;")
        layout.addWidget(sep_label2)
        
        # Options - Using QCheckBox
        options_layout = QHBoxLayout()
        options_layout.setSpacing(20)
        options_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Get values from options widget
        options_widget = getattr(self._parent_widget, "options_widget", None)
        if options_widget is not None:
            print_receipt_enabled = options_widget.is_print_receipt_enabled()
            open_drawer_enabled = options_widget.is_open_drawer_enabled()
        else:
            print_receipt_enabled = False
            open_drawer_enabled = False
        
        # Print Receipt - QCheckBox
        print_text = "🖨️ Print Receipt" if lang_code != "my" else "🖨️ ပြေစာထုတ်မည်"
        self._print_receipt_check = QCheckBox(print_text)
        self._print_receipt_check.setChecked(print_receipt_enabled)
        self._print_receipt_check.setStyleSheet(f"""
            QCheckBox {{
                font-weight: 500;
                padding: 4px 8px;
                color: {text_color};
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid #3498db;
                background-color: {card_bg};
            }}
            QCheckBox::indicator:checked {{
                background-color: #3498db;
                border-color: #3498db;
            }}
            QCheckBox::indicator:hover {{
                border-color: #2980b9;
            }}
        """)
        options_layout.addWidget(self._print_receipt_check)
        
        # Open Cash Drawer - QCheckBox
        drawer_text = "💰 Open Drawer" if lang_code != "my" else "💰 ငွေသေတ္တာဖွင့်မည်"
        self._open_drawer_check = QCheckBox(drawer_text)
        self._open_drawer_check.setChecked(open_drawer_enabled)
        self._open_drawer_check.setStyleSheet(f"""
            QCheckBox {{
                font-weight: 500;
                padding: 4px 8px;
                color: {text_color};
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid #27ae60;
                background-color: {card_bg};
            }}
            QCheckBox::indicator:checked {{
                background-color: #27ae60;
                border-color: #27ae60;
            }}
            QCheckBox::indicator:hover {{
                border-color: #1e8449;
            }}
        """)
        options_layout.addWidget(self._open_drawer_check)
        
        layout.addLayout(options_layout)
        
        # OK button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText("New Sale" if lang_code != "my" else "အရောင်းအသစ်")
            ok_button.setStyleSheet("""
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    font-weight: bold;
                    padding: 10px 32px;
                    border-radius: 4px;
                    min-width: 140px;
                    font-size: 11pt;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #2ecc71;
                }
            """)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.setLayout(layout)
        
        logger.info("CompletionDialog UI setup completed successfully")
    
    def is_print_receipt_enabled(self):
        """Return True if print receipt checkbox is checked"""
        return self._print_receipt_check.isChecked() if self._print_receipt_check else False
    
    def is_open_drawer_enabled(self):
        """Return True if open drawer checkbox is checked"""
        return self._open_drawer_check.isChecked() if self._open_drawer_check else False


class ExpiredItemsDialog(QDialog):
    """Dialog showing expired products - Theme-aware"""
    
    def __init__(self, parent, expired_items, warning_items):
        super().__init__(parent)
        self.parent = parent
        self.expired_items = expired_items
        self.warning_items = warning_items
        self._setup_ui()
    
    def _setup_ui(self):
        is_dark = is_dark_theme()
        colors = get_theme_colors()
        
        bg_color = colors.get('bg', '#2f3136' if is_dark else '#f2f3f5')
        text_color = colors.get('text', '#dcddde' if is_dark else '#2e3338')
        text_secondary = colors.get('text_secondary', '#b9bbbe' if is_dark else '#4a4f55')
        border_color = colors.get('border', '#40444b' if is_dark else '#d0d3d9')
        card_bg = colors.get('card_bg', '#2f3136' if is_dark else '#ffffff')
        table_alt = colors.get('table_alt', '#36393f' if is_dark else '#f8f9fa')
        
        self.setWindowTitle("⚠️ Expired Products")
        self.setMinimumSize(600, 400)
        self.setModal(True)
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
            }}
            QLabel {{
                color: {text_color};
                background: transparent;
            }}
            QTableWidget {{
                background-color: {card_bg};
                alternate-background-color: {table_alt};
                gridline-color: {border_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                color: {text_color};
            }}
            QHeaderView::section {{
                background-color: {border_color};
                color: {text_secondary};
                padding: 6px;
                border: none;
                font-weight: 600;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
                color: {text_color};
            }}
            QPushButton {{
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: 500;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        warning_label = QLabel(
            "❌ The following products have expired and cannot be sold:\n"
            "Please remove them from the cart or select different batches."
        )
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet(f"color: #e74c3c; font-weight: bold; font-size: 12pt; background: transparent;")
        layout.addWidget(warning_label)
        
        if self.expired_items:
            table = QTableWidget()
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["Product", "Location", "Batch", "Expiry Date", "Qty"])
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setAlternatingRowColors(True)
            table.setRowCount(len(self.expired_items))
            
            for i, item in enumerate(self.expired_items):
                table.setItem(i, 0, QTableWidgetItem(item['name']))
                table.setItem(i, 1, QTableWidgetItem(item['location'] or '-'))
                table.setItem(i, 2, QTableWidgetItem(item['batch'] or '-'))
                table.setItem(i, 3, QTableWidgetItem(item['expiry'] or '-'))
                table.setItem(i, 4, QTableWidgetItem(str(item['qty'])))
                
                # Expired items - red background with theme-aware text
                for col in range(5):
                    item_widget = table.item(i, col)
                    if item_widget:
                        if is_dark:
                            item_widget.setBackground(QColor(60, 30, 30))
                            item_widget.setForeground(QColor(255, 180, 180))
                        else:
                            item_widget.setBackground(QColor(255, 220, 220))
                            item_widget.setForeground(QColor(180, 0, 0))
            
            _set_first_column_stretch(table)
            layout.addWidget(table)
        
        if self.warning_items:
            warn_label = QLabel(
                "\n⚠️ The following items are expiring soon (within 7 days):\n"
                "These can still be sold but please check stock rotation."
            )
            warn_label.setWordWrap(True)
            warn_label.setStyleSheet(f"color: #f39c12; font-weight: bold; background: transparent;")
            layout.addWidget(warn_label)
            
            warn_table = QTableWidget()
            warn_table.setColumnCount(5)
            warn_table.setHorizontalHeaderLabels(["Product", "Location", "Batch", "Expiry Date", "Qty"])
            warn_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            warn_table.setAlternatingRowColors(True)
            warn_table.setRowCount(len(self.warning_items))
            
            for i, item in enumerate(self.warning_items):
                warn_table.setItem(i, 0, QTableWidgetItem(item['name']))
                warn_table.setItem(i, 1, QTableWidgetItem(item['location'] or '-'))
                warn_table.setItem(i, 2, QTableWidgetItem(item['batch'] or '-'))
                warn_table.setItem(i, 3, QTableWidgetItem(item['expiry'] or '-'))
                warn_table.setItem(i, 4, QTableWidgetItem(str(item['qty'])))
                
                # Warning items - yellow background with theme-aware text
                for col in range(5):
                    item_widget = warn_table.item(i, col)
                    if item_widget:
                        if is_dark:
                            item_widget.setBackground(QColor(50, 40, 20))
                            item_widget.setForeground(QColor(255, 220, 150))
                        else:
                            item_widget.setBackground(QColor(255, 243, 205))
                            item_widget.setForeground(QColor(180, 120, 0))
            
            _set_first_column_stretch(warn_table)
            layout.addWidget(warn_table)
        
        btn_layout = QHBoxLayout()
        btn_remove = QPushButton("Remove Expired Items from Cart")
        btn_remove.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        btn_remove.clicked.connect(self.accept)
        
        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {border_color};
                color: {text_color};
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {text_secondary};
            }}
        """)
        btn_close.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_remove)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)


class ExpiryWarningDialog(QDialog):
    """Dialog showing expiry warnings - Theme-aware"""
    
    def __init__(self, parent, warning_items):
        super().__init__(parent)
        self.warning_items = warning_items
        self._setup_ui()
    
    def _setup_ui(self):
        is_dark = is_dark_theme()
        colors = get_theme_colors()
        
        bg_color = colors.get('bg', '#2f3136' if is_dark else '#f2f3f5')
        text_color = colors.get('text', '#dcddde' if is_dark else '#2e3338')
        text_secondary = colors.get('text_secondary', '#b9bbbe' if is_dark else '#4a4f55')
        border_color = colors.get('border', '#40444b' if is_dark else '#d0d3d9')
        card_bg = colors.get('card_bg', '#2f3136' if is_dark else '#ffffff')
        table_alt = colors.get('table_alt', '#36393f' if is_dark else '#f8f9fa')
        
        self.setWindowTitle("⚠️ Expiry Warning")
        self.setMinimumSize(550, 350)
        self.setModal(True)
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
            }}
            QLabel {{
                color: {text_color};
                background: transparent;
            }}
            QTableWidget {{
                background-color: {card_bg};
                alternate-background-color: {table_alt};
                gridline-color: {border_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                color: {text_color};
            }}
            QHeaderView::section {{
                background-color: {border_color};
                color: {text_secondary};
                padding: 6px;
                border: none;
                font-weight: 600;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
                color: {text_color};
            }}
            QPushButton {{
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: 500;
                font-size: 10pt;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        warning_label = QLabel(
            "⚠️ The following products are expiring within 7 days:\n"
            "Do you want to continue with the sale?"
        )
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet(f"color: #f39c12; font-weight: bold; font-size: 12pt; background: transparent;")
        layout.addWidget(warning_label)
        
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Product", "Location", "Expiry Date", "Qty"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setRowCount(len(self.warning_items))
        
        for i, item in enumerate(self.warning_items):
            table.setItem(i, 0, QTableWidgetItem(item['name']))
            table.setItem(i, 1, QTableWidgetItem(item['location'] or '-'))
            table.setItem(i, 2, QTableWidgetItem(item['expiry'] or '-'))
            table.setItem(i, 3, QTableWidgetItem(str(item['qty'])))
            
            # Warning items - yellow background with theme-aware text
            for col in range(4):
                item_widget = table.item(i, col)
                if item_widget:
                    if is_dark:
                        item_widget.setBackground(QColor(50, 40, 20))
                        item_widget.setForeground(QColor(255, 220, 150))
                    else:
                        item_widget.setBackground(QColor(255, 243, 205))
                        item_widget.setForeground(QColor(180, 120, 0))
        
        _set_first_column_stretch(table)
        layout.addWidget(table)
        
        btn_layout = QHBoxLayout()
        btn_continue = QPushButton("Continue Sale")
        btn_continue.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
        """)
        btn_continue.clicked.connect(self.accept)
        
        btn_cancel = QPushButton("Cancel Sale")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_continue)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)