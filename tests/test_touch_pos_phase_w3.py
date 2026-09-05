"""Phase W3 product catalog and category tests."""
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from server import api


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "server" / "static" / "touch_pos"


class TouchPosPhaseW3Tests(unittest.TestCase):
    def test_touch_product_removes_cost_and_internal_fields(self):
        product = {
            "id": 11,
            "name": "Coffee",
            "category": "Drinks",
            "price": 2500,
            "original_price": 3000,
            "discount_percent": 10,
            "sku": "CF-1",
            "barcode": "12345",
            "stock": 4,
            "sold_by": "unit",
            "unit": "cup",
            "is_service": False,
            "is_out_of_stock": False,
            "is_low_stock": True,
            "thumbnail_url": "/images/coffee.png",
            "cost": 1200,
            "supplier": "Hidden",
            "variants": [
                {"variant_id": 8, "size": "L", "color": "Black", "sku": "CF-L", "barcode": "888", "price": 3000, "stock": 2, "low_stock": False, "cost": 1800},
                "bad variant",
            ],
        }

        sanitized = api._touch_product(product)

        self.assertEqual(sanitized["name"], "Coffee")
        self.assertEqual(sanitized["variants"], [{"variant_id": 8, "size": "L", "color": "Black", "sku": "CF-L", "barcode": "888", "price": 3000, "stock": 2, "low_stock": False}])
        self.assertNotIn("cost", sanitized)
        self.assertNotIn("supplier", sanitized)
        self.assertNotIn("cost", sanitized["variants"][0])

    def test_touch_catalog_requires_sales_permission(self):
        with self.assertRaises(HTTPException) as caught:
            api._require_touch_pos({"role": "Viewer", "permissions": ["view_reports"]})
        self.assertEqual(caught.exception.status_code, 403)

    def test_touch_categories_uses_existing_cashier_service_for_allowed_user(self):
        with patch("server.api.cashier_service.list_categories", return_value=["Drinks", "Snacks"]) as list_categories:
            result = api.touch_pos_categories({"role": "Cashier", "permissions": ["create_sale"]})
        list_categories.assert_called_once_with()
        self.assertEqual(result, {"categories": ["Drinks", "Snacks"]})

    def test_touch_products_forwards_filters_and_returns_sanitized_rows(self):
        rows = [{"id": 2, "name": "Tea", "category": "Drinks", "price": 1000, "cost": 500, "variants": [{"variant_id": 3, "price": 1200, "cost": 700}]}]
        with patch("server.api.cashier_service.list_products", return_value=rows) as list_products:
            result = api.touch_pos_products(" tea ", " Drinks ", 25, 5, {"role": "Admin", "permissions": []})
        list_products.assert_called_once_with("tea", "Drinks", 25, 5)
        self.assertEqual(result["products"][0]["name"], "Tea")
        self.assertNotIn("cost", result["products"][0])
        self.assertNotIn("cost", result["products"][0]["variants"][0])

    def test_static_shell_contains_catalog_targets(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        for marker in ('id="productSearch"', 'id="categoryList"', 'id="productGrid"', 'id="refreshProducts"', 'id="workspaceToast"'):
            self.assertIn(marker, html)

    def test_client_loads_catalog_without_sale_mutation(self):
        script = (STATIC / "touch-pos.js").read_text(encoding="utf-8")
        self.assertIn("/api/touch-pos/categories", script)
        self.assertIn("/api/touch-pos/products?", script)
        self.assertIn("new URLSearchParams", script)
        self.assertIn("new AbortController", script)
        self.assertIn("setTimeout(loadProducts, 250)", script)
        self.assertIn("escapeHtml(product.name)", script)
        self.assertIn("disabled", script)
        self.assertNotIn("/api/sales", script)
        self.assertIn("addToCart(product)", script)


if __name__ == "__main__":
    unittest.main()
