# ui/sales_page/category_slider.py
from PyQt6.QtWidgets import (
    QWidget, QScrollArea, QHBoxLayout, QPushButton, QSizePolicy, QFrame,
    QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QEvent
from PyQt6.QtGui import QWheelEvent
from ui.themes.theme_manager import get_theme_colors, get_current_theme, is_dark_theme
from ui.widgets.modern_button import ModernButton
from loguru import logger


class CategorySlider(QScrollArea):
    """Horizontal scrollable category buttons with compact flat design."""
    
    category_selected = pyqtSignal(str)
    group_selected = pyqtSignal(str)
    SLIDER_HEIGHT = 42
    BUTTON_HEIGHT = 30
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        
        # ✅ Compact height - same as combobox (32px)
        self.setFixedHeight(self.SLIDER_HEIGHT)
        
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        viewport = self.viewport()
        if viewport is not None:
            viewport.installEventFilter(self)
        
        self._container = QWidget()
        self._container.setStyleSheet("background-color: transparent;")
        
        # ✅ Left-aligned layout
        self._layout = QHBoxLayout(self._container)
        self._layout.setSpacing(4)
        self._layout.setContentsMargins(4, 5, 8, 5)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        self.setWidget(self._container)
        
        self._buttons = []
        self._group_buttons = []
        self._all_btn = None
        self._top_category_names = set()
        self._selected_category = ""
        self._selected_group = ""
        
        # Smooth scroll
        self._scroll_timer = QTimer()
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(self._smooth_scroll)
        self._scroll_target = 0
        self._scroll_step = 0
        self._scroll_multiplier = 3
        
        self.apply_compact_style()

    def _configure_category_button(self, button):
        """Apply category-slider specific metrics after ModernButton compact setup."""
        button.setFixedHeight(self.BUTTON_HEIGHT)
        button.setMinimumWidth(64)
        button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    
    def apply_compact_style(self):
        """Apply compact style for category buttons"""
        is_dark = is_dark_theme()
        colors = get_theme_colors()
        
        if is_dark:
            self.setStyleSheet("""
                QScrollArea {
                    background: transparent;
                    border: none;
                }
                QScrollArea > QWidget > QWidget {
                    background: transparent;
                }
                QScrollBar:horizontal {
                    background: #2f3136;
                    height: 2px;
                    border-radius: 1px;
                }
                QScrollBar::handle:horizontal {
                    background: #5865f2;
                    border-radius: 1px;
                    min-width: 30px;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    border: none;
                    background: none;
                }
            """)
        else:
            self.setStyleSheet("""
                QScrollArea {
                    background: transparent;
                    border: none;
                }
                QScrollArea > QWidget > QWidget {
                    background: transparent;
                }
                QScrollBar:horizontal {
                    background: #f1f3f5;
                    height: 2px;
                    border-radius: 1px;
                }
                QScrollBar::handle:horizontal {
                    background: #5865f2;
                    border-radius: 1px;
                    min-width: 30px;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    border: none;
                    background: none;
                }
            """)
    
    def _get_button_style(self, is_checked=False, is_group=False, is_all=False, is_top=False):
        """
        Get compact button style based on type and state.
        """
        is_dark = is_dark_theme()
        colors = get_theme_colors()
        
        # ✅ Discord Secondary Button Colors
        if is_dark:
            bg_color = "transparent"
            bg_hover = "rgba(255, 255, 255, 0.06)"
            bg_active = "rgba(255, 255, 255, 0.08)"
            bg_checked = "rgba(88, 101, 242, 0.15)"
            text_color = "#b9bbbe"
            text_hover = "#dcddde"
            text_checked = "#ffffff"
            border_color = "transparent"
            border_hover = "rgba(255, 255, 255, 0.1)"
            border_checked = "#5865f2"
        else:
            bg_color = "transparent"
            bg_hover = "rgba(0, 0, 0, 0.04)"
            bg_active = "rgba(0, 0, 0, 0.06)"
            bg_checked = "rgba(88, 101, 242, 0.08)"
            text_color = "#4f5660"
            text_hover = "#2e3338"
            text_checked = "#5865f2"
            border_color = "transparent"
            border_hover = "rgba(0, 0, 0, 0.08)"
            border_checked = "#5865f2"
        
        # Group specific colors
        if is_group:
            if is_dark:
                text_checked = "#a89bff"
                border_checked = "#a89bff"
                bg_checked = "rgba(148, 132, 255, 0.15)"
            else:
                text_checked = "#6c5ce7"
                border_checked = "#6c5ce7"
                bg_checked = "rgba(108, 92, 231, 0.08)"
        
        # All button specific
        if is_all:
            if is_dark:
                text_checked = "#5865f2"
                border_checked = "#5865f2"
                bg_checked = "rgba(88, 101, 242, 0.15)"
            else:
                text_checked = "#5865f2"
                border_checked = "#5865f2"
                bg_checked = "rgba(88, 101, 242, 0.08)"
        
        # ✅ Top Selling - Gold/Star color
        if is_top:
            if is_dark:
                text_checked = "#f1c40f"
                border_checked = "#f1c40f"
                bg_checked = "rgba(241, 196, 15, 0.15)"
            else:
                text_checked = "#f39c12"
                border_checked = "#f39c12"
                bg_checked = "rgba(243, 156, 18, 0.10)"
        
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: none;
                border-bottom: 2px solid {border_color};
                padding: 2px 12px;
                font-size: 12px;
                font-weight: 500;
                min-height: 20px;
                max-height: 28px;
                border-radius: 4px;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }}
            QPushButton:hover {{
                background-color: {bg_hover};
                color: {text_hover};
                border-bottom: 2px solid {border_hover};
            }}
            QPushButton:pressed {{
                background-color: {bg_active};
            }}
            QPushButton:checked {{
                color: {text_checked};
                border-bottom: 2px solid {border_checked};
                font-weight: 600;
                background-color: {bg_checked};
            }}
        """
    
    def load_categories(self, categories, groups=None, top_categories=None):
        """
        Load categories and groups.
        
        Args:
            categories: List of (category_name, group_id, group_name, is_favorite) tuples
            groups: List of (group_id, group_name, description, is_favorite) tuples
            top_categories: List of category names that are top selling (optional)
        """
        self._categories = categories
        self._groups = groups
        self._top_categories = top_categories or []
        self._top_category_names = set(self._top_categories)
        
        # Clear existing buttons
        for btn in self._buttons:
            self._layout.removeWidget(btn)
            btn.deleteLater()
        self._buttons.clear()
        self._group_buttons.clear()
        
        # ✅ "All" button - using ModernButton with PRIMARY style
        self._all_btn = ModernButton("All", ModernButton.SECONDARY)
        self._all_btn.setCheckable(True)
        self._all_btn.setChecked(True)
        self._all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._all_btn.set_compact(True)
        self._configure_category_button(self._all_btn)
        self._all_btn.clicked.connect(lambda: self._on_category_clicked(""))
        self._layout.addWidget(self._all_btn)
        self._buttons.append(self._all_btn)
        
        # Get favorite categories only
        favorite_categories = [c for c in categories if c[3] == 1]
        favorite_group_ids = set()
        
        for cat in favorite_categories:
            if cat[1] is not None:
                favorite_group_ids.add(cat[1])
        
        # ✅ Sort categories: Top selling first, then favorites
        def sort_key(cat):
            cat_name = cat[0]
            is_top = cat_name in self._top_categories
            is_fav = cat[3] == 1
            # Top selling: priority 0, Favorites: priority 1, Others: priority 2
            priority = 0 if is_top else (1 if is_fav else 2)
            return (priority, cat_name)
        
        sorted_categories = sorted(favorite_categories, key=sort_key)
        
        # Favorite Groups - using ModernButton with SECONDARY style
        if groups:
            for group in groups:
                if len(group) == 3:
                    group_id, group_name, description = group
                    is_favorite = 0
                elif len(group) == 4:
                    group_id, group_name, description, is_favorite = group
                else:
                    continue
                
                if group_id in favorite_group_ids or is_favorite:
                    btn = ModernButton(group_name, ModernButton.SECONDARY)
                    btn.setCheckable(True)
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn.set_compact(True)
                    self._configure_category_button(btn)
                    btn.clicked.connect(lambda checked, name=group_name: self._on_group_clicked(name))
                    self._layout.addWidget(btn)
                    self._buttons.append(btn)
                    self._group_buttons.append(btn)
        
        # ✅ Categories - Top selling first with special style
        for cat in sorted_categories:
            if len(cat) == 3:
                cat_name, group_id, group_name = cat
                is_favorite = 0
            elif len(cat) == 4:
                cat_name, group_id, group_name, is_favorite = cat
            else:
                continue
            
            # Check if this is a top selling category
            is_top = cat_name in self._top_categories
            
            # ✅ Use PRIMARY for top selling, SECONDARY for favorites
            btn_type = ModernButton.SECONDARY
            
            btn = ModernButton(cat_name, btn_type)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.set_compact(True)
            self._configure_category_button(btn)
            
            # ✅ Add star emoji for top selling
            if is_top:
                btn.setText(f"⭐ {cat_name}")
                btn.setToolTip(f"Top Selling: {cat_name}")
            
            btn.clicked.connect(lambda checked, name=cat_name: self._on_category_clicked(name))
            self._layout.addWidget(btn)
            self._buttons.append(btn)
        
        self._category_names = [c[0] for c in favorite_categories]
        self._refresh_button_styles()
        
        self._container.adjustSize()
        QTimer.singleShot(50, self._update_scroll_area)

    def _button_category_name(self, button):
        """Return the real category name from a decorated category button."""
        return button.text().replace("â­ ", "").replace("⭐ ", "")

    def _refresh_button_styles(self):
        """Apply selected styling so only checked buttons look primary."""
        for btn in self._buttons:
            is_group = btn in self._group_buttons
            is_all = btn == self._all_btn
            is_top = self._button_category_name(btn) in self._top_category_names
            btn.setStyleSheet(self._get_button_style(
                btn.isChecked(),
                is_group=is_group,
                is_all=is_all,
                is_top=is_top,
            ))
    
    def _on_category_clicked(self, category_name):
        """Handle category button click."""
        self._selected_category = category_name
        self._selected_group = ""
        
        for btn in self._buttons:
            btn.blockSignals(True)
            if btn == self._all_btn:
                btn.setChecked(category_name == "")
            elif btn in self._group_buttons:
                btn.setChecked(False)
            else:
                btn.setChecked(self._button_category_name(btn) == category_name)
            btn.blockSignals(False)
        
        self._refresh_button_styles()
        self.category_selected.emit(category_name)
    
    def _on_group_clicked(self, group_name):
        """Handle group button click."""
        self._selected_group = group_name
        self._selected_category = ""
        
        for btn in self._buttons:
            btn.blockSignals(True)
            if btn == self._all_btn:
                btn.setChecked(False)
            elif btn in self._group_buttons:
                btn.setChecked(btn.text() == group_name)
            else:
                btn.setChecked(False)
            btn.blockSignals(False)
        
        self._refresh_button_styles()
        self.group_selected.emit(group_name)
    
    def set_selected_category(self, category_name):
        """Programmatically select a category."""
        self._on_category_clicked(category_name)
    
    def set_selected_group(self, group_name):
        """Programmatically select a group."""
        self._on_group_clicked(group_name)
    
    def update_theme(self):
        """Update theme for all buttons."""
        for btn in self._buttons:
            if hasattr(btn, 'update_theme'):
                btn.update_theme()
        self._refresh_button_styles()
        self.apply_compact_style()
    
    def _update_scroll_area(self):
        """Update scroll area."""
        container_width = self._container.sizeHint().width()
        viewport = self.viewport()
        viewport_width = viewport.width() if viewport is not None else self.width()
        
        if container_width > viewport_width:
            self._container.setFixedWidth(container_width)
        else:
            self._container.setFixedWidth(viewport_width)
        
        self._container.adjustSize()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(100, self._update_scroll_area)
    
    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(50, self._update_scroll_area)
    
    # ================================================================
    # MOUSE WHEEL SUPPORT - Horizontal Scroll
    # ================================================================
    
    def eventFilter(self, obj, event):
        if obj == self.viewport() and event.type() == QEvent.Type.Wheel:
            return self._handle_wheel_event(event)
        return super().eventFilter(obj, event)
    
    def _handle_wheel_event(self, event):
        delta = event.angleDelta()
        h_delta = delta.x()
        v_delta = delta.y()
        
        if h_delta != 0:
            scroll_amount = -h_delta * self._scroll_multiplier
        else:
            scroll_amount = -v_delta * self._scroll_multiplier
        
        scrollbar = self.horizontalScrollBar()
        if scrollbar is None:
            return False
        
        current = scrollbar.value()
        max_scroll = scrollbar.maximum()
        new_scroll = max(0, min(current + scroll_amount, max_scroll))
        scrollbar.setValue(new_scroll)
        
        return True
    
    def wheelEvent(self, event):
        self._handle_wheel_event(event)
        event.accept()
    
    # ================================================================
    # SMOOTH SCROLL
    # ================================================================
    
    def _smooth_scroll(self):
        scrollbar = self.horizontalScrollBar()
        if scrollbar is None:
            return
        
        current = scrollbar.value()
        remaining = self._scroll_target - current
        
        if abs(remaining) < 1:
            scrollbar.setValue(self._scroll_target)
            return
        
        step = self._scroll_step
        if abs(step) > abs(remaining):
            step = remaining
        
        new_value = current + step
        scrollbar.setValue(int(new_value))
        
        if abs(scrollbar.value() - self._scroll_target) > 1:
            self._scroll_timer.start(16)
        else:
            scrollbar.setValue(self._scroll_target)
    
    # ================================================================
    # KEYBOARD NAVIGATION
    # ================================================================
    
    def keyPressEvent(self, event):
        scrollbar = self.horizontalScrollBar()
        if scrollbar is None:
            return super().keyPressEvent(event)

        if event.key() == Qt.Key.Key_Left:
            scrollbar.setValue(scrollbar.value() - 60)
            event.accept()
        elif event.key() == Qt.Key.Key_Right:
            scrollbar.setValue(scrollbar.value() + 60)
            event.accept()
        else:
            super().keyPressEvent(event)
