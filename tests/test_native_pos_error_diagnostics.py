import unittest
from PyQt6.QtWidgets import QApplication
from native_pos.error_diagnostics import ErrorDiagnosticsDialog, explain_error


class ErrorDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_rules_and_no_pasted_secret_in_output(self):
        for text, title in [('database is locked', 'Database write lock'), ('connection refused', 'Network connection failed'), ('duplicate key', 'Duplicate value'), ('unfamiliar failure', 'Unclassified')]:
            result = explain_error(text + '\nAuthorization: Bearer private-value\npassword="two word secret"')
            self.assertIn(title, result)
            self.assertNotIn('private-value', result)
            self.assertNotIn('two word secret', result)

    def test_limits(self):
        for text in (' ', 'x' * 20001):
            with self.assertRaises(ValueError): explain_error(text)

    def test_edit_invalidates_result_and_close_clears_input(self):
        dialog = ErrorDiagnosticsDialog(); self.addCleanup(dialog.deleteLater)
        dialog.input.setPlainText('database is locked'); dialog.analyze()
        self.assertIn('Database write lock', dialog.output.toPlainText())
        dialog.input.setPlainText('connection refused')
        self.assertEqual(dialog.output.toPlainText(), '')
        dialog.analyze(); dialog.reject()
        self.assertEqual(dialog.input.toPlainText(), '')
        self.assertEqual(dialog.output.toPlainText(), '')
        self.assertFalse(dialog.input.document().isUndoAvailable())
        self.assertLessEqual(dialog.sizeHint().height(), 728)
