from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, QDate, QTime
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from models.database import connect_db
from utils.db_compat import is_postgres_backend


STATUS_LABELS = {
    "pending": "Pending",
    "in_progress": "In Progress",
    "ready_for_pickup": "Ready for Pickup",
    "delivered": "Delivered",
    "cancelled": "Cancelled",
}


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _money(value) -> str:
    return f"{float(value or 0):,.0f} Ks"


class ServiceOrderDialog(QDialog):
    def __init__(self, parent=None, order: dict | None = None):
        super().__init__(parent)
        self.order = dict(order or {})
        self.setWindowTitle("Edit Service Order" if order else "New Service Order")
        self.setMinimumWidth(540)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        received = str(self.order.get("received_at") or _now_text())
        received_date = QDate.fromString(received[:10], "yyyy-MM-dd")
        received_time = QTime.fromString(received[11:16], "HH:mm")
        if not received_date.isValid():
            received_date = QDate.currentDate()
        if not received_time.isValid():
            received_time = QTime.currentTime()

        expected = str(self.order.get("expected_at") or "")
        expected_date = QDate.fromString(expected[:10], "yyyy-MM-dd")
        expected_time = QTime.fromString(expected[11:16], "HH:mm")
        if not expected_date.isValid():
            expected_date = QDate.currentDate().addDays(1)
        if not expected_time.isValid():
            expected_time = QTime.currentTime()

        self.received_date = QDateEdit(received_date)
        self.received_date.setCalendarPopup(True)
        self.received_date.setDisplayFormat("yyyy-MM-dd")
        self.received_time = QTimeEdit(received_time)
        self.received_time.setDisplayFormat("HH:mm")
        received_row = QWidget()
        received_layout = QHBoxLayout(received_row)
        received_layout.setContentsMargins(0, 0, 0, 0)
        received_layout.addWidget(self.received_date)
        received_layout.addWidget(self.received_time)

        self.job_title = QLineEdit(str(self.order.get("job_title") or ""))
        self.customer_name = QLineEdit(str(self.order.get("customer_name") or ""))
        self.customer_phone = QLineEdit(str(self.order.get("customer_phone") or ""))
        self.complaint = QTextEdit(str(self.order.get("complaint") or ""))
        self.complaint.setMaximumHeight(100)
        self.expected_date = QDateEdit(expected_date)
        self.expected_date.setCalendarPopup(True)
        self.expected_date.setDisplayFormat("yyyy-MM-dd")
        self.expected_time = QTimeEdit(expected_time)
        self.expected_time.setDisplayFormat("HH:mm")
        expected_row = QWidget()
        expected_layout = QHBoxLayout(expected_row)
        expected_layout.setContentsMargins(0, 0, 0, 0)
        expected_layout.addWidget(self.expected_date)
        expected_layout.addWidget(self.expected_time)
        self.internal_notes = QTextEdit(str(self.order.get("internal_notes") or ""))
        self.internal_notes.setMaximumHeight(90)
        self.deposit_amount = QDoubleSpinBox()
        self.deposit_amount.setRange(0, 999999999)
        self.deposit_amount.setDecimals(0)
        self.deposit_amount.setSuffix(" Ks")
        self.deposit_amount.setValue(float(self.order.get("deposit_amount") or 0))

        form.addRow("Received", received_row)
        form.addRow("Job Name", self.job_title)
        form.addRow("Customer", self.customer_name)
        form.addRow("Phone", self.customer_phone)
        form.addRow("Details", self.complaint)
        form.addRow("Appointment", expected_row)
        form.addRow("Deposit", self.deposit_amount)
        form.addRow("Notes", self.internal_notes)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self) -> None:
        if not self.job_title.text().strip():
            QMessageBox.warning(self, "Service Order", "Enter a job name.")
            return
        self.accept()

    def values(self) -> dict:
        return {
            "received_at": f"{self.received_date.date().toString('yyyy-MM-dd')} {self.received_time.time().toString('HH:mm')}:00",
            "expected_at": f"{self.expected_date.date().toString('yyyy-MM-dd')} {self.expected_time.time().toString('HH:mm')}:00",
            "job_title": self.job_title.text().strip(),
            "customer_name": self.customer_name.text().strip(),
            "customer_phone": self.customer_phone.text().strip(),
            "complaint": self.complaint.toPlainText().strip(),
            "internal_notes": self.internal_notes.toPlainText().strip(),
            "deposit_amount": self.deposit_amount.value(),
        }


