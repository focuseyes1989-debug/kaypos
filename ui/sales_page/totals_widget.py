# ui/sales_page/totals_widget.py
from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QHBoxLayout, QCheckBox, QDoubleSpinBox, QLabel, QSpinBox
from PyQt6.QtCore import pyqtSignal, QObject
from utils.currency import get_currency_symbol, format_money
from loguru import logger
from ui.themes import get_theme_colors


class TotalsWidget(QObject):
    grand_total_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.cart_widget = parent.cart_widget
        self.tax_rate = 0.0
        self.tax_enabled = False
        self.discount_enabled = False
        self.discount_type = "percentage"
        self.discount_default_value = 0.0
        self.points_per_dollar = 0.0
        self.points_dollar_value = 0.01
        self.points_available = 0
        self.points_expiry_months = 12
        
        # ✅ Store current grand total
        self._current_grand_total = 0.0

        # Discount group
        self.discount_group = QGroupBox("Discount")
        discount_layout = QVBoxLayout()
        self.discount_checkbox = QCheckBox("Apply Discount")
        self.discount_checkbox.toggled.connect(self.toggle_discount_input)
        discount_layout.addWidget(self.discount_checkbox)
        self.discount_input = QDoubleSpinBox()
        self.discount_input.setRange(0, 100000)
        self.discount_input.setDecimals(0)
        self.discount_input.setEnabled(False)
        self.discount_input.valueChanged.connect(self.update_totals)
        discount_layout.addWidget(self.discount_input)
        self.discount_label = QLabel("Discount: 0")
        discount_layout.addWidget(self.discount_label)
        self.discount_group.setLayout(discount_layout)

        # Loyalty group
        self.loyalty_group = QGroupBox("Loyalty Points")
        loyalty_layout = QVBoxLayout()
        self.points_label = QLabel("Available points: 0")
        loyalty_layout.addWidget(self.points_label)
        self.points_use_check = QCheckBox("Use points for discount")
        self.points_use_check.toggled.connect(self.toggle_points_input)
        loyalty_layout.addWidget(self.points_use_check)
        self.points_spin = QSpinBox()
        self.points_spin.setRange(0, 0)
        self.points_spin.setSuffix(" points")
        self.points_spin.valueChanged.connect(self.update_totals)
        self.points_spin.setEnabled(False)
        loyalty_layout.addWidget(self.points_spin)
        self.points_discount_label = QLabel("Points discount: 0")
        loyalty_layout.addWidget(self.points_discount_label)
        self.loyalty_group.setLayout(loyalty_layout)

        # Totals group
        self.totals_group = QGroupBox("Totals")
        totals_layout = QVBoxLayout()
        self.subtotal_label = QLabel("Subtotal: 0")
        self.tax_label = QLabel("Tax: 0")
        self.total_label = QLabel("Grand Total: 0")
        totals_layout.addWidget(self.subtotal_label)
        totals_layout.addWidget(self.tax_label)
        totals_layout.addWidget(self.total_label)
        self.totals_group.setLayout(totals_layout)
        self.update_theme()

    def load_discount_settings(self, enabled, dtype, default_value):
        self.discount_enabled = enabled
        self.discount_type = dtype
        self.discount_default_value = default_value
        self.discount_checkbox.setEnabled(enabled)
        if not enabled:
            self.discount_checkbox.setChecked(False)
        if dtype == "percentage":
            self.discount_input.setSuffix(" %")
            self.discount_input.setRange(0, 100)
        else:
            self.discount_input.setSuffix("")
            self.discount_input.setRange(0, 100000)
        self.discount_input.setValue(default_value)

    def set_loyalty_params(self, points_per_dollar, expiry_months, point_value):
        self.points_per_dollar = points_per_dollar
        self.points_expiry_months = expiry_months
        self.points_dollar_value = point_value

    def set_customer_points(self, points):
        self.points_available = points
        self.update_points_display()

    def update_points_display(self):
        from utils.language import lang
        if lang.get_current() == "my":
            self.points_label.setText(f"ရရှိနိုင်သောအမှတ်: {self.points_available}")
        else:
            self.points_label.setText(f"Available points: {self.points_available}")
        if self.points_use_check.isChecked():
            self.points_spin.setMaximum(self.points_available)

    def toggle_points_input(self, checked):
        self.points_spin.setEnabled(checked)
        if not checked:
            self.points_spin.setValue(0)
        else:
            self.points_spin.setMaximum(self.points_available)
        self.update_totals()

    def toggle_discount_input(self, checked):
        self.discount_input.setEnabled(checked)
        if not checked:
            self.discount_input.setValue(0.0)
        else:
            self.discount_input.setValue(self.discount_default_value)
        self.update_totals()

    def compute_regular_discount(self, subtotal):
        if not self.discount_checkbox.isChecked():
            return 0.0
        val = self.discount_input.value()
        if self.discount_type == "percentage":
            return subtotal * (val / 100.0)
        else:
            return min(val, subtotal)

    def compute_points_discount(self, subtotal):
        if not self.points_use_check.isChecked():
            return 0.0
        pts = self.points_spin.value()
        return min(pts * self.points_dollar_value, subtotal)

    def compute_tax(self, after_discount):
        if self.tax_enabled and hasattr(self.parent, 'tax_rate'):
            return after_discount * (self.parent.tax_rate / 100.0)
        return 0.0

    def update_totals(self):
        subtotal = self.parent.cart_widget.compute_subtotal()
        reg_discount = self.compute_regular_discount(subtotal)
        points_discount = self.compute_points_discount(subtotal)
        total_discount = reg_discount + points_discount
        after_discount = subtotal - total_discount
        tax_amt = self.compute_tax(after_discount)
        grand_total = after_discount + tax_amt

        # ✅ Store current grand total
        self._current_grand_total = grand_total

        symbol = get_currency_symbol()
        self.subtotal_label.setText(f"Subtotal: {format_money(subtotal, symbol)}")
        self.discount_label.setText(f"Discount (reg): -{format_money(reg_discount, symbol)}")
        self.points_discount_label.setText(f"Points discount: -{format_money(points_discount, symbol)}")
        tax_text = f"Tax ({self.parent.tax_rate}%): {format_money(tax_amt, symbol)}" if self.tax_enabled else f"Tax: {format_money(0, symbol)}"
        self.tax_label.setText(tax_text)
        self.total_label.setText(f"Grand Total: {format_money(grand_total, symbol)}")
        self.grand_total_changed.emit(grand_total)

    def update_change_display(self, payment):
        # Called when payment changes, but grand total already known
        self.update_totals()

    # ============================================================
    # ✅ FIXED: get_current_grand_total()
    # ============================================================
    def get_current_grand_total(self):
        """
        Get current grand total.
        
        ✅ FIXED: Uses stored _current_grand_total instead of parsing label.
        This fixes the issue where payment widget couldn't get the correct total.
        """
        return self._current_grand_total

    def retranslateUi(self):
        from utils.language import lang
        if lang.get_current() == "my":
            self.discount_group.setTitle("လျှော့စျေး")
            self.discount_checkbox.setText("လျှော့စျေးသုံးမည်")
            self.discount_label.setText("လျှော့စျေး: 0")
            self.loyalty_group.setTitle("အမှတ်များ")
            self.points_use_check.setText("အမှတ်များသုံးမည်")
            self.points_discount_label.setText("အမှတ်လျှော့စျေး: 0")
            self.totals_group.setTitle("စုစုပေါင်း")
            self.subtotal_label.setText("ကြားဖြတ်စုစုပေါင်း: 0")
            self.tax_label.setText("အခွန်: 0")
            self.total_label.setText("စုစုပေါင်း: 0")
        else:
            self.discount_group.setTitle("Discount")
            self.discount_checkbox.setText("Apply Discount")
            self.discount_label.setText("Discount: 0")
            self.loyalty_group.setTitle("Loyalty Points")
            self.points_use_check.setText("Use points for discount")
            self.points_discount_label.setText("Points discount: 0")
            self.totals_group.setTitle("Totals")
            self.subtotal_label.setText("Subtotal: 0")
            self.tax_label.setText("Tax: 0")
            self.total_label.setText("Grand Total: 0")

    def update_theme(self, theme_name=None):
        """Apply current theme colors to totals sub-widgets."""
        colors = get_theme_colors(theme_name)
        text = colors.get('text', '#212529')
        secondary = colors.get('text_secondary', '#6c757d')
        input_bg = colors.get('input_bg', '#ffffff')
        input_border = colors.get('input_border', colors.get('border', '#dee2e6'))
        focus = colors.get('border_hover', '#5865f2')

        for label in (
            self.discount_label,
            self.points_label,
            self.points_discount_label,
            self.subtotal_label,
            self.tax_label,
            self.total_label,
        ):
            label.setStyleSheet(f"color: {text}; background: transparent;")

        for check in (self.discount_checkbox, self.points_use_check):
            check.setStyleSheet(f"color: {text}; background: transparent;")

        input_style = f"""
            QSpinBox, QDoubleSpinBox {{
                background-color: {input_bg};
                color: {text};
                border: 1px solid {input_border};
                border-radius: 4px;
                padding: 4px 6px;
            }}
            QSpinBox:disabled, QDoubleSpinBox:disabled {{
                color: {secondary};
                background-color: {colors.get('bg_hover', input_bg)};
            }}
            QSpinBox:focus, QDoubleSpinBox:focus {{
                border: 1px solid {focus};
            }}
        """
        self.discount_input.setStyleSheet(input_style)
        self.points_spin.setStyleSheet(input_style)
