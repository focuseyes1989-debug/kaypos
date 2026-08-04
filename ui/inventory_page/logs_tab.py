# ui/inventory_page/logs_tab.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QMessageBox, QFileDialog, QLabel, QComboBox
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QIcon, QPixmap, QPainter
from models.database import connect_db
from ui.widgets.pagination_widget import PaginationWidget
from ui.widgets.modern_button import ModernButton
from ui.widgets.search_widget import SearchWidget
from ui.widgets.date_range_widget import DateRangeWidget
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
from datetime import datetime
import csv
import os


class LogsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_page = parent
        self.current_page = 1
        self.page_size = 50
        self._is_dark = is_dark_theme()
        
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # Button layout with SVG icons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        # ✅ Export PDF button with SVG icon
        self.btn_export_pdf = ModernButton(" Export PDF", ModernButton.SECONDARY)
        self.btn_export_pdf.set_icon("file_export", size=(16, 16))
        self.btn_export_pdf.set_compact(False)
        self.btn_export_pdf.clicked.connect(self.export_pdf)
        btn_layout.addWidget(self.btn_export_pdf)
        
        # ✅ Export Excel button with SVG icon
        self.btn_export_excel = ModernButton(" Export Excel", ModernButton.SECONDARY)
        self.btn_export_excel.set_icon("file_export", size=(16, 16))
        self.btn_export_excel.set_compact(False)
        self.btn_export_excel.clicked.connect(self.export_excel)
        btn_layout.addWidget(self.btn_export_excel)
        
        btn_layout.addStretch()
        
        # ✅ Export Stock Movement button with SVG icon
        self.btn_export_movement = ModernButton(" Export Stock Movement", ModernButton.PRIMARY)
        self.btn_export_movement.set_icon("file_export", size=(16, 16))
        self.btn_export_movement.set_compact(False)
        self.btn_export_movement.clicked.connect(self.export_stock_movement)
        btn_layout.addWidget(self.btn_export_movement)
        
        layout.addLayout(btn_layout)

        # ✅ Filter section with SearchWidget, DateRange and Action filter
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)
        filter_layout.setContentsMargins(0, 8, 0, 8)
        
        # ✅ SearchWidget with SVG icon
        self.search_widget = SearchWidget(
            placeholder="Search by product, supplier or reference...",
            show_label=False
        )
        self.search_widget.search_changed.connect(self.reset_pagination)
        self.search_widget.search_cleared.connect(self.reset_pagination)
        filter_layout.addWidget(self.search_widget, 2)
        
        # Action filter
        filter_layout.addWidget(QLabel("Action:"))
        self.action_filter = QComboBox()
        self.action_filter.addItems(["All", "Stock In", "Stock Out", "Adjustment", "Sale"])
        self.action_filter.currentTextChanged.connect(self.reset_pagination)
        filter_layout.addWidget(self.action_filter, 1)
        
        # ✅ DateRange Widget
        self.date_range = DateRangeWidget()
        self.date_range.date_range_changed.connect(self.reset_pagination)
        filter_layout.addWidget(self.date_range)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Table - NO custom style, use PyQt6 default
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # ✅ NO custom table style
        # self._apply_table_theme()  <-- ဒီ line ကို ဖယ်ရှားပါ
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.pagination = PaginationWidget()
        self.pagination.page_changed.connect(self.on_page_changed)
        layout.addWidget(self.pagination)

        self.setLayout(layout)
        
        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        self.retranslateUi()

    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        # ✅ Only update button icons and reload data - no table style update
        self._update_button_icons()
        self.load_data()
    
    def _update_button_icons(self):
        """Update button icons when theme changes"""
        self.btn_export_pdf.set_icon("file_export", size=(16, 16))
        self.btn_export_excel.set_icon("file_export", size=(16, 16))
        self.btn_export_movement.set_icon("file_export", size=(16, 16))

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

    def reset_pagination(self):
        self.current_page = 1
        self.load_data()

    def on_page_changed(self, page: int, page_size: int):
        self.current_page = page
        self.page_size = page_size
        self.load_data(page, page_size)

    def refresh(self):
        self.load_data()
        self.retranslateUi()

    def load_data(self, page=None, page_size=None):
        if page is None:
            page = self.current_page
        if page_size is None:
            page_size = self.page_size
            
        lang = self.get_lang()
        search_text = self.search_widget.get_text().lower()
        action_filter = self.action_filter.currentText()
        from_date = self.date_range.get_from_date()
        to_date = self.date_range.get_to_date()
        
        # Map action filter to database values
        action_map = {
            "Stock In": "in",
            "Stock Out": "out",
            "Adjustment": "adjustment",
            "Sale": "sale"
        }
        db_action = action_map.get(action_filter) if action_filter != "All" else None
        
        if lang == "my":
            headers = [
                "မှတ်တမ်း ID", "ပစ္စည်းအမည်", "ပေးသွင်းသူ", "လုပ်ဆောင်ချက်", "မပြောင်းမီပမာဏ",
                "ပြောင်းပြီးပမာဏ", "ပြောင်းလဲပမာဏ", "ကိုးကားအမှတ်", "အသုံးပြုသူ", "ရက်စွဲနှင့်အချိန်", "မှတ်ချက်"
            ]
        else:
            headers = [
                "Log ID", "Product Name", "Supplier", "Action Type", "Quantity Before",
                "Quantity After", "Changed Qty", "Reference No", "User", "Date Time", "Notes"
            ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setColumnHidden(0, True)

        conn = connect_db()
        cursor = conn.cursor()
        
        # Build query with filters
        base_query = """
            FROM stock_movements sm
            JOIN products p ON sm.product_id = p.id
            LEFT JOIN suppliers sup ON sm.supplier_id = sup.id
            WHERE date(sm.created_at) BETWEEN ? AND ?
        """
        params = [from_date, to_date]
        
        if search_text:
            like = f'%{search_text}%'
            base_query += " AND (LOWER(p.name) LIKE ? OR LOWER(sup.name) LIKE ? OR LOWER(sm.reference) LIKE ?)"
            params.extend([like, like, like])
        
        if db_action:
            base_query += " AND sm.type = ?"
            params.append(db_action)
        
        # Count total
        count_query = f"SELECT COUNT(*) {base_query}"
        cursor.execute(count_query, params)
        total_items = cursor.fetchone()[0]
        self.pagination.set_total_items(total_items, emit_signal=False)

        offset = (page - 1) * page_size
        data_query = f"""
            SELECT sm.id, p.name, sup.name, sm.type, sm.old_stock, sm.new_stock, 
                   sm.quantity, sm.reference, sm.created_by, sm.created_at, sm.notes
            {base_query}
            ORDER BY sm.created_at DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(data_query, params + [page_size, offset])
        rows = cursor.fetchall()
        conn.close()

        # ✅ Use hardcoded colors
        action_colors = {
            "in": QColor("#28a745"),      # Green
            "out": QColor("#dc3545"),     # Red
            "sale": QColor("#dc3545"),    # Red
            "adjustment": QColor("#f39c12")  # Orange
        }
        
        # Display name mapping
        action_display = {
            "in": "Stock In",
            "out": "Stock Out",
            "adjustment": "Adjustment",
            "sale": "Sale"
        }
        
        if lang == "my":
            action_display_my = {
                "in": "စတော့ဝင်",
                "out": "စတော့ထွက်",
                "adjustment": "ပြင်ဆင်ချက်",
                "sale": "ရောင်းချမှု"
            }

        self.table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(rows):
            for col_idx, value in enumerate(row_data):
                # Color code action type column
                if col_idx == 3:  # Action Type column
                    action_type = value
                    display_text = action_display.get(action_type, action_type)
                    if lang == "my":
                        display_text = action_display_my.get(action_type, action_type)
                    item = QTableWidgetItem(display_text)
                    color = action_colors.get(action_type, QColor("#6c757d"))
                    item.setForeground(color)
                else:
                    item = QTableWidgetItem(str(value) if value is not None else "")
                self.table.setItem(row_idx, col_idx, item)

    def get_all_movement_data(self):
        """Get all stock movement data for export with filters"""
        conn = connect_db()
        cursor = conn.cursor()
        
        search_text = self.search_widget.get_text().lower()
        action_filter = self.action_filter.currentText()
        from_date = self.date_range.get_from_date()
        to_date = self.date_range.get_to_date()
        
        action_map = {
            "Stock In": "in",
            "Stock Out": "out",
            "Adjustment": "adjustment",
            "Sale": "sale"
        }
        db_action = action_map.get(action_filter) if action_filter != "All" else None
        
        query = """
            SELECT sm.id, p.name, sup.name, sm.type, sm.old_stock, sm.new_stock, 
                   sm.quantity, sm.reference, sm.created_by, sm.created_at, sm.notes,
                   sm.reason
            FROM stock_movements sm
            JOIN products p ON sm.product_id = p.id
            LEFT JOIN suppliers sup ON sm.supplier_id = sup.id
            WHERE date(sm.created_at) BETWEEN ? AND ?
        """
        params = [from_date, to_date]
        
        if search_text:
            like = f'%{search_text}%'
            query += " AND (LOWER(p.name) LIKE ? OR LOWER(sup.name) LIKE ? OR LOWER(sm.reference) LIKE ?)"
            params.extend([like, like, like])
        
        if db_action:
            query += " AND sm.type = ?"
            params.append(db_action)
        
        query += " ORDER BY sm.created_at DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return rows

    def export_stock_movement(self):
        """Export stock movement report to CSV"""
        lang = self.get_lang()
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Stock Movement" if lang != "my" else "စတော့လှုပ်ရှားမှုမှတ်တမ်း ထုတ်ရန်", 
            f"stock_movement_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 
            "CSV Files (*.csv)"
        )
        if not file_path:
            return
        
        try:
            rows = self.get_all_movement_data()
            
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                # Header
                writer.writerow(["=" * 90])
                writer.writerow(["STOCK MOVEMENT REPORT"] if lang != "my" else ["စတော့လှုပ်ရှားမှု အစီရင်ခံစာ"])
                writer.writerow(["=" * 90])
                writer.writerow([])
                writer.writerow(["Generated:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                writer.writerow(["Total Movements:", len(rows)])
                writer.writerow([])
                
                # Column Headers
                if lang == "my":
                    writer.writerow(["ပစ္စည်းအမည်", "ပေးသွင်းသူ", "လုပ်ဆောင်ချက်", "မပြောင်းမီပမာဏ",
                                   "ပြောင်းပြီးပမာဏ", "ပြောင်းလဲပမာဏ", "ကိုးကားအမှတ်", 
                                   "အသုံးပြုသူ", "ရက်စွဲနှင့်အချိန်", "အကြောင်းပြချက်", "မှတ်ချက်"])
                else:
                    writer.writerow(["Product Name", "Supplier", "Action Type", "Quantity Before",
                                   "Quantity After", "Changed Qty", "Reference No", 
                                   "User", "Date Time", "Reason", "Notes"])
                writer.writerow(["-" * 90])
                
                stock_in_count = 0
                stock_out_count = 0
                adjustment_count = 0
                
                for row in rows:
                    pid, name, supplier, action, old_stock, new_stock, qty, ref_no, user, created_at, notes, reason = row
                    
                    writer.writerow([
                        name or "",
                        supplier or "",
                        action or "",
                        old_stock if old_stock is not None else "",
                        new_stock if new_stock is not None else "",
                        qty if qty is not None else "",
                        ref_no or "",
                        user or "",
                        created_at[:19] if created_at else "",
                        reason or "",
                        notes or ""
                    ])
                    
                    if action == "in":
                        stock_in_count += 1
                    elif action == "out":
                        stock_out_count += 1
                    else:
                        adjustment_count += 1
                
                writer.writerow([])
                writer.writerow(["=" * 90])
                writer.writerow(["SUMMARY"])
                writer.writerow(["-" * 50])
                writer.writerow(["Stock In Movements:", stock_in_count])
                writer.writerow(["Stock Out Movements:", stock_out_count])
                writer.writerow(["Adjustments:", adjustment_count])
                writer.writerow(["Total Movements:", len(rows)])
                writer.writerow(["=" * 90])
                writer.writerow(["End of Report"])
            
            msg = f"Stock movement report exported successfully to:\n{file_path}" if lang != "my" else f"စတော့လှုပ်ရှားမှုမှတ်တမ်း အောင်မြင်စွာ ထုတ်ယူပြီးပါပြီ:\n{file_path}"
            QMessageBox.information(self, "Export Complete", msg)
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    def get_all_data(self):
        """Get all data for export (without filters for PDF/Excel)"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sm.id, p.name, sup.name, sm.type, sm.old_stock, sm.new_stock, 
                   sm.quantity, sm.reference, sm.created_by, sm.created_at, sm.notes
            FROM stock_movements sm
            JOIN products p ON sm.product_id = p.id
            LEFT JOIN suppliers sup ON sm.supplier_id = sup.id
            ORDER BY sm.created_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        return rows

    def export_pdf(self):
        """Export to PDF"""
        from PyQt6.QtPrintSupport import QPrinter
        from PyQt6.QtGui import QPainter, QFont, QFontMetrics, QPageLayout, QPageSize
        
        rows = self.get_all_data()
        if not rows:
            lang = self.get_lang()
            msg = "No stock movement records to export." if lang != "my" else "စတော့လှုပ်ရှားမှုမှတ်တမ်း ထုတ်ယူရန် မရှိပါ။"
            QMessageBox.information(self, "No Data" if lang != "my" else "ဒေတာမရှိ", msg)
            return
        
        lang = self.get_lang()
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save PDF Report" if lang != "my" else "PDF အစီရင်ခံစာ သိမ်းရန်", 
            "stock_movement_report.pdf", 
            "PDF Files (*.pdf)"
        )
        if not file_path:
            return
        
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(file_path)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        
        painter = QPainter()
        if not painter.begin(printer):
            QMessageBox.critical(self, "Error", "Could not start PDF generation.")
            return
        
        font = QFont("Arial", 8)
        painter.setFont(font)
        fm = QFontMetrics(font)
        
        if lang == "my":
            headers = ["ID", "ပစ္စည်း", "ပေးသွင်းသူ", "အမျိုးအစား", "မပြောင်းမီ", 
                      "ပြောင်းပြီး", "ပြောင်းလဲမှု", "ကိုးကား", "အသုံးပြုသူ", "ရက်စွဲ", "မှတ်ချက်"]
        else:
            headers = ["ID", "Product", "Supplier", "Type", "Old Stock", 
                      "New Stock", "Qty Changed", "Reference", "User", "Date Time", "Notes"]
        
        col_widths = [40, 120, 100, 80, 80, 80, 80, 100, 100, 140, 150]
        y = 20
        x = 20
        row_height = fm.height() + 6
        
        for i, header in enumerate(headers):
            painter.drawText(x, y, col_widths[i], row_height, Qt.AlignmentFlag.AlignLeft, header)
            x += col_widths[i]
        y += row_height
        x = 20
        
        for row in rows:
            if y + row_height > printer.height() - 50:
                printer.newPage()
                y = 20
            painter.drawText(x, y, col_widths[0], row_height, Qt.AlignmentFlag.AlignLeft, str(row[0]))
            painter.drawText(x + col_widths[0], y, col_widths[1], row_height, Qt.AlignmentFlag.AlignLeft, str(row[1] or ""))
            painter.drawText(x + col_widths[0] + col_widths[1], y, col_widths[2], row_height, Qt.AlignmentFlag.AlignLeft, str(row[2] or ""))
            painter.drawText(x + col_widths[0] + col_widths[1] + col_widths[2], y, col_widths[3], row_height, Qt.AlignmentFlag.AlignLeft, str(row[3] or ""))
            painter.drawText(x + col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3], y, col_widths[4], row_height, Qt.AlignmentFlag.AlignLeft, str(row[4] or ""))
            painter.drawText(x + col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3] + col_widths[4], y, col_widths[5], row_height, Qt.AlignmentFlag.AlignLeft, str(row[5] or ""))
            painter.drawText(x + col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3] + col_widths[4] + col_widths[5], y, col_widths[6], row_height, Qt.AlignmentFlag.AlignLeft, str(row[6] or ""))
            painter.drawText(x + col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3] + col_widths[4] + col_widths[5] + col_widths[6], y, col_widths[7], row_height, Qt.AlignmentFlag.AlignLeft, str(row[7] or ""))
            painter.drawText(x + col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3] + col_widths[4] + col_widths[5] + col_widths[6] + col_widths[7], y, col_widths[8], row_height, Qt.AlignmentFlag.AlignLeft, str(row[8] or ""))
            painter.drawText(x + col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3] + col_widths[4] + col_widths[5] + col_widths[6] + col_widths[7] + col_widths[8], y, col_widths[9], row_height, Qt.AlignmentFlag.AlignLeft, str(row[9] or ""))
            painter.drawText(x + col_widths[0] + col_widths[1] + col_widths[2] + col_widths[3] + col_widths[4] + col_widths[5] + col_widths[6] + col_widths[7] + col_widths[8] + col_widths[9], y, col_widths[10], row_height, Qt.AlignmentFlag.AlignLeft, str(row[10] or ""))
            y += row_height
            x = 20
        
        painter.end()
        
        msg = f"PDF saved to:\n{file_path}" if lang != "my" else f"PDF ကို သိမ်းဆည်းပြီးပါပြီ:\n{file_path}"
        QMessageBox.information(self, "Export Complete" if lang != "my" else "ထုတ်ယူပြီးပါပြီ", msg)

    def export_excel(self):
        """Export to Excel (CSV)"""
        lang = self.get_lang()
        rows = self.get_all_data()
        
        if not rows:
            msg = "No stock movement records to export." if lang != "my" else "စတော့လှုပ်ရှားမှုမှတ်တမ်း ထုတ်ယူရန် မရှိပါ။"
            QMessageBox.information(self, "No Data" if lang != "my" else "ဒေတာမရှိ", msg)
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Excel Report" if lang != "my" else "Excel အစီရင်ခံစာ သိမ်းရန်", 
            "stock_movement_report.csv", 
            "CSV Files (*.csv)"
        )
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                if lang == "my":
                    writer.writerow(["ID", "ပစ္စည်း", "ပေးသွင်းသူ", "အမျိုးအစား", "မပြောင်းမီ", 
                                   "ပြောင်းပြီး", "ပြောင်းလဲမှု", "ကိုးကား", "အသုံးပြုသူ", "ရက်စွဲ", "မှတ်ချက်"])
                else:
                    writer.writerow(["ID", "Product", "Supplier", "Type", "Old Stock", 
                                   "New Stock", "Qty Changed", "Reference", "User", "Date Time", "Notes"])
                
                for row in rows:
                    writer.writerow([str(r) for r in row])
            
            msg = f"CSV saved to:\n{file_path}\n\nYou can open this file in Excel." if lang != "my" else f"CSV ကို သိမ်းဆည်းပြီးပါပြီ:\n{file_path}\n\nဤဖိုင်ကို Excel တွင် ဖွင့်နိုင်ပါသည်။"
            QMessageBox.information(self, "Export Complete" if lang != "my" else "ထုတ်ယူပြီးပါပြီ", msg)
            
        except Exception as e:
            msg = f"Failed to export: {e}" if lang != "my" else f"ထုတ်ယူမရပါ: {e}"
            QMessageBox.critical(self, "Error" if lang != "my" else "အမှား", msg)

    def retranslateUi(self):
        lang = self.get_lang()
        
        # Update SearchWidget placeholder
        if lang == "my":
            self.search_widget.set_placeholder_text("ပစ္စည်း / ပေးသွင်းသူ / ကိုးကားဖြင့် ရှာရန်...")
            self.btn_export_pdf.setText(" PDF ထုတ်မည်")
            self.btn_export_excel.setText(" Excel ထုတ်မည်")
            self.btn_export_movement.setText(" စတော့လှုပ်ရှားမှုထုတ်မည်")
            self.action_filter.setItemText(0, "အားလုံး")
            self.action_filter.setItemText(1, "စတော့ဝင်")
            self.action_filter.setItemText(2, "စတော့ထွက်")
            self.action_filter.setItemText(3, "ပြင်ဆင်ချက်")
            self.action_filter.setItemText(4, "ရောင်းချမှု")
        else:
            self.search_widget.set_placeholder_text("Search by product, supplier or reference...")
            self.btn_export_pdf.setText(" Export PDF")
            self.btn_export_excel.setText(" Export Excel")
            self.btn_export_movement.setText(" Export Stock Movement")
            self.action_filter.setItemText(0, "All")
            self.action_filter.setItemText(1, "Stock In")
            self.action_filter.setItemText(2, "Stock Out")
            self.action_filter.setItemText(3, "Adjustment")
            self.action_filter.setItemText(4, "Sale")
        
        # Update button icons
        self._update_button_icons()
        
        self.load_data()
    
    def showEvent(self, event):
        """Handle show event - refresh data"""
        self.load_data()
        super().showEvent(event)