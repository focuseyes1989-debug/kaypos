"""HTTP client for the existing KAY POS Server API."""

from __future__ import annotations

from typing import Any

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

    def scan_product(self, code: str) -> dict | None:
        from urllib.parse import quote
        payload = self._request("GET", f"/api/products/scan/{quote(code.strip(), safe='')}")
        product = payload.get("product")
        return dict(product) if product else None

    def payment_types(self) -> list[str]:
        return list(self._request("GET", "/api/payment-types").get("payment_types") or ["Cash"])

    def checkout(self, items: list[dict], payment: float, payment_type: str = "Cash") -> dict:
        payload = self._request(
            "POST", "/api/sales",
            json={
                "items": items, "payment": float(payment),
                "payment_type": payment_type or "Cash", "sale_mode": "Cash",
                "discount_amount": 0, "points_used": 0, "customer_id": None,
            },
        )
        receipt = payload.get("receipt") or {}
        if not receipt:
            raise LiteApiError("Server returned an incomplete receipt.")
        return dict(receipt)

    def open_cash_drawer(self) -> dict:
        """Ask the Server PC to pulse its configured receipt-printer drawer port."""
        return dict(self._request("POST", "/api/cashdrawer/open"))

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

    def customers(self, query: str = "", limit: int = 100) -> list[dict]:
        return list(self._request(
            "GET", "/api/customers", params={"q": query.strip(), "limit": max(1, min(limit, 200))}
        ).get("customers") or [])

    def dashboard_summary(self, date_text: str) -> dict:
        return self._request(
            "GET", "/api/dashboard/summary",
            params={"from_date": date_text, "to_date": date_text, "trend_days": 0},
        )

    def adjust_stock(
        self, product_id: int, adjustment: int, *, variant_id: int | None = None,
        reason: str = "Lite POS adjustment", location: str = "Shop",
    ) -> dict:
        return dict(self._request("POST", "/api/stock/adjust", json={
            "product_id": int(product_id), "variant_id": variant_id,
            "adjustment": int(adjustment), "reason": reason, "location": location,
        }).get("product") or {})

    def logout(self) -> None:
        self.token = ""

    def close(self) -> None:
        self.token = ""
        self.session.close()
