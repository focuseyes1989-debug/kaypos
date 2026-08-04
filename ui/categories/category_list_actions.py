# ui/categories/category_list_actions.py
"""
Category List Actions - Action handlers for categories
"""

from PyQt6.QtWidgets import QMessageBox, QFileDialog
from PyQt6.QtCore import Qt

from ui.categories.category_form_dialog import CategoryFormDialog
from ui.categories.category_merge_dialog import CategoryMergeDialog
from loguru import logger
from datetime import datetime


class CategoryListActions:
    """Action handlers for Category List Dialog"""
    
    def add_category(self):
        """Add a new category"""
        dialog = CategoryFormDialog(parent=self)
        if dialog.exec():
            self.load_categories()
            self.update_statistics()
            self.categories_changed.emit()
            logger.info("Category added")
    
    def edit_category(self, category_id: int = None):
        """
        Edit a category - ✅ FIXED
        """
        # ✅ signal ကနေပေးပို့လိုက်တဲ့ boolean (True/False) ဖြစ်နေရင် None ပြောင်းပေးပါ
        if isinstance(category_id, bool):
            category_id = None
        
        print("=" * 60)
        print("EDIT CATEGORY CALLED")
        print(f"category_id parameter: {category_id} (type: {type(category_id)})")
        
        # If category_id is not provided, get selected from table
        if category_id is None:
            selected = self.get_selected_ids()
            print(f"[DEBUG] Selected IDs: {selected}")
            if not selected:
                QMessageBox.warning(
                    self, 
                    "No Selection", 
                    "Please select a category to edit."
                )
                return
            category_id = selected[0]
        
        # Ensure category_id is int
        try:
            category_id = int(category_id)
        except (ValueError, TypeError):
            print(f"[ERROR] Invalid category_id: {category_id}")
            QMessageBox.warning(self, "Error", "Invalid category selected.")
            return
        
        print(f"[DEBUG] Final category_id: {category_id} (type: {type(category_id)})")
        print("=" * 60)
        
        # Verify category exists
        category = self.service.get_category(category_id)
        if not category:
            QMessageBox.warning(self, "Not Found", f"Category with ID {category_id} not found.")
            return
        
        # Open edit dialog with the selected category ID
        dialog = CategoryFormDialog(category_id, self)
        if dialog.exec():
            self.load_categories()
            self.update_statistics()
            self.categories_changed.emit()
            logger.info(f"Category {category_id} edited")
    
    def delete_category(self, category_id: int = None):
        """Delete a category - ✅ FIXED"""
        # ✅ signal ကနေပေးပို့လိုက်တဲ့ boolean (True/False) ဖြစ်နေရင် None ပြောင်းပေးပါ
        if isinstance(category_id, bool):
            category_id = None
        
        print("=" * 60)
        print("DELETE CATEGORY CALLED")
        print(f"category_id parameter: {category_id} (type: {type(category_id)})")
        
        if category_id is None:
            selected = self.get_selected_ids()
            print(f"[DEBUG] Selected IDs: {selected}")
            if not selected:
                QMessageBox.warning(
                    self, 
                    "No Selection", 
                    "Please select a category to delete."
                )
                return
            category_id = selected[0]
        
        # Ensure category_id is int
        try:
            category_id = int(category_id)
        except (ValueError, TypeError):
            print(f"[ERROR] Invalid category_id: {category_id}")
            QMessageBox.warning(self, "Error", "Invalid category selected.")
            return
        
        print(f"[DEBUG] Final category_id: {category_id} (type: {type(category_id)})")
        print("=" * 60)
        
        category = self.service.get_category(category_id)
        if not category:
            QMessageBox.warning(self, "Not Found", f"Category with ID {category_id} not found.")
            return
        
        if category['is_system']:
            QMessageBox.warning(
                self, 
                "Cannot Delete", 
                "This is a system category and cannot be deleted."
            )
            return
        
        # Check if has products
        if category['product_count'] > 0:
            reply = QMessageBox.question(
                self,
                "Category Has Products",
                f"Category '{category['name']}' has {category['product_count']} products.\n\n"
                "Delete anyway? Products will be unassigned.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
            force = True
        else:
            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Delete category '{category['name']}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
            force = False
        
        try:
            self.service.delete_category(category_id, force)
            self.load_categories()
            self.update_statistics()
            self.categories_changed.emit()
            logger.info(f"Category {category_id} deleted")
            QMessageBox.information(self, "Deleted", "Category deleted successfully.")
        except Exception as e:
            logger.error(f"Failed to delete category: {e}")
            QMessageBox.critical(self, "Error", str(e))
    
    def merge_categories(self):
        """Merge categories"""
        dialog = CategoryMergeDialog(self)
        if dialog.exec():
            self.load_categories()
            self.update_statistics()
            self.categories_changed.emit()
            logger.info("Categories merged")
    
    def export_categories(self):
        """Export categories"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Categories",
            f"categories_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json);;CSV Files (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            format = 'json' if file_path.endswith('.json') else 'csv'
            data = self.service.export_categories(format)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(data)
            
            QMessageBox.information(
                self, 
                "Export Complete", 
                f"Exported to {file_path}"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))
    
    def import_categories(self):
        """Import categories"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Categories",
            "",
            "JSON Files (*.json);;CSV Files (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = f.read()
            
            format = 'json' if file_path.endswith('.json') else 'csv'
            result = self.service.import_categories(data, format)
            
            msg = f"Imported: {result['imported']}\nUpdated: {result['updated']}\nFailed: {len(result['failed'])}"
            
            if result['failed']:
                error_details = "\n".join([f"- {f['name']}: {f['error']}" for f in result['failed'][:5]])
                if len(result['failed']) > 5:
                    error_details += f"\n... and {len(result['failed']) - 5} more errors."
                msg += f"\n\nErrors:\n{error_details}"
            
            QMessageBox.information(self, "Import Complete", msg)
            
            self.load_categories()
            self.update_statistics()
            self.categories_changed.emit()
            
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", str(e))