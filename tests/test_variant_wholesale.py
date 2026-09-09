import sqlite3,unittest,ast
from pathlib import Path
from utils.wholesale_pricing import ensure_variant_wholesale_schema,get_variant_price_tier,validate_variant_wholesale
class VariantWholesaleTest(unittest.TestCase):
 def test_thresholds_and_disabled(self):
  c=sqlite3.connect(':memory:');cur=c.cursor();cur.execute('CREATE TABLE product_variants(id INTEGER,product_id INTEGER,active INTEGER)');ensure_variant_wholesale_schema(cur)
  cur.executemany('INSERT INTO product_variants VALUES(?,?,?,?,?)',[(1,1,1,12,800),(2,1,1,12,700)])
  self.assertIsNone(get_variant_price_tier(cur,1,1,6));self.assertIsNone(get_variant_price_tier(cur,1,2,6))
  self.assertEqual(get_variant_price_tier(cur,1,1,12)['unit_price'],800)
  self.assertIsNone(get_variant_price_tier(cur,1,2,11));self.assertIsNone(get_variant_price_tier(cur,2,1,12))
  for q,p in [(12,0),(0,800),(-1,800),(1.5,800)]:
   with self.assertRaises(ValueError):validate_variant_wholesale(q,p)
  self.assertEqual(validate_variant_wholesale(0,0),(0,0))
  c.close()
if __name__=='__main__':unittest.main()
