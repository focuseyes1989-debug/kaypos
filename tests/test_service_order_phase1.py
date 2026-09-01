import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from server.service_order_service import ServiceOrderRepository


class ServiceOrderPhase1Tests(unittest.TestCase):
    def setUp(self):
        handle, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.repo = ServiceOrderRepository(self.connect)
        self.repo.ensure_schema()

    def tearDown(self):
        os.unlink(self.db_path)

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def test_schema_is_idempotent_and_creates_phase_one_tables(self):
        self.repo.ensure_schema()
        conn = self.connect()
        names = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        conn.close()
        self.assertTrue({
            "service_orders", "service_order_items", "service_order_status_history"
        }.issubset(names))

    def test_create_generates_daily_order_number_and_initial_history(self):
        first = self.repo.create({
            "received_at": "2026-09-01 09:00:00",
            "customer_name": "Aye Aye",
            "customer_phone": "091111111",
            "item_name": "Laptop",
            "complaint": "No power",
            "deposit_amount": 10000,
        }, created_by="cashier")
        second = self.repo.create({
            "received_at": "2026-09-01 10:00:00",
            "customer_name": "Ko Ko",
        }, created_by="cashier")
        self.assertEqual(first["order_no"], "SO-20260901-0001")
        self.assertEqual(second["order_no"], "SO-20260901-0002")
        self.assertEqual(first["status"], "received")
        self.assertEqual(first["status_history"][0]["to_status"], "received")
        self.assertEqual(first["deposit_amount"], 10000)

    def test_order_and_item_crud(self):
        order = self.repo.create({"customer_name": "Original"}, created_by="admin")
        updated = self.repo.update(order["id"], {
            "customer_name": "Updated",
            "priority": "urgent",
            "diagnosis": "Power supply",
        })
        self.assertEqual(updated["customer_name"], "Updated")
        self.assertEqual(updated["priority"], "urgent")

        item = self.repo.add_item(order["id"], {
            "item_type": "service",
            "product_id": 7,
            "description": "Laptop repair",
            "qty": 1,
            "unit_price": 25000,
        })
        changed = self.repo.update_item(order["id"], item["id"], {
            "unit_price": 30000,
            "warranty_days": 30,
        })
        self.assertEqual(changed["unit_price"], 30000)
        self.assertEqual(changed["warranty_days"], 30)
        self.assertEqual(len(self.repo.get(order["id"])["items"]), 1)
        self.repo.delete_item(order["id"], item["id"])
        self.assertEqual(self.repo.get(order["id"])["items"], [])

    def test_status_rules_and_audit_history(self):
        order = self.repo.create({}, created_by="cashier")
        with self.assertRaisesRegex(ValueError, "Cannot change"):
            self.repo.change_status(order["id"], "delivered", changed_by="manager")
        order = self.repo.change_status(order["id"], "in_progress", changed_by="tech1", note="Started")
        order = self.repo.change_status(order["id"], "ready", changed_by="tech1")
        order = self.repo.change_status(order["id"], "completed", changed_by="cashier")
        order = self.repo.change_status(order["id"], "delivered", changed_by="cashier")
        self.assertEqual(order["status"], "delivered")
        self.assertIsNotNone(order["completed_at"])
        self.assertIsNotNone(order["delivered_at"])
        self.assertEqual(len(order["status_history"]), 5)
        with self.assertRaisesRegex(ValueError, "Closed"):
            self.repo.add_item(order["id"], {
                "item_type": "custom", "description": "Late fee", "qty": 1,
            })

    def test_print_shop_workflow_syncs_approval_and_pickup_notification(self):
        order = self.repo.create({
            "job_title": "Business cards", "customer_name": "Aye", "customer_phone": "09123",
        }, created_by="operator")
        order = self.repo.change_status(order["id"], "typing_designing", changed_by="designer")
        order = self.repo.change_status(order["id"], "waiting_approval", changed_by="designer")
        self.assertEqual(order["approval_status"], "waiting_customer")
        order = self.repo.change_status(order["id"], "ready_to_print", changed_by="designer")
        self.assertEqual(order["approval_status"], "approved")
        order = self.repo.change_status(order["id"], "printing", changed_by="operator")
        order = self.repo.change_status(order["id"], "ready_for_pickup", changed_by="operator")
        self.assertEqual(order["status"], "ready_for_pickup")
        self.assertEqual(order["notifications"][0]["event"], "ready_for_pickup")
        self.assertEqual(order["notifications"][0]["recipient"], "09123")

    def test_list_filters_status_and_search(self):
        first = self.repo.create({"customer_name": "Aye Aye", "serial_no": "SN-100"}, created_by="admin")
        self.repo.create({"customer_name": "Ko Ko", "serial_no": "SN-200"}, created_by="admin")
        self.repo.change_status(first["id"], "in_progress", changed_by="tech")
        self.assertEqual(len(self.repo.list(status="in_progress")), 1)
        self.assertEqual(self.repo.list(search="SN-200")[0]["customer_name"], "Ko Ko")

    def test_validation_rejects_bad_values(self):
        with self.assertRaisesRegex(ValueError, "start as received"):
            self.repo.create({"status": "completed"}, created_by="admin")
        order = self.repo.create({}, created_by="admin")
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            self.repo.add_item(order["id"], {"description": "Bad", "qty": 0})
        with self.assertRaisesRegex(ValueError, "normal or urgent"):
            self.repo.update(order["id"], {"priority": "high"})

    def test_print_shop_job_fields_and_pricing_quantity_calculation(self):
        order = self.repo.create({
            "customer_name": "Aye", "job_title": "Training Manual",
            "file_source": "Telegram", "file_reference": "message-100",
            "approval_status": "waiting_customer",
        }, created_by="operator")
        item = self.repo.add_item(order["id"], {
            "item_type": "custom", "description": "A4 double-side print",
            "pricing_unit": "per_sheet", "pages_per_copy": 5, "copy_count": 3,
            "paper_size": "A4", "paper_type": "Normal 80gsm",
            "color_mode": "bw", "print_side": "double", "finishing": "Staple",
            "file_name": "manual.pdf", "unit_price": 100,
        })
        saved = self.repo.get(order["id"])
        self.assertEqual(saved["job_title"], "Training Manual")
        self.assertEqual(saved["file_source"], "Telegram")
        self.assertEqual(item["pages_per_copy"], 5)
        self.assertEqual(item["copy_count"], 3)
        self.assertEqual(item["total_sheets"], 9)
        self.assertEqual(item["qty"], 9)
        self.assertEqual(item["paper_size"], "A4")
        self.assertEqual(item["color_mode"], "bw")
        updated = self.repo.update_item(order["id"], item["id"], {
            "pricing_unit": "per_page", "pages_per_copy": 4, "copy_count": 2,
            "print_side": "single",
        })
        self.assertEqual(updated["qty"], 8)
        self.assertEqual(updated["total_sheets"], 8)
        report = self.repo.analytics("2026-09-01", "2026-09-01")
        self.assertEqual(report["service_types"][0]["name"], "A4 double-side print")
        self.assertEqual(report["service_types"][0]["revenue"], 800)
        self.assertEqual(report["paper_sizes"][0]["name"], "A4")
        self.assertEqual(report["paper_sizes"][0]["sheets"], 8)
        self.assertEqual(report["color_modes"][0]["name"], "bw")
        with self.assertRaisesRegex(ValueError, "pricing unit"):
            self.repo.add_item(order["id"], {
                "item_type": "custom", "description": "Bad", "pricing_unit": "per_meter",
            })

    def test_catalog_mapping_checks_service_variants_and_stock_without_deducting(self):
        conn = self.connect()
        conn.executescript("""
            CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, sold_by TEXT, stock REAL);
            CREATE TABLE product_variants (id INTEGER PRIMARY KEY, product_id INTEGER, stock REAL, active INTEGER);
            INSERT INTO products VALUES (1, 'Repair Labor', 'Service', 0);
            INSERT INTO products VALUES (2, 'Keyboard', 'Each', 3);
            INSERT INTO products VALUES (3, 'Screen', 'Variants', 5);
            INSERT INTO product_variants VALUES (31, 3, 2, 1);
        """)
        conn.commit(); conn.close()
        order = self.repo.create({}, created_by="admin")
        self.repo.add_item(order["id"], {"item_type": "service", "product_id": 1, "description": "Repair", "qty": 1})
        self.repo.add_item(order["id"], {"item_type": "part", "product_id": 2, "description": "Keyboard", "qty": 2})
        self.repo.add_item(order["id"], {"item_type": "part", "product_id": 3, "variant_id": 31, "description": "Screen", "qty": 2})
        conn = self.connect()
        self.assertEqual(conn.execute("SELECT stock FROM products WHERE id = 2").fetchone()[0], 3)
        self.assertEqual(conn.execute("SELECT stock FROM product_variants WHERE id = 31").fetchone()[0], 2)
        conn.close()
        with self.assertRaisesRegex(ValueError, "not a Sold by Service"):
            self.repo.add_item(order["id"], {"item_type": "service", "product_id": 2, "description": "Wrong", "qty": 1})
        with self.assertRaisesRegex(ValueError, "Select a variant"):
            self.repo.add_item(order["id"], {"item_type": "part", "product_id": 3, "description": "No variant", "qty": 1})
        with self.assertRaisesRegex(ValueError, "currently available"):
            self.repo.add_item(order["id"], {"item_type": "part", "product_id": 2, "description": "Too many", "qty": 4})

    def test_print_service_presets_require_service_product_and_can_be_deactivated(self):
        conn = self.connect()
        conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, sold_by TEXT, stock REAL)")
        conn.execute("INSERT INTO products VALUES (1, 'A4 Color Print', 'Service', 0)")
        conn.execute("INSERT INTO products VALUES (2, 'Paper', 'Each', 10)"); conn.commit(); conn.close()
        preset = self.repo.save_preset({
            "name": "A4 Color Single", "product_id": 1, "description": "A4 Color Print",
            "pricing_unit": "per_page", "unit_price": 500, "paper_size": "A4",
            "paper_type": "Normal 80gsm", "color_mode": "color", "print_side": "single",
        })
        self.assertEqual(preset["unit_price"], 500)
        self.assertEqual(self.repo.list_presets()[0]["name"], "A4 Color Single")
        with self.assertRaisesRegex(ValueError, "Sold by Service"):
            self.repo.save_preset({"name": "Bad", "product_id": 2})
        self.repo.deactivate_preset(preset["id"])
        self.assertEqual(self.repo.list_presets(), [])
        self.assertEqual(len(self.repo.list_presets(include_inactive=True)), 1)

    def test_deposit_and_checkout_link_one_sale_and_block_duplicates(self):
        conn = self.connect()
        conn.executescript("""
            CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, sold_by TEXT, stock REAL);
            CREATE TABLE product_variants (id INTEGER PRIMARY KEY, product_id INTEGER, stock REAL, active INTEGER);
            INSERT INTO products VALUES (1, 'Repair', 'Service', 0);
            INSERT INTO products VALUES (2, 'Part', 'Each', 3);
        """)
        conn.commit(); conn.close()
        order = self.repo.create({"customer_name": "Aye"}, created_by="cashier")
        self.repo.add_item(order["id"], {"item_type": "service", "product_id": 1, "description": "Repair", "qty": 1, "unit_price": 20000, "warranty_days": 30})
        self.repo.add_item(order["id"], {"item_type": "part", "product_id": 2, "description": "Part", "qty": 1, "unit_price": 5000})
        order = self.repo.record_deposit(order["id"], 5000, payment_type="Cash", received_by="cashier")
        self.assertEqual(order["deposit_amount"], 5000)
        order = self.repo.change_status(order["id"], "in_progress", changed_by="tech")
        order = self.repo.change_status(order["id"], "ready", changed_by="tech")
        with patch("server.cashier_service.create_sale", return_value={"id": 77, "invoice_no": "WEB-77", "total": 25000}) as create_sale:
            checked_out = self.repo.checkout(order["id"], payment=20000, payment_type="Cash", created_by="cashier")
        self.assertEqual(checked_out["sale_id"], 77)
        self.assertEqual(checked_out["status"], "completed")
        self.assertEqual(len(checked_out["payments"]), 2)
        self.assertEqual(len(checked_out["notifications"]), 1)
        sent = create_sale.call_args.kwargs
        self.assertEqual(sent["payment"], 25000)
        self.assertEqual(sent["items"][0]["manual_price"], 20000)
        self.assertIsNone(sent["items"][1]["manual_price"])
        refunded = self.repo.mark_sale_refunded(77, refunded_by="manager", note="Customer refund")
        self.assertIsNotNone(refunded["sale_refunded_at"])
        self.assertEqual(refunded["status"], "completed")
        returned = self.repo.add_return_visit(order["id"], reason="Same issue", created_by="cashier")
        self.assertEqual(returned["return_visits"][0]["status"], "open")
        returned = self.repo.close_return_visit(order["id"], returned["return_visits"][0]["id"], resolution="Repaired", handled_by="tech")
        self.assertEqual(returned["return_visits"][0]["status"], "closed")
        report = self.repo.analytics("2026-09-01", "2026-09-01")
        self.assertGreaterEqual(report["orders"], 1)
        self.assertEqual(report["revenue"], 25000)
        self.assertEqual(len(self.repo.warranty_items(days=30)), 1)
        pending = self.repo.notifications(); self.assertEqual(len(pending), 1)
        sent = self.repo.update_notification(pending[0]["id"], status="sent")
        self.assertEqual(sent["status"], "sent")
        with self.assertRaisesRegex(ValueError, "already been checked out"):
            self.repo.checkout(order["id"], payment=20000, payment_type="Cash", created_by="cashier")

    def test_failed_checkout_releases_order_claim(self):
        conn = self.connect()
        conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, sold_by TEXT, stock REAL)")
        conn.execute("INSERT INTO products VALUES (1, 'Repair', 'Service', 0)"); conn.commit(); conn.close()
        order = self.repo.create({}, created_by="cashier")
        self.repo.add_item(order["id"], {"item_type": "service", "product_id": 1, "description": "Repair", "qty": 1, "unit_price": 1000})
        self.repo.change_status(order["id"], "in_progress", changed_by="tech")
        self.repo.change_status(order["id"], "ready", changed_by="tech")
        with patch("server.cashier_service.create_sale", side_effect=ValueError("Stock changed")):
            with self.assertRaisesRegex(ValueError, "Stock changed"):
                self.repo.checkout(order["id"], payment=1000, payment_type="Cash", created_by="cashier")
        self.assertIsNone(self.repo.get(order["id"])["sale_id"])


if __name__ == "__main__":
    unittest.main()
