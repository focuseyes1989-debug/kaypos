from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QComboBox, QDateEdit, QPushButton, QLabel, QMessageBox
from PyQt6.QtCore import Qt, QDate
from models.database import connect_db
from utils.language import lang
from ui.widgets.pagination_widget import PaginationWidget


class ActivityLogPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()

        # Filter bar
        filter_layout = QHBoxLayout()
        self.search_user = QLineEdit()
        self.search_user.setPlaceholderText("Filter by username...")
        filter_layout.addWidget(self.search_user)
        self.action_combo = QComboBox()
        self.action_combo.addItem("All Actions")
        filter_layout.addWidget(self.action_combo)
        self.from_date = QDateEdit()
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addDays(-7))
        filter_layout.addWidget(QLabel("From:"))
        filter_layout.addWidget(self.from_date)
        self.to_date = QDateEdit()
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        filter_layout.addWidget(QLabel("To:"))
        filter_layout.addWidget(self.to_date)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.load_logs)
        filter_layout.addWidget(self.btn_refresh)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Time", "User", "Action", "Details", "IP"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        # Pagination
        self.pagination = PaginationWidget()
        self.pagination.page_changed.connect(self.on_page_changed)
        layout.addWidget(self.pagination)

        self.setLayout(layout)
        self.load_actions_combo()
        self.load_logs()
        lang.language_changed.connect(self.retranslateUi)

    def load_actions_combo(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT action FROM user_activity_log ORDER BY action")
        rows = cursor.fetchall()
        self.action_combo.addItems([row[0] for row in rows])
        conn.close()

    def retranslateUi(self):
        if lang.get_current() == "my":
            self.table.setHorizontalHeaderLabels(["အချိန်", "အသုံးပြုသူ", "လုပ်ဆောင်ချက်", "အသေးစိတ်", "IP"])
            self.search_user.setPlaceholderText("အသုံးပြုသူအမည်ဖြင့် စစ်ထုတ်ရန်...")
            self.btn_refresh.setText("ပြန်လည်")
        else:
            self.table.setHorizontalHeaderLabels(["Time", "User", "Action", "Details", "IP"])
            self.search_user.setPlaceholderText("Filter by username...")
            self.btn_refresh.setText("Refresh")

    def on_page_changed(self, page: int, page_size: int):
        self.load_logs(page, page_size)

    def load_logs(self, page=1, page_size=25):
        username_filter = self.search_user.text().strip()
        action_filter = self.action_combo.currentText()
        from_date = self.from_date.date().toString("yyyy-MM-dd")
        to_date = self.to_date.date().toString("yyyy-MM-dd")

        conn = connect_db()
        cursor = conn.cursor()
        query = """
            SELECT created_at, username, action, details, ip_address
            FROM user_activity_log
            WHERE date(created_at) BETWEEN ? AND ?
        """
        params = [from_date, to_date]
        if username_filter:
            query += " AND username LIKE ?"
            params.append(f'%{username_filter}%')
        if action_filter != "All Actions":
            query += " AND action = ?"
            params.append(action_filter)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        # Count total
        count_query = query.replace("SELECT created_at, username, action, details, ip_address", "SELECT COUNT(*)")
        count_query = count_query.split(" ORDER BY")[0]
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]
        self.pagination.set_total_items(total, emit_signal=False)
        # Fetch page
        cursor.execute(query, params + [page_size, (page-1)*page_size])
        rows = cursor.fetchall()
        conn.close()

        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(row[0]))
            self.table.setItem(i, 1, QTableWidgetItem(row[1]))
            self.table.setItem(i, 2, QTableWidgetItem(row[2]))
            self.table.setItem(i, 3, QTableWidgetItem(row[3] or ""))
            self.table.setItem(i, 4, QTableWidgetItem(row[4] or ""))