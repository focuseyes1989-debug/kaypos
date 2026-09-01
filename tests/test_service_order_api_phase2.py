import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from server import api


class ServiceOrderApiPhase2Tests(unittest.TestCase):
    def setUp(self):
        self.repo = MagicMock()
        self.repo.create.return_value = {"id": 1, "order_no": "SO-20260901-0001"}
        self.repo.get.return_value = {"id": 1, "items": [], "status_history": []}
        self.repo.list.return_value = [{"id": 1}]
        self.repo.update.return_value = {"id": 1, "priority": "urgent"}
        self.repo.add_item.return_value = {"id": 10, "description": "Repair"}
        self.repo.update_item.return_value = {"id": 10, "unit_price": 2000}
        self.repo.change_status.return_value = {"id": 1, "status": "in_progress"}
        self.repo.record_deposit.return_value = {"id": 1, "deposit_amount": 5000}
        self.repo.checkout.return_value = {"id": 1, "sale_id": 77}
        self.repo.analytics.return_value = {"orders": 1}
        self.repo.warranty_items.return_value = []
        self.repo.notifications.return_value = []
        self.repo.list_presets.return_value = [{"id": 1}]
        self.repo.save_preset.return_value = {"id": 1, "name": "A4 Color"}
        self.patch = patch("server.api.ServiceOrderRepository", return_value=self.repo)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def test_routes_are_registered(self):
        paths = {route.path for route in api.app.routes}
        self.assertTrue({
            "/api/service-orders",
            "/api/service-orders/{order_id}",
            "/api/service-orders/{order_id}/items",
            "/api/service-orders/{order_id}/items/{item_id}",
            "/api/service-orders/{order_id}/status",
            "/api/service-orders/{order_id}/deposit",
            "/api/service-orders/{order_id}/checkout",
            "/api/service-orders/{order_id}/return-visits",
            "/api/service-orders-reports/summary",
            "/api/service-orders-reports/warranties",
            "/api/service-orders-notifications",
            "/api/print-service-presets",
            "/api/print-service-presets/{preset_id}",
        }.issubset(paths))

    def test_create_uses_authenticated_username_for_audit(self):
        payload = api.ServiceOrderCreateRequest(customer_name="Aye", complaint="No power")
        result = api.create_service_order(payload, {"username": "cashier1", "role": "Cashier"})
        self.assertEqual(result["service_order"]["id"], 1)
        values = self.repo.create.call_args.args[0]
        self.assertEqual(values["customer_name"], "Aye")
        self.repo.create.assert_called_once_with(values, created_by="cashier1")

    def test_list_detail_and_partial_update(self):
        self.assertEqual(api.service_orders("received", "SO-1", 20, 0, {})["service_orders"], [{"id": 1}])
        self.repo.list.assert_called_once_with(status="received", search="SO-1", limit=20, offset=0)
        self.assertEqual(api.service_order(1, {})["service_order"]["id"], 1)
        api.update_service_order(1, api.ServiceOrderUpdateRequest(priority="urgent"), {})
        self.repo.update.assert_called_once_with(1, {"priority": "urgent"})

    def test_item_crud_calls_repository(self):
        created = api.add_service_order_item(
            1,
            api.ServiceOrderItemRequest(description="Repair", qty=1, unit_price=1000),
            {},
        )
        self.assertEqual(created["item"]["id"], 10)
        api.update_service_order_item(
            1, 10, api.ServiceOrderItemUpdateRequest(unit_price=2000), {},
        )
        self.repo.update_item.assert_called_once_with(1, 10, {"unit_price": 2000.0})
        self.assertEqual(api.delete_service_order_item(1, 10, {}), {"status": "SUCCESS"})
        self.repo.delete_item.assert_called_once_with(1, 10)

    def test_status_change_uses_authenticated_username(self):
        result = api.change_service_order_status(
            1,
            api.ServiceOrderStatusRequest(status="in_progress", note="Started"),
            {"username": "tech1"},
        )
        self.assertEqual(result["service_order"]["status"], "in_progress")
        self.repo.change_status.assert_called_once_with(
            1, "in_progress", changed_by="tech1", note="Started",
        )

    def test_request_models_reject_invalid_values(self):
        with self.assertRaises(ValidationError):
            api.ServiceOrderItemRequest(description="", qty=0)
        with self.assertRaises(ValidationError):
            api.ServiceOrderCreateRequest(priority="critical")
        with self.assertRaises(ValidationError):
            api.ServiceOrderStatusRequest(status="unknown")
        with self.assertRaises(ValidationError):
            api.ServiceOrderCreateRequest(approval_status="maybe")
        with self.assertRaises(ValidationError):
            api.ServiceOrderItemRequest(description="Print", pricing_unit="per_meter")

    def test_repository_not_found_becomes_http_404(self):
        self.repo.get.side_effect = ValueError("Service order not found")
        with self.assertRaises(HTTPException) as caught:
            api.service_order(999, {})
        self.assertEqual(caught.exception.status_code, 404)

    def test_deposit_and_checkout_take_actor_from_login(self):
        api.record_service_order_deposit(
            1, api.ServiceOrderDepositRequest(amount=5000, payment_type="Cash"), {"username": "cashier", "role": "Cashier"},
        )
        self.repo.record_deposit.assert_called_once_with(
            1, 5000.0, payment_type="Cash", reference_no="", note="", received_by="cashier",
        )
        api.checkout_service_order(
            1, api.ServiceOrderCheckoutRequest(payment=20000, payment_type="Cash"), {"username": "cashier", "role": "Cashier"},
        )
        self.repo.checkout.assert_called_once_with(
            1, payment=20000.0, payment_type="Cash", allow_credit_over_limit=False, created_by="cashier",
        )

    def test_reports_require_manager_role(self):
        with self.assertRaises(HTTPException) as caught:
            api.service_order_report_summary("2026-09-01", "2026-09-01", {"role": "Cashier"})
        self.assertEqual(caught.exception.status_code, 403)
        result = api.service_order_report_summary("2026-09-01", "2026-09-01", {"role": "Manager"})
        self.assertEqual(result["summary"]["orders"], 1)

    def test_preset_write_requires_manager(self):
        payload = api.PrintServicePresetRequest(name="A4 Color", product_id=1)
        with self.assertRaises(HTTPException) as caught:
            api.create_print_service_preset(payload, {"role": "Cashier"})
        self.assertEqual(caught.exception.status_code, 403)
        result = api.create_print_service_preset(payload, {"role": "Manager"})
        self.assertEqual(result["preset"]["name"], "A4 Color")


if __name__ == "__main__":
    unittest.main()
