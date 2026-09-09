import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtPdf import QPdfDocument
from local_print_bridge import print_receipt, receipt_document


class PrintRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
    def test_paper_layouts_and_long_receipt_pagination(self):
        receipt={'total':1000,'items':[{'product_name':f'SKU{index:04d} မြန်မာစာ Test product long name','qty':1,'price':100,'total':100} for index in range(100)]}
        with tempfile.TemporaryDirectory() as tmp:
            for paper in ('58','80','a4'):
                target=str(Path(tmp)/f'{paper}.pdf')
                class FilePrinter(QPrinter):
                    def __init__(self,*args):
                        super().__init__(*args)
                        self.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
                        self.setOutputFileName(target)
                    def setPrinterName(self,_name):
                        pass
                with patch('PyQt6.QtPrintSupport.QPrinter',FilePrinter):
                    print_receipt({'printer':'TEST FILE ONLY','receipt':receipt,'paid':1000,'paper':paper})
                pdf=QPdfDocument(None)
                try:
                    self.assertEqual(pdf.load(target),QPdfDocument.Error.None_)
                    pages=pdf.pageCount()
                    width=pdf.pagePointSize(0).width()*25.4/72
                    text=''.join(pdf.getAllText(i).text() for i in range(pages))
                finally:
                    pdf.close()
                    del pdf
                self.assertGreater(pages,1)
                self.assertAlmostEqual(width,{'58':58,'80':80,'a4':210}[paper],delta=1)
                normalized=''.join(text.split())
                self.assertTrue('Thankyou.' in normalized, paper+' footer missing')
                for index in range(100):
                    self.assertTrue(f'SKU{index:04d}' in normalized, paper+f' missing SKU{index:04d}')
    def test_receipt_values_and_escaping(self):
        document=receipt_document({'total':945,'discount_amount':100,'items':[{'product_name':'<script>name</script>','qty':2,'price':500,'total':1000}]},1000,48)
        text=document.toPlainText()
        self.assertIn('<script>name</script>',text)
        self.assertIn('45 Ks',text)
        self.assertIn('55 Ks',text)


if __name__=='__main__':unittest.main()

