# ui/products_page/manage_category_groups_handlers.py
from PyQt6.QtWidgets import (
    QMessageBox, QDialog, QLabel, QPushButton, QHBoxLayout,
    QVBoxLayout, QGridLayout, QScrollArea, QFrame, QGroupBox,
    QLineEdit, QTextEdit, QSpinBox, QCheckBox, QButtonGroup,
    QColorDialog, QTableWidgetItem, QWidget  # ✅ QWidget ကို ထည့်ပါ
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from models.database import connect_db
from utils.language import lang
from utils.translations import tr
from ui.widgets.modern_button import ModernButton
from ui.themes.theme_manager import get_theme_colors, is_dark_theme, theme_manager


class CategoryGroupsHandlers:
    """Event handlers for CategoryGroupsDialog"""
    
    PREDEFINED_ICONS = [
        "📁", "📝", "📱", "💻", "🖥️", "⌨️", "🖨️", "📷", "🎥", "🎮",
        "📚", "📖", "📕", "📘", "📗", "📓", "📔", "📒", "📰", "📑",
        "🏠", "🏢", "🏪", "🏬", "🏫", "🏥", "🏦", "🏨", "🏩", "🏪",
        "👕", "👗", "👔", "👖", "👟", "👠", "👒", "🧢", "🧣", "🧤",
        "🍔", "🍕", "🌮", "🌯", "🍣", "🍱", "🍜", "🍲", "🍳", "☕",
        "🚗", "🚕", "🚙", "🚌", "🚎", "🏎️", "🚓", "🚑", "🚒", "🚐",
        "💄", "💅", "🧴", "🧹", "🧺", "🧻", "🪣", "🪥", "🪒", "🧼",
        "🎵", "🎶", "🎨", "🎭", "🎪", "🎯", "🎲", "🎳", "🎮", "🎰",
        "⚽", "🏀", "🏈", "⚾", "🎾", "🏐", "🏉", "🥏", "🎱", "🪀",
        "🔧", "🔨", "⚒️", "🛠️", "⛏️", "🔩", "⚙️", "🧰", "🧲", "🔫",
        "🧸", "🎁", "🎀", "🎈", "🎉", "🎊", "🎋", "🎌", "🏆", "🏅",
        "🥇", "🥈", "🥉", "🏵️", "🎗️", "🎟️", "🎫", "🎭", "🎨", "🎬"
    ]
    
    def __init__(self, dialog):
        self.dialog = dialog
        self.all_groups = []
        self.current_icon = "📁"
        self.current_color = "#6c5ce7"
        self._theme_name = "Light"
    
    def setup_signals(self):
        """Connect all signals"""
        d = self.dialog
        
        d.btn_add.clicked.connect(self.add_group)
        d.btn_edit.clicked.connect(self.edit_group)
        d.btn_delete.clicked.connect(self.delete_group)
        d.btn_manage_categories.clicked.connect(self.manage_categories)
        d.btn_quick_add.clicked.connect(self.add_group)
        
        d.search_input.textChanged.connect(self.filter_groups)
        d.show_favorites_only.stateChanged.connect(self.filter_groups)
        
        d.table_widget.itemDoubleClicked.connect(lambda item: self.edit_group())
    
    def load_groups(self):
        """Load groups from database"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                g.id, g.name, g.description, g.sort_order, g.icon, g.color, g.is_favorite,
                COUNT(c.id) as category_count
            FROM category_groups g
            LEFT JOIN categories c ON c.group_id = g.id
            WHERE g.is_active = 1
            GROUP BY g.id
            ORDER BY g.is_favorite DESC, g.sort_order, g.name
        """)
        self.all_groups = cursor.fetchall()
        conn.close()
        self.filter_groups()
        self.update_stats()
    
    def filter_groups(self):
        """Filter groups by search text and favorite status"""
        search_text = self.dialog.search_input.text().strip().lower()
        show_favorites = self.dialog.show_favorites_only.isChecked()
        
        table = self.dialog.table_widget
        table.setRowCount(0)
        
        # ✅ Get theme colors for text
        is_dark = is_dark_theme()
        colors = get_theme_colors()
        text_color = colors['text']
        
        for group in self.all_groups:
            group_id, name, description, sort_order, icon, color, is_favorite, category_count = group
            
            if show_favorites and not is_favorite:
                continue
            
            if search_text and search_text not in name.lower() and (not description or search_text not in description.lower()):
                continue
            
            row = table.rowCount()
            table.insertRow(row)
            
            # Icon
            icon_text = icon or "📁"
            icon_item = QTableWidgetItem(icon_text)
            icon_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_item.setData(Qt.ItemDataRole.UserRole, group_id)
            icon_item.setForeground(QColor(text_color))
            table.setItem(row, 0, icon_item)
            
            # Name
            name_text = f"⭐ " if is_favorite else ""
            name_text += name
            name_item = QTableWidgetItem(name_text)
            name_item.setData(Qt.ItemDataRole.UserRole, group_id)
            
            if is_favorite:
                name_item.setForeground(QColor("#f1c40f"))
            elif color:
                name_item.setForeground(QColor(color))
            else:
                name_item.setForeground(QColor(text_color))
            
            table.setItem(row, 1, name_item)
            
            # Description
            desc_item = QTableWidgetItem(description or "")
            desc_item.setForeground(QColor(text_color))
            table.setItem(row, 2, desc_item)
            
            # Categories count
            count_item = QTableWidgetItem(str(category_count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            count_item.setForeground(QColor(text_color))
            table.setItem(row, 3, count_item)
            
            # Favorite
            fav_text = "⭐" if is_favorite else ""
            fav_item = QTableWidgetItem(fav_text)
            fav_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            if is_favorite:
                fav_item.setForeground(QColor("#f1c40f"))
            else:
                fav_item.setForeground(QColor(text_color))
            
            table.setItem(row, 4, fav_item)
        
        self.update_stats()
    
    def update_stats(self):
        """Update statistics labels"""
        d = self.dialog
        total = len(self.all_groups)
        favorites = sum(1 for g in self.all_groups if g[6] == 1)
        visible = d.table_widget.rowCount()
        
        d.total_label.setText(f"📊 Total: {total}")
        d.favorites_label.setText(f"⭐ Favorites: {favorites}")
        d.count_badge.setText(str(visible))
        d.status_label.setText(f"Showing {visible} of {total} groups")
    
    def get_current_group_id(self):
        """Get selected group ID"""
        current_row = self.dialog.table_widget.currentRow()
        if current_row >= 0:
            item = self.dialog.table_widget.item(current_row, 0)
            if item:
                return item.data(Qt.ItemDataRole.UserRole)
        return None
    
    def get_group_by_id(self, group_id):
        """Get group data by ID"""
        for group in self.all_groups:
            if group[0] == group_id:
                return group
        return None
    
    def get_next_sort_order(self):
        """Get next sort order number"""
        if not self.all_groups:
            return 1
        max_order = max([g[3] for g in self.all_groups] or [0])
        return max_order + 1
    
    def add_group(self):
        """Add new group"""
        self.show_group_dialog()
    
    def edit_group(self):
        """Edit selected group"""
        group_id = self.get_current_group_id()
        if group_id is None:
            if lang.get_current() == "my":
                QMessageBox.warning(self.dialog, "အုပ်စုမရွေးရသေးပါ", "ကျေးဇူးပြုပြီး ပြင်ဆင်ရန် အုပ်စုတစ်ခုကို ရွေးချယ်ပါ။")
            else:
                QMessageBox.warning(self.dialog, "No Selection", "Please select a group to edit.")
            return
        self.show_group_dialog(group_id)
    
    def delete_group(self):
        """Delete selected group"""
        group_id = self.get_current_group_id()
        if group_id is None:
            if lang.get_current() == "my":
                QMessageBox.warning(self.dialog, "အုပ်စုမရွေးရသေးပါ", "ကျေးဇူးပြုပြီး ဖျက်ရန် အုပ်စုတစ်ခုကို ရွေးချယ်ပါ။")
            else:
                QMessageBox.warning(self.dialog, "No Selection", "Please select a group to delete.")
            return
        
        group = self.get_group_by_id(group_id)
        if not group:
            return
        
        group_name = group[1]
        is_favorite = group[6]
        category_count = group[7] if len(group) > 7 else 0
        
        # Build confirmation message
        if lang.get_current() == "my":
            fav_text = "⭐ " if is_favorite else ""
            msg = f"{fav_text}အုပ်စု '{group_name}' ကို ဖျက်မည်လား?"
            if category_count > 0:
                msg += f"\n\n⚠️ ဤအုပ်စုတွင် အမျိုးအစား {category_count} ခု ပါဝင်နေပါသည်။\nဖျက်ပါက အဆိုပါ အမျိုးအစားများ အုပ်စုမဲ့ ဖြစ်သွားမည်။"
        else:
            fav_text = "⭐ " if is_favorite else ""
            msg = f"{fav_text}Delete group '{group_name}'?"
            if category_count > 0:
                msg += f"\n\n⚠️ This group has {category_count} categories assigned to it.\nDeleting will unassign these categories."
        
        reply = QMessageBox.question(
            self.dialog,
            "Confirm Delete" if lang.get_current() != "my" else "အုပ်စုဖျက်ရန် အတည်ပြုချက်",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            conn = connect_db()
            cursor = conn.cursor()
            try:
                cursor.execute("UPDATE category_groups SET is_active = 0 WHERE id = ?", (group_id,))
                cursor.execute("UPDATE categories SET group_id = NULL WHERE group_id = ?", (group_id,))
                conn.commit()
                
                if lang.get_current() == "my":
                    QMessageBox.information(self.dialog, "အောင်မြင်ပါသည်", f"{fav_text}အုပ်စု '{group_name}' ကို ဖျက်သိမ်းပြီးပါပြီ။")
                else:
                    QMessageBox.information(self.dialog, "Success", f"{fav_text}Group '{group_name}' deleted successfully.")
                
                self.dialog.groups_changed.emit()
                self.load_groups()
            except Exception as e:
                conn.rollback()
                QMessageBox.critical(self.dialog, "Error" if lang.get_current() != "my" else "အမှား", str(e))
            finally:
                conn.close()
    
    def show_icon_picker(self, current_icon):
        """Show icon picker dialog with theme support"""
        dialog = QDialog(self.dialog)
        dialog.setWindowTitle("Choose Icon" if lang.get_current() != "my" else "အိုင်ကွန်ရွေးရန်")
        dialog.setFixedSize(700, 450)
        dialog.setModal(True)
        
        # ✅ Apply theme to icon picker
        self._apply_theme_to_dialog(dialog)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)
        
        colors = get_theme_colors()
        
        header_label = QLabel("Click an icon to select:" if lang.get_current() != "my" else "အိုင်ကွန်တစ်ခုကို နှိပ်ပြီး ရွေးချယ်ပါ:")
        header_label.setStyleSheet(f"font-weight: 600; font-size: 11pt; color: {colors['text']};")
        layout.addWidget(header_label)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ 
                background: transparent; 
                border: none; 
            }}
            QScrollBar:vertical {{
                background: {colors['bg']};
                width: 6px;
                border-radius: 3px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {colors['input_border']};
                border-radius: 3px;
                min-height: 16px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #5865f2;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        
        container = QWidget()
        container.setStyleSheet(f"background: transparent;")
        grid = QGridLayout(container)
        grid.setSpacing(4)
        grid.setContentsMargins(4, 4, 4, 4)
        
        icon_button_group = QButtonGroup()
        icon_button_group.setExclusive(True)
        
        selected_icon = current_icon
        
        is_dark = is_dark_theme()
        btn_style = f"""
            QPushButton {{
                font-size: 18px;
                border: 2px solid {colors['input_border']};
                border-radius: 6px;
                background: {colors['bg']};
                color: {colors['text']};
            }}
            QPushButton:hover {{
                background-color: rgba(88, 101, 242, 0.1);
                border-color: #5865f2;
            }}
            QPushButton:checked {{
                background-color: rgba(88, 101, 242, 0.2);
                border-color: #5865f2;
            }}
        """
        
        for idx, icon in enumerate(self.PREDEFINED_ICONS):
            btn = QPushButton(icon)
            btn.setCheckable(True)
            btn.setFixedSize(44, 44)
            btn.setStyleSheet(btn_style)
            if icon == current_icon:
                btn.setChecked(True)
                selected_icon = icon
            icon_button_group.addButton(btn)
            row = idx // 10
            col = idx % 10
            grid.addWidget(btn, row, col)
        
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
        
        btn_layout = QHBoxLayout()
        
        btn_cancel = ModernButton("✕ Cancel" if lang.get_current() != "my" else "✕ မလုပ်တော့ပါ", ModernButton.TERTIARY)
        btn_cancel.set_compact(True)
        
        btn_ok = ModernButton("✓ Select" if lang.get_current() != "my" else "✓ ရွေးမည်", ModernButton.PRIMARY)
        btn_ok.set_compact(True)
        
        result_icon = current_icon
        
        def on_select():
            nonlocal result_icon
            for btn in icon_button_group.buttons():
                if btn.isChecked():
                    result_icon = btn.text()
                    break
            dialog.accept()
        
        btn_ok.clicked.connect(on_select)
        btn_cancel.clicked.connect(dialog.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return result_icon
        return current_icon
    
    def _apply_theme_to_dialog(self, dialog):
        """Apply theme to child dialog"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
                color: {colors['text']};
            }}
            QLabel {{
                color: {colors['text']};
            }}
            QPushButton {{
                background-color: {colors['input_border']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: #5865f2;
                color: white;
            }}
            QPushButton:checked {{
                background-color: #5865f2;
                color: white;
                border-color: #5865f2;
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QWidget {{
                background-color: {colors['bg']};
                color: {colors['text']};
            }}
            QScrollBar:vertical {{
                background: {colors['bg']};
                width: 6px;
                border-radius: 3px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {colors['input_border']};
                border-radius: 3px;
                min-height: 16px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #5865f2;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
    
    def pick_icon(self, button):
        """Open icon picker dialog"""
        selected = self.show_icon_picker(self.current_icon)
        if selected:
            self.current_icon = selected
            button.setText(selected)
    
    def pick_color(self, preview_label):
        """Open color picker dialog"""
        color = QColorDialog.getColor(QColor(self.current_color), self.dialog, "Choose Color" if lang.get_current() != "my" else "အရောင်ရွေးရန်")
        if color.isValid():
            hex_code = color.name()
            self.current_color = hex_code
            preview_label.setStyleSheet(f"""
                background-color: {hex_code};
                border: 2px solid {'#40444b' if is_dark_theme() else '#2c3e50'};
                border-radius: 8px;
            """)
    
    def show_group_dialog(self, group_id=None):
        """Show add/edit group dialog with theme support"""
        dialog = QDialog(self.dialog)
        is_edit = group_id is not None
        
        if is_edit:
            dialog.setWindowTitle("Edit Group" if lang.get_current() != "my" else "အုပ်စုပြင်ဆင်ရန်")
        else:
            dialog.setWindowTitle("Add Group" if lang.get_current() != "my" else "အုပ်စုအသစ်ထည့်ရန်")
        
        dialog.setMinimumWidth(450)
        dialog.setMaximumWidth(550)
        dialog.setModal(True)
        
        # ✅ Apply theme
        self._apply_theme_to_dialog(dialog)
        
        main_layout = QVBoxLayout(dialog)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        # Group Name
        name_label = QLabel("Group Name" if lang.get_current() != "my" else "အုပ်စုနာမည်")
        name_label.setStyleSheet(f"font-weight: 600; font-size: 10pt; color: {colors['text']};")
        main_layout.addWidget(name_label)
        
        name_input = QLineEdit()
        name_input.setPlaceholderText("Enter group name..." if lang.get_current() != "my" else "အုပ်စုနာမည် ထည့်ပါ...")
        name_input.setObjectName("dialogNameInput")
        name_input.setStyleSheet(f"""
            QLineEdit {{
                padding: 10px 14px;
                background: {'#40444b' if is_dark else '#ffffff'};
                color: {colors['text']};
                border: 1px solid {colors['input_border']};
                border-radius: 6px;
                font-size: 10pt;
            }}
            QLineEdit:focus {{
                border-color: #5865f2;
            }}
            QLineEdit::placeholder {{
                color: {'#72767d' if is_dark else '#adb5bd'};
            }}
        """)
        main_layout.addWidget(name_input)
        
        # Icon & Color
        icon_color_layout = QHBoxLayout()
        icon_color_layout.setSpacing(14)
        
        # Icon
        icon_group = QGroupBox("Icon" if lang.get_current() != "my" else "အိုင်ကွန်")
        icon_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: 600;
                border: 1px solid {colors['border']};
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 8px;
                color: {colors['text']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                color: {colors['text']};
            }}
        """)
        icon_layout = QHBoxLayout(icon_group)
        icon_layout.setContentsMargins(8, 8, 8, 8)
        
        self.current_icon = "📁"
        btn_pick_icon = QPushButton("📁")
        btn_pick_icon.setObjectName("btnPickIcon")
        btn_pick_icon.setFixedSize(48, 48)
        btn_pick_icon.setToolTip("Click to choose icon" if lang.get_current() != "my" else "အိုင်ကွန်ရွေးရန် နှိပ်ပါ")
        btn_pick_icon.setStyleSheet(f"""
            QPushButton {{
                font-size: 24px;
                border: 2px solid {colors['input_border']};
                border-radius: 8px;
                background: transparent;
                color: {colors['text']};
            }}
            QPushButton:hover {{
                border-color: #5865f2;
                background-color: rgba(88, 101, 242, 0.05);
            }}
        """)
        btn_pick_icon.clicked.connect(lambda: self.pick_icon(btn_pick_icon))
        icon_layout.addWidget(btn_pick_icon)
        icon_layout.addStretch()
        icon_color_layout.addWidget(icon_group, 2)
        
        # Color
        color_group = QGroupBox("Color" if lang.get_current() != "my" else "အရောင်")
        color_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: 600;
                border: 1px solid {colors['border']};
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 8px;
                color: {colors['text']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                color: {colors['text']};
            }}
        """)
        color_layout = QHBoxLayout(color_group)
        color_layout.setContentsMargins(8, 8, 8, 8)
        
        self.current_color = "#6c5ce7"
        color_preview = QLabel()
        color_preview.setFixedSize(48, 48)
        color_preview.setStyleSheet(f"""
            background-color: {self.current_color};
            border: 2px solid {'#40444b' if is_dark else '#2c3e50'};
            border-radius: 8px;
        """)
        color_layout.addWidget(color_preview)
        
        btn_color_picker = ModernButton("Choose" if lang.get_current() != "my" else "ရွေးရန်", ModernButton.SECONDARY)
        btn_color_picker.set_compact(True)
        btn_color_picker.clicked.connect(lambda: self.pick_color(color_preview))
        color_layout.addWidget(btn_color_picker)
        color_layout.addStretch()
        icon_color_layout.addWidget(color_group, 3)
        
        main_layout.addLayout(icon_color_layout)
        
        # Description
        desc_label = QLabel("Description (optional)" if lang.get_current() != "my" else "ဖော်ပြချက် (မထည့်လည်းရပါ)")
        desc_label.setStyleSheet(f"font-weight: 600; font-size: 10pt; color: {colors['text']};")
        main_layout.addWidget(desc_label)
        
        desc_input = QTextEdit()
        desc_input.setMaximumHeight(50)
        desc_input.setPlaceholderText("Add description..." if lang.get_current() != "my" else "ဖော်ပြချက် ထည့်ပါ...")
        desc_input.setStyleSheet(f"""
            QTextEdit {{
                padding: 8px 12px;
                background: {'#40444b' if is_dark else '#ffffff'};
                color: {colors['text']};
                border: 1px solid {colors['input_border']};
                border-radius: 6px;
                font-size: 10pt;
            }}
            QTextEdit:focus {{
                border-color: #5865f2;
            }}
            QTextEdit::placeholder {{
                color: {'#72767d' if is_dark else '#adb5bd'};
            }}
        """)
        main_layout.addWidget(desc_input)
        
        # Sort Order
        sort_layout = QHBoxLayout()
        sort_label = QLabel("Sort Order" if lang.get_current() != "my" else "စီအစဉ်")
        sort_label.setStyleSheet(f"font-weight: 600; font-size: 10pt; color: {colors['text']};")
        sort_layout.addWidget(sort_label)
        
        sort_input = QSpinBox()
        sort_input.setRange(1, 999)
        sort_input.setMinimumWidth(80)
        sort_input.setStyleSheet(f"""
            QSpinBox {{
                padding: 6px 10px;
                background: {'#40444b' if is_dark else '#ffffff'};
                color: {colors['text']};
                border: 1px solid {colors['input_border']};
                border-radius: 6px;
            }}
            QSpinBox:focus {{
                border-color: #5865f2;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background: transparent;
                border: none;
                color: {colors['text']};
            }}
        """)
        sort_layout.addWidget(sort_input)
        
        btn_auto = ModernButton("Auto" if lang.get_current() != "my" else "အလိုအလျောက်", ModernButton.SECONDARY)
        btn_auto.set_compact(True)
        btn_auto.setFixedWidth(60)
        btn_auto.setToolTip("Auto-assign next sort order" if lang.get_current() != "my" else "နောက်စီအစဉ်ကို အလိုအလျောက်သတ်မှတ်မည်")
        btn_auto.clicked.connect(lambda: sort_input.setValue(self.get_next_sort_order()))
        sort_layout.addWidget(btn_auto)
        sort_layout.addStretch()
        main_layout.addLayout(sort_layout)
        
        # Favorite
        favorite_check = QCheckBox("⭐ Add to Favorites" if lang.get_current() != "my" else "⭐ အနှစ်သက်ဆုံးသို့ ထည့်မည်")
        favorite_check.setStyleSheet(f"""
            QCheckBox {{
                font-weight: 500;
                color: #f1c40f;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                background: {'#40444b' if is_dark else '#ffffff'};
                border: 1px solid {colors['input_border']};
                border-radius: 4px;
            }}
            QCheckBox::indicator:checked {{
                background: #f1c40f;
                border-color: #f1c40f;
            }}
        """)
        main_layout.addWidget(favorite_check)
        
        # Load data if editing
        if is_edit and group_id:
            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, description, sort_order, icon, color, is_favorite
                FROM category_groups WHERE id = ?
            """, (group_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                name_input.setText(row[0])
                desc_input.setPlainText(row[1] or "")
                sort_input.setValue(row[2] or 1)
                
                icon = row[3] or "📁"
                self.current_icon = icon
                btn_pick_icon.setText(icon)
                
                color = row[4] or "#6c5ce7"
                self.current_color = color
                color_preview.setStyleSheet(f"""
                    background-color: {color};
                    border: 2px solid {'#40444b' if is_dark else '#2c3e50'};
                    border-radius: 8px;
                """)
                
                favorite_check.setChecked(bool(row[5] if len(row) > 5 else 0))
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"background-color: {colors['border']}; max-height: 1px;")
        main_layout.addWidget(separator)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        btn_cancel = ModernButton("✖ Cancel" if lang.get_current() != "my" else "✖ မလုပ်တော့ပါ", ModernButton.TERTIARY)
        btn_cancel.set_compact(False)
        btn_cancel.setMinimumHeight(34)
        
        btn_save = ModernButton("💾 Save" if lang.get_current() != "my" else "💾 သိမ်းမည်", ModernButton.PRIMARY)
        btn_save.set_compact(False)
        btn_save.setMinimumHeight(34)
        
        def on_ok():
            name = name_input.text().strip()
            if not name:
                if lang.get_current() == "my":
                    QMessageBox.warning(dialog, "အမှား", "ကျေးဇူးပြုပြီး အုပ်စုနာမည် ထည့်ပါ။")
                else:
                    QMessageBox.warning(dialog, "Error", "Please enter a group name.")
                name_input.setFocus()
                return
            
            conn = connect_db()
            cursor = conn.cursor()
            
            if is_edit:
                cursor.execute(
                    "SELECT id FROM category_groups WHERE name = ? AND id != ?",
                    (name, group_id)
                )
            else:
                cursor.execute(
                    "SELECT id FROM category_groups WHERE name = ?",
                    (name,)
                )
            
            existing = cursor.fetchone()
            if existing:
                if lang.get_current() == "my":
                    error_msg = f"'{name}' ဆိုတဲ့ အုပ်စုနာမည် ရှိပြီးသားဖြစ်နေပါတယ်။\nကျေးဇူးပြုပြီး အခြားနာမည်တစ်ခု သုံးပါ။"
                else:
                    error_msg = f"A group with the name '{name}' already exists.\nPlease use a different name."
                
                QMessageBox.warning(dialog, "Duplicate Name" if lang.get_current() != "my" else "နာမည်တူရှိနေပါသည်", error_msg)
                conn.close()
                name_input.setFocus()
                name_input.selectAll()
                return
            
            is_favorite = 1 if favorite_check.isChecked() else 0
            
            try:
                if is_edit:
                    cursor.execute("""
                        UPDATE category_groups 
                        SET name = ?, description = ?, sort_order = ?, icon = ?, color = ?, is_favorite = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (name, desc_input.toPlainText(), sort_input.value(),
                          self.current_icon, self.current_color, is_favorite, group_id))
                    
                    if lang.get_current() == "my":
                        msg = "အုပ်စု ပြင်ဆင်မှု အောင်မြင်ပါသည်!"
                    else:
                        msg = "Group updated successfully!"
                else:
                    cursor.execute("""
                        INSERT INTO category_groups (name, description, sort_order, icon, color, is_favorite, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, 1)
                    """, (name, desc_input.toPlainText(), sort_input.value(),
                          self.current_icon, self.current_color, is_favorite))
                    
                    if lang.get_current() == "my":
                        msg = "အုပ်စု အသစ်ထည့်သွင်းမှု အောင်မြင်ပါသည်!"
                    else:
                        msg = "Group added successfully!"
                
                conn.commit()
                
                fav_text = "⭐ " if is_favorite else ""
                QMessageBox.information(dialog, "Success" if lang.get_current() != "my" else "အောင်မြင်ပါသည်", f"{fav_text}{msg}")
                self.dialog.groups_changed.emit()
                dialog.accept()
                
            except Exception as e:
                conn.rollback()
                QMessageBox.critical(dialog, "Error" if lang.get_current() != "my" else "အမှား", str(e))
            finally:
                conn.close()
        
        btn_save.clicked.connect(on_ok)
        btn_cancel.clicked.connect(dialog.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        main_layout.addLayout(btn_layout)
        
        name_input.setFocus()
        
        if dialog.exec():
            self.load_groups()
    
    def manage_categories(self):
        """Open manage categories dialog"""
        from ui.products_page.manage_categories_dialog import ManageCategoriesDialog
        dialog = ManageCategoriesDialog(self.dialog)
        dialog.categories_changed.connect(self.load_groups)
        dialog.exec()
    
    def apply_theme(self):
        """Apply theme to the main dialog"""
        self._apply_theme_to_ui(self.dialog)
    
    def _apply_theme_to_ui(self, dialog):
        """Apply theme colors to UI"""
        is_dark = is_dark_theme()
        colors = get_theme_colors()
        
        # Table scrollbar style
        scrollbar_style = f"""
            QScrollBar:vertical {{
                background: {colors['bg']};
                width: 6px;
                border-radius: 3px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {colors['input_border']};
                border-radius: 3px;
                min-height: 16px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #5865f2;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                border: none;
                background: transparent;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            QScrollBar:horizontal {{
                background: {colors['bg']};
                height: 6px;
                border-radius: 3px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: {colors['input_border']};
                border-radius: 3px;
                min-width: 16px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: #5865f2;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
                border: none;
                background: transparent;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: transparent;
            }}
        """
        
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
                color: {colors['text']};
            }}
            QLabel {{
                color: {colors['text']};
            }}
            QLabel#headerTitle {{
                color: {colors['text']};
            }}
            QLabel#countBadge {{
                background: #5865f2;
                color: white;
            }}
            QLineEdit#searchInput {{
                background-color: {'#40444b' if is_dark else '#ffffff'};
                color: {colors['text']};
                border: 1px solid {colors['input_border']};
                border-radius: 6px;
                padding: 8px 14px;
            }}
            QLineEdit#searchInput:focus {{
                border-color: #5865f2;
            }}
            QLineEdit#searchInput::placeholder {{
                color: {'#72767d' if is_dark else '#adb5bd'};
            }}
            QCheckBox#favoritesFilter {{
                color: #f1c40f;
            }}
            QCheckBox#favoritesFilter::indicator {{
                background-color: {'#40444b' if is_dark else '#ffffff'};
                border: 1px solid {colors['input_border']};
                border-radius: 4px;
                width: 20px;
                height: 20px;
            }}
            QCheckBox#favoritesFilter::indicator:checked {{
                background-color: #f1c40f;
                border-color: #f1c40f;
            }}
            QTableWidget#groupsTable {{
                background-color: {'#2f3136' if is_dark else '#ffffff'};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 8px;
                padding: 2px;
                outline: none;
                gridline-color: transparent;
            }}
            QTableWidget#groupsTable::item {{
                padding: 10px 12px;
                border: none;
                color: {colors['text']};
            }}
            QTableWidget#groupsTable::item:selected {{
                background-color: #5865f2;
                color: white;
            }}
            QTableWidget#groupsTable::item:hover:!selected {{
                background-color: rgba(88, 101, 242, 0.05);
            }}
            QHeaderView::section {{
                background: {'#202225' if is_dark else '#f8f9fa'};
                color: {colors['text']};
                border: none;
                border-bottom: 2px solid {colors['border']};
                padding: 10px 12px;
                font-weight: 600;
                font-size: 10pt;
            }}
            QWidget#statsWidget {{
                background-color: rgba(88, 101, 242, 0.08);
                border-radius: 8px;
            }}
            QLabel#statLabel {{
                color: {colors['text_secondary']};
            }}
            QWidget#searchWidget {{
                background: transparent;
            }}
            QFrame#statusBar {{
                background: transparent;
            }}
            QFrame#statusBar QLabel {{
                color: {'#72767d' if is_dark else '#adb5bd'};
            }}
            {scrollbar_style}
        """)
    
    def on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._theme_name = theme_name
        self.apply_theme()
        self.filter_groups()