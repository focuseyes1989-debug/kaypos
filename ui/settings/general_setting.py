# ui/general_setting.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView,
    QDialog, QFormLayout, QDialogButtonBox, QCheckBox, QDoubleSpinBox,
    QSpinBox, QScrollArea, QFrame, QComboBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from models.database import connect_db
from utils.language import lang
from ui.responsive_utils import get_supported_resolution_options, parse_resolution
from utils.sale_mode import get_sale_mode, save_sale_mode


def _save_setting(cursor, key, value):
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, str(value)),
    )


class PaymentTypeDialog(QDialog):
    def __init__(self, payment_id=None, current_name=""):
        super().__init__()
        self.payment_id = payment_id
        self.setMinimumWidth(300)
        layout = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setText(current_name)
        layout.addRow(QLabel("Name:"), self.name_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.setLayout(layout)
        self.retranslateUi()

    def retranslateUi(self):
        if lang.get_current() == "my":
            self.setWindowTitle("ငွေပေးချေမှုအမျိုးအစား" if self.payment_id is None else "ငွေပေးချေမှုအမျိုးအစားပြင်ဆင်ရန်")
        else:
            self.setWindowTitle("Add Payment Type" if self.payment_id is None else "Edit Payment Type")

    def get_name(self):
        return self.name_edit.text().strip()


class GeneralSettingWidget(QWidget):
    settings_saved = pyqtSignal()
    follow_system_theme_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_payment_id = None
        self.setup_ui()
        self.load_payment_types()
        self.load_tax_settings()
        self.load_loyalty_settings()
        self.load_discount_settings()
        self.load_appearance_settings()

    def setup_ui(self):
        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(20)

        # Main two-column layout with equal width distribution
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(20)

        left_column = QWidget()
        self.left_column = left_column
        left_column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(15)

        right_column = QWidget()
        self.right_column = right_column
        right_column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)

        # Payment Types (left)
        self.payment_group = QGroupBox()
        self.payment_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        payment_layout = QVBoxLayout()
        payment_layout.setSpacing(8)
        
        # Table with fixed height to prevent over-expansion
        self.payment_table = QTableWidget()
        self.payment_table.setColumnCount(2)
        self.payment_table.setColumnHidden(0, True)
        self.payment_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.payment_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.payment_table.setMinimumHeight(200)
        self.payment_table.setMaximumHeight(300)
        self.payment_table.cellClicked.connect(self.select_payment)
        self.payment_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        payment_layout.addWidget(self.payment_table)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        self.btn_add_pay = QPushButton()
        self.btn_edit_pay = QPushButton()
        self.btn_delete_pay = QPushButton()
        self.btn_add_pay.clicked.connect(self.add_payment_type)
        self.btn_edit_pay.clicked.connect(self.edit_payment_type)
        self.btn_delete_pay.clicked.connect(self.delete_payment_type)
        btn_layout.addWidget(self.btn_add_pay)
        btn_layout.addWidget(self.btn_edit_pay)
        btn_layout.addWidget(self.btn_delete_pay)
        btn_layout.addStretch()
        payment_layout.addLayout(btn_layout)
        self.payment_group.setLayout(payment_layout)
        left_layout.addWidget(self.payment_group)

        # Tax (left) - compact layout
        self.tax_group = QGroupBox()
        self.tax_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        tax_layout = QHBoxLayout()
        tax_layout.setSpacing(10)
        self.tax_enabled = QCheckBox()
        self.tax_rate = QDoubleSpinBox()
        self.tax_rate.setRange(0, 100)
        self.tax_rate.setSuffix(" %")
        self.tax_rate.setDecimals(2)
        self.tax_rate.setFixedWidth(100)
        tax_layout.addWidget(self.tax_enabled)
        tax_layout.addWidget(QLabel("Tax Rate:"))
        tax_layout.addWidget(self.tax_rate)
        tax_layout.addStretch()
        self.tax_group.setLayout(tax_layout)
        left_layout.addWidget(self.tax_group)

        # Loyalty (right)
        self.royalty_group = QGroupBox()
        self.royalty_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        royalty_layout = QFormLayout()
        royalty_layout.setSpacing(6)
        
        self.points_per_dollar = QDoubleSpinBox()
        self.points_per_dollar.setRange(0, 100)
        self.points_per_dollar.setDecimals(2)
        self.points_per_dollar.setSuffix(" per $")
        self.min_points = QSpinBox()
        self.min_points.setRange(0, 10000)
        self.min_points.setSuffix(" pts")
        self.reward_discount = QDoubleSpinBox()
        self.reward_discount.setRange(0, 1000)
        self.reward_discount.setDecimals(2)
        self.reward_discount.setSuffix(" $")
        self.points_expiry_months = QSpinBox()
        self.points_expiry_months.setRange(0, 60)
        self.points_expiry_months.setSuffix(" months")
        self.points_dollar_value = QDoubleSpinBox()
        self.points_dollar_value.setRange(0, 1)
        self.points_dollar_value.setDecimals(3)
        self.points_dollar_value.setSingleStep(0.001)
        self.points_dollar_value.setSuffix(" $")

        royalty_layout.addRow("Points per $:", self.points_per_dollar)
        royalty_layout.addRow("Min points for reward:", self.min_points)
        royalty_layout.addRow("Reward discount:", self.reward_discount)
        royalty_layout.addRow("Points expiry (0=never):", self.points_expiry_months)
        royalty_layout.addRow("Value per point:", self.points_dollar_value)
        self.royalty_group.setLayout(royalty_layout)
        right_layout.addWidget(self.royalty_group)

        # Discount (right)
        self.discount_group = QGroupBox()
        self.discount_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        discount_layout = QFormLayout()
        discount_layout.setSpacing(6)
        
        self.discount_enabled = QCheckBox()
        discount_layout.addRow("", self.discount_enabled)
        
        # Radio buttons for discount type
        self.discount_type_percent = QCheckBox("Percentage (%)")
        self.discount_type_fixed = QCheckBox("Fixed Amount ($)")
        self.discount_type_manual = QCheckBox("Manual")
        
        # Connect toggle signals properly
        self.discount_type_percent.toggled.connect(lambda checked: self.discount_type_fixed.setChecked(False) if checked and self.discount_type_fixed.isChecked() else None)
        self.discount_type_percent.toggled.connect(lambda checked: self.discount_type_manual.setChecked(False) if checked and self.discount_type_manual.isChecked() else None)
        self.discount_type_fixed.toggled.connect(lambda checked: self.discount_type_percent.setChecked(False) if checked and self.discount_type_percent.isChecked() else None)
        self.discount_type_fixed.toggled.connect(lambda checked: self.discount_type_manual.setChecked(False) if checked and self.discount_type_manual.isChecked() else None)
        self.discount_type_manual.toggled.connect(lambda checked: self.discount_type_percent.setChecked(False) if checked and self.discount_type_percent.isChecked() else None)
        self.discount_type_manual.toggled.connect(lambda checked: self.discount_type_fixed.setChecked(False) if checked and self.discount_type_fixed.isChecked() else None)
        
        type_widget = QWidget()
        type_layout = QVBoxLayout(type_widget)
        type_layout.setSpacing(2)
        type_layout.addWidget(self.discount_type_percent)
        type_layout.addWidget(self.discount_type_fixed)
        type_layout.addWidget(self.discount_type_manual)
        discount_layout.addRow("Discount Type:", type_widget)
        
        self.discount_value = QDoubleSpinBox()
        self.discount_value.setRange(0, 100000)
        self.discount_value.setDecimals(2)
        self.discount_value.setSuffix("%")
        self.discount_value.setEnabled(False)
        
        def update_discount_suffix():
            if self.discount_type_percent.isChecked():
                self.discount_value.setSuffix("%")
                self.discount_value.setEnabled(True)
            elif self.discount_type_fixed.isChecked():
                self.discount_value.setSuffix("$")
                self.discount_value.setEnabled(True)
            else:
                self.discount_value.setEnabled(False)
        
        self.discount_type_percent.toggled.connect(update_discount_suffix)
        self.discount_type_fixed.toggled.connect(update_discount_suffix)
        self.discount_type_manual.toggled.connect(update_discount_suffix)
        
        discount_layout.addRow("Default Value:", self.discount_value)
        self.discount_group.setLayout(discount_layout)
        right_layout.addWidget(self.discount_group)

        # Appearance (right) - with theme selection
        self.appearance_group = QGroupBox()
        self.appearance_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        appearance_layout = QFormLayout()
        appearance_layout.setSpacing(6)
        
        # Theme selection combo box
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Light Gray", "Dark"])
        appearance_layout.addRow("Theme:", self.theme_combo)

        self.resolution_combo = QComboBox()
        self._load_resolution_options()
        appearance_layout.addRow("Resolution:", self.resolution_combo)

        self.sale_mode_combo = QComboBox()
        self.sale_mode_combo.addItem("Retail Sale", "retail")
        self.sale_mode_combo.addItem("Restaurant Mode", "restaurant")
        self.sale_mode_combo.addItem("Both", "both")
        appearance_layout.addRow("POS Sale Mode:", self.sale_mode_combo)
        
        self.follow_system_theme_check = QCheckBox("Follow system theme")
        self.follow_system_theme_check.toggled.connect(self.on_follow_system_toggled)
        appearance_layout.addRow("", self.follow_system_theme_check)

        self.dashboard_digest_enabled = QCheckBox("Generate local AI executive digests")
        self.dashboard_digest_enabled.setToolTip("Creates completed daily, weekly and monthly reports locally while the app is running.")
        appearance_layout.addRow("", self.dashboard_digest_enabled)
        
        self.appearance_group.setLayout(appearance_layout)
        right_layout.addWidget(self.appearance_group)

        # Add columns to main layout
        columns_layout.addWidget(left_column, 1)  # Equal stretch
        columns_layout.addWidget(right_column, 1)  # Equal stretch
        content_layout.addLayout(columns_layout)

        # Save button
        self.btn_save = QPushButton()
        self.btn_save.clicked.connect(self.save_settings)
        self.btn_save.setMinimumWidth(200)
        self.btn_save.setMaximumWidth(300)
        content_layout.addWidget(self.btn_save, alignment=Qt.AlignmentFlag.AlignCenter)
        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.setLayout(layout)
        self.retranslateUi()

    def set_visible_sections(self, sections):
        """Show only selected setting groups when embedded in Settings Center."""
        visible = set(sections or [])
        group_map = {
            "payments": self.payment_group,
            "tax": self.tax_group,
            "loyalty": self.royalty_group,
            "discount": self.discount_group,
            "appearance": self.appearance_group,
        }
        for key, group in group_map.items():
            group.setVisible(key in visible)

        self.left_column.setVisible(any(key in visible for key in ("payments", "tax")))
        self.right_column.setVisible(any(key in visible for key in ("loyalty", "discount", "appearance")))

    def retranslateUi(self):
        if lang.get_current() == "my":
            self.payment_group.setTitle("ငွေပေးချေမှုအမျိုးအစားများ")
            self.payment_table.setHorizontalHeaderLabels(["ID", "ငွေပေးချေမှုအမည်"])
            self.btn_add_pay.setText("အသစ်ထည့်")
            self.btn_edit_pay.setText("ပြင်ဆင်")
            self.btn_delete_pay.setText("ဖျက်")
            self.tax_group.setTitle("အခွန်သတ်မှတ်ချက်")
            self.tax_enabled.setText("အခွန်သုံးမည်")
            self.royalty_group.setTitle("အမှတ်ပေးစနစ်")
            # Update royalty labels
            for row in range(self.royalty_group.layout().rowCount()):
                label_item = self.royalty_group.layout().itemAt(row, QFormLayout.ItemRole.LabelRole)
                if label_item and isinstance(label_item.widget(), QLabel):
                    text = label_item.widget().text()
                    if "Points per $" in text or "per $" in text:
                        label_item.widget().setText("တစ်ဒေါ်လာလျှင်ရမည့်အမှတ်:")
                    elif "Min points" in text:
                        label_item.widget().setText("ဆုချီးမြှင့်ရန်အနည်းဆုံးအမှတ်:")
                    elif "Reward discount" in text:
                        label_item.widget().setText("ဆုလျှော့စျေးပမာဏ:")
                    elif "Points expiry" in text:
                        label_item.widget().setText("အမှတ်သက်တမ်းကုန်ရက် (၀=ဘယ်တော့မှမကုန်):")
                    elif "Value per point" in text:
                        label_item.widget().setText("တစ်အမှတ်တန်ဖိုး:")
            self.discount_group.setTitle("လျှော့စျေးသတ်မှတ်ချက်")
            self.discount_enabled.setText("လျှော့စျေးသုံးမည်")
            for row in range(self.discount_group.layout().rowCount()):
                label_item = self.discount_group.layout().itemAt(row, QFormLayout.ItemRole.LabelRole)
                if label_item and isinstance(label_item.widget(), QLabel):
                    text = label_item.widget().text()
                    if "Discount Type" in text:
                        label_item.widget().setText("လျှော့စျေးအမျိုးအစား:")
                    elif "Default Value" in text:
                        label_item.widget().setText("မူလတန်ဖိုး:")
            self.discount_type_percent.setText("ရာခိုင်နှုန်း (%)")
            self.discount_type_fixed.setText("သတ်မှတ်ပမာဏ ($)")
            self.discount_type_manual.setText("လက်ဖြင့်ရိုက်ထည့်ရန်")
            self.appearance_group.setTitle("အပြင်အဆင်")
            self.follow_system_theme_check.setText("စနစ်၏အပြင်အဆင်ကို အလိုအလျောက်လိုက်ရန်")
            self.dashboard_digest_enabled.setText("AI အုပ်ချုပ်မှုအစီရင်ခံစာများကို စက်အတွင်း ဖန်တီးမည်")
            self.btn_save.setText("သိမ်းဆည်းမည်")
        else:
            self.payment_group.setTitle("Payment Types")
            self.payment_table.setHorizontalHeaderLabels(["ID", "Payment Method"])
            self.btn_add_pay.setText("Add")
            self.btn_edit_pay.setText("Edit")
            self.btn_delete_pay.setText("Delete")
            self.tax_group.setTitle("Tax Setting")
            self.tax_enabled.setText("Enable Tax")
            self.royalty_group.setTitle("Loyalty Settings")
            for row in range(self.royalty_group.layout().rowCount()):
                label_item = self.royalty_group.layout().itemAt(row, QFormLayout.ItemRole.LabelRole)
                if label_item and isinstance(label_item.widget(), QLabel):
                    text = label_item.widget().text()
                    if "တစ်ဒေါ်လာလျှင်ရမည့်အမှတ်" in text:
                        label_item.widget().setText("Points per $:")
                    elif "ဆုချီးမြှင့်ရန်အနည်းဆုံးအမှတ်" in text:
                        label_item.widget().setText("Min points for reward:")
                    elif "ဆုလျှော့စျေးပမာဏ" in text:
                        label_item.widget().setText("Reward discount:")
                    elif "အမှတ်သက်တမ်းကုန်ရက်" in text:
                        label_item.widget().setText("Points expiry (0=never):")
                    elif "တစ်အမှတ်တန်ဖိုး" in text:
                        label_item.widget().setText("Value per point:")
            self.discount_group.setTitle("Discount Setting")
            self.discount_enabled.setText("Enable Discount")
            for row in range(self.discount_group.layout().rowCount()):
                label_item = self.discount_group.layout().itemAt(row, QFormLayout.ItemRole.LabelRole)
                if label_item and isinstance(label_item.widget(), QLabel):
                    text = label_item.widget().text()
                    if "လျှော့စျေးအမျိုးအစား" in text:
                        label_item.widget().setText("Discount Type:")
                    elif "မူလတန်ဖိုး" in text:
                        label_item.widget().setText("Default Value:")
            self.discount_type_percent.setText("Percentage (%)")
            self.discount_type_fixed.setText("Fixed Amount ($)")
            self.discount_type_manual.setText("Manual")
            self.appearance_group.setTitle("Appearance")
            self.follow_system_theme_check.setText("Follow system theme")
            self.dashboard_digest_enabled.setText("Generate local AI executive digests")
            self.btn_save.setText("Save General Settings")

    def _load_resolution_options(self):
        from PyQt6.QtWidgets import QApplication

        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.availableGeometry()
            screen_width = geometry.width()
            screen_height = geometry.height()
        else:
            screen_width = 1366
            screen_height = 768

        self.resolution_combo.clear()
        for label, width, height in get_supported_resolution_options(screen_width, screen_height):
            self.resolution_combo.addItem(label, f"{width}x{height}")

    def on_follow_system_toggled(self, checked):
        conn = None
        try:
            conn = connect_db()
            cursor = conn.cursor()
            _save_setting(cursor, "follow_system_theme", "1" if checked else "0")
            conn.commit()
        except Exception as exc:
            QMessageBox.warning(self, "Database Error", f"Could not save theme setting:\n{exc}")
            return
        finally:
            if conn:
                conn.close()
        # Emit signal so MainWindow can update menu states and apply theme
        self.follow_system_theme_changed.emit(checked)

    def load_appearance_settings(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key='follow_system_theme'")
        row = cursor.fetchone()
        checked = row[0] == '1' if row else True
        was_blocked = self.follow_system_theme_check.blockSignals(True)
        self.follow_system_theme_check.setChecked(checked)
        self.follow_system_theme_check.blockSignals(was_blocked)
        
        # Load saved theme
        cursor.execute("SELECT value FROM settings WHERE key='theme'")
        row = cursor.fetchone()
        saved_theme = row[0] if row else "Light"
        if saved_theme not in {"Light", "Light Gray", "Dark"}:
            saved_theme = "Light"
        index = self.theme_combo.findText(saved_theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)

        self._load_resolution_options()
        cursor.execute("SELECT value FROM settings WHERE key='window_resolution'")
        row = cursor.fetchone()
        saved_resolution = row[0] if row else "1366x768"
        width, height = parse_resolution(saved_resolution)
        resolution_value = f"{width}x{height}"
        index = self.resolution_combo.findData(resolution_value)
        if index >= 0:
            self.resolution_combo.setCurrentIndex(index)
        elif self.resolution_combo.count() > 0:
            self.resolution_combo.setCurrentIndex(0)
        cursor.execute("SELECT value FROM settings WHERE key='ai_dashboard_digest_enabled'")
        row=cursor.fetchone();self.dashboard_digest_enabled.setChecked(str(row[0] if row else "1").lower() in ("1","true","yes","on"))
        conn.close()

        sale_mode = get_sale_mode()
        index = self.sale_mode_combo.findData(sale_mode)
        if index >= 0:
            self.sale_mode_combo.setCurrentIndex(index)

    def save_settings(self):
        main_window = self.window()
        if hasattr(main_window, "show_loading"):
            main_window.show_loading("Saving general settings...", 15)
        conn = None
        try:
            conn = connect_db()
            cursor = conn.cursor()
            values = {
                "tax_enabled": "1" if self.tax_enabled.isChecked() else "0",
                "tax_rate": self.tax_rate.value(),
                "loyalty_points_per_dollar": self.points_per_dollar.value(),
                "loyalty_min_points_for_reward": self.min_points.value(),
                "loyalty_reward_discount": self.reward_discount.value(),
                "points_expiry_months": self.points_expiry_months.value(),
                "points_dollar_value": self.points_dollar_value.value(),
                "discount_enabled": "1" if self.discount_enabled.isChecked() else "0",
                "discount_value": self.discount_value.value(),
                "theme": self.theme_combo.currentText(),
                "window_resolution": self.resolution_combo.currentData() or "1366x768",
                "ai_dashboard_digest_enabled": "1" if self.dashboard_digest_enabled.isChecked() else "0",
            }

            if self.discount_type_percent.isChecked():
                values["discount_type"] = "percentage"
            elif self.discount_type_fixed.isChecked():
                values["discount_type"] = "fixed"
            else:
                values["discount_type"] = "manual"

            for key, value in values.items():
                _save_setting(cursor, key, value)
            conn.commit()
        except Exception as exc:
            if hasattr(main_window, "hide_loading"):
                main_window.hide_loading()
            QMessageBox.warning(self, "Database Error", f"Could not save general settings:\n{exc}")
            return
        finally:
            if conn:
                conn.close()
        save_sale_mode(self.sale_mode_combo.currentData() or "retail")
        if hasattr(main_window, "update_loading"):
            main_window.update_loading("General settings saved.", 100)
        if hasattr(main_window, "hide_loading"):
            main_window.hide_loading()
        
        msg = "အထွေထွေသတ်မှတ်ချက်များ သိမ်းဆည်းပြီးပါပြီ။" if lang.get_current() == "my" else "General settings saved."
        QMessageBox.information(self, "Saved", msg)
        self.settings_saved.emit()

    # ---------- Payment type methods ----------
    def load_payment_types(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM payment_types ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        self.payment_table.setRowCount(0)
        self.selected_payment_id = None
        for row in rows:
            r = self.payment_table.rowCount()
            self.payment_table.insertRow(r)
            self.payment_table.setItem(r, 0, QTableWidgetItem(str(row[0])))
            self.payment_table.setItem(r, 1, QTableWidgetItem(row[1]))

    def select_payment(self, row, col):
        id_item = self.payment_table.item(row, 0)
        if id_item:
            self.selected_payment_id = int(id_item.text())

    def add_payment_type(self):
        dialog = PaymentTypeDialog()
        if dialog.exec():
            name = dialog.get_name()
            if not name:
                msg = "အမည်မဖြည့်နိုင်ပါ။" if lang.get_current() == "my" else "Name cannot be empty"
                QMessageBox.warning(self, "Error", msg)
                return
            conn = connect_db()
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO payment_types (name) VALUES (?)", (name,))
                conn.commit()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Cannot add: {e}")
            finally:
                conn.close()
            self.load_payment_types()
            self.settings_saved.emit()

    def edit_payment_type(self):
        if not hasattr(self, 'selected_payment_id') or not self.selected_payment_id:
            msg = "ကျေးဇူးပြု၍ ပြင်ဆင်လိုသော အမျိုးအစားကို ရွေးပါ။" if lang.get_current() == "my" else "Select a payment type first"
            QMessageBox.warning(self, "No Selection", msg)
            return
        current_name = ""
        for row in range(self.payment_table.rowCount()):
            if int(self.payment_table.item(row, 0).text()) == self.selected_payment_id:
                current_name = self.payment_table.item(row, 1).text()
                break
        dialog = PaymentTypeDialog(self.selected_payment_id, current_name)
        if dialog.exec():
            new_name = dialog.get_name()
            if not new_name:
                msg = "အမည်မဖြည့်နိုင်ပါ။" if lang.get_current() == "my" else "Name cannot be empty"
                QMessageBox.warning(self, "Error", msg)
                return
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("UPDATE payment_types SET name=? WHERE id=?", (new_name, self.selected_payment_id))
            conn.commit()
            conn.close()
            self.load_payment_types()
            self.settings_saved.emit()

    def delete_payment_type(self):
        if not hasattr(self, 'selected_payment_id') or not self.selected_payment_id:
            msg = "ကျေးဇူးပြု၍ ဖျက်လိုသော အမျိုးအစားကို ရွေးပါ။" if lang.get_current() == "my" else "Select a payment type first"
            QMessageBox.warning(self, "No Selection", msg)
            return
        confirm = "ဤငွေပေးချေမှုအမျိုးအစားကို ဖျက်မည်လား?" if lang.get_current() == "my" else "Delete this payment type?"
        reply = QMessageBox.question(self, "Confirm Delete", confirm, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM payment_types WHERE id=?", (self.selected_payment_id,))
            conn.commit()
            conn.close()
            self.load_payment_types()
            self.settings_saved.emit()

    def load_tax_settings(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key='tax_enabled'")
        enabled = cursor.fetchone()
        cursor.execute("SELECT value FROM settings WHERE key='tax_rate'")
        rate = cursor.fetchone()
        conn.close()
        self.tax_enabled.setChecked(enabled[0] == '1' if enabled else False)
        self.tax_rate.setValue(float(rate[0]) if rate else 0.0)

    def load_loyalty_settings(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key='loyalty_points_per_dollar'")
        points = cursor.fetchone()
        cursor.execute("SELECT value FROM settings WHERE key='loyalty_min_points_for_reward'")
        min_pts = cursor.fetchone()
        cursor.execute("SELECT value FROM settings WHERE key='loyalty_reward_discount'")
        discount = cursor.fetchone()
        cursor.execute("SELECT value FROM settings WHERE key='points_expiry_months'")
        expiry = cursor.fetchone()
        cursor.execute("SELECT value FROM settings WHERE key='points_dollar_value'")
        point_value = cursor.fetchone()
        conn.close()
        self.points_per_dollar.setValue(float(points[0]) if points else 0.0)
        self.min_points.setValue(int(min_pts[0]) if min_pts else 100)
        self.reward_discount.setValue(float(discount[0]) if discount else 5.0)
        self.points_expiry_months.setValue(int(expiry[0]) if expiry else 12)
        self.points_dollar_value.setValue(float(point_value[0]) if point_value else 0.01)

    def load_discount_settings(self):
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key='discount_enabled'")
        enabled = cursor.fetchone()
        cursor.execute("SELECT value FROM settings WHERE key='discount_type'")
        dtype = cursor.fetchone()
        cursor.execute("SELECT value FROM settings WHERE key='discount_value'")
        dvalue = cursor.fetchone()
        conn.close()
        self.discount_enabled.setChecked(enabled[0] == '1' if enabled else False)
        discount_type = dtype[0] if dtype else "percentage"
        if discount_type == "percentage":
            self.discount_type_percent.setChecked(True)
        elif discount_type == "fixed":
            self.discount_type_fixed.setChecked(True)
        else:
            self.discount_type_manual.setChecked(True)
        self.discount_value.setValue(float(dvalue[0]) if dvalue else 0.0)