class ServiceOrderItemDialog(QDialog):
    def __init__(self, parent=None, item: dict | None = None):
        super().__init__(parent)
        self.item = dict(item or {})
        self.setWindowTitle("Edit Order Item" if item else "Add Order Item")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.item_type = QComboBox()
        self.item_type.addItem("Service", "service")
        self.item_type.addItem("Part", "part")
        self.item_type.addItem("Custom Charge", "custom")
        index = self.item_type.findData(str(self.item.get("item_type") or "service"))
        self.item_type.setCurrentIndex(max(0, index))
        self.description = QLineEdit(str(self.item.get("description") or ""))
        self.qty = QDoubleSpinBox()
        self.qty.setRange(0.01, 999999)
        self.qty.setDecimals(2)
        self.qty.setValue(float(self.item.get("qty") or 1))
        self.unit_price = QDoubleSpinBox()
        self.unit_price.setRange(0, 999999999)
        self.unit_price.setDecimals(0)
        self.unit_price.setSuffix(" Ks")
        self.unit_price.setValue(float(self.item.get("unit_price") or 0))
        self.estimated_cost = QDoubleSpinBox()
        self.estimated_cost.setRange(0, 999999999)
        self.estimated_cost.setDecimals(0)
        self.estimated_cost.setSuffix(" Ks")
        self.estimated_cost.setValue(float(self.item.get("estimated_cost") or 0))
        self.warranty_days = QSpinBox()
        self.warranty_days.setRange(0, 36500)
        self.warranty_days.setValue(int(self.item.get("warranty_days") or 0))
        self.file_name = QLineEdit(str(self.item.get("file_name") or ""))
        self.line_total = QLabel(_money(float(self.item.get("qty") or 1) * float(self.item.get("unit_price") or 0)))

        for label, widget in (
            ("Type", self.item_type),
            ("Description", self.description),
            ("Quantity", self.qty),
            ("Unit Price", self.unit_price),
            ("Line Amount", self.line_total),
            ("Estimated Cost", self.estimated_cost),
            ("Warranty Days", self.warranty_days),
            ("File Name", self.file_name),
        ):
            form.addRow(label, widget)
        layout.addLayout(form)
        self.qty.valueChanged.connect(self._refresh_total)
        self.unit_price.valueChanged.connect(self._refresh_total)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh_total(self) -> None:
        self.line_total.setText(_money(self.qty.value() * self.unit_price.value()))

    def _validate(self) -> None:
        if not self.description.text().strip():
            QMessageBox.warning(self, "Order Item", "Enter a description.")
            return
        self.accept()

    def values(self) -> dict:
        return {
            "item_type": self.item_type.currentData() or "service",
            "description": self.description.text().strip(),
            "qty": self.qty.value(),
            "unit_price": self.unit_price.value(),
            "estimated_cost": self.estimated_cost.value(),
            "warranty_days": self.warranty_days.value(),
            "file_name": self.file_name.text().strip(),
        }


