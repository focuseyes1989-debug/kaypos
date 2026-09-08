import sqlite3
import unittest
from models import variant_batches as batches


class VariantBatchTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(':memory:')
        self.cursor=self.conn.cursor()
        batches.ensure_schema(self.cursor)

    def tearDown(self):
        self.conn.close()

    def test_legacy_opening_is_unknown_and_idempotent(self):
        batches.reconcile(self.cursor,1,10,5)
        batches.reconcile(self.cursor,1,10,5)
        rows=batches.list_batches(self.cursor,1)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['quantity'],5)
        self.assertEqual(rows[0]['expiry_unknown'],1)

    def test_same_batch_number_does_not_mix_variants_or_expiries(self):
        for variant,expiry in [(10,'2027-01-01'),(11,'2027-01-01'),(10,'')]:
            batches.receive(self.cursor,1,variant,3,'Shop','LOT',expiry)
        self.assertEqual(len(batches.list_batches(self.cursor,1)),3)
        allocations=batches.allocate(self.cursor,1,10,6,4)
        self.assertEqual([(a['qty'],a['expire_date']) for a in allocations],[(3,'2027-01-01'),(1,'')])
        self.assertEqual(sum(b['quantity'] for b in batches.list_batches(self.cursor,1) if b['variant_id']==11),3)
        for a in allocations:
            current=sum(b['quantity'] for b in batches.list_batches(self.cursor,1) if b['variant_id']==10)
            batches.restore(self.cursor,1,10,current,a['qty'],a['location'],a['batch_no'],a['expire_date'])
        self.assertEqual(sum(b['quantity'] for b in batches.list_batches(self.cursor,1) if b['variant_id']==10),6)

    def test_transaction_rollback_and_location_shortage(self):
        batches.receive(self.cursor,1,10,3,'Shop','A','2027-01-01')
        self.conn.commit()
        with self.assertRaises(ValueError):batches.allocate(self.cursor,1,10,3,2,'Warehouse')
        batches.allocate(self.cursor,1,10,3,2)
        self.conn.rollback()
        self.assertEqual(batches.list_batches(self.cursor,1)[0]['quantity'],3)

    def test_external_legacy_deduction_fails_closed(self):
        batches.receive(self.cursor,1,10,5,'Shop','A','2027-01-01')
        with self.assertRaisesRegex(ValueError,'differs'):
            batches.reconcile(self.cursor,1,10,4)

    def test_reversal_restores_exact_batch_and_rejects_consumed_receipt(self):
        batch=batches.receive(self.cursor,1,10,5,'Shop','A','2027-01-01')
        batches.record_change(self.cursor,1,1,10,[dict(location='Shop',batch_no=batch,expire_date='2027-01-01',delta=5)])
        allocations=batches.allocate(self.cursor,1,10,5,2)
        batches.record_change(self.cursor,2,1,10,[dict(a,delta=-a['qty']) for a in allocations])
        with self.assertRaisesRegex(ValueError,'insufficient'):
            batches.reverse_change(self.cursor,1,1,10)
        batches.reverse_change(self.cursor,2,1,10)
        self.assertEqual(batches.list_batches(self.cursor,1)[0]['quantity'],5)
        batches.reverse_change(self.cursor,1,1,10)
        self.assertEqual(batches.list_batches(self.cursor,1),[])
