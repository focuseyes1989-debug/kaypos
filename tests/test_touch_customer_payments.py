import sqlite3,unittest
from unittest.mock import patch
from server import cashier_service as s
class PaymentTest(unittest.TestCase):
 def test_atomic_collection_retry_and_delete(self):
  class C(sqlite3.Connection):
   def close(self):pass
  c=sqlite3.connect(':memory:',factory=C)
  c.executescript('''CREATE TABLE customers(id INTEGER PRIMARY KEY,current_balance REAL);INSERT INTO customers VALUES(1,1000),(2,0);
  CREATE TABLE credit_sales(id INTEGER,customer_id INTEGER,total_amount REAL,paid_amount REAL,balance_amount REAL,status TEXT);INSERT INTO credit_sales VALUES(10,1,1000,0,1000,'pending');
  CREATE TABLE credit_payments(id INTEGER PRIMARY KEY,credit_sale_id INTEGER,customer_id INTEGER,amount REAL,payment_date TEXT,payment_method TEXT,reference_no TEXT,note TEXT);''')
  with patch.object(s,'connect_db',return_value=c),patch.object(s,'is_postgres_backend',return_value=False):
   s.collect_touch_payment(1,10,400,'Cash','request-123456789')
   s.collect_touch_payment(1,10,400,'Cash','request-123456789')
   self.assertEqual(c.execute('SELECT current_balance FROM customers WHERE id=1').fetchone()[0],600)
   self.assertEqual(c.execute('SELECT COUNT(*) FROM credit_payments').fetchone()[0],1)
   c.rollback()
   with self.assertRaises(ValueError):s.collect_touch_payment(1,10,700,'Cash','request-other12345')
   with self.assertRaises(ValueError):s.collect_touch_payment(2,10,10,'Cash','request-other12345')
   with self.assertRaises(ValueError):s.delete_touch_customer(1)
   s.collect_touch_payment(1,10,600,'Cash','request-final12345')
   self.assertEqual(c.execute('SELECT status FROM credit_sales').fetchone()[0],'paid')
   with self.assertRaises(ValueError):s.delete_touch_customer(1)
   s.delete_touch_customer(2)
   self.assertIsNone(c.execute('SELECT id FROM customers WHERE id=2').fetchone())
  sqlite3.Connection.close(c)
if __name__=='__main__':unittest.main()
