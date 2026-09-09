import sqlite3,unittest
from unittest.mock import patch
from server import cashier_service as s
class SuppliersTest(unittest.TestCase):
 def test_shared_fields_filter_and_edit(self):
  class C(sqlite3.Connection):
   def close(self):pass
  c=sqlite3.connect(':memory:',factory=C);c.execute('CREATE TABLE suppliers(id INTEGER PRIMARY KEY,'+','.join(k+' TEXT' for k in s.SUPPLIER_FIELDS)+')')
  with patch.object(s,'connect_db',return_value=c):
   s.save_touch_supplier({'name':'ABC','company_name':'Wholesale','status':'Active','phone':'123'})
   self.assertEqual(s.list_touch_suppliers('wholesale','Active')['total_count'],1)
   s.save_touch_supplier({'name':'ABC','status':'Inactive','payment_terms':'30 days'},1)
   self.assertEqual(s.list_touch_suppliers('','Active')['total_count'],0)
   self.assertEqual(s.list_touch_suppliers()['suppliers'][0]['payment_terms'],'30 days')
   with self.assertRaises(ValueError):s.save_touch_supplier({'name':' ','status':'Active'})
  sqlite3.Connection.close(c)
if __name__=='__main__':unittest.main()