class ServiceOrdersPage(QWidget):
    def __init__(self, current_user: dict | None = None):
        super().__init__()
        self.current_user = dict(current_user or {})
        self.orders: list[dict] = []
        self.selected_order: dict | None = None
        self._build_ui()
        self.load_orders()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        top = QHBoxLayout()
        title = QLabel("Service Orders")
        title.setObjectName("title")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search job, customer, phone, details...")
        self.search.returnPressed.connect(self.load_orders)
        self.status_filter = QComboBox()
        self.status_filter.addItem("All", "")
        for value, label in STATUS_LABELS.items():
            self.status_filter.addItem(label, value)
        self.status_filter.currentIndexChanged.connect(self.load_orders)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.load_orders)
        new = QPushButton("New Job")
        new.clicked.connect(self.new_order)
        top.addWidget(title)
        top.addWidget(self.search, 1)
        top.addWidget(self.status_filter)
        top.addWidget(refresh)
        top.addWidget(new)
        layout.addLayout(top)

        body = QHBoxLayout()
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Date", "Time", "Job Name", "Customer", "Phone", "Appointment", "Status", "Total"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for column, width in {0: 95, 1: 70, 3: 150, 4: 120, 5: 150, 6: 130, 7: 110}.items():
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(column, width)
        self.table.itemSelectionChanged.connect(self.load_selected_order)
        body.addWidget(self.table, 3)

        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(8, 0, 0, 0)
        self.detail_title = QLabel("Select a service order")
        self.detail_title.setWordWrap(True)
        self.detail_summary = QLabel("")
        self.detail_summary.setWordWrap(True)
        self.items_table = QTableWidget(0, 4)
        self.items_table.setHorizontalHeaderLabels(["Description", "Type", "Qty", "Amount"])
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.items_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.history = QListWidget()
        self.history.setMaximumHeight(130)
        detail_layout.addWidget(self.detail_title)
        detail_layout.addWidget(self.detail_summary)
        detail_layout.addWidget(QLabel("Items"))
        detail_layout.addWidget(self.items_table, 1)
        item_actions = QHBoxLayout()
        add_item = QPushButton("Add Item")
        edit_item = QPushButton("Edit")
        remove_item = QPushButton("Remove")
        add_item.clicked.connect(self.add_item)
        edit_item.clicked.connect(self.edit_item)
        remove_item.clicked.connect(self.remove_item)
        item_actions.addWidget(add_item)
        item_actions.addWidget(edit_item)
        item_actions.addWidget(remove_item)
        detail_layout.addLayout(item_actions)
        detail_layout.addWidget(QLabel("Activity History"))
        detail_layout.addWidget(self.history)
        actions = QHBoxLayout()
        edit = QPushButton("Edit Job")
        start = QPushButton("Start")
        ready = QPushButton("Ready")
        deliver = QPushButton("Delivered")
        cancel = QPushButton("Cancel")
        delete = QPushButton("Delete")
        edit.clicked.connect(self.edit_order)
        start.clicked.connect(lambda: self.set_status("in_progress"))
        ready.clicked.connect(lambda: self.set_status("ready_for_pickup"))
        deliver.clicked.connect(lambda: self.set_status("delivered"))
        cancel.clicked.connect(lambda: self.set_status("cancelled"))
        delete.clicked.connect(self.delete_order)
        for button in (edit, start, ready, deliver, cancel, delete):
            actions.addWidget(button)
        detail_layout.addLayout(actions)
        body.addWidget(detail, 2)
        layout.addLayout(body, 1)
        self.status = QLabel("")
        layout.addWidget(self.status)

    def load_orders(self) -> None:
        query = self.search.text().strip()
        status = self.status_filter.currentData() or ""
        sql = """
            SELECT * FROM service_orders
            WHERE (? = '' OR status = ?)
              AND (? = '' OR job_title LIKE ? OR customer_name LIKE ? OR customer_phone LIKE ? OR complaint LIKE ? OR internal_notes LIKE ?)
            ORDER BY received_at DESC, id DESC
            LIMIT 500
        """
        like = f"%{query}%"
        conn = connect_db()
        conn.row_factory = None
        cursor = conn.cursor()
        cursor.execute(sql, (status, status, query, like, like, like, like, like))
        cols = [d[0] for d in cursor.description]
        self.orders = [dict(zip(cols, row)) for row in cursor.fetchall()]
        conn.close()
        self.table.setRowCount(len(self.orders))
        for row, order in enumerate(self.orders):
            received = str(order.get("received_at") or "")
            expected = str(order.get("expected_at") or "")
            values = [
                received[:10],
                received[11:16],
                order.get("job_title") or "",
                order.get("customer_name") or "",
                order.get("customer_phone") or "",
                expected[:16],
                STATUS_LABELS.get(order.get("status"), order.get("status") or ""),
                _money(order.get("total_amount")),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, int(order.get("id") or 0))
                if column == 6:
                    item.setForeground(QColor(self._status_color(str(order.get("status") or ""))))
                if column == 7:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, column, item)
        self.status.setText(f"{len(self.orders)} service order(s)")
        self.load_selected_order()

    def load_selected_order(self) -> None:
        row = self.table.currentRow()
        self.selected_order = self.orders[row] if 0 <= row < len(self.orders) else None
        if not self.selected_order:
            self.detail_title.setText("Select a service order")
            self.detail_summary.clear()
            self.items_table.setRowCount(0)
            self.history.clear()
            return
        order = self.selected_order
        self.detail_title.setText(str(order.get("job_title") or "Service Order"))
        self.detail_summary.setText(
            f"Customer: {order.get('customer_name') or '-'}\n"
            f"Phone: {order.get('customer_phone') or '-'}\n"
            f"Status: {STATUS_LABELS.get(order.get('status'), order.get('status') or '-')}\n"
            f"Deposit: {_money(order.get('deposit_amount'))} | Total: {_money(order.get('total_amount'))}\n\n"
            f"{order.get('complaint') or ''}"
        )
        self.load_items()
        self.load_history()

    def load_items(self) -> None:
        order_id = self._selected_order_id()
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM service_order_items WHERE service_order_id = ? ORDER BY id", (order_id,))
        cols = [d[0] for d in cursor.description]
        items = [dict(zip(cols, row)) for row in cursor.fetchall()]
        conn.close()
        self.items_table.setRowCount(len(items))
        for row, item in enumerate(items):
            values = [
                item.get("description") or "",
                item.get("item_type") or "",
                f"{float(item.get('qty') or 0):g}",
                _money(float(item.get("qty") or 0) * float(item.get("unit_price") or 0)),
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, int(item.get("id") or 0))
                self.items_table.setItem(row, column, cell)

    def load_history(self) -> None:
        self.history.clear()
        order_id = self._selected_order_id()
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT action, note, created_by, created_at FROM service_order_history WHERE service_order_id = ? ORDER BY created_at DESC, id DESC LIMIT 50",
            (order_id,),
        )
        for action, note, created_by, created_at in cursor.fetchall():
            by = f" · {created_by}" if created_by else ""
            details = f" · {note}" if note else ""
            self.history.addItem(f"{created_at} · {action}{by}{details}")
        conn.close()

    def new_order(self) -> None:
        dialog = ServiceOrderDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        job_no = "SJ-" + datetime.now().strftime("%Y%m%d%H%M%S")
        conn = connect_db()
        cursor = conn.cursor()
        if is_postgres_backend():
            cursor.execute(
                """
                INSERT INTO service_orders (job_no, job_title, customer_name, customer_phone, complaint, internal_notes, received_at, expected_at, deposit_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (job_no, values["job_title"], values["customer_name"], values["customer_phone"], values["complaint"], values["internal_notes"], values["received_at"], values["expected_at"], values["deposit_amount"]),
            )
            order_id = int(cursor.fetchone()[0])
        else:
            cursor.execute(
                """
                INSERT INTO service_orders (job_no, job_title, customer_name, customer_phone, complaint, internal_notes, received_at, expected_at, deposit_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_no, values["job_title"], values["customer_name"], values["customer_phone"], values["complaint"], values["internal_notes"], values["received_at"], values["expected_at"], values["deposit_amount"]),
            )
            order_id = int(cursor.lastrowid)
        self._add_history(cursor, order_id, "Created", "")
        conn.commit()
        conn.close()
        self.load_orders()

    def edit_order(self) -> None:
        if not self.selected_order:
            return
        dialog = ServiceOrderDialog(self, self.selected_order)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE service_orders
            SET job_title = ?, customer_name = ?, customer_phone = ?, complaint = ?, internal_notes = ?,
                received_at = ?, expected_at = ?, deposit_amount = ?, updated_at = ?
            WHERE id = ?
            """,
            (values["job_title"], values["customer_name"], values["customer_phone"], values["complaint"], values["internal_notes"], values["received_at"], values["expected_at"], values["deposit_amount"], _now_text(), self._selected_order_id()),
        )
        self._add_history(cursor, self._selected_order_id(), "Updated", "")
        conn.commit()
        conn.close()
        self.load_orders()

    def set_status(self, status: str) -> None:
        if not self.selected_order:
            return
        fields = {"status": status, "updated_at": _now_text()}
        if status == "in_progress":
            fields["work_started_at"] = _now_text()
            fields["working_by"] = self._username()
        elif status == "ready_for_pickup":
            fields["work_completed_at"] = _now_text()
            fields["work_completed_by"] = self._username()
        elif status == "delivered":
            fields["delivered_at"] = _now_text()
            fields["delivered_by"] = self._username()
        elif status == "cancelled":
            fields["cancelled_at"] = _now_text()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE service_orders SET {assignments} WHERE id = ?", (*fields.values(), self._selected_order_id()))
        self._add_history(cursor, self._selected_order_id(), f"Status: {STATUS_LABELS.get(status, status)}", "")
        conn.commit()
        conn.close()
        self.load_orders()

    def delete_order(self) -> None:
        if not self.selected_order:
            return
        if QMessageBox.question(self, "Delete Service Order", "Delete this service order and its items?") != QMessageBox.StandardButton.Yes:
            return
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM service_orders WHERE id = ?", (self._selected_order_id(),))
        conn.commit()
        conn.close()
        self.load_orders()

    def add_item(self) -> None:
        if not self.selected_order:
            return
        dialog = ServiceOrderItemDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO service_order_items (service_order_id, item_type, description, qty, unit_price, estimated_cost, warranty_days, file_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (self._selected_order_id(), values["item_type"], values["description"], values["qty"], values["unit_price"], values["estimated_cost"], values["warranty_days"], values["file_name"]),
        )
        self._add_history(cursor, self._selected_order_id(), "Item Added", values["description"])
        self._recalculate_total(cursor, self._selected_order_id())
        conn.commit()
        conn.close()
        self.load_orders()

    def edit_item(self) -> None:
        item = self._selected_item()
        if not item:
            return
        dialog = ServiceOrderItemDialog(self, item)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE service_order_items
            SET item_type = ?, description = ?, qty = ?, unit_price = ?, estimated_cost = ?, warranty_days = ?, file_name = ?, updated_at = ?
            WHERE id = ?
            """,
            (values["item_type"], values["description"], values["qty"], values["unit_price"], values["estimated_cost"], values["warranty_days"], values["file_name"], _now_text(), item["id"]),
        )
        self._add_history(cursor, self._selected_order_id(), "Item Updated", values["description"])
        self._recalculate_total(cursor, self._selected_order_id())
        conn.commit()
        conn.close()
        self.load_orders()

    def remove_item(self) -> None:
        item = self._selected_item()
        if not item:
            return
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM service_order_items WHERE id = ?", (item["id"],))
        self._add_history(cursor, self._selected_order_id(), "Item Removed", item["description"])
        self._recalculate_total(cursor, self._selected_order_id())
        conn.commit()
        conn.close()
        self.load_orders()

    def _selected_item(self) -> dict | None:
        row = self.items_table.currentRow()
        if row < 0:
            return None
        cell = self.items_table.item(row, 0)
        if cell is None:
            return None
        item_id = int(cell.data(Qt.ItemDataRole.UserRole) or 0)
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM service_order_items WHERE id = ?", (item_id,))
        row_data = cursor.fetchone()
        cols = [d[0] for d in cursor.description]
        conn.close()
        return dict(zip(cols, row_data)) if row_data else None

    def _selected_order_id(self) -> int:
        return int((self.selected_order or {}).get("id") or 0)

    def _username(self) -> str:
        return str(self.current_user.get("username") or self.current_user.get("full_name") or "")

    def _add_history(self, cursor, order_id: int, action: str, note: str) -> None:
        cursor.execute(
            "INSERT INTO service_order_history (service_order_id, action, note, created_by) VALUES (?, ?, ?, ?)",
            (order_id, action, note, self._username()),
        )

    def _recalculate_total(self, cursor, order_id: int) -> None:
        cursor.execute(
            "SELECT COALESCE(SUM(qty * unit_price), 0) FROM service_order_items WHERE service_order_id = ?",
            (order_id,),
        )
        total = float(cursor.fetchone()[0] or 0)
        cursor.execute("UPDATE service_orders SET total_amount = ?, updated_at = ? WHERE id = ?", (total, _now_text(), order_id))

    @staticmethod
    def _status_color(status: str) -> str:
        return {
            "pending": "#92400e",
            "in_progress": "#1e40af",
            "ready_for_pickup": "#6b21a8",
            "delivered": "#166534",
            "cancelled": "#991b1b",
        }.get(status, "#334155")
