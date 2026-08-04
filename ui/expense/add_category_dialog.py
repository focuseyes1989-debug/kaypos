# ui/expense/add_category_dialog.py
"""
Add Category Dialog - Compact
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QWidget, QLabel, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QColor, QIcon

from models.database import connect_db
from utils.language import lang

# ✅ Import ModernButton
from ui.widgets.modern_button import ModernButton


class AddCategoryDialog(QDialog):
    """Dialog for adding a new expense category - Compact"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Category" if lang.get_current() != "my" else "အမျိုးအစားအသစ်ထည့်ရန်")
        self.setFixedSize(420, 280)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._setup_ui()
        self._apply_theme()
        
        # Connect language change
        lang.language_changed.connect(self._on_language_changed)
        
        # Connect theme change
        try:
            from ui.themes.theme_manager import theme_manager
            theme_manager.theme_changed.connect(self._on_theme_changed)
        except:
            pass
        
        # Focus on input field after dialog is shown
        QTimer.singleShot(50, self.input_name.setFocus)
    
    def _get_icon(self, icon_name):
        """Get QIcon from assets/icons folder"""
        try:
            from pathlib import Path
            
            # Get the base directory
            base_dir = Path(__file__).parent.parent.parent
            icon_path = base_dir / "assets" / "icons" / f"{icon_name}.svg"
            
            if icon_path.exists():
                return QIcon(str(icon_path))
            else:
                # Fallback: try relative path
                alt_path = Path("assets/icons") / f"{icon_name}.svg"
                if alt_path.exists():
                    return QIcon(str(alt_path))
        except Exception as e:
            pass
        return QIcon()
    
    def _setup_ui(self):
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # ========== Header Section ==========
        header_widget = QWidget()
        header_widget.setStyleSheet("QWidget { background-color: transparent; }")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        
        # ✅ Icon using SVG
        icon_label = QLabel()
        icon = self._get_icon("folder")
        if not icon.isNull():
            icon_label.setPixmap(icon.pixmap(QSize(24, 24)))
        else:
            icon_label.setText("📂")
            icon_label.setStyleSheet("font-size: 24px; background: transparent;")
        header_layout.addWidget(icon_label)
        
        # Title
        self.title_label = QLabel("Add New Category" if lang.get_current() != "my" else "အမျိုးအစားအသစ် ထည့်ရန်")
        self.title_label.setObjectName("dialog_title")
        self.title_label.setStyleSheet("""
            QLabel#dialog_title {
                font-size: 14pt;
                font-weight: bold;
                color: #2c3e50;
                background: transparent;
            }
        """)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        main_layout.addWidget(header_widget)
        
        # ========== Separator ==========
        self.sep = QFrame()
        self.sep.setFrameShape(QFrame.Shape.HLine)
        self.sep.setFrameShadow(QFrame.Shadow.Sunken)
        self.sep.setStyleSheet("""
            QFrame {
                background-color: #dee2e6;
                margin: 2px 0px 8px 0px;
                max-height: 1px;
                border: none;
            }
        """)
        main_layout.addWidget(self.sep)
        
        # ========== Input Field Section ==========
        input_container = QWidget()
        input_container.setStyleSheet("QWidget { background-color: transparent; }")
        input_container_layout = QVBoxLayout(input_container)
        input_container_layout.setSpacing(6)
        input_container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Label
        self.label = QLabel("Category Name" if lang.get_current() != "my" else "အမျိုးအစားအမည်")
        self.label.setStyleSheet("""
            font-size: 9pt;
            font-weight: 600;
            color: #495057;
            background: transparent;
            padding-left: 2px;
        """)
        input_container_layout.addWidget(self.label)
        
        # Input Text Box
        self.input_name = QLineEdit()
        self.input_name.setObjectName("category_input")
        self.input_name.setPlaceholderText("Enter category name..." if lang.get_current() != "my" else "အမျိုးအစားအမည် ထည့်ပါ...")
        self.input_name.setMinimumHeight(38)
        self.input_name.returnPressed.connect(self._accept)
        
        # Clear button for input
        self.input_name.textChanged.connect(self._update_clear_button_visibility)
        
        # Create clear button
        self.clear_button = QPushButton("✕")
        self.clear_button.setFixedSize(24, 24)
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.setVisible(False)
        self.clear_button.clicked.connect(self._clear_input)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #e9ecef;
                color: #495057;
                border: none;
                border-radius: 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #dee2e6;
            }
        """)
        
        # Input layout with clear button
        input_layout = QHBoxLayout()
        input_layout.setSpacing(0)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.addWidget(self.input_name, 1)
        input_layout.addWidget(self.clear_button)
        
        input_container_layout.addLayout(input_layout)
        
        # Helper text
        self.helper_text = QLabel("Press Enter to add or click Add button" if lang.get_current() != "my" else "Enter နှိပ်ပြီး ထည့်ပါ သို့မဟုတ် Add ခလုတ်ကို နှိပ်ပါ")
        self.helper_text.setStyleSheet("""
            font-size: 8pt;
            color: #6c757d;
            background: transparent;
            padding-left: 2px;
            font-style: italic;
        """)
        input_container_layout.addWidget(self.helper_text)
        
        main_layout.addWidget(input_container)
        
        # ========== Button Box ==========
        btn_container = QWidget()
        btn_container.setStyleSheet("QWidget { background-color: transparent; }")
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setSpacing(8)
        btn_layout.setContentsMargins(0, 8, 0, 0)
        btn_layout.addStretch()
        
        # ✅ Cancel button - Secondary (Gray icon in Light, White in Dark)
        self.btn_cancel = ModernButton(
            " Cancel" if lang.get_current() != "my" else " မလုပ်တော့ပါ", 
            ModernButton.SECONDARY
        )
        self.btn_cancel.set_icon("close", size=(14, 14))
        self.btn_cancel.set_compact(True)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_cancel.setFixedSize(90, 32)
        btn_layout.addWidget(self.btn_cancel)
        
        # ✅ Add button - Primary (White icon in both themes)
        self.btn_ok = ModernButton(
            " Add" if lang.get_current() != "my" else " ထည့်မည်", 
            ModernButton.PRIMARY
        )
        self.btn_ok.set_icon("add", size=(14, 14))
        self.btn_ok.set_compact(True)
        self.btn_ok.clicked.connect(self._accept)
        self.btn_ok.setFixedSize(100, 32)
        btn_layout.addWidget(self.btn_ok)
        
        main_layout.addWidget(btn_container)
        
        self.setLayout(main_layout)
    
    def _update_clear_button_visibility(self, text):
        """Show/hide clear button based on input text"""
        self.clear_button.setVisible(bool(text.strip()))
    
    def _clear_input(self):
        """Clear the input field"""
        self.input_name.clear()
        self.input_name.setFocus()
    
    def _apply_theme(self):
        """Apply theme to dialog"""
        try:
            from ui.themes.theme_manager import is_dark_theme
            is_dark = is_dark_theme()
        except:
            is_dark = False
        
        # Update input style
        if is_dark:
            self.input_name.setStyleSheet("""
                QLineEdit#category_input {
                    background-color: #40444b;
                    color: #dcddde;
                    border: 2px solid #40444b;
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 10pt;
                    selection-background-color: #7289da;
                }
                QLineEdit#category_input:focus {
                    border: 2px solid #7289da;
                    background-color: #36393f;
                }
                QLineEdit#category_input:hover {
                    border: 2px solid #5a5f6b;
                }
                QLineEdit#category_input::placeholder {
                    color: #7a7f8b;
                }
            """)
            
            self.setStyleSheet("QDialog { background-color: #2f3136; }")
            
            self.title_label.setStyleSheet("""
                QLabel#dialog_title {
                    font-size: 14pt;
                    font-weight: bold;
                    color: #dcddde;
                    background: transparent;
                }
            """)
            
            self.label.setStyleSheet("""
                font-size: 9pt;
                font-weight: 600;
                color: #b9bbbe;
                background: transparent;
                padding-left: 2px;
            """)
            
            self.helper_text.setStyleSheet("""
                font-size: 8pt;
                color: #7a7f8b;
                background: transparent;
                padding-left: 2px;
                font-style: italic;
            """)
            
            self.clear_button.setStyleSheet("""
                QPushButton {
                    background-color: #40444b;
                    color: #b9bbbe;
                    border: none;
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #5a5f6b;
                }
            """)
            
            self.sep.setStyleSheet("""
                QFrame {
                    background-color: #40444b;
                    margin: 2px 0px 8px 0px;
                    max-height: 1px;
                    border: none;
                }
            """)
        else:
            self.input_name.setStyleSheet("""
                QLineEdit#category_input {
                    background-color: white;
                    color: #2c3e50;
                    border: 2px solid #ced4da;
                    border-radius: 6px;
                    padding: 8px 12px;
                    font-size: 10pt;
                    selection-background-color: #3498db;
                    selection-color: white;
                }
                QLineEdit#category_input:focus {
                    border: 2px solid #3498db;
                    background-color: #f8f9fa;
                }
                QLineEdit#category_input:hover {
                    border: 2px solid #adb5bd;
                }
                QLineEdit#category_input::placeholder {
                    color: #adb5bd;
                }
            """)
            
            self.setStyleSheet("QDialog { background-color: white; }")
            
            self.title_label.setStyleSheet("""
                QLabel#dialog_title {
                    font-size: 14pt;
                    font-weight: bold;
                    color: #2c3e50;
                    background: transparent;
                }
            """)
            
            self.label.setStyleSheet("""
                font-size: 9pt;
                font-weight: 600;
                color: #495057;
                background: transparent;
                padding-left: 2px;
            """)
            
            self.helper_text.setStyleSheet("""
                font-size: 8pt;
                color: #6c757d;
                background: transparent;
                padding-left: 2px;
                font-style: italic;
            """)
            
            self.clear_button.setStyleSheet("""
                QPushButton {
                    background-color: #e9ecef;
                    color: #495057;
                    border: none;
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #dee2e6;
                }
            """)
            
            self.sep.setStyleSheet("""
                QFrame {
                    background-color: #dee2e6;
                    margin: 2px 0px 8px 0px;
                    max-height: 1px;
                    border: none;
                }
            """)
        
        # Update buttons
        if hasattr(self, 'btn_ok'):
            self.btn_ok.update_theme()
            self.btn_ok.set_compact(True)
            self.btn_ok.setFixedSize(100, 32)
        if hasattr(self, 'btn_cancel'):
            self.btn_cancel.update_theme()
            self.btn_cancel.set_compact(True)
            self.btn_cancel.setFixedSize(90, 32)
    
    def _on_theme_changed(self, theme_name):
        self._apply_theme()
    
    def _on_language_changed(self, lang_code):
        self.retranslate_ui()
    
    def retranslate_ui(self):
        lang_code = lang.get_current()
        
        if lang_code == "my":
            self.setWindowTitle("အမျိုးအစားအသစ်ထည့်ရန်")
            self.title_label.setText("အမျိုးအစားအသစ် ထည့်ရန်")
            self.label.setText("အမျိုးအစားအမည်")
            self.input_name.setPlaceholderText("အမျိုးအစားအမည် ထည့်ပါ...")
            self.helper_text.setText("Enter နှိပ်ပြီး ထည့်ပါ သို့မဟုတ် Add ခလုတ်ကို နှိပ်ပါ")
            self.btn_ok.setText(" ထည့်မည်")
            self.btn_cancel.setText(" မလုပ်တော့ပါ")
        else:
            self.setWindowTitle("Add Category")
            self.title_label.setText("Add New Category")
            self.label.setText("Category Name")
            self.input_name.setPlaceholderText("Enter category name...")
            self.helper_text.setText("Press Enter to add or click Add button")
            self.btn_ok.setText(" Add")
            self.btn_cancel.setText(" Cancel")
        
        self.btn_ok.update_theme()
        self.btn_ok.set_compact(True)
        self.btn_ok.setFixedSize(100, 32)
        self.btn_cancel.update_theme()
        self.btn_cancel.set_compact(True)
        self.btn_cancel.setFixedSize(90, 32)
        self._apply_theme()
    
    def _accept(self):
        """Accept the dialog and return category name"""
        name = self.input_name.text().strip()
        if not name:
            QMessageBox.warning(self, 
                               "Warning" if lang.get_current() != "my" else "သတိပေးချက်",
                               "Please enter a category name." if lang.get_current() != "my" else "အမျိုးအစားအမည် ထည့်ပါ။")
            self.input_name.setFocus()
            return
        
        # Check if category already exists
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM expense_categories WHERE name = ?", (name,))
        exists = cursor.fetchone()
        conn.close()
        
        if exists:
            QMessageBox.warning(self,
                               "Warning" if lang.get_current() != "my" else "သတိပေးချက်",
                               f"Category '{name}' already exists." if lang.get_current() != "my" else f"'{name}' ဆိုတဲ့ အမျိုးအစား ရှိပြီးသားပါ။")
            self.input_name.clear()
            self.input_name.setFocus()
            return
        
        self._category_name = name
        self.accept()
    
    def get_category_name(self):
        """Return the entered category name"""
        return getattr(self, '_category_name', '')