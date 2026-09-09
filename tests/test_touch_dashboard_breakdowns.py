import sqlite3
import unittest
from server.cashier_service import _dashboard_extra_breakdowns

class DashboardBreakdownsTest(unittest.TestCase):
    def test_recorded_wholesale_discount_and_expense_dates(self):
        c=sqlite3.connect(':memory:')
        c.executescript('''CREATE TABLE sales(id INTEGER,invoice_no TEXT,status TEXT,created_at TEXT,discount_amount REAL,total REAL);
        CREATE TABLE sale_items(sale_id INTEGER,product_name TEXT,qty REAL,total REAL,wholesale_tier_min_qty INTEGER);
        CREATE TABLE expenses(description TEXT,category TEXT,expense_date TEXT,amount REAL);
        INSERT INTO sales VALUES(1,'A','completed','2026-09-09',500,4500),(2,'B','refunded','2026-09-09',100,1000),(3,'C','completed','2026-09-08',200,2000);
        INSERT INTO sale_items VALUES(1,'Water',5,5000,5),(1,'Retail',1,1000,NULL),(2,'Refund',1,1000,1),(3,'Old',1,2000,1);
        INSERT INTO expenses VALUES('Rent','Shop','2026-09-09',100),('Rent','Shop','2026-09-09',200),('Old','Shop','2026-09-08',900);''')
        r=_dashboard_extra_breakdowns(c.cursor(),'2026-09-09','2026-09-09')
        self.assertEqual(r['wholesale_sales'],[{'label':'Water','qty':5.0,'total':5000.0}])
        self.assertEqual(r['discount_sales'],[{'label':'A','discount':500.0,'total':4500.0}])
        self.assertEqual(r['expense_items'],[{'label':'Rent','count':2,'total':300.0}])
        c.execute('ALTER TABLE sale_items DROP COLUMN wholesale_tier_min_qty')
        self.assertFalse(_dashboard_extra_breakdowns(c.cursor(),'2026-09-09','2026-09-09')['wholesale_available'])
        c.close()

if __name__=='__main__':unittest.main()
