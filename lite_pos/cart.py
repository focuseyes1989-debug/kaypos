"""In-memory Lite cart with stock-safe quantity handling."""

from __future__ import annotations


class CartError(ValueError):
    pass


def sold_by_mode(value: object) -> str:
    """Normalize legacy and display-form sold-by values."""
    mode = " ".join(str(value or "each").strip().lower().replace("_", " ").split())
    if mode in {"service", "services"} or mode.endswith(" service"):
        return "service"
    if mode in {"variant", "variants"} or mode.endswith(" variants"):
        return "variants"
    return mode


class LiteCart:
    def __init__(self):
        self.items: dict[str, dict] = {}

    @staticmethod
    def key(product: dict, variant: dict | None = None) -> str:
        return f"{int(product.get('id') or 0)}:{int((variant or {}).get('variant_id') or 0)}"

    def add(self, product: dict, variant: dict | None = None) -> dict:
        variant = variant or {}
        is_service = sold_by_mode(product.get("sold_by")) == "service"
        stock = int(variant.get("stock") if variant else product.get("stock") or 0)
        if not is_service and stock <= 0:
            raise CartError(f"{product.get('name') or 'Product'} is out of stock.")
        key = self.key(product, variant)
        if is_service:
            # The same service may be sold at different entered prices.
            key = f"{key}:service:{float(product.get('price') or 0):.2f}"
        item = self.items.get(key) or {
            "key": key, "product_id": int(product.get("id") or 0),
            "variant_id": int(variant.get("variant_id") or 0) or None,
            "name": str(product.get("name") or ""),
            "variant_label": " / ".join(x for x in (str(variant.get("color") or ""), str(variant.get("size") or "")) if x),
            "price": float(variant.get("price") or product.get("price") or 0),
            "stock": stock, "qty": 0, "is_service": is_service,
        }
        if not is_service and item["qty"] + 1 > stock:
            raise CartError(f"Only {stock} left: {item['name']}")
        item["qty"] += 1
        self.items[key] = item
        return item

    def change(self, key: str, delta: int) -> None:
        item = self.items.get(key)
        if not item:
            return
        quantity = item["qty"] + int(delta)
        if quantity <= 0:
            self.items.pop(key, None)
        elif not item["is_service"] and quantity > item["stock"]:
            raise CartError(f"Only {item['stock']} left: {item['name']}")
        else:
            item["qty"] = quantity

    def clear(self) -> None:
        self.items.clear()

    def count(self) -> int:
        return sum(int(item["qty"]) for item in self.items.values())

    def total(self) -> float:
        return sum(float(item["price"]) * int(item["qty"]) for item in self.items.values())
