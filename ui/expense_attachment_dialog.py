from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from models.database import connect_db
import os
import shutil
from datetime import datetime
from utils.branded_icons import pos_icon


class ExpenseAttachmentDialog(QDialog):
    def __init__(self, expense_id, expense_no, parent=None):
        super().__init__(parent)
        self.expense_id = expense_id
        self.expense_no = expense_no
        self.attachments_dir = "attachments/expenses"
        self.setWindowTitle(f"Attachments - {expense_no}")
        self.setMinimumSize(550, 400)
        self.setWindowIcon(pos_icon())
        self.setModal(True)

        # Create attachments directory if not exists
        os.makedirs(self.attachments_dir, exist_ok=True)

        layout = QVBoxLayout()
        layout.setSpacing(10)

        # Info label
        info_label = QLabel(f"Expense: {expense_no}")
        info_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        layout.addWidget(info_label)

        # Attachment list
        self.attachment_list = QListWidget()
        self.attachment_list.setMinimumHeight(250)
        self.attachment_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.attachment_list.itemDoubleClicked.connect(self.view_attachment)
        layout.addWidget(self.attachment_list)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_upload = QPushButton("Upload")
        self.btn_upload.clicked.connect(self.upload_attachment)

        self.btn_view = QPushButton("View")
        self.btn_view.clicked.connect(self.view_selected_attachment)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self.delete_attachment)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_upload)
        btn_layout.addWidget(self.btn_view)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.load_attachments()
        self.apply_theme_style()  # Only call once
        self.retranslateUi()

    def get_theme(self):
        """Get current theme from settings"""
        try:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='theme'")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else "Light"
        except:
            return "Light"

    def apply_theme_style(self):
        """Apply simple theme styling without borders"""
        theme = self.get_theme()
        
        if theme == "Dark":
            self.setStyleSheet("""
                QDialog {
                    background-color: #36393f;
                }
                QLabel {
                    color: #dcddde;
                }
                QListWidget {
                    background-color: #2f3136;
                    color: #dcddde;
                    border: none;
                    outline: none;
                }
                QListWidget::item {
                    padding: 5px;
                }
                QListWidget::item:selected {
                    background-color: #40444b;
                }
                QListWidget::item:hover {
                    background-color: #383a40;
                }
                QPushButton {
                    background-color: #5865f2;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    padding: 6px 16px;
                }
                QPushButton:hover {
                    background-color: #4752c4;
                }
                QPushButton#closeBtn {
                    background-color: #40444b;
                }
                QPushButton#closeBtn:hover {
                    background-color: #5865f2;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f8f9fa;
                }
                QLabel {
                    color: #2c2f33;
                }
                QListWidget {
                    background-color: #ffffff;
                    color: #2c2f33;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                }
                QListWidget::item {
                    padding: 5px;
                }
                QListWidget::item:selected {
                    background-color: #e3f2fd;
                }
                QListWidget::item:hover {
                    background-color: #f1f3f5;
                }
                QPushButton {
                    background-color: #5865f2;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    padding: 6px 16px;
                }
                QPushButton:hover {
                    background-color: #4752c4;
                }
                QPushButton#closeBtn {
                    background-color: #6c757d;
                }
                QPushButton#closeBtn:hover {
                    background-color: #5865f2;
                }
            """)
        
        # Set object names for specific buttons
        self.btn_close.setObjectName("closeBtn")

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
            self.setWindowTitle(f"ပူးတွဲဖိုင်များ - {self.expense_no}")
            self.btn_upload.setText("တင်ရန်")
            self.btn_view.setText("ကြည့်ရန်")
            self.btn_delete.setText("ဖျက်ရန်")
            self.btn_close.setText("ပိတ်မည်")
        else:
            self.setWindowTitle(f"Attachments - {self.expense_no}")
            self.btn_upload.setText("Upload")
            self.btn_view.setText("View")
            self.btn_delete.setText("Delete")
            self.btn_close.setText("Close")

    def load_attachments(self):
        """Load all attachments for this expense"""
        self.attachment_list.clear()
        
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, filename, file_path, created_at
            FROM expense_attachments
            WHERE expense_id = ?
            ORDER BY created_at DESC
        """, (self.expense_id,))
        attachments = cursor.fetchall()
        conn.close()

        for att_id, filename, file_path, created_at in attachments:
            # Format date
            date_str = created_at[:16] if created_at else ""
            item_text = f"{filename}  ({date_str})"
            item = QListWidgetItem(item_text)
            item.setData(1, att_id)
            item.setData(2, file_path)
            self.attachment_list.addItem(item)

    def upload_attachment(self):
        """Upload a new attachment file"""
        lang = self.get_lang()
        
        file_filter = "Image Files (*.png *.jpg *.jpeg *.gif *.bmp);;PDF Files (*.pdf);;All Files (*.*)"
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", file_filter)
        
        if not file_paths:
            return
        
        uploaded_count = 0
        for file_path in file_paths:
            if not os.path.exists(file_path):
                continue
            
            original_filename = os.path.basename(file_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{self.expense_id}_{timestamp}_{original_filename}"
            dest_path = os.path.join(self.attachments_dir, unique_filename)
            file_size = os.path.getsize(file_path)
            
            try:
                shutil.copy2(file_path, dest_path)
                
                conn = connect_db()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO expense_attachments (expense_id, filename, file_path, file_size)
                    VALUES (?, ?, ?, ?)
                """, (self.expense_id, original_filename, dest_path, file_size))
                conn.commit()
                conn.close()
                
                uploaded_count += 1
            except Exception as e:
                print(f"Error uploading {original_filename}: {e}")
        
        if uploaded_count > 0:
            msg = f"Successfully uploaded {uploaded_count} file(s)." if lang != "my" else f"ဖိုင် {uploaded_count} ခု အောင်မြင်စွာ တင်ခဲ့သည်။"
            QMessageBox.information(self, "Success", msg)
            self.load_attachments()
        else:
            msg = "No files uploaded." if lang != "my" else "ဖိုင်များ မတင်နိုင်ပါ။"
            QMessageBox.warning(self, "Error", msg)

    def get_selected_attachment(self):
        """Get selected attachment data"""
        current = self.attachment_list.currentItem()
        if current:
            # Extract filename from display text
            display_text = current.text()
            filename = display_text.split("  (")[0] if "  (" in display_text else display_text
            return {
                'id': current.data(1),
                'file_path': current.data(2),
                'filename': filename
            }
        return None

    def view_selected_attachment(self):
        """View the selected attachment"""
        attachment = self.get_selected_attachment()
        if not attachment:
            lang = self.get_lang()
            msg = "Please select a file to view." if lang != "my" else "ကျေးဇူးပြု၍ ဖိုင်တစ်ခုရွေးပါ။"
            QMessageBox.warning(self, "No Selection", msg)
            return
        
        self.view_attachment_file(attachment['file_path'])

    def view_attachment(self, item):
        """View attachment on double click"""
        file_path = item.data(2)
        self.view_attachment_file(file_path)

    def view_attachment_file(self, file_path):
        """Open file with default application"""
        import subprocess
        import sys
        
        if not os.path.exists(file_path):
            lang = self.get_lang()
            msg = "File not found." if lang != "my" else "ဖိုင်မတွေ့ပါ။"
            QMessageBox.warning(self, "Error", msg)
            return
        
        try:
            if sys.platform == 'win32':
                os.startfile(file_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', file_path])
            else:
                subprocess.run(['xdg-open', file_path])
        except Exception as e:
            lang = self.get_lang()
            msg = f"Cannot open file: {e}" if lang != "my" else f"ဖိုင်မဖွင့်နိုင်ပါ: {e}"
            QMessageBox.warning(self, "Error", msg)

    def delete_attachment(self):
        """Delete selected attachment"""
        attachment = self.get_selected_attachment()
        if not attachment:
            lang = self.get_lang()
            msg = "Please select a file to delete." if lang != "my" else "ကျေးဇူးပြု၍ ဖျက်လိုသော ဖိုင်ကိုရွေးပါ။"
            QMessageBox.warning(self, "No Selection", msg)
            return
        
        lang = self.get_lang()
        confirm = f"Delete '{attachment['filename']}' permanently?" if lang != "my" else f"'{attachment['filename']}' ကို အပြီးတိုင်ဖျက်မည်လား?"
        reply = QMessageBox.question(self, "Confirm Delete", confirm,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            if os.path.exists(attachment['file_path']):
                try:
                    os.remove(attachment['file_path'])
                except:
                    pass
            
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM expense_attachments WHERE id = ?", (attachment['id'],))
            conn.commit()
            conn.close()
            
            self.load_attachments()
            msg = "File deleted successfully." if lang != "my" else "ဖိုင်ဖျက်ပြီးပါပြီ။"
            QMessageBox.information(self, "Deleted", msg)

    def showEvent(self, event):
        """Re-apply theme style when dialog becomes visible"""
        self.apply_theme_style()
        super().showEvent(event)
