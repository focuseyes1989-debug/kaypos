"""HTTP client for the existing KAY POS Server API."""

from __future__ import annotations

from typing import Any
import base64
import mimetypes
from pathlib import Path

import requests


class LiteApiError(RuntimeError):
    pass


class LiteApiClient:
    def __init__(self, server_url: str, insecure_tls: bool = False, timeout: float = 12):
        self.server_url = str(server_url or "").strip().rstrip("/")
        if self.server_url and "://" not in self.server_url:
            self.server_url = f"https://{self.server_url}"
        self.verify_tls = not insecure_tls
        self.timeout = timeout
        self.token = ""
        self.session = requests.Session()

    def _request(self, method: str, path: str, **kwargs) -> dict:
        if not self.server_url:
            raise LiteApiError("Server URL is required.")
        headers = dict(kwargs.pop("headers", {}))
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            response = self.session.request(
                method, f"{self.server_url}{path}", headers=headers,
                timeout=self.timeout, verify=self.verify_tls, **kwargs,
            )
        except requests.exceptions.SSLError as exc:
            raise LiteApiError(
                "HTTPS certificate verification failed. Enable "
                "'Allow self-signed HTTPS certificate' and try again."
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            hint = (
                " The POS Server on port 8000 normally uses https://, not http://."
                if self.server_url.lower().startswith("http://") else ""
            )
            raise LiteApiError(f"Server connection failed.{hint}") from exc
        except requests.RequestException as exc:
            raise LiteApiError(f"Server connection failed: {exc}") from exc
        try:
            payload: Any = response.json()
        except ValueError:
            payload = {}
        if not response.ok:
            detail = payload.get("detail") if isinstance(payload, dict) else ""
            raise LiteApiError(str(detail or f"Server request failed ({response.status_code})"))
        return payload if isinstance(payload, dict) else {}

    def health(self) -> dict:
        return self._request("GET", "/health")

    def login(self, username: str, password: str) -> dict:
        payload = self._request(
            "POST", "/api/login",
            json={"username": username.strip(), "password": password},
        )
        token = str(payload.get("token") or "")
        user = payload.get("user") or {}
        if not token or not user:
            raise LiteApiError("Server returned an incomplete login response.")
        self.token = token
        return dict(user)

    def current_user(self) -> dict:
        return dict(self._request("GET", "/api/me").get("user") or {})

    def products(
        self, query: str = "", limit: int = 60, offset: int = 0, category: str = "",
    ) -> list[dict]:
        payload = self._request(
            "GET", "/api/products",
            params={
                "q": query.strip(), "category": category.strip(),
                "limit": max(1, min(limit, 100)), "offset": max(0, offset),
            },
        )
        return list(payload.get("products") or [])

    def categories(self) -> list[str]:
        return [str(value) for value in self._request("GET", "/api/categories").get("categories") or []]

    def managed_categories(self) -> list[dict]:
        return list(self._request("GET", "/api/categories/manage").get("categories") or [])

    def save_category(self, values: dict, category_id: int | None = None) -> dict:
        method = "PUT" if category_id else "POST"
        route = f"/api/categories/manage/{int(category_id)}" if category_id else "/api/categories/manage"
        return dict(self._request(method, route, json=values).get("category") or {})

    def delete_category(self, category_id: int) -> None:
        self._request("DELETE", f"/api/categories/manage/{int(category_id)}")

    def scan_product(self, code: str) -> dict | None:
        from urllib.parse import quote
        payload = self._request("GET", f"/api/products/scan/{quote(code.strip(), safe='')}")
        product = payload.get("product")
        return dict(product) if product else None

    def save_product(self, values: dict, product_id: int | None = None, image_path: str = "") -> dict:
        payload = dict(values)
        if image_path:
            path = Path(image_path)
            payload.update({
                "image_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
                "image_filename": path.name,
                "image_mime": mimetypes.guess_type(path.name)[0] or "image/jpeg",
            })
        method = "PUT" if product_id else "POST"
        route = f"/api/products/manage/{int(product_id)}" if product_id else "/api/products/manage"
        return dict(self._request(method, route, json=payload).get("product") or {})

    def payment_types(self) -> list[str]:
        return list(self._request("GET", "/api/payment-types").get("payment_types") or ["Cash"])

    def credit_settings(self) -> dict:
        return dict(self._request("GET", "/api/credit/settings").get("settings") or {})

    def lite_settings(self) -> dict:
        return dict(self._request("GET", "/api/settings/lite").get("settings") or {})

    def receipt_settings(self) -> dict:
        return dict(self._request("GET", "/api/settings/receipt").get("settings") or {})

    def save_lite_settings(self, values: dict) -> dict:
        return dict(self._request("PUT", "/api/settings/lite", json={"settings": values}).get("settings") or {})

    def payment_type_records(self) -> list[dict]:
        return list(self._request("GET", "/api/settings/payment-types").get("payment_types") or [])

    def save_payment_type(self, name: str, payment_id: int | None = None) -> dict:
        method = "PUT" if payment_id else "POST"
        path = f"/api/settings/payment-types/{int(payment_id)}" if payment_id else "/api/settings/payment-types"
        return dict(self._request(method, path, json={"name": name.strip()}).get("payment_type") or {})

    def delete_payment_type(self, payment_id: int) -> None:
        self._request("DELETE", f"/api/settings/payment-types/{int(payment_id)}")

    def users_settings(self) -> dict:
        return self._request("GET", "/api/settings/users")

    def save_user(self, values: dict, user_id: int | None = None) -> dict:
        method = "PUT" if user_id else "POST"
        path = f"/api/settings/users/{int(user_id)}" if user_id else "/api/settings/users"
        return dict(self._request(method, path, json=values).get("user") or {})

    def delete_user(self, user_id: int) -> None:
        self._request("DELETE", f"/api/settings/users/{int(user_id)}")

    def expense_categories(self) -> list[str]:
        return list(self._request("GET", "/api/expenses/categories").get("categories") or [])

    def expenses(
        self, query: str = "", from_date: str = "", to_date: str = "",
        limit: int = 100, offset: int = 0,
    ) -> dict:
        return self._request("GET", "/api/expenses", params={
            "q": query.strip(), "from_date": from_date, "to_date": to_date,
            "limit": max(1, min(limit, 200)), "offset": max(0, offset),
        })

    def add_expense(self, values: dict) -> dict:
        return dict(self._request("POST", "/api/expenses", json=values).get("expense") or {})

    def checkout(
        self, items: list[dict], payment: float, payment_type: str = "Cash",
        customer_id: int | None = None, due_date: str = "", credit_notes: str = "",
        allow_credit_over_limit: bool = False, discount_amount: float = 0,
    ) -> dict:
        payload = self._request(
            "POST", "/api/sales",
            json={
                "items": items, "payment": float(payment),
                "payment_type": payment_type or "Cash",
                "sale_mode": "Credit" if str(payment_type).lower() == "credit" else "Cash",
                "discount_amount": max(0.0, float(discount_amount or 0)),
                "points_used": 0, "customer_id": customer_id,
                "due_date": due_date, "credit_notes": credit_notes,
                "allow_credit_over_limit": bool(allow_credit_over_limit),
            },
        )
        receipt = payload.get("receipt") or {}
        if not receipt:
            raise LiteApiError("Server returned an incomplete receipt.")
        return dict(receipt)

    def receipts(self, query: str = "", limit: int = 50, offset: int = 0) -> list[dict]:
        payload = self._request(
            "GET", "/api/receipts",
            params={"q": query.strip(), "limit": max(1, min(limit, 100)), "offset": max(0, offset)},
        )
        return list(payload.get("receipts") or [])

    def receipt(self, sale_id: int) -> dict:
        return dict(self._request("GET", f"/api/receipts/{int(sale_id)}").get("receipt") or {})

    def refund(self, sale_id: int, reason: str) -> dict:
        return dict(self._request(
            "POST", f"/api/sales/{int(sale_id)}/refund", json={"reason": reason.strip()}
        ).get("receipt") or {})

    def service_orders(
        self, query: str = "", status: str = "", limit: int = 100, offset: int = 0,
    ) -> list[dict]:
        return list(self._request("GET", "/api/service-orders", params={
            "q": query.strip(), "status": status.strip(),
            "limit": max(1, min(limit, 200)), "offset": max(0, offset),
        }).get("service_orders") or [])

    def service_order(self, order_id: int) -> dict:
        return dict(self._request(
            "GET", f"/api/service-orders/{int(order_id)}"
        ).get("service_order") or {})

    def create_service_order(self, values: dict) -> dict:
        return dict(self._request(
            "POST", "/api/service-orders", json=values,
        ).get("service_order") or {})

    def update_service_order(self, order_id: int, values: dict) -> dict:
        return dict(self._request(
            "PUT", f"/api/service-orders/{int(order_id)}", json=values,
        ).get("service_order") or {})

    def change_service_order_status(self, order_id: int, status: str, note: str = "") -> dict:
        return dict(self._request(
            "POST", f"/api/service-orders/{int(order_id)}/status",
            json={"status": status.strip(), "note": note.strip()},
        ).get("service_order") or {})

    def add_service_order_item(self, order_id: int, values: dict) -> dict:
        return dict(self._request(
            "POST", f"/api/service-orders/{int(order_id)}/items", json=values,
        ).get("item") or {})

    def update_service_order_item(self, order_id: int, item_id: int, values: dict) -> dict:
        return dict(self._request(
            "PUT", f"/api/service-orders/{int(order_id)}/items/{int(item_id)}", json=values,
        ).get("item") or {})

    def delete_service_order_item(self, order_id: int, item_id: int) -> None:
        self._request("DELETE", f"/api/service-orders/{int(order_id)}/items/{int(item_id)}")

    def record_service_order_deposit(
        self, order_id: int, amount: float, payment_type: str = "Cash",
        reference_no: str = "", note: str = "",
    ) -> dict:
        return dict(self._request(
            "POST", f"/api/service-orders/{int(order_id)}/deposit",
            json={"amount": float(amount), "payment_type": payment_type, "reference_no": reference_no, "note": note},
        ).get("service_order") or {})

    def checkout_service_order(
        self, order_id: int, payment: float, payment_type: str = "Cash",
        allow_credit_over_limit: bool = False,
    ) -> dict:
        return dict(self._request(
            "POST", f"/api/service-orders/{int(order_id)}/checkout",
            json={"payment": float(payment), "payment_type": payment_type, "allow_credit_over_limit": bool(allow_credit_over_limit)},
        ).get("service_order") or {})

    def add_service_order_return_visit(self, order_id: int, reason: str, handled_by: str = "") -> dict:
        return dict(self._request(
            "POST", f"/api/service-orders/{int(order_id)}/return-visits",
            json={"reason": reason, "handled_by": handled_by, "visited_at": ""},
        ).get("service_order") or {})

    def close_service_order_return_visit(self, order_id: int, visit_id: int, resolution: str) -> dict:
        return dict(self._request(
            "POST", f"/api/service-orders/{int(order_id)}/return-visits/{int(visit_id)}/close",
            json={"resolution": resolution},
        ).get("service_order") or {})

    def service_order_report(self, from_date: str, to_date: str) -> dict:
        return dict(self._request(
            "GET", "/api/service-orders-reports/summary",
            params={"from_date": from_date, "to_date": to_date},
        ).get("summary") or {})

    def service_order_warranties(self, days: int = 30) -> list[dict]:
        return list(self._request(
            "GET", "/api/service-orders-reports/warranties", params={"days": max(0, int(days))},
        ).get("warranties") or [])

    def service_order_notifications(self, status: str = "pending") -> list[dict]:
        return list(self._request(
            "GET", "/api/service-orders-notifications", params={"status": status, "limit": 200},
        ).get("notifications") or [])

    def print_service_presets(self) -> list[dict]:
        return list(self._request("GET", "/api/print-service-presets").get("presets") or [])

    def save_print_service_preset(self, values: dict, preset_id: int | None = None) -> dict:
        method = "PUT" if preset_id else "POST"
        path = f"/api/print-service-presets/{int(preset_id)}" if preset_id else "/api/print-service-presets"
        return dict(self._request(method, path, json=values).get("preset") or {})

    def delete_print_service_preset(self, preset_id: int) -> None:
        self._request("DELETE", f"/api/print-service-presets/{int(preset_id)}")

    def customers(self, query: str = "", limit: int = 100) -> list[dict]:
        return list(self._request(
            "GET", "/api/customers", params={"q": query.strip(), "limit": max(1, min(limit, 200))}
        ).get("customers") or [])

    def suppliers(self) -> list[dict]:
        return list(self._request("GET", "/api/suppliers").get("suppliers") or [])

    def stock_locations(self) -> list[str]:
        return [str(value) for value in self._request("GET", "/api/stock/locations").get("locations") or ["Shop"]]

    def dashboard_summary(
        self, from_date: str, to_date: str | None = None, trend_days: int = 0,
    ) -> dict:
        to_date = to_date or from_date
        return self._request(
            "GET", "/api/dashboard/summary",
            params={
                "from_date": from_date,
                "to_date": to_date,
                "trend_days": max(0, min(int(trend_days), 31)),
            },
        )

    def adjust_stock(
        self, product_id: int, adjustment: int, *, variant_id: int | None = None,
        reason: str = "Lite POS adjustment", location: str = "Shop",
        supplier_id: int | None = None, unit_cost: float = 0, batch_no: str = "",
        received_by: str = "", notes: str = "",
        customer_id: int | None = None, reference: str = "", issued_by: str = "",
        transaction_date: str = "",
    ) -> dict:
        return dict(self._request("POST", "/api/stock/adjust", json={
            "product_id": int(product_id), "variant_id": variant_id,
            "adjustment": int(adjustment), "reason": reason, "location": location,
            "supplier_id": supplier_id, "unit_cost": float(unit_cost or 0),
            "batch_no": batch_no.strip(), "received_by": received_by.strip(),
            "notes": notes.strip(),
            "customer_id": customer_id, "reference": reference.strip(),
            "issued_by": issued_by.strip(), "transaction_date": transaction_date.strip(),
        }).get("product") or {})

    def set_stock_quantity(self, values: dict) -> dict:
        return dict(self._request(
            "POST", "/api/stock/adjustment", json=values
        ).get("product") or {})

    def transfer_stock(self, values: dict) -> dict:
        return dict(self._request(
            "POST", "/api/stock/transfer", json=values
        ).get("product") or {})

    def stock_movements(self, product_id: int, limit: int = 200) -> list[dict]:
        return list(self._request(
            "GET", "/api/stock/movements",
            params={"product_id": int(product_id), "limit": max(1, min(limit, 500))},
        ).get("movements") or [])

    def reverse_stock_movement(self, movement_id: int, reason: str) -> dict:
        return self._request(
            "POST", f"/api/stock/movements/{int(movement_id)}/reverse",
            json={"reason": reason.strip() or "User requested reversal"},
        )

    def logout(self) -> None:
        self.token = ""

    def close(self) -> None:
        self.token = ""
        self.session.close()
