from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QPushButton, QMessageBox, QCheckBox, QSpinBox, QComboBox,
    QGroupBox, QFrame, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QIcon
from models.database import connect_db
from utils.currency import get_currency_symbol, format_money
from datetime import datetime
from utils.branded_icons import pos_icon


class ExpenseNotificationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Expense Notification Settings")
        self.setMinimumSize(800, 600)
        self.setWindowIcon(pos_icon())
        self.setModal(True)

        layout = QVBoxLayout()
        layout.setSpacing(20)

        # ========== NOTIFICATION SETTINGS ==========
        settings_group = QGroupBox("Notification Settings")
        settings_layout = QFormLayout()
        settings_layout.setVerticalSpacing(15)

        # Enable notifications
        self.enable_check = QCheckBox("Enable Expense Notifications")
        settings_layout.addRow("", self.enable_check)

        # Warning threshold
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(50, 100)
        self.threshold_spin.setSuffix("%")
        self.threshold_spin.setToolTip("Alert when expenses reach this percentage of budget")
        settings_layout.addRow("Warning Threshold:", self.threshold_spin)

        # Check frequency
        self.frequency_combo = QComboBox()
        self.frequency_combo.addItems(["Daily", "Weekly", "Monthly"])
        self.frequency_combo.setToolTip("How often to check for budget alerts")
        settings_layout.addRow("Check Frequency:", self.frequency_combo)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # ========== ALERTS HISTORY ==========
        alerts_group = QGroupBox("Recent Alerts")
        alerts_layout = QVBoxLayout()

        self.alerts_table = QTableWidget()
        self.alerts_table.setColumnCount(6)
        self.alerts_table.setHorizontalHeaderLabels([
            "Date", "Category", "Budget", "Actual", "Usage", "Message"
        ])
        self.alerts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.alerts_table.setAlternatingRowColors(True)
        header = self.alerts_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        alerts_layout.addWidget(self.alerts_table)

        btn_clear_alerts = QPushButton("Clear All Alerts")
        btn_clear_alerts.clicked.connect(self.clear_alerts)
        alerts_layout.addWidget(btn_clear_alerts, alignment=Qt.AlignmentFlag.AlignRight)

        alerts_group.setLayout(alerts_layout)
        layout.addWidget(alerts_group)

        # ========== BUTTONS ==========
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save Settings")
        self.btn_save.setStyleSheet("background-color: #27ae60; color: white; padding: 8px 20px;")
        self.btn_save.clicked.connect(self.save_settings)
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_close)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.load_settings()
        self.load_alerts()
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
            self.setWindowTitle("အသုံးစရိတ်သတိပေးချက် သတ်မှတ်ချက်များ")
            self.threshold_spin.setToolTip("ဘတ်ဂျက်၏ ရာခိုင်နှုန်းကိုရောက်ရှိပါက သတိပေးချက်ပြမည်")
            self.frequency_combo.setToolTip("ဘတ်ဂျက်သတိပေးချက်များကို မည်မျှကြာကြာ စစ်ဆေးမည်")
            self.btn_save.setText("သိမ်းဆည်းမည်")
            self.btn_close.setText("ပိတ်မည်")
            self.enable_check.setText("အသုံးစရိတ်သတိပေးချက်များ ဖွင့်မည်")
            self.alerts_table.setHorizontalHeaderLabels([
                "ရက်စွဲ", "အမျိုးအစား", "ဘတ်ဂျက်", "အသုံးစရိတ်", "အသုံးပြုမှု", "စာတို"
            ])
        else:
            self.setWindowTitle("Expense Notification Settings")
            self.threshold_spin.setToolTip("Alert when expenses reach this percentage of budget")
            self.frequency_combo.setToolTip("How often to check for budget alerts")
            self.btn_save.setText("Save Settings")
            self.btn_close.setText("Close")
            self.enable_check.setText("Enable Expense Notifications")
            self.alerts_table.setHorizontalHeaderLabels([
                "Date", "Category", "Budget", "Actual", "Usage", "Message"
            ])

    def load_settings(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT enable_notifications, warning_threshold, check_frequency 
            FROM expense_notification_settings LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()

        if row:
            self.enable_check.setChecked(row[0] == 1)
            self.threshold_spin.setValue(row[1] if row[1] else 80)
            freq = row[2] if row[2] else "daily"
            if freq == "daily":
                self.frequency_combo.setCurrentIndex(0)
            elif freq == "weekly":
                self.frequency_combo.setCurrentIndex(1)
            else:
                self.frequency_combo.setCurrentIndex(2)

    def save_settings(self):
        conn = connect_db()
        cursor = conn.cursor()
        try:
            enable = 1 if self.enable_check.isChecked() else 0
            threshold = self.threshold_spin.value()
            freq = self.frequency_combo.currentText().lower()

            cursor.execute("""
                UPDATE expense_notification_settings 
                SET enable_notifications = ?, warning_threshold = ?, check_frequency = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = (SELECT id FROM expense_notification_settings LIMIT 1)
            """, (enable, threshold, freq))

            conn.commit()
            lang = self.get_lang()
            msg = "Notification settings saved successfully!" if lang != "my" else "သတိပေးချက်သတ်မှတ်ချက်များ သိမ်းဆည်းပြီးပါပြီ။"
            QMessageBox.information(self, "Success", msg)
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")
        finally:
            conn.close()

    def load_alerts(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT created_at, category, budget_amount, actual_amount, used_percentage, message
            FROM expense_alerts_log
            ORDER BY created_at DESC
            LIMIT 50
        """)
        rows = cursor.fetchall()
        conn.close()

        symbol = get_currency_symbol()
        self.alerts_table.setRowCount(0)

        for row in rows:
            r = self.alerts_table.rowCount()
            self.alerts_table.insertRow(r)
            
            self.alerts_table.setItem(r, 0, QTableWidgetItem(row[0][:16] if row[0] else ""))
            self.alerts_table.setItem(r, 1, QTableWidgetItem(row[1] or ""))
            self.alerts_table.setItem(r, 2, QTableWidgetItem(format_money(row[2], symbol) if row[2] else "0"))
            self.alerts_table.setItem(r, 3, QTableWidgetItem(format_money(row[3], symbol) if row[3] else "0"))
            
            percent_item = QTableWidgetItem(f"{row[4]:.1f}%" if row[4] else "0%")
            if row[4] and row[4] >= 100:
                percent_item.setForeground(Qt.GlobalColor.red)
            elif row[4] and row[4] >= 80:
                percent_item.setForeground(Qt.GlobalColor.darkYellow)
            self.alerts_table.setItem(r, 4, percent_item)
            
            self.alerts_table.setItem(r, 5, QTableWidgetItem(row[5] or ""))

    def clear_alerts(self):
        reply = QMessageBox.question(self, "Clear Alerts", "Delete all alert history?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM expense_alerts_log")
            conn.commit()
            conn.close()
            self.load_alerts()
            QMessageBox.information(self, "Success", "Alert history cleared.")
