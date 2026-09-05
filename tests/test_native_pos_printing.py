"""Receipt printer settings and PDF output; no physical print jobs."""
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QApplication
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtGui import QPageLayout
from native_pos.config import load_config, save_config
from native_pos.data import Session
from native_pos.printing import PrinterSettingsDialog, prepare_printer, printer_preferences
from native_pos.receipt import ReceiptDialog


class PrintingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def test_local_settings_roundtrip_keeps_server_and_missing_printer(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            save_config(dict(server_url='https://fixture.invalid', receipt_printer='Offline printer', receipt_paper='58mm'), path)
            host = types.SimpleNamespace(settings_path=path, config=load_config(path), session=Session(1, 'admin', 'Admin', 'Admin', frozenset()))
            with patch('native_pos.printing.QPrinterInfo.availablePrinterNames', return_value=['Fixture printer']):
                dialog = PrinterSettingsDialog(host)
                self.assertEqual(dialog.printer.currentData(), 'Offline printer')
                dialog.printer.setCurrentIndex(dialog.printer.findData('Fixture printer')); dialog.paper.setCurrentText('80mm')
                dialog.dpi.setCurrentIndex(dialog.dpi.findData(203)); dialog.save()
            saved = load_config(path)
            self.assertEqual((saved['receipt_printer'], saved['receipt_paper'], saved['receipt_dpi']), ('Fixture printer', '80mm', 203))
            self.assertEqual(saved['server_url'], 'https://fixture.invalid')
            receipt = ReceiptDialog({}); receipt.host = host
            self.assertEqual(printer_preferences(receipt)['receipt_paper'], '80mm'); receipt.close()

    def test_unavailable_printer_and_malformed_preferences(self):
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            prepare_printer(dict(receipt_printer='Missing'), available=[])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'; path.write_text('{"receipt_paper":"bad","receipt_dpi":-1}')
            values = load_config(path)
            self.assertEqual((values['receipt_paper'], values['receipt_dpi']), ('A4', 300))

    def test_after_sale_preference_roundtrip_and_invalid_default(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            save_config({'after_sale': 'show_receipt_ask_drawer'}, path)
            self.assertEqual(load_config(path)['after_sale'], 'show_receipt_ask_drawer')
            path.write_text('{"after_sale":"automatic-unconfirmed-drawer"}', encoding='utf-8')
            self.assertEqual(load_config(path)['after_sale'], 'show_receipt')

    def test_after_sale_actions_never_open_drawer_without_selected_prompt_mode(self):
        from native_pos.sales import SalesPage
        page = types.SimpleNamespace()
        with tempfile.TemporaryDirectory() as folder:
            page.host = types.SimpleNamespace(settings_path=Path(folder) / 'config.json', closing=False)
            page.show_receipt = Mock(); page.open_drawer = Mock()
            for action, receipt_calls, drawer_calls in [('stay_sales', 0, 0), ('show_receipt', 1, 0), ('show_receipt_ask_drawer', 2, 1)]:
                save_config({'after_sale': action}, page.host.settings_path)
                SalesPage.after_sale(page)
                self.assertEqual(page.show_receipt.call_count, receipt_calls)
                self.assertEqual(page.open_drawer.call_count, drawer_calls)

    def test_receipt_pdf_paper_sizes(self):
        with tempfile.TemporaryDirectory() as folder:
            receipt = ReceiptDialog(dict(invoice_no='FIXTURE', items=[dict(product_name='Test receipt item', qty=1, price=100, total=100)], total=100))
            try:
                for paper, width in [('58mm', 58), ('80mm', 80), ('A4', 210)]:
                    printer = prepare_printer(dict(receipt_paper=paper, receipt_dpi=203), available=[])
                    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
                    path = Path(folder) / (paper + '.pdf'); printer.setOutputFileName(str(path))
                    self.assertAlmostEqual(printer.pageLayout().fullRect(QPageLayout.Unit.Millimeter).width(), width, delta=0.1)
                    self.assertEqual(printer.resolution(), 203)
                    receipt.document.document().print(printer)
                    self.assertTrue(path.read_bytes().startswith(b'%PDF-'))
            finally: receipt.close()


if __name__ == '__main__': unittest.main()
