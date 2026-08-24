# ui/products_page/manage_categories_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QMessageBox, 
    QInputDialog, QWidget, QComboBox, QCheckBox, QFrame, QAbstractItemView
)
from PyQt6.QtGui import QIcon
from PyQt6.QtGui import QColor
from PyQt6.QtCore import pyqtSignal, Qt
from models.database import connect_db
from utils.language import lang
from utils.translations import tr
from utils.speech_to_text import SpeechButton
from ui.widgets.modern_button import ModernButton
from ui.themes.theme_manager import theme_manager, get_theme_colors
from loguru import logger


class ManageCategoriesDialog(QDialog):
    categories_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setWindowTitle(tr("manage_categories"))
        self.resize(760, 720)
        self.setMinimumSize(680, 600)
        self.all_categories = []
        self.all_groups = []

        layout = QVBoxLayout()
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        self.header_frame = QFrame()
        self.header_frame.setObjectName("categoryHeader")
        header_layout = QVBoxLayout(self.header_frame)
        header_layout.setContentsMargins(0, 0, 0, 4)
        header_layout.setSpacing(4)
        self.title_label = QLabel("Manage Categories")
        self.title_label.setObjectName("categoryTitle")
        self.subtitle_label = QLabel("Organize products into clear, searchable categories.")
        self.subtitle_label.setObjectName("categorySubtitle")
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.subtitle_label)
        layout.addWidget(self.header_frame)

        # ===== SEARCH WITH SPEECH =====
        search_widget = QWidget()
        search_widget.setObjectName("categorySearchPanel")
        search_layout = QHBoxLayout(search_widget)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(5)
        
        self.search_input = QLineEdit()
        self.search_input.setObjectName("categorySearch")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setPlaceholderText(tr("search_category"))
        self.search_input.textChanged.connect(self.filter_categories)
        search_layout.addWidget(self.search_input)
        
        # Speech button for search
        self.btn_search_speech = ModernButton("", ModernButton.SECONDARY)
        self.btn_search_speech.set_icon("speech_to_text", size=(17, 17))
        self.btn_search_speech.setFixedSize(38, 38)
        self.btn_search_speech.setToolTip("Speak to search category")
        self.btn_search_speech.set_compact(True)
        search_layout.addWidget(self.btn_search_speech)
        
        layout.addWidget(search_widget)

        # ===== LANGUAGE SELECTION =====
        lang_widget = QWidget()
        lang_layout = QHBoxLayout(lang_widget)
        lang_layout.setContentsMargins(0, 5, 0, 5)
        lang_layout.setSpacing(5)

        self.language_label = QLabel("Speech Language:")
        self.language_combo = QComboBox()
        self.language_combo.addItem("🇲🇲 မြန်မာ", "my")
        self.language_combo.addItem("🇬🇧 English", "en")
        self.language_combo.setCurrentIndex(0)
        self.language_combo.currentIndexChanged.connect(self.on_language_changed)

        lang_layout.addWidget(self.language_label)
        lang_layout.addWidget(self.language_combo)
        lang_layout.addStretch()
        
        layout.addWidget(lang_widget)

        # ===== FILTER: Show Only Favorites =====
        filter_widget = QWidget()
        filter_layout = QHBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 5, 0, 5)
        
        self.show_favorites_only = QCheckBox("⭐ Show Favorites Only")
        self.show_favorites_only.setStyleSheet("""
            QCheckBox {
                font-weight: 500;
                color: #f1c40f;
            }
        """)
        self.show_favorites_only.stateChanged.connect(self.filter_categories)
        filter_layout.addWidget(self.show_favorites_only)
        filter_layout.addStretch()
        
        layout.addWidget(filter_widget)

        # Category list
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("categoryList")
        self.list_widget.setMinimumHeight(300)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setSpacing(2)
        layout.addWidget(self.list_widget)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_add = ModernButton("Add New", ModernButton.PRIMARY)
        self.btn_add.set_icon("add")
        
        self.btn_edit = ModernButton("Edit", ModernButton.SECONDARY)
        self.btn_edit.set_icon("edit")
        
        self.btn_delete = ModernButton("Delete", ModernButton.DANGER)
        self.btn_delete.set_icon("delete")
        
        self.btn_add.clicked.connect(self.add_category)
        self.btn_edit.clicked.connect(self.edit_category)
        self.btn_delete.clicked.connect(self.delete_category)
        
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.load_groups()
        self.load_categories()
        
        # Setup speech button for search
        self.setup_speech_search()
        
        lang.language_changed.connect(self.retranslateUi)
        theme_manager.theme_changed.connect(self._on_theme_changed)
        self._apply_theme()
        self.retranslateUi()

    def _on_theme_changed(self, _theme_name):
        self._apply_theme()

    def _apply_theme(self):
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']};
                color: {colors['text']};
                font-family: "Segoe UI", "Myanmar Text", "Noto Sans Myanmar";
            }}
            QFrame#categoryHeader {{ background: transparent; border: none; }}
            QLabel#categoryTitle {{ color: {colors['text']}; font-size: 20pt; font-weight: 700; }}
            QLabel#categorySubtitle {{ color: {colors['text_secondary']}; font-size: 9.5pt; }}
            QWidget#categorySearchPanel {{ background: transparent; }}
            QLineEdit#categorySearch, QComboBox {{
                background-color: {colors['input_bg']}; color: {colors['text']};
                border: 1px solid {colors['input_border']}; border-radius: 8px;
                padding: 8px 12px; min-height: 20px;
            }}
            QLineEdit#categorySearch:focus, QComboBox:focus {{ border-color: {colors['border_hover']}; }}
            QLabel, QCheckBox {{ color: {colors['text_secondary']}; }}
            QListWidget#categoryList {{
                background-color: {colors['card_bg']}; color: {colors['text']};
                alternate-background-color: {colors['table_alt']};
                border: 1px solid {colors['border']}; border-radius: 12px;
                padding: 7px; outline: none;
            }}
            QListWidget#categoryList::item {{ padding: 11px 12px; border-radius: 8px; }}
            QListWidget#categoryList::item:hover {{ background-color: {colors['card_hover']}; }}
            QListWidget#categoryList::item:selected {{
                background-color: {colors['bg_hover']}; color: {colors['text']};
                border-left: 3px solid {colors['border_hover']};
            }}
        """)

    def setup_speech_search(self):
        """Setup speech-to-text for search input"""
        from utils.speech_to_text import SpeechButton
        
        language = self.language_combo.currentData()
        
        self.speech_handler_search = SpeechButton(
            parent=self,
            text_input=self.search_input,
            duration=3,
            language=language
        )
        self.btn_search_speech.clicked.connect(self.speech_handler_search.toggle_recording)

    def on_language_changed(self):
        """Handle language selection change for speech recognition"""
        language = self.language_combo.currentData()
        if hasattr(self, 'speech_handler_search'):
            self.speech_handler_search.set_language(language)
        self.update_speech_tooltips(language)

    def update_speech_tooltips(self, language):
        """Update speech button tooltips based on selected language"""
        if language == "my":
            self.btn_search_speech.setToolTip("အသံဖြင့် ရှာရန် (မြန်မာ)")
        else:
            self.btn_search_speech.setToolTip("Speak to search (English)")

    def show_message(self, title, message):
        """Show a warning message"""
        QMessageBox.warning(self, title, message)

    def retranslateUi(self):
        self.setWindowTitle(tr("manage_categories"))
        self.search_input.setPlaceholderText(tr("search_category"))
        self.btn_add.setText(tr("add_new"))
        self.btn_edit.setText(tr("edit"))
        self.btn_delete.setText(tr("delete"))
        
        if lang.get_current() == "my":
            self.title_label.setText("အမျိုးအစားများ စီမံရန်")
            self.subtitle_label.setText("ကုန်ပစ္စည်းများကို ရှာဖွေရလွယ်ကူသော အမျိုးအစားများဖြင့် စနစ်တကျ စုစည်းပါ။")
            self.language_label.setText("အသံဘာသာစကား:")
            self.show_favorites_only.setText("⭐ အနှစ်သက်ဆုံးများသာ ပြရန်")
        else:
            self.title_label.setText("Manage Categories")
            self.subtitle_label.setText("Organize products into clear, searchable categories.")
            self.language_label.setText("Speech Language:")
            self.show_favorites_only.setText("⭐ Show Favorites Only")
        
        current_lang = self.language_combo.currentData()
        self.update_speech_tooltips(current_lang)

    def load_groups(self):
        """Load groups from database"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, icon, color, is_favorite
            FROM category_groups 
            WHERE is_active = 1 
            ORDER BY sort_order, name
        """)
        self.all_groups = cursor.fetchall()
        conn.close()

    def load_categories(self):
        """Load categories with group information and favorite status"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.name, c.group_id, cg.name as group_name, cg.icon, c.is_favorite
            FROM categories c
            LEFT JOIN category_groups cg ON c.group_id = cg.id
            ORDER BY cg.sort_order, c.name
        """)
        self.all_categories = cursor.fetchall()
        conn.close()
        self.filter_categories()

    def filter_categories(self):
        """Filter categories by search text and favorite status"""
        search_text = self.search_input.text().strip().lower()
        show_favorites = self.show_favorites_only.isChecked()
        
        self.list_widget.clear()
        for cat in self.all_categories:
            cat_id, cat_name, group_id, group_name, icon, is_favorite = cat
            
            if show_favorites and not is_favorite:
                continue
            
            if search_text:
                if search_text not in cat_name.lower() and (not group_name or search_text not in group_name.lower()):
                    continue
            
            star = "⭐ " if is_favorite else ""
            if group_name:
                icon_display = icon or "📁"
                display_text = f"{star}{icon_display} {cat_name} ({group_name})"
            else:
                display_text = f"{star}📄 {cat_name}"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, cat_id)
            
            if is_favorite:
                item.setForeground(QColor("#f1c40f"))
            
            self.list_widget.addItem(item)

    def get_current_category_id(self):
        current = self.list_widget.currentItem()
        if current:
            return current.data(Qt.ItemDataRole.UserRole)
        return None

    def get_category_data(self, cat_id):
        """Get category data by ID"""
        for cat in self.all_categories:
            if cat[0] == cat_id:
                return cat
        return None

    def add_category(self):
        self.show_add_category_dialog()

    def show_add_category_dialog(self):
        """Custom dialog for adding category with group support and speech"""
        dialog = QDialog(self)
        dialog.setObjectName("addCategoryDialog")
        dialog.setWindowTitle(tr("new_category"))
        dialog.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        dialog.setMinimumSize(520, 450)
        dialog.resize(560, 480)
        colors = get_theme_colors()
        is_my = lang.get_current() == "my"

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title_label = QLabel("အမျိုးအစားအသစ်" if is_my else "Add Category")
        title_label.setObjectName("formTitle")
        subtitle_label = QLabel(
            "အမည်၊ အုပ်စုနှင့် အနှစ်သက်ဆုံးအခြေအနေကို သတ်မှတ်ပါ။"
            if is_my else "Create a category and choose where it belongs."
        )
        subtitle_label.setObjectName("formSubtitle")
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

        form_card = QFrame()
        form_card.setObjectName("formCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(20, 18, 20, 18)
        form_layout.setSpacing(10)
        
        name_label = QLabel(tr("enter_category_name"))
        name_label.setObjectName("fieldLabel")
        form_layout.addWidget(name_label)
        
        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)
        
        name_input = QLineEdit()
        name_input.setObjectName("categoryNameInput")
        name_input.setClearButtonEnabled(True)
        name_input.setPlaceholderText(tr("enter_category_name"))
        input_layout.addWidget(name_input)
        
        btn_speech = ModernButton("", ModernButton.SECONDARY)
        btn_speech.set_icon("speech_to_text", size=(18, 18))
        btn_speech.setFixedSize(40, 40)
        btn_speech.setToolTip("Speak category name")
        input_layout.addWidget(btn_speech)
        
        form_layout.addWidget(input_widget)
        
        group_label = QLabel("အုပ်စု" if is_my else "Group")
        group_label.setObjectName("fieldLabel")
        form_layout.addWidget(group_label)
        
        group_combo = QComboBox()
        group_combo.setObjectName("categoryGroupCombo")
        group_combo.addItem("အုပ်စုမရှိ" if is_my else "No Group", None)
        for group in self.all_groups:
            group_id, group_name, icon, color, is_favorite = group
            display_name = f"{icon or '📁'} {group_name}"
            group_combo.addItem(display_name, group_id)
        form_layout.addWidget(group_combo)
        
        favorite_check = QCheckBox("အနှစ်သက်ဆုံးထဲ ထည့်မည်" if is_my else "Add to favorites")
        favorite_check.setObjectName("favoriteCheck")
        form_layout.addWidget(favorite_check)
        
        info_label = QLabel(
            "အုပ်စုတစ်ခုရွေးထားလျှင် ကုန်ပစ္စည်းများကို ပိုမိုလွယ်ကူစွာ ရှာဖွေစီမံနိုင်သည်။"
            if is_my else "Groups make categories easier to find and manage across the catalog."
        )
        info_label.setObjectName("infoLabel")
        info_label.setWordWrap(True)
        form_layout.addWidget(info_label)
        layout.addWidget(form_card, 1)
        
        button_layout = QHBoxLayout()
        
        btn_cancel = ModernButton(tr("cancel"), ModernButton.TERTIARY)
        btn_cancel.set_icon("close")
        
        btn_ok = ModernButton(tr("save"), ModernButton.PRIMARY)
        btn_ok.set_icon("save")
        
        def on_ok():
            name = name_input.text().strip()
            if not name:
                QMessageBox.warning(dialog, tr("error"), tr("please_enter_category_name"))
                return
            
            group_id = group_combo.currentData()
            is_favorite = 1 if favorite_check.isChecked() else 0
            self.save_category(name, group_id, is_favorite)
            dialog.accept()
        
        btn_ok.clicked.connect(on_ok)
        btn_cancel.clicked.connect(dialog.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(btn_cancel)
        button_layout.addWidget(btn_ok)
        layout.addLayout(button_layout)
        
        dialog.setStyleSheet(f"""
            QDialog#addCategoryDialog {{
                background-color: {colors['bg']}; color: {colors['text']};
                font-family: "Segoe UI", "Myanmar Text", "Noto Sans Myanmar";
            }}
            QLabel#formTitle {{ color: {colors['text']}; font-size: 18pt; font-weight: 700; }}
            QLabel#formSubtitle {{ color: {colors['text_secondary']}; font-size: 9.5pt; }}
            QFrame#formCard {{
                background-color: {colors['card_bg']}; border: 1px solid {colors['border']};
                border-radius: 12px;
            }}
            QLabel#fieldLabel {{ color: {colors['text_secondary']}; font-weight: 600; }}
            QLineEdit#categoryNameInput, QComboBox#categoryGroupCombo {{
                background-color: {colors['input_bg']}; color: {colors['text']};
                border: 1px solid {colors['input_border']}; border-radius: 8px;
                padding: 8px 12px; min-height: 22px;
            }}
            QLineEdit#categoryNameInput:focus, QComboBox#categoryGroupCombo:focus {{
                border-color: {colors['border_hover']};
            }}
            QCheckBox#favoriteCheck {{ color: {colors['text']}; spacing: 8px; }}
            QLabel#infoLabel {{
                background-color: {colors['bg_hover']}; color: {colors['text_secondary']};
                border-radius: 8px; padding: 10px 12px; font-size: 9pt;
            }}
        """)
        
        speech_handler = SpeechButton(
            parent=self,
            text_input=name_input,
            duration=4,
            language=self.language_combo.currentData()
        )
        btn_speech.clicked.connect(speech_handler.toggle_recording)
        
        name_input.setFocus()
        dialog.exec()

    def save_category(self, name, group_id=None, is_favorite=0):
        """Save new category to database with group assignment"""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO categories (name, group_id, is_favorite) VALUES (?, ?, ?)",
                (name, group_id, is_favorite)
            )
            conn.commit()
            
            group_name = "No Group"
            if group_id:
                for g in self.all_groups:
                    if g[0] == group_id:
                        group_name = g[1]
                        break
            
            fav_text = "⭐ " if is_favorite else ""
            QMessageBox.information(
                self, 
                tr("success"), 
                f"{fav_text}Category '{name}' added successfully!\nGroup: {group_name}"
            )
            self.categories_changed.emit()
        except Exception as e:
            QMessageBox.warning(self, tr("error"), tr("cannot_add").format(e=str(e)))
        finally:
            conn.close()
        self.load_groups()
        self.load_categories()

    def edit_category(self):
        cat_id = self.get_current_category_id()
        if cat_id is None:
            QMessageBox.warning(self, tr("no_selection"), tr("select_category_to_edit"))
            return

        cat_data = self.get_category_data(cat_id)
        if not cat_data:
            return
        
        current_name = cat_data[1]
        current_group_id = cat_data[2]
        current_favorite = cat_data[5] if len(cat_data) > 5 else 0

        self.show_edit_category_dialog(cat_id, current_name, current_group_id, current_favorite)

    def show_edit_category_dialog(self, cat_id, current_name, current_group_id, current_favorite):
        """Custom dialog for editing category with group support and speech"""
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("edit_category"))
        dialog.setMinimumWidth(450)
        
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        name_label = QLabel(tr("new_name"))
        layout.addWidget(name_label)
        
        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(5)
        
        name_input = QLineEdit()
        name_input.setText(current_name)
        name_input.selectAll()
        input_layout.addWidget(name_input)
        
        btn_speech = ModernButton("🎤", ModernButton.PRIMARY)
        btn_speech.setFixedSize(32, 32)
        btn_speech.setToolTip("Speak new category name")
        btn_speech.set_compact(True)
        btn_speech.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                border: none;
                border-radius: 16px;
                font-size: 14px;
                padding: 2px 8px;
                min-height: 28px;
                max-height: 32px;
            }
            QPushButton:hover {
                background-color: #e67e22;
            }
            QPushButton:pressed {
                background-color: #d35400;
            }
        """)
        input_layout.addWidget(btn_speech)
        
        layout.addWidget(input_widget)
        
        group_label = QLabel("Group:")
        layout.addWidget(group_label)
        
        group_combo = QComboBox()
        group_combo.addItem("No Group", None)
        for group in self.all_groups:
            group_id, group_name, icon, color, is_favorite = group
            display_name = f"{icon or '📁'} {group_name}"
            group_combo.addItem(display_name, group_id)
            if group_id == current_group_id:
                group_combo.setCurrentIndex(group_combo.count() - 1)
        layout.addWidget(group_combo)
        
        favorite_check = QCheckBox("⭐ Add to Favorites")
        favorite_check.setChecked(bool(current_favorite))
        favorite_check.setStyleSheet("""
            QCheckBox {
                font-weight: 500;
                color: #f1c40f;
            }
        """)
        layout.addWidget(favorite_check)
        
        info_label = QLabel("💡 Change the group to reorganize your categories.")
        info_label.setStyleSheet("color: #5865f2; font-size: 9pt;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        button_layout = QHBoxLayout()
        
        btn_cancel = ModernButton(tr("cancel"), ModernButton.TERTIARY)
        btn_cancel.set_compact(True)
        
        btn_ok = ModernButton(tr("save"), ModernButton.PRIMARY)
        btn_ok.set_compact(True)
        
        def on_ok():
            new_name = name_input.text().strip()
            if not new_name:
                QMessageBox.warning(dialog, tr("error"), tr("please_enter_category_name"))
                return
            
            new_group_id = group_combo.currentData()
            is_favorite = 1 if favorite_check.isChecked() else 0
            self.update_category(cat_id, new_name, new_group_id, is_favorite)
            dialog.accept()
        
        btn_ok.clicked.connect(on_ok)
        btn_cancel.clicked.connect(dialog.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(btn_cancel)
        button_layout.addWidget(btn_ok)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        
        speech_handler = SpeechButton(
            parent=self,
            text_input=name_input,
            duration=4,
            language=self.language_combo.currentData()
        )
        btn_speech.clicked.connect(speech_handler.toggle_recording)
        
        name_input.setFocus()
        dialog.exec()

    def update_category(self, cat_id, new_name, group_id=None, is_favorite=0):
        """Update category in database with group assignment"""
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE categories SET name=?, group_id=?, is_favorite=? WHERE id=?",
                (new_name, group_id, is_favorite, cat_id)
            )
            conn.commit()
            
            group_name = "No Group"
            if group_id:
                for g in self.all_groups:
                    if g[0] == group_id:
                        group_name = g[1]
                        break
            
            fav_text = "⭐ " if is_favorite else ""
            QMessageBox.information(
                self, 
                tr("success"), 
                f"{fav_text}Category updated successfully!\nGroup: {group_name}"
            )
            self.categories_changed.emit()
        except Exception as e:
            QMessageBox.warning(self, tr("error"), tr("cannot_update").format(e=str(e)))
        finally:
            conn.close()
        self.load_groups()
        self.load_categories()

    def delete_category(self):
        cat_id = self.get_current_category_id()
        if cat_id is None:
            QMessageBox.warning(self, tr("no_selection"), tr("select_category_to_delete"))
            return

        cat_data = self.get_category_data(cat_id)
        cat_name = cat_data[1] if cat_data else "Unknown"

        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products WHERE category = ?", (cat_name,))
        count = cursor.fetchone()[0]
        conn.close()

        if count > 0:
            QMessageBox.warning(
                self, 
                tr("cannot_delete"), 
                tr("category_in_use").format(count=count)
            )
            return

        reply = QMessageBox.question(
            self, 
            tr("confirm_delete"), 
            f"Delete category '{cat_name}' permanently?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            conn = connect_db()
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM categories WHERE id=?", (cat_id,))
                conn.commit()
                QMessageBox.information(self, tr("success"), tr("category_deleted"))
                self.categories_changed.emit()
            except Exception as e:
                QMessageBox.warning(self, tr("error"), tr("cannot_delete_error").format(e=str(e)))
            finally:
                conn.close()
            self.load_groups()
            self.load_categories()
