from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.modern_button import ModernButton
from utils.restaurant_service import (
    get_restaurant_setting,
    list_restaurant_tables,
    save_restaurant_setting,
    save_restaurant_table,
    set_restaurant_table_active,
)


class RestaurantSettingWidget(QWidget):
    """Restaurant Mode settings and manual table management."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []
        self.setup_ui()
        self.load_settings()
        self.load_tables()

    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(14)

        options_group = QFrame()
        options_group.setObjectName("restaurantSettingsPanel")
        options_layout = QVBoxLayout(options_group)
        options_layout.setContentsMargins(12, 12, 12, 12)
        options_layout.setSpacing(8)
        title = QLabel("Restaurant Options")
        title.setObjectName("restaurantSettingsTitle")
        self.auto_preview_check = QCheckBox("Open kitchen ticket preview after Send Kitchen")
        self.auto_preview_check.stateChanged.connect(self.save_settings)
        options_layout.addWidget(title)
        options_layout.addWidget(self.auto_preview_check)
        layout.addWidget(options_group)

        table_group = QFrame()
        table_group.setObjectName("restaurantSettingsPanel")
        table_layout = QVBoxLayout(table_group)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_layout.setSpacing(8)

        header = QHBoxLayout()
        table_title = QLabel("Tables")
        table_title.setObjectName("restaurantSettingsTitle")
        header.addWidget(table_title)
        header.addStretch()
        self.btn_add = ModernButton(" Add Table", ModernButton.PRIMARY)
        self.btn_add.set_icon("plus", size=(15, 15))
        self.btn_add.setFixedHeight(34)
        self.btn_add.clicked.connect(self.add_table)
        header.addWidget(self.btn_add)
        self.btn_edit = ModernButton(" Edit", ModernButton.SECONDARY)
        self.btn_edit.set_icon("edit", size=(15, 15))
        self.btn_edit.setFixedHeight(34)
        self.btn_edit.clicked.connect(self.edit_selected_table)
        header.addWidget(self.btn_edit)
        self.btn_toggle = ModernButton(" Activate/Deactivate", ModernButton.SECONDARY)
        self.btn_toggle.set_text_only(True)
        self.btn_toggle.setFixedHeight(34)
        self.btn_toggle.clicked.connect(self.toggle_selected_table)
        header.addWidget(self.btn_toggle)
        self.btn_refresh = ModernButton(" Refresh", ModernButton.SECONDARY)
        self.btn_refresh.set_text_only(True)
        self.btn_refresh.setFixedHeight(34)
        self.btn_refresh.clicked.connect(self.load_tables)
        header.addWidget(self.btn_refresh)
        table_layout.addLayout(header)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Table No", "Display Name", "Seats", "Sort", "Active"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.doubleClicked.connect(self.edit_selected_table)
        table_layout.addWidget(self.table, 1)
        layout.addWidget(table_group, 1)

        scroll.setWidget(content)
        root.addWidget(scroll)
        self.update_theme()

    def load_settings(self):
        value = get_restaurant_setting("restaurant_auto_kitchen_preview", "1")
        self.auto_preview_check.blockSignals(True)
        self.auto_preview_check.setChecked(str(value) == "1")
        self.auto_preview_check.blockSignals(False)

    def save_settings(self):
        save_restaurant_setting("restaurant_auto_kitchen_preview", "1" if self.auto_preview_check.isChecked() else "0")

    def load_tables(self):
        self._rows = list_restaurant_tables(include_inactive=True)
        self.table.setRowCount(len(self._rows))
        for row_idx, row in enumerate(self._rows):
            values = [row[0], row[1], row[2], row[3], row[5], "Yes" if row[6] else "No"]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col in (0, 3, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 5 and not row[6]:
                    item.setForeground(Qt.GlobalColor.red)
                self.table.setItem(row_idx, col, item)
        self.table.resizeRowsToContents()

    def selected_row(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(self, "Restaurant Settings", "Select a table first.")
            return None
        index = selected[0].row()
        if index < 0 or index >= len(self._rows):
            return None
        return self._rows[index]

    def add_table(self):
        next_sort = max((int(row[5] or 0) for row in self._rows), default=0) + 1
        self.open_table_dialog(None, f"T{next_sort}", f"Table {next_sort}", 4, next_sort, True)

    def edit_selected_table(self):
        row = self.selected_row()
        if not row:
            return
        table_id, table_no, display_name, seats, status, sort_order, active = row
        self.open_table_dialog(table_id, table_no, display_name, seats, sort_order, bool(active))

    def toggle_selected_table(self):
        row = self.selected_row()
        if not row:
            return
        table_id, table_no, display_name, seats, status, sort_order, active = row
        new_active = not bool(active)
        action = "activate" if new_active else "deactivate"
        reply = QMessageBox.question(
            self,
            "Restaurant Settings",
            f"{action.title()} {display_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        set_restaurant_table_active(table_id, new_active)
        self.load_tables()

    def open_table_dialog(self, table_id, table_no, display_name, seats, sort_order, active):
        dialog = QDialog(self)
        dialog.setWindowTitle("Table")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        table_no_edit = QLineEdit(str(table_no or ""))
        name_edit = QLineEdit(str(display_name or ""))
        seats_spin = QSpinBox()
        seats_spin.setRange(1, 100)
        seats_spin.setValue(max(1, int(seats or 4)))
        sort_spin = QSpinBox()
        sort_spin.setRange(0, 9999)
        sort_spin.setValue(max(0, int(sort_order or 0)))
        active_check = QCheckBox("Active")
        active_check.setChecked(bool(active))
        form.addRow("Table No", table_no_edit)
        form.addRow("Display Name", name_edit)
        form.addRow("Seats", seats_spin)
        form.addRow("Sort Order", sort_spin)
        form.addRow("", active_check)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            save_restaurant_table(
                table_id,
                table_no_edit.text(),
                name_edit.text(),
                seats_spin.value(),
                sort_spin.value(),
                1 if active_check.isChecked() else 0,
            )
            self.load_tables()
        except Exception as exc:
            QMessageBox.critical(self, "Restaurant Settings", f"Could not save table: {exc}")

    def update_theme(self):
        self.setStyleSheet("""
            QFrame#restaurantSettingsPanel {
                border: 1px solid #d0d3d9;
                border-radius: 8px;
                background: transparent;
            }
            QLabel#restaurantSettingsTitle {
                font-weight: 700;
                font-size: 12pt;
            }
        """)
        for button in (self.btn_add, self.btn_edit, self.btn_toggle, self.btn_refresh):
            button.update_theme()

    def retranslateUi(self):
        return
