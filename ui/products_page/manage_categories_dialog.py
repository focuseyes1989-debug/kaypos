# ui/products_page/manage_categories_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QMessageBox, 
    QInputDialog, QWidget, QComboBox, QCheckBox
)
from PyQt6.QtGui import QIcon
from PyQt6.QtGui import QColor
from PyQt6.QtCore import pyqtSignal, Qt
from models.database import connect_db
from utils.language import lang
from utils.translations import tr
from utils.speech_to_text import SpeechButton
from ui.widgets.modern_button import ModernButton
from loguru import logger


class ManageCategoriesDialog(QDialog):
    categories_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setWindowTitle(tr("manage_categories"))
        self.resize(550, 700)
        self.all_categories = []
        self.all_groups = []

        layout = QVBoxLayout()
        layout.setSpacing(10)

        # ===== SEARCH WITH SPEECH =====
        search_widget = QWidget()
        search_layout = QHBoxLayout(search_widget)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(5)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(tr("search_category"))
        self.search_input.textChanged.connect(self.filter_categories)
        search_layout.addWidget(self.search_input)
        
        # Speech button for search
        self.btn_search_speech = ModernButton("🎤", ModernButton.PRIMARY)
        self.btn_search_speech.setFixedSize(32, 32)
        self.btn_search_speech.setToolTip("Speak to search category")
        self.btn_search_speech.set_compact(True)
        self.btn_search_speech.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border: none;
                border-radius: 16px;
                font-size: 14px;
                padding: 2px 8px;
                min-height: 28px;
                max-height: 32px;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
            QPushButton:pressed {
                background-color: #6c3483;
            }
        """)
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
        self.list_widget.setMinimumHeight(300)
        layout.addWidget(self.list_widget)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_add = ModernButton("Add New", ModernButton.PRIMARY)
        self.btn_add.set_compact(True)
        
        self.btn_edit = ModernButton("Edit", ModernButton.SECONDARY)
        self.btn_edit.set_compact(True)
        
        self.btn_delete = ModernButton("Delete", ModernButton.TERTIARY)
        self.btn_delete.set_compact(True)
        
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
        self.retranslateUi()

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
            self.language_label.setText("အသံဘာသာစကား:")
            self.show_favorites_only.setText("⭐ အနှစ်သက်ဆုံးများသာ ပြရန်")
        else:
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
        dialog.setWindowTitle(tr("new_category"))
        dialog.setMinimumWidth(450)
        
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        name_label = QLabel(tr("enter_category_name"))
        layout.addWidget(name_label)
        
        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(5)
        
        name_input = QLineEdit()
        name_input.setPlaceholderText(tr("enter_category_name"))
        input_layout.addWidget(name_input)
        
        btn_speech = ModernButton("🎤", ModernButton.PRIMARY)
        btn_speech.setFixedSize(32, 32)
        btn_speech.setToolTip("Speak category name")
        btn_speech.set_compact(True)
        btn_speech.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 16px;
                font-size: 14px;
                padding: 2px 8px;
                min-height: 28px;
                max-height: 32px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1a6e9e;
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
        layout.addWidget(group_combo)
        
        favorite_check = QCheckBox("⭐ Add to Favorites")
        favorite_check.setStyleSheet("""
            QCheckBox {
                font-weight: 500;
                color: #f1c40f;
            }
        """)
        layout.addWidget(favorite_check)
        
        info_label = QLabel("💡 Categories can be organized into groups for better management.")
        info_label.setStyleSheet("color: #5865f2; font-size: 9pt;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        button_layout = QHBoxLayout()
        
        btn_cancel = ModernButton(tr("cancel"), ModernButton.TERTIARY)
        btn_cancel.set_compact(True)
        
        btn_ok = ModernButton(tr("save"), ModernButton.PRIMARY)
        btn_ok.set_compact(True)
        
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