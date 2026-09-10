import os
from pathlib import Path
import unittest

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
