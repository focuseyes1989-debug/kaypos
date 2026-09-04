import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox

from lite_pos.api import LiteApiClient
from lite_pos.window import LiteWindow, ServiceOrderDialog, ServiceOrderItemDialog


class ServiceOrderUiPhase3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_service_order_page_is_in_sidebar_and_workspace(self):
        window = LiteWindow()
        self.assertIn("Service Orders", window.nav_buttons)
        self.assertIs(window.workspace_pages["Service Orders"], window.service_orders_page)
        self.assertEqual(window.service_order_table.columnCount(), 12)
        window.close()

    def test_dialog_maps_job_details_and_payment_notes(self):
        dialog = ServiceOrderDialog()
        dialog.job_title.setText("A4 color print")
        dialog.complaint.setPlainText("No power")
        dialog.internal_notes.setPlainText("Deposit 5000; balance unpaid")
        values = dialog.values()
        self.assertEqual(values["job_title"], "A4 color print")
        self.assertEqual(values["complaint"], "No power")
        self.assertEqual(values["internal_notes"], "Deposit 5000; balance unpaid")
        dialog.close()

    def test_detail_renders_items_history_and_valid_transitions(self):
        window = LiteWindow()
        window._show_service_order_detail({
            "id": 1, "order_no": "SO-20260901-0001", "status": "in_progress",
            "customer_name": "Aye", "item_name": "Laptop", "priority": "urgent",
            "items": [{"description": "Repair", "item_type": "service", "qty": 1, "unit_price": 20000}],
            "status_history": [{"to_status": "in_progress", "changed_by": "tech", "changed_at": "2026-09-01"}],
        })
        self.assertEqual(window.service_order_items_table.rowCount(), 1)
        self.assertEqual(window.service_order_history.count(), 1)
        self.assertFalse(window.service_order_collect_button.isEnabled())
        self.assertFalse(hasattr(window, "service_order_next_status"))
        window.close()

    def test_print_shop_status_controls_follow_production_flow(self):
        window = LiteWindow()
        window._show_service_order_detail({
            "id": 2, "order_no": "SO-2", "status": "ready_to_print",
            "job_title": "Color booklet", "items": [], "status_history": [],
        })
        self.assertFalse(window.service_order_collect_button.isEnabled())
        window._show_service_order_detail({
            "id": 2, "order_no": "SO-2", "status": "ready_for_pickup",
            "job_title": "Color booklet", "items": [], "status_history": [],
        })
        self.assertTrue(window.service_order_collect_button.isEnabled())
        window.close()

    def test_order_item_dialog_filters_sold_by_mode_and_variants(self):
        products = [
            {"id": 1, "name": "Repair", "sold_by": "Service", "price": 1000, "stock": 0},
            {"id": 2, "name": "Cable", "sold_by": "Each", "price": 500, "stock": 4},
            {"id": 3, "name": "Screen", "sold_by": "Variants", "price": 0, "stock": 2,
             "variants": [{"variant_id": 31, "color": "Black", "stock": 2, "price": 5000}]},
        ]
        dialog = ServiceOrderItemDialog(products=products)
        self.assertEqual(dialog.product.count(), 1)
        self.assertEqual(dialog.product.currentData()["id"], 1)
        dialog.item_type.setCurrentIndex(dialog.item_type.findData("part"))
        self.assertEqual(dialog.product.count(), 2)
        screen_index = next(i for i in range(dialog.product.count()) if dialog.product.itemData(i)["id"] == 3)
        dialog.product.setCurrentIndex(screen_index)
        self.assertEqual(dialog.variant.currentData()["variant_id"], 31)
        dialog.pricing_unit.setCurrentIndex(dialog.pricing_unit.findData("per_sheet"))
        dialog.pages_per_copy.setValue(5)
        dialog.copy_count.setValue(3)
        dialog.print_side.setCurrentIndex(dialog.print_side.findData("double"))
        dialog.unit_price.setValue(100)
        self.assertEqual(dialog.qty.value(), 9)
        self.assertEqual(dialog.total_sheets_label.text(), "9 sheet(s)")
        self.assertEqual(dialog.line_amount_label.text(), "900 Ks")
        values = dialog.values()
        self.assertEqual(values["item_type"], "part")
        self.assertEqual(values["variant_id"], 31)
        self.assertEqual(values["pricing_unit"], "per_sheet")
        self.assertEqual(values["pages_per_copy"], 5)
        dialog.close()

    def test_quick_preset_populates_service_and_print_defaults(self):
        products = [{"id": 1, "name": "A4 Color", "sold_by": "Service", "price": 0, "stock": 0}]
        presets = [{
            "id": 8, "name": "A4 Color Single", "product_id": 1, "description": "A4 Color Print",
            "pricing_unit": "per_page", "unit_price": 500, "pages_per_copy": 2, "copy_count": 3,
            "paper_size": "A4", "paper_type": "Normal 80gsm", "color_mode": "color",
            "print_side": "single", "finishing": "Staple",
        }]
        dialog = ServiceOrderItemDialog(products=products, presets=presets)
        dialog.preset.setCurrentIndex(1)
        values = dialog.values()
        self.assertEqual(values["product_id"], 1)
        self.assertEqual(values["description"], "A4 Color Print")
        self.assertEqual(values["pricing_unit"], "per_page")
        self.assertEqual(values["qty"], 6)
        self.assertEqual(values["unit_price"], 500)
        self.assertEqual(values["paper_size"], "A4")
        self.assertEqual(values["color_mode"], "color")
        dialog.close()

    @patch("lite_pos.api.requests.Session.request")
    def test_api_client_uses_phase_three_routes(self, request):
        response = Mock(ok=True)
        response.json.side_effect = [
            {"service_orders": [{"id": 1}]}, {"service_order": {"id": 1}},
            {"service_order": {"id": 2}}, {"service_order": {"id": 2}},
            {"status": "SUCCESS"},
            {"service_order": {"id": 2, "status": "assigned"}},
            {"item": {"id": 5}}, {"item": {"id": 5}}, {"status": "SUCCESS"},
            {"service_order": {"id": 2, "deposit_amount": 5000}},
            {"service_order": {"id": 2, "sale_id": 77}},
        ]
        request.return_value = response
        client = LiteApiClient("https://server", insecure_tls=True)
        client.service_orders("Aye", "received")
        client.service_order(1)
        client.create_service_order({"customer_name": "Aye"})
        client.update_service_order(2, {"priority": "urgent"})
        client.delete_service_order(2)
        client.change_service_order_status(2, "assigned", "Assigned")
        client.add_service_order_item(2, {"description": "Repair"})
        client.update_service_order_item(2, 5, {"unit_price": 2000})
        client.delete_service_order_item(2, 5)
        client.record_service_order_deposit(2, 5000, "Cash")
        client.checkout_service_order(2, 20000, "Cash")
        calls = request.call_args_list
        self.assertEqual(calls[0].args[1], "https://server/api/service-orders")
        self.assertEqual(calls[1].args[1], "https://server/api/service-orders/1")
        self.assertEqual(calls[2].args[:2], ("POST", "https://server/api/service-orders"))
        self.assertEqual(calls[3].args[:2], ("PUT", "https://server/api/service-orders/2"))
        self.assertEqual(calls[4].args[:2], ("DELETE", "https://server/api/service-orders/2"))
        self.assertEqual(calls[5].args[1], "https://server/api/service-orders/2/status")
        self.assertEqual(calls[6].args[:2], ("POST", "https://server/api/service-orders/2/items"))
        self.assertEqual(calls[7].args[:2], ("PUT", "https://server/api/service-orders/2/items/5"))
        self.assertEqual(calls[8].args[:2], ("DELETE", "https://server/api/service-orders/2/items/5"))
        self.assertEqual(calls[9].args[1], "https://server/api/service-orders/2/deposit")
        self.assertEqual(calls[10].args[1], "https://server/api/service-orders/2/checkout")
        client.close()


if __name__ == "__main__":
    unittest.main()
