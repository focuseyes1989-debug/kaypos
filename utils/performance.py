from __future__ import annotations

from dataclasses import dataclass

from models.database import connect_db


@dataclass(frozen=True)
class PerformanceSettings:
    low_end_mode: bool = True
    product_page_size: int = 12
    search_debounce_ms: int = 600
    thumbnail_quality: str = "off"
    customer_display_youtube_enabled: bool = False


_CACHE: PerformanceSettings | None = None


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(str(value).strip())
    except Exception:
        number = default
    return max(minimum, min(maximum, number))


def get_performance_settings(refresh: bool = False) -> PerformanceSettings:
    global _CACHE
    if _CACHE is not None and not refresh:
        return _CACHE

    values: dict[str, str] = {}
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT key, value
            FROM settings
            WHERE key IN (
                'performance_low_end_mode',
                'performance_product_page_size',
                'performance_search_debounce_ms',
                'performance_thumbnail_quality',
                'performance_customer_display_youtube_enabled'
            )
        """)
        values = dict(cursor.fetchall())
        conn.close()
    except Exception:
        values = {}

    low_end = _bool(values.get("performance_low_end_mode"), True)
    default_page_size = 12 if low_end else 25
    default_debounce = 600 if low_end else 300
    default_quality = "off" if low_end else "normal"
    configured_page_size = _int(values.get("performance_product_page_size"), default_page_size, 12, 100)

    _CACHE = PerformanceSettings(
        low_end_mode=low_end,
        product_page_size=min(configured_page_size, 12) if low_end else configured_page_size,
        search_debounce_ms=max(
            600,
            _int(values.get("performance_search_debounce_ms"), default_debounce, 150, 1200),
        ) if low_end else _int(values.get("performance_search_debounce_ms"), default_debounce, 150, 1200),
        thumbnail_quality="off" if low_end else (
            values.get("performance_thumbnail_quality") or default_quality
        ).strip().lower(),
        customer_display_youtube_enabled=_bool(values.get("performance_customer_display_youtube_enabled"), False),
    )
    return _CACHE


def refresh_performance_settings() -> PerformanceSettings:
    return get_performance_settings(refresh=True)
