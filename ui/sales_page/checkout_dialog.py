"""Touch-style payment review with an always-available received keypad."""

import math

from PyQt6.QtCore import Qt, QEvent
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
        self.target = page.payment_widget.payment_input
        self._replace = True
        totals = page.totals_widget
        discount = totals.compute_regular_discount(page.cart_widget.compute_subtotal())
        field = totals.discount_input
        self._discount_config = (totals.discount_type, field.minimum(), field.maximum(), field.decimals(), field.suffix())
        self._received_decimals = page.payment_widget.payment_input.validator().decimals()
        page._touch_checkout_active = True
        totals.discount_type = "fixed"
        field.setRange(0, 999999999)
        field.setDecimals(2)
        field.setSuffix("")
        totals.discount_checkbox.setChecked(True)
        field.setValue(discount)
        totals.points_use_check.setChecked(False)
        page.payment_widget.payment_input.validator().setDecimals(2)
        totals.update_totals()
        page.payment_widget.payment_input.setValue(totals.get_current_grand_total())
        page.payment_widget.payment_manual_override = True
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
        rows = QGridLayout(summary)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(0)
        colors = get_theme_colors()
        self.values = {}
        self.summary_labels = {}
        for index, title in enumerate(("Items", "Subtotal", "Discount", "Tax", "Total", "Received", "Change")):
            label = QLabel(title)
            self.summary_labels[title] = label
            value = QLabel()
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            background = colors['bg_hover'] if title == "Total" else "transparent"
            cell_style = f"background: {background}; padding: 10px; border: none; border-bottom: 1px solid {colors['border']};"
            label.setStyleSheet(cell_style + f"border-right: 1px solid {colors['border']};")
            value.setStyleSheet(cell_style + ("font-size: 18px; font-weight: 700;" if title == "Total" else "font-weight: 600;"))
            rows.addWidget(label, index, 0)
            rows.addWidget(value, index, 1)
            rows.setRowStretch(index, 1)
            self.values[title] = value
        rows.setColumnStretch(0, 1)
        rows.setColumnStretch(1, 1)
        body.addWidget(summary, 2)
        form_content = QWidget()
        form_content.setMinimumHeight(480)
        form = QVBoxLayout(form_content)
        form.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        form.setContentsMargins(0, 0, 6, 0)
        form.setSpacing(6)
        self.sale_type = QComboBox()
        self.sale_type.addItems(list(dict.fromkeys(["Cash"] + [page.payment_widget.payment_combo.itemText(i) for i in range(page.payment_widget.payment_combo.count())] + ["Credit"])))
        self.sale_type.setCurrentText("Cash")
        self.sale_type.currentTextChanged.connect(self._mode_changed)
        self._mode_changed("Cash")
        for title, field in (("Customer", page.customer_combo), ("Sale type", self.sale_type)):
            form.addWidget(QLabel(title))
            if field is not self.sale_type:
                self._borrow(field)
            field.setMinimumWidth(0)
            form.addWidget(field)
            field.show()
        form.addWidget(QLabel("Discount"))
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
        keypad_content = QWidget()
        keypad = QVBoxLayout(keypad_content)
        keypad.setContentsMargins(0, 0, 4, 0)
        self.keypad_title = QLabel("Keypad - Received")
        keypad.addWidget(self.keypad_title)
        grid = QGridLayout()
        grid.setSpacing(8)
        for i, text in enumerate(("1", "2", "3", "4", "5", "6", "7", "8", "9", "00", "0", ".")):
            button = QPushButton(text)
            button.setFixedHeight(72)
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
            button.setFixedHeight(56)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        grid.addWidget(clear, 4, 0, 1, 2)
        grid.addWidget(back, 4, 2)
        keypad.addLayout(grid)
        keypad.addWidget(QLabel("Quick received"))
        quick = QGridLayout()
        quick.setSpacing(8)
        self.exact = QPushButton()
        self.rounded = QPushButton()
        self.suggestions = [self.exact, self.rounded] + [QPushButton() for _ in range(4)]
        for index, button in enumerate(self.suggestions):
            button.setFixedHeight(48)
            button.clicked.connect(lambda checked=False, item=button: self._quick_received(item.property("amount")))
            quick.addWidget(button, index // 2, index % 2)
        keypad.addLayout(quick)
        keypad.addStretch()
        keypad_scroll = QScrollArea()
        keypad_scroll.setFrameShape(QFrame.Shape.NoFrame)
        keypad_scroll.setWidgetResizable(True)
        keypad_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        keypad_scroll.setWidget(keypad_content)
        keypad_content.setAutoFillBackground(False)
        keypad_scroll.viewport().setAutoFillBackground(False)
        root.addWidget(keypad_scroll, 2)
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
        for field in (page.payment_widget.payment_input, page.totals_widget.discount_input, page.totals_widget.discount_input.lineEdit()):
            field.installEventFilter(self)
        self.refresh()

    def _mode_changed(self, mode):
        options = self.page.options_widget
        blocked = options.blockSignals(True)
        try:
            options.set_payment_type("Credit" if mode == "Credit" else "Cash")
        finally:
            options.blockSignals(blocked)
        combo = self.page.payment_widget.payment_combo
        if mode != "Credit":
            combo.setCurrentText(mode)
        if hasattr(self, "save"):
            self.refresh()

    def _quick_received(self, amount):
        field = self.page.payment_widget.payment_input
        field.setValue(amount)
        field.setFocus()
        field.selectAll()
        self.target = field
        self._replace = True
        self.keypad_title.setText("Keypad - Received")

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.FocusIn:
            self.target = obj.lineEdit() if obj is self.page.totals_widget.discount_input else obj
            self._replace = True
            self.target.selectAll()
            self.keypad_title.setText("Keypad - Received" if obj is self.page.payment_widget.payment_input else "Keypad - Discount")
        return super().eventFilter(obj, event)

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
        totals = self.page.totals_widget
        kind, low, high, decimals, suffix = self._discount_config
        totals.discount_type = kind
        totals.discount_input.setRange(low, high)
        totals.discount_input.setDecimals(decimals)
        totals.discount_input.setSuffix(suffix)
        self.page.payment_widget.payment_input.validator().setDecimals(self._received_decimals)
        self.page._touch_checkout_active = False
        for layout, index, widget, hidden, minimum_width, stylesheet in reversed(self._borrowed):
            layout.insertWidget(index, widget)
            widget.setMinimumWidth(minimum_width)
            widget.setStyleSheet(stylesheet)
            widget.setVisible(not hidden)
        self._borrowed.clear()

    def _key(self, key):
        field = self.target
        if not field.isEnabled():
            return
        if key == "clear":
            field.setText("")
        elif key == "back":
            if self._replace:
                field.clear()
            else:
                field.backspace()
        else:
            if self._replace or field.text() == "0":
                field.selectAll()
            field.insert(key)
        self._replace = False
        if field is not self.page.payment_widget.payment_input:
            typed = field.text()
            self.page.totals_widget.discount_input.setValue(float(typed) if typed not in ("", ".") else 0)
            field.setText(typed)
            field.setCursorPosition(len(typed))
        field.setFocus()

    def refresh(self, *_):
        page = self.page
        totals = page.totals_widget
        subtotal = page.cart_widget.compute_subtotal()
        discount = totals.compute_regular_discount(subtotal) + totals.compute_points_discount(subtotal)
        self.total = totals.get_current_grand_total()
        received = page.payment_widget.get_payment_amount()
        credit = page.options_widget.get_payment_type() == "Credit"
        page.payment_widget.payment_input.setEnabled(True)
        self.values['Items'].setText(str(sum(item['qty'] for item in page.cart_widget.get_cart())))
        for title, value in (("Subtotal", subtotal), ("Discount", discount), ("Tax", self.total - max(0, subtotal - discount)),
                             ("Total", self.total), ("Received", received), ("Change", max(0, self.total - received) if credit else max(0, received - self.total))):
            self.values[title].setText(format_money(value, get_currency_symbol()))
        self.summary_labels['Change'].setText("Credit Balance" if credit else "Change")
        step = 1000 if self.total < 5000 else 5000 if self.total < 10000 else 10000
        suggestions = sorted(amount for amount in {self.total, math.ceil(self.total / step) * step, 500, 1000, 5000, 10000} if self.total <= amount <= 999999999)
        self.next_amount = suggestions[1] if len(suggestions) > 1 else suggestions[0] if suggestions else 999999999
        for index, button in enumerate(self.suggestions):
            button.setVisible(index < len(suggestions))
            if index < len(suggestions):
                button.setProperty("amount", suggestions[index])
                button.setText(format_money(suggestions[index], get_currency_symbol()))
        ready = (bool(page.customer_combo.currentData()) and received <= self.total) if credit else received >= self.total
        excessive_discount = totals.discount_input.value() > subtotal
        ready = ready and not excessive_discount
        self.save.setEnabled(ready and bool(page.cart_widget.get_cart()) and not self._saving)
        if credit:
            self.status.setText("Ready to save." if ready else "Select a customer for credit sale." if not page.customer_combo.currentData() else "Credit received amount cannot exceed total.")
        else:
            self.status.setText("Ready to save." if ready else "Amount due: " + format_money(self.total - received, get_currency_symbol()))
        if excessive_discount:
            self.status.setText("Discount cannot exceed subtotal.")
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
