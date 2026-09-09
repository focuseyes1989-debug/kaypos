import sqlite3, unittest
from unittest.mock import patch
from server import cashier_service as service
class CustomersTest(unittest.TestCase):
 def test_edit_preserves_financial_values_and_pagination(self):
  class Connection(sqlite3.Connection):
   def close(self):pass
  c=sqlite3.connect(':memory:',factory=Connection)
  c.execute('CREATE TABLE customers(id INTEGER PRIMARY KEY,name TEXT,phone TEXT,email TEXT,address TEXT,remarks TEXT,points REAL DEFAULT 0,current_balance REAL DEFAULT 0,credit_limit REAL DEFAULT 0)')
  with patch.object(service,'connect_db',return_value=c):
   service.save_touch_customer({'name':'Alice','phone':'123'})
   c.execute('UPDATE customers SET points=5,current_balance=100,credit_limit=1000 WHERE id=1');c.commit()
   service.save_touch_customer({'name':'Alice updated','phone':'456'},1)
   r=service.list_customers('ALICE')[0]
   self.assertEqual((r['points'],r['current_balance'],r['credit_limit']),(5,100,1000))
   service.save_touch_customer({'name':'Bob'})
   self.assertEqual(service.list_customers('',1,1)[0]['name'],'Bob')
   with self.assertRaises(ValueError):service.save_touch_customer({'name':'   '})
   with self.assertRaises(ValueError):service.save_touch_customer({'name':'Missing'},999)
  sqlite3.Connection.close(c)
if __name__=='__main__':unittest.main()
