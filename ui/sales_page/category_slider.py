# ui/sales_page/category_slider.py
from PyQt6.QtWidgets import (
    QWidget, QScrollArea, QHBoxLayout, QPushButton, QSizePolicy, QFrame,
    QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QEvent
from PyQt6.QtGui import QWheelEvent
from ui.themes.theme_manager import get_theme_colors, theme_manager
from ui.widgets.modern_button import ModernButton
from loguru import logger


class CategorySlider(QScrollArea):
    """Horizontal category chips styled as a modern filter surface."""
    
    category_selected = pyqtSignal(str)
    group_selected = pyqtSignal(str)
    SLIDER_HEIGHT = 52
    BUTTON_HEIGHT = 34
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setObjectName("categorySlider")
        
        # ✅ Compact height - same as combobox (32px)
        self.setFixedHeight(self.SLIDER_HEIGHT)
        
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        viewport = self.viewport()
        if viewport is not None:
            viewport.installEventFilter(self)
        
        self._container = QWidget()
        self._container.setObjectName("categorySliderContent")
        
        # ✅ Left-aligned layout
        self._layout = QHBoxLayout(self._container)
        self._layout.setSpacing(7)
        self._layout.setContentsMargins(8, 8, 8, 8)
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
        theme_manager.theme_changed.connect(self.update_theme)

    def _configure_category_button(self, button):
        """Apply category-slider specific metrics after ModernButton compact setup."""
        button.setFixedHeight(self.BUTTON_HEIGHT)
        button.setMinimumWidth(68)
        button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    
    def apply_compact_style(self):
        """Apply compact style for category buttons"""
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QScrollArea#categorySlider {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 12px;
            }}
            QScrollArea#categorySlider QWidget#qt_scrollarea_viewport,
            QWidget#categorySliderContent {{
                background: transparent;
                border: none;
            }}
            QScrollBar:horizontal {{
                background: {colors['border']};
                height: 3px;
                border-radius: 1px;
            }}
            QScrollBar::handle:horizontal {{
                background: {colors['progress_bg']};
                border-radius: 1px;
                min-width: 30px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                border: none;
                background: transparent;
                width: 0px;
            }}
        """)
    
    def _get_button_style(self, is_checked=False, is_group=False, is_all=False, is_top=False):
        """
        Get compact button style based on type and state.
        """
        colors = get_theme_colors()
        text_color = colors['warning'] if is_top and not is_checked else colors['text_secondary']
        
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {text_color};
                border: 1px solid transparent;
                padding: 0px 13px;
                font-size: 9.5pt;
                font-weight: 500;
                border-radius: 8px;
            }}
            QPushButton:hover {{
                background-color: {colors['bg_hover']};
                color: {colors['text']};
                border-color: {colors['border']};
            }}
            QPushButton:pressed {{
                background-color: {colors['card_hover']};
            }}
            QPushButton:checked {{
                color: #ffffff;
                border: 1px solid {colors['progress_bg']};
                font-weight: 600;
                background-color: {colors['progress_bg']};
            }}
            QPushButton:checked:hover {{
                color: #ffffff;
                border-color: {colors['border_hover']};
                background-color: {colors['border_hover']};
            }}
        """
    
    def load_categories(self, categories, groups=None, top_categories=None):
        """
        Load categories and groups.
        
        Args:
            categories: List of (category_name, group_id, group_name, is_favorite) tuples
            groups: Retained for API compatibility; groups are not shown.
            top_categories: Category names ordered by usage/sales frequency.
        """
        self._categories = categories
        self._groups = groups
        self._top_categories = top_categories or []
        self._top_category_names = set(self._top_categories)
        self._top_category_rank = {
            name: index for index, name in enumerate(self._top_categories)
        }
        
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
        
        # Popular categories are always visible even when they were not marked
        # as favorites. Favorites fill the remainder of the slider.
        visible_categories = [
            category for category in categories
            if category[3] == 1 or category[0] in self._top_category_names
        ]
        # Most-used categories keep their database ranking. Remaining favorite
        # categories follow alphabetically; category-group buttons are omitted.
        def sort_key(cat):
            cat_name = cat[0]
            if cat_name in self._top_category_rank:
                return (0, self._top_category_rank[cat_name], cat_name.casefold())
            return (1, 0, cat_name.casefold())

        sorted_categories = sorted(visible_categories, key=sort_key)

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
            
            # Use the shared SVG set so the icon aligns with the chip text.
            if is_top:
                btn.set_icon("trophy", size=(14, 14))
                btn.setToolTip(f"Top Selling: {cat_name}")
            
            btn.clicked.connect(lambda checked, name=cat_name: self._on_category_clicked(name))
            self._layout.addWidget(btn)
            self._buttons.append(btn)
        
        self._category_names = [c[0] for c in visible_categories]
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
    
    def update_theme(self, *_):
        """Update theme for all buttons."""
        for btn in self._buttons:
            if hasattr(btn, 'update_theme'):
                btn.update_theme()
            self._configure_category_button(btn)
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
