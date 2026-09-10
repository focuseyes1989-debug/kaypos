import os
from pathlib import Path
import unittest
from unittest.mock import Mock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDialog, QHBoxLayout, QVBoxLayout, QPushButton, QTabWidget, QWidget, QTableWidgetItem, QMessageBox
from ui.design_system.buttons import PrimaryButton, SecondaryButton, DangerButton
from ui.design_system.metrics import CONTROL_HEIGHT, TABLE_ROW_HEIGHT, CARD_HEIGHT
from ui.design_system.stylesheet import apply_design_system
from ui.design_system.message_box import ModernMessageBoxFilter
from ui.design_system.table import ModernTable
from ui.dashboard.modern_card import ModernSummaryCard
from ui.base_form_dialog import BaseFormDialog
from ui.widgets.modern_button import ModernButton
from ui.themes.theme_manager import get_current_theme, set_current_theme
from ui.themes.theme_manager import get_theme_colors
from ui.design_system.tabs import tab_stylesheet
from ui.reports.base_report_dialog import BaseReportDialog
from ui.reports.reports_dialog import ReportsDialog
from ui.profit_report_dialog import ProfitReportDialog
from ui.employee_page import EmployeeManagementPage
from ui.expense.expense_page import ExpensePage
from ui.ai_pages.ai_pages_page import AIPagesPage


class DesignConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_shared_controls_in_light_and_dark(self):
        previous = self.app.styleSheet()
        self.addCleanup(self.app.setStyleSheet, previous)
        self.addCleanup(set_current_theme, get_current_theme())
        for theme in ("Light", "Dark"):
            with self.subTest(theme=theme):
                set_current_theme(theme)
                apply_design_system(self.app, theme)
                dialog = QDialog()
                layout = QVBoxLayout(dialog)
                row = QHBoxLayout()
                buttons = [QPushButton("Cancel"), PrimaryButton("Save"), SecondaryButton("Print"), DangerButton("Delete"), ModernButton("Refresh")]
                for button in buttons:
                    row.addWidget(button)
                layout.addLayout(row)
                tabs = QTabWidget()
                tabs.addTab(QWidget(), "Products")
                tabs.addTab(QWidget(), "Inventory")
                layout.addWidget(tabs)
                table = ModernTable()
                table.setColumnCount(2)
                table.setHorizontalHeaderLabels(["Product", "Amount"])
                table.setRowCount(1)
                table.setItem(0, 0, QTableWidgetItem("Example product"))
                table.setItem(0, 1, QTableWidgetItem("1,234,567 Ks"))
                layout.addWidget(table)
                card = ModernSummaryCard("Total sales", "1,234,567 Ks", "", "#26786a")
                layout.addWidget(card)
                dialog.resize(850, 560)
                dialog.show()
                self.app.processEvents()
                heights = [button.height() for button in buttons]
                self.assertLessEqual(max(heights) - min(heights), 2, heights)
                self.assertTrue(all(button.height() >= CONTROL_HEIGHT - 2 for button in buttons))
                self.assertEqual(table.verticalHeader().defaultSectionSize(), TABLE_ROW_HEIGHT)
                self.assertGreaterEqual(card.height(), CARD_HEIGHT)
                output = os.environ.get("DESKTOP_QA_OUTPUT")
                if output:
                    dialog.grab().save(str(Path(output) / f"design-{theme}.png"))
                dialog.close()

    def test_form_and_message_actions_remain_functional(self):
        form = BaseFormDialog("Customer", [{"name": "name", "label": "Name"}])
        form.resize(520, 300)
        form.show()
        self.app.processEvents()
        self.assertTrue(form.rect().contains(form.buttons.geometry()))
        form.reject()
        self.assertEqual(form.result(), QDialog.DialogCode.Rejected)
        box = QMessageBox(QMessageBox.Icon.Warning, "Confirm", "Continue with this change?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        ModernMessageBoxFilter._modernize(box)
        self.assertEqual(box.defaultButton(), box.button(QMessageBox.StandardButton.Cancel))
        box.button(QMessageBox.StandardButton.Cancel).click()
        self.assertEqual(box.result(), QMessageBox.StandardButton.Cancel)

    def test_multiline_message_is_not_clipped(self):
        from PyQt6.QtWidgets import QLabel
        from ui.design_system.message_box import install_modern_message_boxes
        install_modern_message_boxes(self.app)
        previous = self.app.styleSheet()
        self.addCleanup(self.app.setStyleSheet, previous)
        apply_design_system(self.app, "Light")
        box = QMessageBox(QMessageBox.Icon.Information, "ZKTeco Sync",
                          "Sync complete.\nNew punches: 74", QMessageBox.StandardButton.Ok)
        box.show()
        self.app.processEvents()
        self.app.processEvents()
        label = box.findChild(QLabel, "qt_msgbox_label")
        self.assertGreaterEqual(label.height(), label.heightForWidth(label.width()))
        self.assertGreaterEqual(label.height(), label.fontMetrics().lineSpacing() * 2)
        output = os.environ.get("DESKTOP_QA_OUTPUT")
        if output:
            box.grab().save(str(Path(output) / "message-multiline.png"))
        box.button(QMessageBox.StandardButton.Ok).click()
        box.deleteLater()

    def test_legacy_tab_styles_match_after_theme_refresh(self):
        self.addCleanup(set_current_theme, get_current_theme())
        methods = [
            (EmployeeManagementPage._apply_theme, "employeeTabs"),
            (ExpensePage._apply_tab_bar_style, "expenseTabs"),
            (AIPagesPage._apply_tab_style, "aiPagesTabs"),
            (ReportsDialog._apply_tab_bar_style, ""),
            (ProfitReportDialog._apply_tab_style, ""),
        ]
        for method, name in methods:
            page = QWidget()
            page.tabs = QTabWidget(page)
            page.tabs.setObjectName(name)
            page.tab_widget = page.tabs
            page._update_tab_icons_color = Mock()
            for theme in ("Light", "Dark", "Light"):
                with self.subTest(method=method.__qualname__, theme=theme):
                    set_current_theme(theme)
                    method(page)
                    self.assertEqual(page.tabs.styleSheet(), tab_stylesheet(get_theme_colors(), name))
            page.close()

    def test_report_footer_and_summary_card_fit_short_dialog(self):
        previous = self.app.styleSheet()
        self.addCleanup(self.app.setStyleSheet, previous)
        self.addCleanup(set_current_theme, get_current_theme())
        for theme in ("Light", "Dark"):
            set_current_theme(theme)
            apply_design_system(self.app, theme)
            report = BaseReportDialog()
            content = QWidget()
            layout = QVBoxLayout(content)
            card = report.create_summary_card("Total sales", "1,234,567 Ks")
            layout.addWidget(card)
            layout.addStretch()
            report.tabs.addTab(content, "Sales")
            report.tabs.addTab(QWidget(), "Expenses")
            report.resize(1000, 600)
            report.show()
            self.app.processEvents()
            self.assertGreater(report.btn_close.y(), report.tabs.geometry().bottom())
            self.assertTrue(report.rect().contains(report.btn_close.geometry()))
            self.assertGreaterEqual(card.card.height(), CARD_HEIGHT)
            self.assertLessEqual(card.height(), 116)
            output = os.environ.get("DESKTOP_QA_OUTPUT")
            if output:
                report.grab().save(str(Path(output) / f"report-design-{theme}.png"))
            report.btn_close.click()
            self.assertEqual(report.result(), QDialog.DialogCode.Accepted)
