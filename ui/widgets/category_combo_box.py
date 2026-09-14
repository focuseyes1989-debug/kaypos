from __future__ import annotations

from collections import defaultdict

from models.database import connect_db
from ui.themes.theme_manager import get_icon_with_color, get_theme_colors
from ui.widgets.combo_box_widget import ComboBoxWidget


class CategoryComboBox(ComboBoxWidget):
    """Searchable, theme-aware product category combo with shared hierarchy UI."""

    def __init__(
        self,
        placeholder: str = "All Categories",
        parent=None,
        *,
        include_all: bool = False,
        all_label: str = "All Categories",
        include_none: bool = False,
        none_label: str = "None (Root Category)",
        root_only: bool = False,
        exclude_id: int | None = None,
    ):
        super().__init__(placeholder, parent=parent, searchable=True)
        self.include_all = include_all
        self.all_label = all_label
        self.include_none = include_none
        self.none_label = none_label
        self.root_only = root_only
        self.exclude_id = exclude_id
        self.setMinimumHeight(34)

    def set_all_label(self, label: str) -> None:
        self.all_label = label
        if self.include_all and self.count() > 0:
            self.setItemText(0, label)

    def set_none_label(self, label: str) -> None:
        self.none_label = label
        offset = 1 if self.include_all else 0
        if self.include_none and self.count() > offset:
            self.setItemText(offset, label)

    def load_categories(self) -> None:
        current_data = self.currentData()
        current_text = self.currentText()

        rows = self._fetch_categories()
        self.blockSignals(True)
        self.clear()
        if self.include_all:
            self.addItem(self.all_label, None)
        if self.include_none:
            self.addItem(self.none_label, -1 if self.include_all else None)

        self._add_category_rows(rows)
        idx = self.findData(current_data) if current_data is not None else -1
        if idx < 0:
            idx = self.findText(current_text)
        self.setCurrentIndex(idx if idx >= 0 else 0)
        self.blockSignals(False)

    def _fetch_categories(self) -> list[dict]:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, parent_id, COALESCE(sort_order, 0)
            FROM categories
            ORDER BY COALESCE(sort_order, 0), name
            """
        )
        rows = [
            {"id": row[0], "name": row[1], "parent_id": row[2], "sort_order": row[3]}
            for row in cursor.fetchall()
        ]
        conn.close()
        return rows

    def _add_category_rows(self, rows: list[dict]) -> None:
        children_by_parent = defaultdict(list)
        by_id = {}
        excluded = {self.exclude_id} if self.exclude_id else set()

        for row in rows:
            if row["id"] in excluded:
                continue
            by_id[row["id"]] = row
            children_by_parent[row["parent_id"]].append(row)

        def sort_key(row):
            return (row.get("sort_order", 0), row.get("name") or "")

        def add_row(row, level: int = 0):
            if self.root_only and level > 0:
                return
            icon_name = "folder" if level == 0 else "category"
            text = f"{'  ' * level}{row['name']}"
            self.addItem(self._combo_icon(icon_name), text, row["id"])
            for child in sorted(children_by_parent.get(row["id"], []), key=sort_key):
                add_row(child, level + 1)

        for root in sorted(children_by_parent.get(None, []), key=sort_key):
            add_row(root)

        orphaned = [row for row in rows if row["parent_id"] and row["parent_id"] not in by_id and row["id"] not in excluded]
        for row in sorted(orphaned, key=sort_key):
            add_row(row)

    def _combo_icon(self, icon_name: str):
        colors = get_theme_colors()
        return get_icon_with_color(icon_name, colors.get("icon_color", colors.get("text_secondary", "#667085")), (16, 16))
