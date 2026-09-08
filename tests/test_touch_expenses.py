import sqlite3
import tempfile
import os
import unittest
from unittest.mock import patch
from server import cashier_service as service

class ExpenseRoundtripTests(unittest.TestCase):
    def test_shared_expense_create_edit_and_filter(self):
        with tempfile.TemporaryDirectory() as folder:
            path=os.path.join(folder,'test.db')
            conn=sqlite3.connect(path)
            conn.execute("CREATE TABLE expenses(id INTEGER PRIMARY KEY,expense_no TEXT,expense_date TEXT,category TEXT,description TEXT,amount REAL,payment_method TEXT,reference_no TEXT,notes TEXT,created_by TEXT)")
            conn.commit();conn.close()
            service._TABLE_COLUMNS_CACHE.clear()
            with patch.object(service,'connect_db',side_effect=lambda:sqlite3.connect(path)), patch.object(service,'is_postgres_backend',return_value=False):
                item=service.add_expense(category='Transport',description='Delivery',amount=5000,expense_date='2026-09-09',created_by='tester')
                result=service.list_expenses('Transport','2026-09-09','2026-09-09')
                self.assertEqual(result['total'],5000)
                self.assertEqual(result['total_count'],1)
                self.assertEqual(result['expenses'][0]['created_by'],'tester')
                service.update_expense(item['id'],category='Transport',description='Corrected',amount=6000,expense_date='2026-09-09')
                updated=service.list_expenses()['expenses'][0]
                self.assertEqual(updated['expense_no'],item['expense_no'])
                self.assertEqual(updated['created_by'],'tester')
                self.assertEqual(service.list_expenses()['total'],6000)
                self.assertEqual(service.list_expenses(from_date='2026-09-10')['expenses'],[])
                conn=sqlite3.connect(path)
                conn.execute("CREATE TABLE expense_attachments(id INTEGER PRIMARY KEY,expense_id INTEGER,filename TEXT)")
                conn.execute("INSERT INTO expense_attachments VALUES(1,?, 'receipt.png')", (item['id'],))
                conn.commit();conn.close()
                service.delete_expense(item['id'])
                self.assertEqual(service.list_expenses()['total_count'],0)
                conn=sqlite3.connect(path)
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM expense_attachments').fetchone()[0],0)
                conn.close()
                with self.assertRaisesRegex(ValueError,'not found'):
                    service.delete_expense(item['id'])
            service._TABLE_COLUMNS_CACHE.clear()
