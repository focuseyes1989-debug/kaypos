from __future__ import annotations

from dataclasses import dataclass

from models.database import connect_db


@dataclass(frozen=True)
class PerformanceSettings:
    lite_mode_enabled: bool = False
    product_page_size: int = 36
    search_debounce_ms: int = 350
    thumbnail_quality: str = "low"
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
                'performance_product_page_size',
                'performance_search_debounce_ms',
                'performance_thumbnail_quality',
                'performance_customer_display_youtube_enabled',
                'performance_lite_mode_enabled'
            )
        """)
        values = dict(cursor.fetchall())
        conn.close()
    except Exception:
        values = {}

    default_page_size = 36
    default_debounce = 350
    default_quality = "low"
    lite_mode_enabled = _bool(values.get("performance_lite_mode_enabled"), False)
    if lite_mode_enabled:
        configured_page_size = _int(values.get("performance_product_page_size"), 18, 12, 36)
        configured_debounce = 450
        configured_quality = "off"
    else:
        configured_page_size = _int(values.get("performance_product_page_size"), default_page_size, 12, 72)
        configured_debounce = _int(values.get("performance_search_debounce_ms"), default_debounce, 150, 1200)
        configured_quality = (values.get("performance_thumbnail_quality") or default_quality).strip().lower()

    _CACHE = PerformanceSettings(
        lite_mode_enabled=lite_mode_enabled,
        product_page_size=configured_page_size,
        search_debounce_ms=configured_debounce,
        thumbnail_quality=configured_quality,
        customer_display_youtube_enabled=_bool(values.get("performance_customer_display_youtube_enabled"), False),
    )
    return _CACHE


def refresh_performance_settings() -> PerformanceSettings:
    return get_performance_settings(refresh=True)
