# ui/products_page/manage_category_groups_dialog.py
from PyQt6.QtWidgets import QDialog, QMessageBox
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QIcon
from ui.products_page.manage_category_groups_ui import CategoryGroupsUI
from ui.products_page.manage_category_groups_handlers import CategoryGroupsHandlers
from ui.themes.theme_manager import register_theme_callback, theme_manager, get_theme_colors, is_dark_theme
from utils.language import lang


class ManageCategoryGroupsDialog(QDialog):
    groups_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Category Groups")
        self.setModal(True)
        self.resize(700, 620)
        self.setMinimumWidth(650)
        self.setMinimumHeight(500)
        
        # Set window icon
        try:
            self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        except:
            pass
        
        # Setup UI
        self.ui = CategoryGroupsUI()
        self.ui.setup_ui(self)
        
        # Setup handlers
        self.handlers = CategoryGroupsHandlers(self)
        self.handlers.setup_signals()
        
        # Load data
        self.handlers.load_groups()
        
        # Apply theme
        self.handlers.apply_theme()
        
        # Register for theme changes
        register_theme_callback(self.handlers.on_theme_changed)
        
        # ✅ Connect theme manager for auto refresh
        theme_manager.theme_changed.connect(self._on_theme_changed)
        
        # Language support
        lang.language_changed.connect(self.retranslateUi)
        self.retranslateUi()
    
    def _on_theme_changed(self, theme_name):
        """✅ Handle theme change - update UI"""
        self.handlers.apply_theme()
        self.handlers.filter_groups()
    
    def retranslateUi(self):
        """Retranslate UI elements"""
        self.ui.retranslate_ui()
    
    def showEvent(self, event):
        """Handle show event"""
        super().showEvent(event)
        QTimer.singleShot(100, lambda: self.search_input.setFocus())
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() == Qt.Key.Key_Delete and self.table_widget.hasFocus():
            self.handlers.delete_group()
        elif event.key() == Qt.Key.Key_F and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.search_input.setFocus()
            self.search_input.selectAll()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.table_widget.hasFocus():
            if self.table_widget.currentRow() >= 0:
                self.handlers.edit_group()
        else:
            super().keyPressEvent(event)
    
    def closeEvent(self, event):
        """Handle close event"""
        try:
            theme_manager.theme_changed.disconnect(self._on_theme_changed)
        except:
            pass
        event.accept()