import unittest
from datetime import datetime, timedelta

from ui.products_page.product_ai_insights import ProductAIInsights


def product(product_id, name, stock=10, low_stock=2, price=100, cost=50, **extra):
    value = {
        "id": product_id, "name": name, "category": "Test", "price": float(price),
        "cost": float(cost), "sku": "", "barcode": "", "stock": float(stock),
        "low_stock": float(low_stock), "expire_date": "",
    }
    value.update(extra)
    return value


class ProductAIInsightsTests(unittest.TestCase):
    def test_reorder_is_prioritized_and_explainable(self):
        item = product(1, "Fast Item", stock=2, low_stock=3)
        sales = {"id": {1: 60.0}, "name": {}}
        result = ProductAIInsights._reorder([item], sales)
        self.assertEqual(result[0]["priority"], "high")
        self.assertGreater(result[0]["recommended_qty"], 0)
        self.assertGreaterEqual(result[0]["recommended_low_stock"], 14)

    def test_dead_stock_has_value_for_authorized_analysis(self):
        item = product(2, "Dead Item", stock=5, cost=40)
        _, dead = ProductAIInsights._slow_and_dead([item], {"id": {}, "name": {}})
        self.assertEqual(dead[0]["stock_value"], 200)

    def test_sensitive_values_are_removed_for_restricted_roles(self):
        items = [{"id": 1, "cost": 40, "stock_value": 200, "stock": 5}]
        ProductAIInsights._hide_sensitive(items)
        self.assertNotIn("cost", items[0])
        self.assertNotIn("stock_value", items[0])
        self.assertEqual(items[0]["stock"], 5)

    def test_duplicate_detection_covers_normalized_names_and_barcodes(self):
        first = product(1, "Blue Pen", barcode="123")
        second = product(2, "Blue-Pen", barcode="123")
        groups = ProductAIInsights._duplicates([first, second])
        reasons = {group["reason"] for group in groups}
        self.assertIn("name", reasons)
        self.assertIn("barcode", reasons)

    def test_expiry_risk_orders_expired_before_expiring(self):
        expired = product(1, "Expired", expire_date=(datetime.now() - timedelta(days=2)).date().isoformat())
        expiring = product(2, "Expiring", expire_date=(datetime.now() + timedelta(days=3)).date().isoformat())
        result = ProductAIInsights._expiry_risks([expiring, expired])
        self.assertEqual([row["id"] for row in result], [1, 2])

    def test_margin_warning_flags_loss(self):
        result = ProductAIInsights._margin_warnings([product(1, "Loss", price=80, cost=100)])
        self.assertEqual(result[0]["margin_status"], "loss")
        self.assertLess(result[0]["margin_pct"], 0)

    def test_reorder_ignores_healthy_stock_without_recent_velocity(self):
        item = product(3, "Healthy Item", stock=20, low_stock=5)
        result = ProductAIInsights._reorder([item], {"id": {}, "name": {}})
        self.assertEqual(result, [])

    def test_invalid_expiry_date_is_ignored(self):
        item = product(4, "No Expiry", expire_date="not-a-date")
        self.assertEqual(ProductAIInsights._expiry_risks([item]), [])


if __name__ == "__main__":
    unittest.main()
