"""Touch-style payment review with an always-available received keypad."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout, QPushButton, QScrollArea, QVBoxLayout, QWidget
from ui.themes.theme_manager import get_theme_colors, get_icon_with_color
from utils.currency import format_money, get_currency_symbol
from ui.widgets.dialog_backdrop import exec_with_blurred_backdrop


class CheckoutDialog(QDialog):
    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self._borrowed = []
        self._saving = False
        self.setWindowTitle("Checkout")
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(20)
        review = QVBoxLayout()
        heading = QLabel("Checkout")
        heading.setStyleSheet("font-size: 16px; font-weight: 600;")
        review.addWidget(heading)
        body = QHBoxLayout()
        body.setSpacing(20)
        summary = QFrame()
        summary.setObjectName("checkoutSummary")
        rows = QVBoxLayout(summary)
        rows.setContentsMargins(12, 8, 12, 8)
        self.values = {}
        for title in ("Items", "Subtotal", "Discount", "Tax", "Total", "Received", "Change"):
            row = QHBoxLayout()
            row.addWidget(QLabel(title))
            value = QLabel()
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value.setStyleSheet("font-weight: 600;")
            if title == "Total":
                value.setStyleSheet("font-size: 19px; font-weight: 700;")
            row.addWidget(value)
            rows.addLayout(row)
            self.values[title] = value
        body.addWidget(summary, 2)
        form_content = QWidget()
        form_content.setMinimumHeight(480)
        form = QVBoxLayout(form_content)
        form.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        form.setContentsMargins(0, 0, 6, 0)
        form.setSpacing(6)
        self.sale_type = QComboBox()
        self.sale_type.addItems(["Cash", "Credit"])
        self.sale_type.setCurrentText(page.options_widget.get_payment_type())
        self.sale_type.currentTextChanged.connect(page.options_widget.set_payment_type)
        for title, field in (("Customer", page.customer_combo), ("Sale type", self.sale_type),
                             ("Payment method", page.payment_widget.payment_combo)):
            form.addWidget(QLabel(title))
            if field is not self.sale_type:
                self._borrow(field)
            field.setMinimumWidth(0)
            form.addWidget(field)
            field.show()
        self._borrow(page.totals_widget.discount_checkbox)
        form.addWidget(page.totals_widget.discount_checkbox)
        page.totals_widget.discount_checkbox.show()
        self._borrow(page.totals_widget.discount_input)
        form.addWidget(page.totals_widget.discount_input)
        page.totals_widget.discount_input.show()
        form.addWidget(QLabel("Received"))
        self._borrow(page.payment_widget.payment_input)
        form.addWidget(page.payment_widget.payment_input)
        page.payment_widget.payment_input.show()
        self.status = QLabel()
        self.status.setWordWrap(True)
        form.addWidget(self.status)
        details = QPushButton("Sale Details")
        details.setFixedHeight(32)
        details.clicked.connect(page.open_sale_details_dialog)
        form.addWidget(details)
        form.addStretch()
        form_scroll = QScrollArea()
        form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_scroll.setWidgetResizable(True)
        form_scroll.setWidget(form_content)
        form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form_content.setAutoFillBackground(False)
        form_scroll.viewport().setAutoFillBackground(False)
        body.addWidget(form_scroll, 3)
        review.addLayout(body, 1)
        actions = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.save = QPushButton("Save Sale")
        self.save.setObjectName("saveSale")
        self.save.clicked.connect(self._save)
        for button in (cancel, self.save):
            button.setFixedHeight(44)
            actions.addWidget(button)
        review.addLayout(actions)
        root.addLayout(review, 5)
        keypad = QVBoxLayout()
        keypad.addWidget(QLabel("Keypad - Received"))
        grid = QGridLayout()
        grid.setSpacing(8)
        for i, text in enumerate(("1", "2", "3", "4", "5", "6", "7", "8", "9", "00", "0", ".")):
            button = QPushButton(text)
            button.setFixedHeight(64)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda checked=False, key=text: self._key(key))
            grid.addWidget(button, i // 3, i % 3)
        clear = QPushButton("Clear")
        clear.clicked.connect(lambda: self._key("clear"))
        back = QPushButton()
        back.setIcon(get_icon_with_color("undo", get_theme_colors()['text'], (18, 18)))
        back.setToolTip("Backspace")
        back.clicked.connect(lambda: self._key("back"))
        for button in (clear, back):
            button.setFixedHeight(52)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        grid.addWidget(clear, 4, 0, 1, 2)
        grid.addWidget(back, 4, 2)
        keypad.addLayout(grid)
        keypad.addWidget(QLabel("Quick received"))
        quick = QHBoxLayout()
        self.exact = QPushButton()
        self.rounded = QPushButton()
        self.exact.clicked.connect(lambda: self.page.payment_widget.payment_input.setValue(self.total))
        self.rounded.clicked.connect(lambda: self.page.payment_widget.payment_input.setValue(self.next_amount))
        for button in (self.exact, self.rounded):
            button.setFixedHeight(52)
            quick.addWidget(button)
        keypad.addLayout(quick)
        keypad.addStretch()
        root.addLayout(keypad, 2)
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QDialog {{ background: {colors['card_bg']}; }}
            QLabel {{ background: transparent; color: {colors['text']}; font-family: 'Segoe UI'; font-size: 13px; }}
            QFrame#checkoutSummary {{ border: 1px solid {colors['border']}; border-radius: 8px; }}
            QPushButton {{ background: {colors['card_bg']}; color: {colors['text']}; border: 1px solid {colors['border']};
                border-radius: 8px; min-width: 0; padding: 0 8px; font-size: 14px; }}
            QPushButton:hover {{ background: {colors['bg_hover']}; }}
            QComboBox, QDoubleSpinBox {{ background: {colors['card_bg']}; color: {colors['text']};
                border: 1px solid {colors['border']}; border-radius: 6px; min-height: 28px; padding: 2px 6px; }}
            QPushButton#saveSale {{ background: #2563eb; color: white; border: none; }}
            QPushButton#saveSale:disabled {{ background: {colors['bg_hover']}; color: {colors['text_secondary']}; }}
        """)
        page.payment_widget.payment_input.setStyleSheet(
            f"QLineEdit {{ background: {colors['card_bg']}; color: {colors['text']}; border: 2px solid #2563eb;"
            "border-radius: 6px; padding: 4px 28px 4px 8px; font-size: 20px; font-weight: 600; }"
        )
        page.totals_widget.grand_total_changed.connect(self.refresh)
        page.payment_widget.payment_amount_changed.connect(self.refresh)
        page.options_widget.payment_type_changed.connect(self.refresh)
        page.customer_combo.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def exec(self):
        return exec_with_blurred_backdrop(self)

    def _borrow(self, widget):
        def find(layout):
            if layout is None:
                return None
            for index in range(layout.count()):
                item = layout.itemAt(index)
                if item.widget() is widget:
                    return layout, index
                result = find(item.layout())
                if result:
                    return result
            return None
        location = find(widget.parentWidget().layout())
        if location is None:
            raise RuntimeError("Checkout control has no owning layout")
        self._borrowed.append((*location, widget, widget.isHidden(), widget.minimumWidth(), widget.styleSheet()))

    def restore_controls(self):
        for layout, index, widget, hidden, minimum_width, stylesheet in reversed(self._borrowed):
            layout.insertWidget(index, widget)
            widget.setMinimumWidth(minimum_width)
            widget.setStyleSheet(stylesheet)
            widget.setVisible(not hidden)
        self._borrowed.clear()

    def _key(self, key):
        field = self.page.payment_widget.payment_input
        if not field.isEnabled():
            return
        if key == "clear":
            field.setValue(0)
        elif key == "back":
            field.backspace()
        else:
            if field.text() == "0":
                field.selectAll()
            field.insert(key)
        field.setFocus()

    def refresh(self, *_):
        page = self.page
        totals = page.totals_widget
        subtotal = page.cart_widget.compute_subtotal()
        discount = totals.compute_regular_discount(subtotal) + totals.compute_points_discount(subtotal)
        self.total = totals.get_current_grand_total()
        received = page.payment_widget.get_payment_amount()
        credit = page.options_widget.get_payment_type() == "Credit"
        self.sale_type.blockSignals(True)
        self.sale_type.setCurrentText("Credit" if credit else "Cash")
        self.sale_type.blockSignals(False)
        page.payment_widget.payment_input.setEnabled(not credit)
        page.payment_widget.payment_combo.setEnabled(not credit)
        if credit:
            received = 0
        self.values['Items'].setText(str(sum(item['qty'] for item in page.cart_widget.get_cart())))
        for title, value in (("Subtotal", subtotal), ("Discount", discount), ("Tax", self.total - max(0, subtotal - discount)),
                             ("Total", self.total), ("Received", received), ("Change", max(0, received - self.total))):
            self.values[title].setText(format_money(value, get_currency_symbol()))
        self.next_amount = min(999999999, (int(self.total // 5000) + 1) * 5000)
        self.exact.setText(format_money(self.total, get_currency_symbol()))
        self.rounded.setText(format_money(self.next_amount, get_currency_symbol()))
        self.exact.setEnabled(not credit)
        self.rounded.setEnabled(not credit)
        ready = bool(page.customer_combo.currentData()) if credit else received >= self.total
        self.save.setEnabled(ready and bool(page.cart_widget.get_cart()) and not self._saving)
        if credit:
            self.status.setText("Balance due: " + format_money(self.total, get_currency_symbol()) if ready else "Select a customer for a credit sale.")
        else:
            self.status.setText("Ready to save." if ready else "Amount due: " + format_money(self.total - received, get_currency_symbol()))
        self.status.setStyleSheet("color: #16805d;" if ready else "color: #c43d3d;")

    def _save(self):
        if self._saving or not self.save.isEnabled():
            return
        self._saving = True
        self.save.setEnabled(False)
        self.save.setText("Saving...")
        try:
            self.page.confirm_checkout()
        finally:
            self._saving = False
            self.save.setText("Save Sale")
            self.refresh()
