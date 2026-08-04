"""
Bilingual keyword helpers for AI Chat.

Keep Myanmar strings as unicode escapes so this file stays stable across
Windows console/codepage settings.
"""

import re


class QueryLexicon:
    """Small bilingual lexicon for routing English/Myanmar POS questions."""

    MYANMAR_PATTERN = re.compile(r"[\u1000-\u109F]")

    TERMS = {
        "help": [
            "help", "guide", "commands", "what can i ask", "questions",
            "\u1021\u1000\u1030\u1021\u100a\u102e", "\u101c\u1019\u103a\u1038\u100a\u103d\u103e\u1014\u103a",
            "\u1018\u102c\u1010\u103d\u1031\u1019\u1031\u1038", "\u1019\u1031\u1038\u101c\u102d\u102f\u1037\u101b",
            "\u1018\u102c\u1019\u1031\u1038",
        ],
        "project": [
            "project", "app", "system", "pages", "modules", "features",
            "\u1015\u101b\u1031\u102c\u1002\u103b\u1000\u103a", "\u1021\u1000\u103a\u1015\u103a",
            "\u1005\u1014\u1005\u103a", "\u1005\u102c\u1019\u103b\u1000\u103a\u1014\u103e\u102c",
            "\u1015\u1031\u1038\u1002\u103b\u103a", "\u1021\u1000\u103c\u1031\u102c\u1004\u103a\u1038\u1021\u101b\u102c",
        ],
        "summary": [
            "summary", "overview", "report", "total", "totals", "all",
            "\u1021\u1000\u103b\u1009\u103a\u1038\u1001\u103b\u102f\u1015\u103a", "\u1005\u102c\u101b\u1004\u103a\u1038\u1001\u103b\u102f\u1015\u103a",
            "\u1005\u102f\u1005\u102f\u1015\u1031\u102b\u1004\u103a\u1038", "\u1021\u102c\u1038\u101c\u102f\u1036\u1038",
        ],
        "list": [
            "list", "recent", "latest", "last", "show", "find", "search", "check",
            "\u1005\u102c\u101b\u1004\u103a\u1038", "\u1014\u1031\u102c\u1000\u103a\u1006\u102f\u1036\u1038",
            "\u101b\u103e\u102c", "\u101b\u103e\u102c\u1016\u103d\u1031", "\u1005\u1005\u103a", "\u1000\u103c\u100a\u1037\u103a",
        ],
        "top": [
            "top", "best", "highest", "popular",
            "\u1011\u102d\u1015\u103a\u1006\u102f\u1036\u1038", "\u1021\u1000\u1031\u102c\u1004\u103a\u1038\u1006\u102f\u1036\u1038",
        ],
        "sales": [
            "sales", "sale", "revenue", "orders", "order",
            "\u101b\u1031\u102c\u1004\u103a\u1038\u1021\u102c\u1038", "\u1021\u101b\u1031\u102c\u1004\u103a\u1038",
            "\u101b\u1031\u102c\u1004\u103a\u1038\u101b\u1004\u103d\u1031",
        ],
        "sales_summary": [
            "sales summary", "sale summary", "summary sales", "sales by",
            "sales report", "sales overview",
            "\u101b\u1031\u102c\u1004\u103a\u1038\u1021\u102c\u1038\u1005\u102f\u1005\u100a\u103a\u1038",
            "\u101b\u1031\u102c\u1004\u103a\u1038\u1021\u102c\u1038\u1021\u1000\u103b\u1009\u103a\u1038\u1001\u103b\u102f\u1015\u103a",
            "\u1021\u101b\u1031\u102c\u1004\u103a\u1038\u1005\u102c\u101b\u1004\u103a\u1038\u1001\u103b\u102f\u1015\u103a",
        ],
        "product": [
            "product", "products", "item", "items", "sku", "barcode",
            "\u1015\u1005\u1039\u1005\u100a\u103a\u1038", "\u1000\u102f\u1014\u103a\u1015\u1005\u1039\u1005\u100a\u103a\u1038",
            "\u1018\u102c\u1000\u102f\u1010\u103a",
        ],
        "stock": [
            "stock", "inventory", "qty", "quantity", "on hand",
            "\u1005\u1010\u1031\u102c\u1037", "\u101c\u1000\u103a\u1000\u103b\u1014\u103a",
            "\u1021\u101b\u1031\u1021\u1010\u103d\u1000\u103a", "\u1000\u102f\u1014\u103a\u101c\u1000\u103a\u1000\u103b\u1014\u103a",
        ],
        "low": [
            "low", "alert", "out of stock", "reorder",
            "\u1014\u100a\u103a\u1038", "\u1000\u102f\u1014\u103a", "\u101e\u1010\u102d\u1015\u1031\u1038",
        ],
        "customer": [
            "customer", "customers", "buyer", "client",
            "\u101d\u101a\u103a\u101e\u1030", "\u101d\u101a\u103a\u101a\u1030\u101e\u1030",
            "\u1016\u1031\u102c\u1000\u103a\u101e\u100a\u103a",
        ],
        "debt": [
            "debt", "debts", "credit", "balance", "outstanding",
            "\u1021\u1000\u103c\u103d\u1031\u1038", "\u1001\u103b\u1031\u1038\u1004\u103d\u1031",
            "\u101c\u1000\u103a\u1000\u103b\u1014\u103a", "\u1000\u103b\u1014\u103a\u1004\u103d\u1031",
        ],
        "overdue": [
            "overdue", "late", "past due",
            "\u1000\u103c\u102c\u1019\u103c\u1004\u1037\u103a", "\u1014\u1031\u102c\u1000\u103a\u1000\u103b",
            "\u101e\u1010\u103a\u1019\u103e\u1010\u103a\u101b\u1000\u103a\u1000\u103b\u1031\u102c\u103a",
        ],
        "expense": [
            "expense", "expenses", "cost", "costs", "spending", "spent",
            "\u1021\u101e\u102f\u1036\u1038\u1005\u101b\u102d\u1010\u103a", "\u1000\u102f\u1014\u103a\u1000\u103b",
            "\u1021\u101e\u102f\u1036\u1038", "\u101e\u102f\u1036\u1038\u1005\u103d\u1032", "\u1005\u101b\u102d\u1010\u103a",
        ],
        "category": [
            "category", "categories", "group", "parent category",
            "\u1021\u1019\u103b\u102d\u102f\u1038\u1021\u1005\u102c\u1038", "\u1000\u100f\u1039\u100d",
            "\u1021\u102f\u1015\u103a\u1005\u102f", "\u1021\u1019\u103b\u102d\u102f\u1038\u1005\u102c\u1038",
        ],
        "profit": [
            "profit", "margin", "gross profit", "net profit",
            "\u1021\u1019\u103c\u1010\u103a", "\u1021\u101e\u102c\u1038\u1010\u1004\u103a\u1021\u1019\u103c\u1010\u103a",
        ],
        "receipt": [
            "receipt", "receipts", "invoice", "invoices", "voucher", "vouchers",
            "\u1015\u103c\u1031\u1005\u102c", "\u1018\u1031\u102c\u1004\u103a\u1001\u103b\u102c",
            "\u1018\u1031\u102c\u1004\u103a\u1001\u103b\u102c\u101b\u1005\u103a",
        ],
        "refund": [
            "refund", "refunded", "return", "returned",
            "\u1015\u103c\u1014\u103a\u1021\u1019\u103a\u1038", "\u1015\u103c\u1014\u103a\u101e\u103d\u1004\u103a\u1038",
        ],
        "discount": [
            "discount", "discounted",
            "\u101c\u103b\u103e\u1031\u102c\u1037", "\u101c\u103b\u103e\u1031\u102c\u1037\u1005\u103b\u1031\u1038",
        ],
        "payment": [
            "payment", "payments", "payment type", "cash", "card", "kpay", "wave",
            "\u1004\u103d\u1031\u1015\u1031\u1038", "\u1015\u1031\u1038\u1001\u103b\u1031", "\u1004\u103d\u1031\u101e\u102c\u1038",
        ],
        "this_month": [
            "this month", "monthly",
            "\u1012\u102e\u101c", "\u101c\u1005\u1009\u103a", "\u1012\u102e\u101c\u1021\u1010\u103d\u1000\u103a",
        ],
        "last_month": [
            "last month", "previous month",
            "\u1015\u103c\u102e\u1038\u1001\u1032\u1037\u1010\u1032\u1037\u101c", "\u101c\u1000\u102f\u1014\u103a",
        ],
        "this_week": [
            "this week", "weekly",
            "\u1012\u102e\u1010\u1005\u103a\u1015\u1010\u103a", "\u1021\u1015\u1010\u103a\u1005\u1009\u103a",
        ],
        "this_year": [
            "this year", "yearly",
            "\u1012\u102e\u1014\u103e\u1005\u103a", "\u1014\u103e\u1005\u103a\u1005\u1009\u103a",
        ],
        "today": [
            "today", "today's",
            "\u101a\u1014\u1031\u1037", "\u1012\u102e\u1014\u1031\u1037",
        ],
        "yesterday": [
            "yesterday", "yesterday's",
            "\u1019\u1014\u1031\u1037\u1000",
        ],
        "day_before_yesterday": [
            "day before yesterday",
            "\u1019\u1014\u1031\u1037\u1010\u1005\u103a\u1014\u1031\u1037\u1000", "\u1010\u1005\u103a\u1014\u1031\u1037\u1000",
        ],
    }

    @classmethod
    def words(cls, *keys):
        values = []
        for key in keys:
            values.extend(cls.TERMS.get(key, []))
        return values

    @classmethod
    def has_any(cls, text, *keys):
        haystack = (text or "").lower()
        return any(word.lower() in haystack for word in cls.words(*keys))

    @classmethod
    def remove_terms(cls, text, *keys, extra=None):
        cleaned = text or ""
        terms = cls.words(*keys)
        if extra:
            terms.extend(extra)
        for word in sorted(set(terms), key=len, reverse=True):
            cleaned = re.sub(rf"\b{re.escape(word)}\b", " ", cleaned, flags=re.IGNORECASE)
            cleaned = cleaned.replace(word, " ")
        return " ".join(cleaned.split())

    @classmethod
    def is_myanmar(cls, text):
        return bool(cls.MYANMAR_PATTERN.search(text or ""))
