# ui/categories/category_list_table.py
"""
Category List Table - Table population and operations
"""

from PyQt6.QtWidgets import QTableWidgetItem, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

from loguru import logger
from typing import List, Optional, Dict


class CategoryListTable:
    """Table operations for Category List Dialog"""

    def populate_table(self, categories):
        """Populate table with category data"""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        category_map = {cat.get('id'): cat for cat in categories}

        if not categories:
            self.status_label.setText("📭 No categories found")
            self.table.setSortingEnabled(True)
            return

        for row_idx, cat in enumerate(categories):
            self.table.insertRow(row_idx)
            self.table.setRowHeight(row_idx, 44)

            # ✅ Column 0: ID (hidden) - Store actual ID in UserRole AND text
            id_item = QTableWidgetItem()
            id_item.setData(Qt.ItemDataRole.UserRole, cat['id'])
            id_item.setText(str(cat['id']))
            self.table.setItem(row_idx, 0, id_item)
            
            # Column 1: Name (with hierarchy hint)
            name_text = cat['name']
            if cat.get('is_system'):
                name_text = f"⭐ {cat['name']}"
            
            depth = self._category_depth(cat, category_map)
            prefix = ("   " * depth + "↳ ") if depth else ""
            name_item = QTableWidgetItem(f"{prefix}{cat.get('icon', '📁')} {name_text}")
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            name_item.setToolTip(self._category_tooltip(cat))
            
            if cat.get('is_system'):
                name_item.setForeground(QColor('#5865f2'))
                name_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            else:
                name_item.setFont(QFont("Segoe UI", 10))
            
            self.table.setItem(row_idx, 1, name_item)
            
            # Column 2: Parent
            parent_text = cat.get('parent_name') or '—'
            parent_item = QTableWidgetItem(parent_text)
            parent_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            parent_item.setToolTip("Root category" if not cat.get('parent_name') else f"Parent: {cat.get('parent_name')}")
            parent_item.setForeground(QColor('#94a3b8'))
            self.table.setItem(row_idx, 2, parent_item)
            
            # Column 3: Products
            product_count = cat.get('product_count', 0)
            product_item = QTableWidgetItem(str(product_count))
            product_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            product_item.setToolTip(f"{product_count} product{'s' if product_count != 1 else ''}")
            
            if product_count > 0:
                product_item.setForeground(QColor('#3b82f6'))
                product_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            else:
                product_item.setForeground(QColor('#cbd5e1'))
            
            self.table.setItem(row_idx, 3, product_item)
            
            # Column 4: Status
            status = cat.get('status', 'active')
            status_display = {
                'active': '🟢 Active',
                'inactive': '🔴 Inactive',
                'hidden': '⚪ Hidden'
            }.get(status, status.capitalize())
            
            status_item = QTableWidgetItem(status_display)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setToolTip(f"Status: {status.capitalize()}")
            
            status_colors = {
                'active': QColor('#16a34a'),
                'inactive': QColor('#dc2626'),
                'hidden': QColor('#94a3b8')
            }
            status_item.setForeground(status_colors.get(status, QColor('#16a34a')))
            status_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
            self.table.setItem(row_idx, 4, status_item)

        self.table.setSortingEnabled(True)
        self._update_status_label(len(categories))

    def _update_status_label(self, count):
        """Update status label"""
        total_count = self.pagination.total_items if hasattr(self.pagination, 'total_items') else count
        start = (self.current_page - 1) * self.page_size + 1

        if total_count > 0:
            end = min(start + count - 1, total_count)
            self.status_label.setText(f"Showing {start}–{end} of {total_count} categories")
        else:
            self.status_label.setText("No categories found")

    def get_selected_ids(self) -> List[int]:
        """Get selected category IDs."""
        selected = []
        selected_indexes = self.table.selectedIndexes()
        if not selected_indexes:
            return selected
        
        selected_rows = set()
        for index in selected_indexes:
            selected_rows.add(index.row())
        
        for row in selected_rows:
            id_item = self.table.item(row, 0)
            if id_item:
                cat_id = id_item.data(Qt.ItemDataRole.UserRole)
                if cat_id is not None:
                    try:
                        cat_id = int(cat_id)
                        if cat_id not in selected:
                            selected.append(cat_id)
                        continue
                    except (ValueError, TypeError):
                        pass
                
                # Fallback: try to parse text
                try:
                    text = id_item.text()
                    if text:
                        cat_id = int(text)
                        if cat_id not in selected:
                            selected.append(cat_id)
                except (ValueError, TypeError):
                    pass
        
        return selected

    def _category_depth(self, category: Dict, category_map: Dict) -> int:
        """Return the visible parent depth for indentation."""
        depth = 0
        parent_id = category.get('parent_id')
        seen = set()
        while parent_id and parent_id in category_map and parent_id not in seen:
            seen.add(parent_id)
            depth += 1
            parent_id = category_map[parent_id].get('parent_id')
        return min(depth, 4)

    def _category_tooltip(self, category: Dict) -> str:
        parent = category.get('parent_name') or 'Root'
        products = category.get('product_count', 0)
        status = category.get('status', 'active').capitalize()
        return f"{category.get('name', '')}\nParent: {parent}\nProducts: {products}\nStatus: {status}"

    def get_category_from_row(self, row: int) -> Optional[Dict]:
        """Get category data from a row"""
        id_item = self.table.item(row, 0)
        if id_item:
            try:
                cat_id = id_item.data(Qt.ItemDataRole.UserRole)
                if cat_id is None:
                    cat_id = int(id_item.text())
                
                for cat in self.categories:
                    if cat['id'] == int(cat_id):
                        return cat
            except (ValueError, TypeError):
                pass
        return None
