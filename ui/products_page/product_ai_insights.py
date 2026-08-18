"""Read-only inventory intelligence for the Products AI assistant."""

import math
import re
from collections import defaultdict
from datetime import datetime, timedelta

from loguru import logger

from models.database.connection import DBContext
from utils.db_compat import table_columns


class ProductAIInsights:
    """Build explainable product insights from stock and completed sales."""

    SALES_WINDOW_DAYS = 30
    SLOW_WINDOW_DAYS = 90
    TARGET_STOCK_DAYS = 14

    @classmethod
    def analyze(cls, include_sensitive=True):
        try:
            products, sales_30, sales_90 = cls._load_data()
            reorder = cls._reorder(products, sales_30)
            fast = cls._fast_movers(products, sales_30)
            slow, dead = cls._slow_and_dead(products, sales_90)
            expiry = cls._expiry_risks(products)
            margins = cls._margin_warnings(products)
            duplicates = cls._duplicates(products)
            if not include_sensitive:
                margins = []
                for section in (reorder, fast, slow, dead, expiry):
                    cls._hide_sensitive(section)
                for group in duplicates:
                    cls._hide_sensitive(group.get("products", []))
            return {
                "type": "product_insights",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "windows": {"velocity_days": 30, "slow_days": 90, "target_days": 14},
                "summary": {
                    "reorder": len(reorder), "fast": len(fast), "slow": len(slow),
                    "dead": len(dead), "expiry": len(expiry),
                    "margin": len(margins) if include_sensitive else None,
                    "duplicates": len(duplicates),
                },
                "reorder": reorder[:20],
                "fast": fast[:10],
                "slow": slow[:10],
                "dead": dead[:10],
                "expiry": expiry[:10],
                "margin": margins[:10],
                "duplicates": duplicates[:10],
                "sensitive_hidden": not include_sensitive,
            }
        except Exception as exc:
            logger.exception(f"Product insight analysis failed: {exc}")
            return {"type": "error", "message": f"Could not analyze inventory: {exc}"}

    @staticmethod
    def _hide_sensitive(items):
        for item in items:
            item.pop("stock_value", None)
            item.pop("cost", None)
        return items

    @classmethod
    def _load_data(cls):
        cutoff_30 = (datetime.now() - timedelta(days=cls.SALES_WINDOW_DAYS)).isoformat(sep=" ")
        cutoff_90 = (datetime.now() - timedelta(days=cls.SLOW_WINDOW_DAYS)).isoformat(sep=" ")
        with DBContext() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, category, price, cost, sku, barcode, stock,
                       low_stock, expire_date, sold_by
                FROM products
                WHERE sold_by IS NULL OR LOWER(sold_by) != 'service'
            """)
            products = [cls._product(row) for row in cursor.fetchall()]

            sale_item_columns = table_columns(cursor, "sale_items")
            product_id_expr = "si.product_id" if "product_id" in sale_item_columns else "NULL"
            cursor.execute(f"""
                SELECT {product_id_expr}, si.product_name, COALESCE(SUM(si.qty), 0)
                FROM sale_items si
                JOIN sales s ON s.id = si.sale_id
                WHERE (s.status = 'completed' OR s.status IS NULL)
                  AND s.created_at >= ?
                GROUP BY {product_id_expr}, si.product_name
            """, (cutoff_90,))
            rows_90 = cursor.fetchall()

            cursor.execute(f"""
                SELECT {product_id_expr}, si.product_name, COALESCE(SUM(si.qty), 0)
                FROM sale_items si
                JOIN sales s ON s.id = si.sale_id
                WHERE (s.status = 'completed' OR s.status IS NULL)
                  AND s.created_at >= ?
                GROUP BY {product_id_expr}, si.product_name
            """, (cutoff_30,))
            rows_30 = cursor.fetchall()
        return products, cls._sales_map(rows_30), cls._sales_map(rows_90)

    @staticmethod
    def _product(row):
        return {
            "id": row[0], "name": row[1] or "Unknown", "category": row[2] or "",
            "price": float(row[3] or 0), "cost": float(row[4] or 0),
            "sku": row[5] or "", "barcode": row[6] or "",
            "stock": float(row[7] or 0), "low_stock": float(row[8] or 0),
            "expire_date": row[9] or "",
        }

    @staticmethod
    def _sales_map(rows):
        by_id, by_name = defaultdict(float), defaultdict(float)
        for product_id, name, qty in rows:
            if product_id is not None:
                by_id[int(product_id)] += float(qty or 0)
            by_name[str(name or "").strip().casefold()] += float(qty or 0)
        return {"id": by_id, "name": by_name}

    @staticmethod
    def _sold(product, sales):
        return sales["id"].get(product["id"], sales["name"].get(product["name"].casefold(), 0))

    @classmethod
    def _reorder(cls, products, sales):
        rows = []
        for product in products:
            sold = cls._sold(product, sales)
            daily = sold / cls.SALES_WINDOW_DAYS
            target = max(product["low_stock"], math.ceil(daily * cls.TARGET_STOCK_DAYS))
            order_qty = max(0, math.ceil(target + product["low_stock"] - product["stock"]))
            days_left = product["stock"] / daily if daily > 0 else None
            if product["stock"] <= 0:
                priority = "critical"
            elif product["stock"] <= product["low_stock"] or (days_left is not None and days_left < 7):
                priority = "high"
            elif days_left is not None and days_left < cls.TARGET_STOCK_DAYS:
                priority = "medium"
            else:
                continue
            item = dict(product)
            item.update({"sold_30": sold, "daily_velocity": round(daily, 2),
                         "days_left": round(days_left, 1) if days_left is not None else None,
                         "recommended_qty": max(order_qty, 1),
                         "recommended_low_stock": max(1, math.ceil(daily * 7), math.ceil(product["low_stock"])),
                         "priority": priority})
            rows.append(item)
        order = {"critical": 0, "high": 1, "medium": 2}
        return sorted(rows, key=lambda x: (order[x["priority"]], x["days_left"] or 999, -x["sold_30"]))

    @classmethod
    def _fast_movers(cls, products, sales):
        rows = []
        for product in products:
            sold = cls._sold(product, sales)
            if sold <= 0:
                continue
            item = dict(product)
            item.update({"sold_30": sold, "daily_velocity": round(sold / cls.SALES_WINDOW_DAYS, 2)})
            rows.append(item)
        return sorted(rows, key=lambda x: (-x["sold_30"], x["stock"]))

    @classmethod
    def _slow_and_dead(cls, products, sales):
        slow, dead = [], []
        for product in products:
            if product["stock"] <= 0:
                continue
            sold = cls._sold(product, sales)
            item = dict(product)
            item["sold_90"] = sold
            if sold <= 0:
                item["stock_value"] = round(product["stock"] * product["cost"], 2)
                dead.append(item)
            elif sold <= 2:
                slow.append(item)
        return (sorted(slow, key=lambda x: (x["sold_90"], -x["stock"])),
                sorted(dead, key=lambda x: -x["stock_value"]))

    @staticmethod
    def _parse_date(value):
        text = str(value or "").strip()
        for candidate in (text, text[:10]):
            try:
                return datetime.fromisoformat(candidate).date()
            except (ValueError, TypeError):
                pass
        return None

    @classmethod
    def _expiry_risks(cls, products):
        today = datetime.now().date()
        rows = []
        for product in products:
            expiry = cls._parse_date(product["expire_date"])
            if not expiry:
                continue
            days = (expiry - today).days
            if days <= 30:
                item = dict(product)
                item.update({"days_to_expiry": days, "expiry_status": "expired" if days < 0 else "expiring"})
                rows.append(item)
        return sorted(rows, key=lambda x: x["days_to_expiry"])

    @staticmethod
    def _margin_warnings(products):
        rows = []
        for product in products:
            if product["cost"] <= 0:
                continue
            margin = ((product["price"] - product["cost"]) / product["price"] * 100) if product["price"] > 0 else -100
            if margin < 15:
                item = dict(product)
                item.update({"margin_pct": round(margin, 1),
                             "margin_status": "loss" if product["price"] <= product["cost"] else "low"})
                rows.append(item)
        return sorted(rows, key=lambda x: x["margin_pct"])

    @staticmethod
    def _duplicates(products):
        groups = defaultdict(list)
        for product in products:
            normalized = re.sub(r"[^\w]+", "", product["name"].casefold())
            if normalized:
                groups[("name", normalized)].append(product)
            if product["sku"]:
                groups[("sku", product["sku"].strip().casefold())].append(product)
            if product["barcode"]:
                groups[("barcode", product["barcode"].strip())].append(product)
        results, seen = [], set()
        for (reason, value), matches in groups.items():
            ids = tuple(sorted(item["id"] for item in matches))
            key = (reason, ids)
            if len(matches) > 1 and key not in seen:
                seen.add(key)
                results.append({"reason": reason, "value": value, "products": matches})
        return results
