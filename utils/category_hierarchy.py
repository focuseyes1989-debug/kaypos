"""Shared helpers for filtering products through the category hierarchy."""

from collections.abc import Iterable
from typing import Any


def expand_category_scope(category: str, rows: Iterable[Any]) -> tuple[list[str], list[int]]:
    """Return a selected category and all of its child/sub-child categories."""
    selected = str(category or "").strip()
    records = [
        (int(row[0]), str(row[1] or "").strip(), int(row[2]) if row[2] is not None else None)
        for row in rows if row and row[0] is not None and str(row[1] or "").strip()
    ]
    selected_ids = {
        record_id for record_id, name, _parent_id in records
        if name.casefold() == selected.casefold()
    }
    descendant_ids = set(selected_ids)
    changed = True
    while changed:
        changed = False
        for record_id, _name, parent_id in records:
            if parent_id in descendant_ids and record_id not in descendant_ids:
                descendant_ids.add(record_id)
                changed = True
    names = {selected}
    names.update(name for record_id, name, _parent_id in records if record_id in descendant_ids)
    return sorted(names, key=str.casefold), sorted(descendant_ids)


def product_category_filter(cursor, category: str, table_alias: str = "") -> tuple[str, list[Any]]:
    """Build a parameterized product filter covering category names and IDs."""
    cursor.execute("SELECT id, name, parent_id FROM categories")
    names, category_ids = expand_category_scope(category, cursor.fetchall())
    prefix = f"{table_alias}." if table_alias else ""
    name_placeholders = ", ".join("?" for _ in names)
    clauses = [f"LOWER(TRIM(COALESCE({prefix}category, ''))) IN ({name_placeholders})"]
    params: list[Any] = [name.casefold() for name in names]
    if category_ids:
        id_placeholders = ", ".join("?" for _ in category_ids)
        clauses.append(f"{prefix}category_id IN ({id_placeholders})")
        params.extend(category_ids)
    return f"({' OR '.join(clauses)})", params
