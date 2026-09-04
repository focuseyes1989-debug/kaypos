"""Phase 6 reads disposable databases; no live server or physical printer."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import csv
from datetime import datetime
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from PyQt6.QtCore import Qt, QDate, QEventLoop, QTimer, QRect
from PyQt6.QtWidgets import QApplication
from server.native_reports import ReportRepository, VIEWS, install_routes
from native_pos.reports import ReportPage, ReportModel, ReportPreview
from native_pos.report_export import write_csv, write_xlsx, report_html
from native_pos.data import Session, ServerStore, Target
from native_pos.theme import NativeTheme
from native_pos.window import NativeWindow
from tests import test_native_pos_phase5 as phase5
from tests.test_native_pos_phase3 import isolated_service, LocalApiClient
from utils.wholesale_pricing import ensure_wholesale_sale_item_columns


class ReportDatabaseTests(unittest.TestCase):
    connect = phase5.BusinessDatabaseTests.connect
    count = phase5.BusinessDatabaseTests.count

    def setUp(self):
        phase5.BusinessDatabaseTests.setUp(self)
        with self.connect() as c:
            ensure_wholesale_sale_item_columns(c.cursor())
            c.executescript('''
                ALTER TABLE categories ADD COLUMN group_id INTEGER;
                CREATE TABLE category_groups(id INTEGER PRIMARY KEY,name TEXT);
                INSERT INTO category_groups VALUES(1,'Retail');
                INSERT INTO categories(id,name) VALUES(3,'Shop');
                UPDATE categories SET parent_id=3,group_id=1 WHERE id IN (1,2);
                UPDATE products SET category='Clothes',category_id=2 WHERE id=2;
            ''')
        self.scope = isolated_service(self.connect); self.sale = self.scope['create_sale']
        self.business = phase5.BusinessRepository(types.SimpleNamespace(**self.scope), phase5.isolated_restaurant())
        self.repo = ReportRepository(types.SimpleNamespace(**self.scope))
        self.receipts = [self.sale(items=[dict(product_id=1,qty=2),dict(product_id=3,qty=1)], payment=1000, discount_amount=10),
            self.sale(items=[dict(product_id=2,variant_id=21,qty=1)],payment=300),
            self.sale(items=[dict(product_id=1,qty=3)],payment=300),
            self.sale(items=[dict(product_id=1,qty=1)],payment=0,payment_type='Credit',customer_id=1)]
        refunded = self.sale(items=[dict(product_id=1,qty=1)],payment=105)
        with self.connect() as c:
            row = self.business.record(c.cursor(),'sales',refunded['id'])
        self.business.command(self.user,str(phase5.uuid.uuid4()),'receipt.refund',dict(row,reason='Fixture return'))
        with self.connect() as c: c.execute("UPDATE sales SET created_at='2026-09-04 23:59:59'")
        previous = self.sale(items=[dict(product_id=3,qty=2)],payment=42)
        with self.connect() as c:
            c.execute("UPDATE sales SET created_at='2026-09-03 10:00:00' WHERE id=?",(previous['id'],))
            c.execute('UPDATE products SET cost=1000 WHERE id=1')
            c.executescript("""
                INSERT INTO expenses(expense_no,category,amount,expense_date) VALUES('E1','Rent',80,'2026-09-04'),('E2','Rent',20,'2026-09-03'),('E3','Rent',99,'2026-09-05');
            """)

    def report(self, section='summary', view='overview', start='2026-09-04', end='2026-09-04'):
        return self.repo.read(self.user,section,view,start,end)

    def test_receipt_totals_discount_once_refunds_separate_and_cost_snapshot(self):
        report = self.report('reports','financial'); m=report['metrics']
        self.assertEqual((m['gross'],m['discount'],m['net'],m['invoice_total']), (810,10,800,840))
        self.assertEqual((m['cogs'],m['expenses'],m['net_profit']), (400,80,360))
        self.assertEqual((m['transactions'],m['quantity'],m['refunds']), (4,8,105))
        self.assertEqual(m['invoice_adjustments'],40)
        self.assertEqual(report['previous_period'],dict(start='2026-09-03',end='2026-09-03'))
        comparisons={r['label']:r for r in report['tables'][0]['rows']}
        self.assertEqual(comparisons['Invoice Total']['previous'],42)

    def test_all_groupings_reconcile_to_receipts_without_duplicate_names(self):
        with self.connect() as c:
            c.execute("INSERT INTO products(id,name,price,cost,stock,sold_by,category) VALUES(9,'Paper',100,9999,0,'Each','Duplicate')")
        for view in ('items','categories','parents','groups','payments','daily','hourly'):
            with self.subTest(view=view):
                report=self.report(view=view);rows=report['tables'][0]['rows']
                self.assertAlmostEqual(sum(float(r['gross']) for r in rows),810)
                self.assertAlmostEqual(sum(float(r['discount']) for r in rows),10)
                self.assertAlmostEqual(sum(float(r['net']) for r in rows),800)
        items=self.report(view='items')['tables'][0]['rows']
        self.assertEqual(sum(float(r['cogs']) for r in items),400)

    def test_penny_discount_remainder_and_receipt_without_items(self):
        with self.connect() as c:
            c.execute("INSERT INTO sales(id,invoice_no,total,discount_amount,status,created_at) VALUES(100,'PENNY',2,1,'completed','2026-08-01')")
            for i in range(3):
                c.execute('INSERT INTO sale_items(sale_id,product_name,qty,price,cost) VALUES(100,?,1,1,0)',(f'Line {i}',))
        rows=self.report(view='items',start='2026-08-01',end='2026-08-01')['tables'][0]['rows']
        self.assertEqual(sorted(round(r['discount'],2) for r in rows),[.33,.33,.34])
        self.assertAlmostEqual(sum(r['net'] for r in rows),2)
        with self.connect() as c:
            c.execute("INSERT INTO sales(id,invoice_no,total,discount_amount,status,created_at) VALUES(101,'NO-ITEMS',0,0,'completed','2026-08-01')")
        report=self.report(start='2026-08-01',end='2026-08-01')
        self.assertEqual(report['metrics']['missing_item_receipts'],1)

    def test_wholesale_is_recorded_at_checkout_and_not_reconstructed(self):
        report=self.report(view='wholesale');rows=report['tables'][0]['rows']
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['wholesale_savings'],60)
        self.assertEqual(rows[0]['quantity'],3);self.assertEqual(rows[0]['net'],240)

    def test_zero_cost_preserved_missing_cost_estimated_and_flagged(self):
        with self.connect() as c: c.execute('UPDATE products SET cost=7 WHERE id=3')
        self.assertEqual(self.report()['metrics']['cogs'],400)
        with self.connect() as c: c.execute('UPDATE sale_items SET cost=NULL WHERE product_id=3')
        m=self.report()['metrics'];self.assertEqual(m['cogs'],407);self.assertEqual(m['estimated_lines'],1)

    def test_expenses_monthly_and_snapshot_semantics(self):
        report=self.report('reports','monthly');row=report['tables'][0]['rows'][0]
        self.assertEqual((row['label'],row['invoice_total'],row['expenses'],row['net_profit']),('2026-09',840,80,360))
        expenses=self.report('reports','expenses')['tables'];self.assertEqual(expenses[0]['rows'][0]['amount'],80)
        self.assertEqual(len(expenses[1]['rows']),1)
        credit=self.report('reports','credit');self.assertEqual(credit['snapshot']['outstanding_credit'],105)
        inventory=self.report('reports','inventory');self.assertEqual(inventory['snapshot']['stock_value'],4200)
        self.assertTrue(all(r['sold_by'] not in ('Service','Restaurant') for r in inventory['tables'][0]['rows']))

    def test_credit_collections_and_movement_dates_do_not_change_sales_totals(self):
        with self.connect() as c:
            credit_id=c.execute('SELECT id FROM credit_sales').fetchone()[0]
            credit=self.business.record(c.cursor(),'credit_sales',credit_id)
            c.execute("UPDATE stock_movements SET created_at='2026-09-04 08:00:00'")
        self.business.command(self.user,str(phase5.uuid.uuid4()),'credit.pay',dict(credit,amount=50,payment_date='2026-09-04'))
        report=self.report('reports','credit')
        self.assertEqual(report['snapshot']['outstanding_credit'],55)
        self.assertEqual(sum(row['amount'] for row in report['tables'][1]['rows']),50)
        self.assertEqual(self.report()['metrics']['invoice_total'],840)
        self.assertTrue(self.report('reports','movements')['tables'][0]['rows'])
        self.assertEqual(self.report('reports','movements',start='2026-09-05',end='2026-09-05')['tables'][0]['rows'],[])

    def test_empty_dates_invalid_range_and_unknown_view(self):
        report=self.report(start='2020-01-01',end='2020-01-01')
        self.assertEqual(report['metrics']['transactions'],0);self.assertEqual(report['tables'][1]['rows'],[])
        for start,end in [('2026-09-05','2026-09-04'),('bad','2026-09-04'),('2000-01-01','2026-09-04')]:
            with self.assertRaises(ValueError): self.report(start=start,end=end)
        with self.assertRaises(ValueError): self.report(view='anything;DROP TABLE sales')

    def test_permissions_checked_on_every_read_and_snapshot_cards_redacted(self):
        with self.connect() as c: c.execute("UPDATE users SET role='Cashier',permissions='dashboard'")
        report=self.report('dashboard','overview');self.assertEqual(report['snapshot'],{})
        with self.assertRaises(PermissionError):self.report('reports','financial')
        with self.connect() as c:c.execute("UPDATE users SET permissions='reports'")
        self.report('reports','financial')
        for view in ('credit','inventory','movements'):
            with self.assertRaises(PermissionError):self.report('reports',view)
        with self.connect() as c:c.execute('UPDATE users SET force_password_change=1')
        with self.assertRaises(PermissionError):self.report('reports','financial')

    def test_every_view_read_only_and_concurrent_reads(self):
        with self.connect() as c:before=list(c.iterdump())
        for section,views in VIEWS.items():
            for view in views:
                with self.subTest(section=section,view=view):
                    report=self.report(section,view);self.assertEqual(report['version'],1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.report(),range(2)))
        self.assertEqual(results[0]['metrics'],results[1]['metrics'])
        with self.connect() as c:self.assertEqual(list(c.iterdump()),before)

    def test_read_snapshot_does_not_mix_a_sale_committed_between_queries(self):
        with self.connect() as c:c.execute('PRAGMA journal_mode=WAL')
        original = self.repo.metrics; wrote = False
        def interleave(*args, **kwargs):
            nonlocal wrote
            result=original(*args, **kwargs)
            if not wrote:
                wrote=True
                with self.connect() as c:
                    c.execute("INSERT INTO sales(id,invoice_no,total,discount_amount,status,created_at) VALUES(500,'CONCURRENT',10,0,'completed','2026-09-04 12:00:00')")
                    c.execute("INSERT INTO sale_items(sale_id,product_name,qty,price,cost) VALUES(500,'Fixture',1,10,0)")
            return result
        with patch.object(self.repo,'metrics',side_effect=interleave): report=self.report('reports','financial')
        self.assertEqual(report['metrics']['invoice_total'],840)
        self.assertEqual(report['tables'][1]['rows'][0]['invoice_total'],840)
        self.assertEqual(self.report()['metrics']['invoice_total'],850)

    def test_http_read_route_and_permission_error(self):
        from fastapi import FastAPI
        app=FastAPI();install_routes(app,lambda:self.user,self.repo)
        client=LocalApiClient(app)
        url='/api/native/reports?section=summary&view=overview&start=2026-09-04&end=2026-09-04'
        response=client.get(url);self.assertEqual(response.status_code,200);self.assertEqual(response.json()['metrics']['net'],800)
        with self.connect() as c:c.execute("UPDATE users SET role='Cashier',permissions='sales'")
        self.assertEqual(client.get(url).status_code,403)


class ReportUiExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.window=NativeWindow(NativeTheme(self.app),Path(self.folder.name)/'config.json')
        with patch.object(self.window,'screen') as screen:
            screen.return_value.availableGeometry.return_value=QRect(0,0,1366,728);self.window._fit_display()
        self.window.session=Session(1,'tester','Tester','Admin',frozenset())
        self.window.store=ServerStore(Target('Server',server_url='https://fixture.invalid'))
        self.api=Mock();self.api.server_url='https://fixture.invalid';self.window.store.client=self.api
        self.window.populate_routes();self.addCleanup(self.window.close)
        for page in self.window.route_pages.values():
            if hasattr(page,'loaded'):page.loaded=True
        self.report=dict(version=1,section='summary',view='items',start='2026-09-01',end='2026-09-04',as_of='2026-09-04T12:00:00',
            notes=['Discount counted once. <script>literal</script>'],metrics=dict(net=102,invoice_total=107.1,discount=3,transactions=2,refunds=0,cogs=40),
            tables=[dict(key='items',title='Products',columns=[dict(key='label',label='Item',kind='text'),dict(key='net',label='Net sales',kind='money')],
                         rows=[dict(label='=2+2',net=100),dict(label='<b>Paper</b>',net=2)])])

    def wait(self):
        if self.window.runner.busy:
            loop=QEventLoop();self.window.runner.idle.connect(loop.quit);QTimer.singleShot(5000,loop.quit);loop.exec()
            self.assertFalse(self.window.runner.busy)

    def test_routes_minimum_screen_numeric_sort_filter_and_snapshot_capture(self):
        for route in (0,1,12):self.assertIsInstance(self.window.route_pages[route],ReportPage)
        page=self.window.route_pages[1];page.render(deepcopy(self.report));self.window.navigate(1);self.window.show();self.app.processEvents()
        self.assertLessEqual(self.window.width(),1366);self.assertLessEqual(self.window.height(),728)
        self.assertLessEqual(page.minimumSizeHint().height(),580);self.assertFalse(page.styleSheet())
        page.proxies[0].sort(1,Qt.SortOrder.AscendingOrder)
        self.assertEqual(page.captured_table(0)['rows'][0]['net'],2)
        page.search.setText('Paper');self.assertEqual(page.proxies[0].rowCount(),1)
        self.assertEqual(page.captured_table(0)['rows'][0]['label'],'<b>Paper</b>')
        self.assertEqual(page.data['metrics']['net'],102)

    def test_failed_refresh_removes_stale_totals_and_exports(self):
        page=self.window.route_pages[1];page.render(deepcopy(self.report));self.api._request.side_effect=RuntimeError('Server unavailable')
        page.start.setDate(QDate(2026,9,1));page.end.setDate(QDate(2026,9,4));page.refresh();self.wait()
        self.assertIsNone(page.data);self.assertFalse(page.csv.isEnabled());self.assertEqual(page.tabs.count(),0)
        self.assertIn('Server unavailable',page.status.text())

    def test_csv_xlsx_and_html_export_preserve_values_without_formulas(self):
        folder=Path(self.folder.name);table=self.report['tables'][0]
        write_csv(folder/'report.csv',self.report,table)
        with (folder/'report.csv').open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.reader(stream))
        self.assertEqual(rows[1][-2],"'=2+2");self.assertEqual(float(rows[1][-1]),100)
        write_xlsx(folder/'report.xlsx',self.report,[table])
        from openpyxl import load_workbook
        book=load_workbook(folder/'report.xlsx');self.assertEqual(book['Products']['A2'].value,'=2+2')
        self.assertEqual(book['Products']['A2'].data_type,'s');self.assertEqual(book['Products']['B2'].value,100);book.close()
        html=report_html(self.report,table);self.assertNotIn('<script>',html);self.assertIn('&lt;b&gt;Paper&lt;/b&gt;',html)

    def test_report_document_exports_pdf_without_physical_printer(self):
        from PyQt6.QtPrintSupport import QPrinter
        preview=ReportPreview(report_html(self.report,self.report['tables'][0]),self.window)
        path=Path(self.folder.name)/'report.pdf';printer=QPrinter();printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat);printer.setOutputFileName(str(path))
        preview.document.print(printer);preview.close()
        self.assertTrue(path.read_bytes().startswith(b'%PDF'));self.assertGreater(path.stat().st_size,1000)

    def test_date_changes_clear_old_values_and_export_failure_preserves_file(self):
        page=self.window.route_pages[1];page.render(deepcopy(self.report));page.start.setDate(QDate(2020,1,1))
        self.assertIsNone(page.data);self.assertFalse(page.xlsx.isEnabled())
        path=Path(self.folder.name)/'report.xlsx';path.write_bytes(b'previous export')
        with patch('openpyxl.workbook.workbook.Workbook.save',side_effect=OSError('Fixture disk failure')):
            with self.assertRaises(OSError):write_xlsx(path,self.report,self.report['tables'])
        self.assertEqual(path.read_bytes(),b'previous export')


if __name__=='__main__':unittest.main()
