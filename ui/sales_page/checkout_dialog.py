"""Touch-style payment review with an always-available received keypad."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from ui.themes.theme_manager import get_theme_colors, get_icon_with_color
from utils.currency import format_money, get_currency_symbol


class CheckoutDialog(QDialog):
    def __init__(self, page):
        super().__init__(page)
        self.page = page
        self.setWindowTitle("Checkout")
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)
        review = QVBoxLayout()
        heading = QLabel("Checkout")
        heading.setStyleSheet("font-size: 16px; font-weight: 600;")
        review.addWidget(heading)
        body = QHBoxLayout()
        summary = QFrame()
        summary.setObjectName("checkoutSummary")
        rows = QVBoxLayout(summary)
        self.values = {}
        for title in ("Items", "Subtotal", "Discount", "Tax", "Total", "Received", "Change"):
            row = QHBoxLayout()
            row.addWidget(QLabel(title))
            value = QLabel()
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value.setStyleSheet("font-weight: 600;")
            row.addWidget(value)
            rows.addLayout(row)
            self.values[title] = value
        body.addWidget(summary, 1)
        form = QVBoxLayout()
        sale_type = QComboBox()
        sale_type.addItems(["Cash", "Credit"])
        sale_type.setCurrentText(page.options_widget.get_payment_type())
        sale_type.currentTextChanged.connect(page.options_widget.set_payment_type)
        sale_row = QHBoxLayout()
        sale_row.addWidget(QLabel("Sale type"))
        sale_row.addWidget(sale_type, 1)
        form.addLayout(sale_row)
        form.addWidget(page.checkout_controls)
        page.checkout_controls.show()
        page.btn_add_expense.hide()
        page.checkout_handler.btn_checkout.hide()
        form.addWidget(page.totals_widget.discount_group)
        page.totals_widget.discount_group.show()
        self.status = QLabel()
        self.status.setWordWrap(True)
        form.addWidget(self.status)
        form.addStretch()
        body.addLayout(form, 1)
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
        root.addLayout(review, 3)
        keypad = QVBoxLayout()
        keypad.addWidget(QLabel("Keypad - Received"))
        grid = QGridLayout()
        grid.setSpacing(8)
        for i, text in enumerate(("1", "2", "3", "4", "5", "6", "7", "8", "9", "00", "0", ".")):
            button = QPushButton(text)
            button.setFixedHeight(48)
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
            button.setFixedHeight(44)
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
            button.setFixedHeight(44)
            quick.addWidget(button)
        keypad.addLayout(quick)
        keypad.addStretch()
        root.addLayout(keypad, 1)
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QDialog {{ background: {colors['card_bg']}; }}
            QLabel {{ background: transparent; color: {colors['text']}; font-family: 'Segoe UI'; font-size: 13px; }}
            QFrame#checkoutSummary {{ border: 1px solid {colors['border']}; border-radius: 8px; }}
            QPushButton {{ background: {colors['card_bg']}; color: {colors['text']}; border: 1px solid {colors['border']};
                border-radius: 8px; min-width: 0; padding: 0 8px; font-size: 14px; }}
            QPushButton:hover {{ background: {colors['bg_hover']}; }}
            QPushButton#saveSale {{ background: #2563eb; color: white; border: none; }}
            QPushButton#saveSale:disabled {{ background: {colors['bg_hover']}; color: {colors['text_secondary']}; }}
        """)
        page.totals_widget.grand_total_changed.connect(self.refresh)
        page.payment_widget.payment_amount_changed.connect(self.refresh)
        page.options_widget.payment_type_changed.connect(self.refresh)
        self.refresh()

    def _key(self, key):
        field = self.page.payment_widget.payment_input
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
        self.values['Items'].setText(str(sum(item['qty'] for item in page.cart_widget.get_cart())))
        for title, value in (("Subtotal", subtotal), ("Discount", discount), ("Tax", self.total - max(0, subtotal - discount)),
                             ("Total", self.total), ("Received", received), ("Change", max(0, received - self.total))):
            self.values[title].setText(format_money(value, get_currency_symbol()))
        self.next_amount = (int(self.total // 5000) + 1) * 5000
        self.exact.setText(format_money(self.total, get_currency_symbol()))
        self.rounded.setText(format_money(self.next_amount, get_currency_symbol()))
        ready = credit or received >= self.total
        self.save.setEnabled(ready and bool(page.cart_widget.get_cart()))
        self.status.setText("Ready to save." if ready else "Received amount is below the total.")

    def _save(self):
        self.save.setEnabled(False)
        try:
            self.page.confirm_checkout()
        finally:
            self.refresh()
