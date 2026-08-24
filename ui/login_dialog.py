# ui/login_dialog.py
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFormLayout, QFrame, QWidget
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap, QColor, QFont, QAction
import hashlib
from models.database import connect_db
from utils.language import lang
from utils.translations import tr
from ui.widgets.modern_button import ModernButton
from ui.themes.theme_manager import theme_manager, get_theme_colors, is_dark_theme
from ui.responsive_utils import get_responsive_dialog_size
import os


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dark = is_dark_theme()
        
        self.setWindowTitle(tr("login_title"))
        self.setWindowIcon(QIcon("assets/icons/zaypos.png"))
        self.setModal(True)

        screen = self.screen()
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is not None:
            screen_geometry = screen.availableGeometry()
            dialog_width, dialog_height = get_responsive_dialog_size(
                screen_geometry.width(),
                screen_geometry.height(),
                preferred_width=940,
                preferred_height=580,
                min_width=820,
                min_height=520,
            )
            self.resize(dialog_width, dialog_height)
        else:
            self.resize(940, 580)
        self.user_info = None

        # Connect theme change
        theme_manager.theme_changed.connect(self._on_theme_changed)

        # ============================================================
        # MAIN LAYOUT - 2 Columns
        # ============================================================
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------- LEFT COLUMN (Image - Full Height) ----------
        left_widget = QWidget()
        left_widget.setObjectName("left_widget")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(34, 34, 34, 30)
        left_layout.setSpacing(12)

        brand_row = QHBoxLayout()
        brand_mark = QLabel("K")
        brand_mark.setObjectName("brandMark")
        brand_mark.setFixedSize(44, 44)
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_name = QLabel("KAY")
        brand_name.setObjectName("brandName")
        brand_row.addWidget(brand_mark)
        brand_row.addWidget(brand_name)
        brand_row.addStretch()
        left_layout.addLayout(brand_row)

        self.hero_title = QLabel("Your business, one workspace.")
        self.hero_title.setObjectName("heroTitle")
        self.hero_title.setWordWrap(True)
        self.hero_subtitle = QLabel("Sales, inventory and reports—ready for your next working day.")
        self.hero_subtitle.setObjectName("heroSubtitle")
        self.hero_subtitle.setWordWrap(True)
        left_layout.addWidget(self.hero_title)
        left_layout.addWidget(self.hero_subtitle)

        # Market Image - Full height
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("""
            background: transparent;
            border: none;
        """)
        
        # Load market.png and scale to fill left column
        market_path = "assets/launcher/pos-system.png"
        if os.path.exists(market_path):
            pixmap = QPixmap(market_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    430, 360,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
                self.image_label.setScaledContents(True)
                #self.image_label.setFixedSize(400, 500)
        else:
            # Fallback if image not found
            self.image_label.setText("🏪")
            self.image_label.setStyleSheet("""
                font-size: 100px;
                color: #5865f2;
                background: transparent;
                border: none;
            """)
        
        left_layout.addWidget(self.image_label)

        # ---------- RIGHT COLUMN (Login Form) ----------
        right_widget = QWidget()
        right_widget.setObjectName("right_widget")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(14)
        right_layout.setContentsMargins(52, 42, 52, 28)

        # ========== Spacer to push content down ==========
        right_layout.addStretch()

        # ========== Logo and Title ==========
        logo_layout = QVBoxLayout()
        logo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Logo container - NO BORDER
        logo_container = QFrame()
        logo_container.setFixedSize(76, 76)
        logo_container.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
                border-radius: 0px;
            }
        """)
        logo_container_layout = QVBoxLayout(logo_container)
        logo_container_layout.setContentsMargins(0, 0, 0, 0)
        logo_container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo_label = QLabel()
        logo_path = "assets/icons/zaypos.png"
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(68, 68, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                logo_label.setPixmap(scaled_pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_container_layout.addWidget(logo_label)
        
        logo_layout.addWidget(logo_container, alignment=Qt.AlignmentFlag.AlignCenter)

        # Title
        self.title_label = QLabel("Welcome back")
        self.title_label.setObjectName("loginTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_layout.addWidget(self.title_label)

        # Subtitle
        self.subtitle_label = QLabel("Sign in to continue to KAY Point of Sales")
        self.subtitle_label.setObjectName("loginSubtitle")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_layout.addWidget(self.subtitle_label)

        right_layout.addLayout(logo_layout)

        # ========== Form (Username / Password) ==========
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setHorizontalSpacing(15)

        self.username_edit = QLineEdit()
        self.username_edit.setObjectName("loginInput")
        self.username_edit.setPlaceholderText(tr("enter_username"))
        self.username_edit.setMinimumHeight(38)
        self.username_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px 14px;
                border: 1px solid #ced4da;
                border-radius: 6px;
                background: white;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border-color: #5865f2;
                border-width: 2px;
            }
        """)

        self.password_edit = QLineEdit()
        self.password_edit.setObjectName("loginInput")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText(tr("enter_password"))
        self.password_edit.setMinimumHeight(38)
        self.password_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px 14px;
                border: 1px solid #ced4da;
                border-radius: 6px;
                background: white;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border-color: #5865f2;
                border-width: 2px;
            }
        """)

        self.password_visibility_action = QAction(self)
        self.password_visibility_action.setCheckable(True)
        self.password_visibility_action.setToolTip("Show password")
        self.password_visibility_action.toggled.connect(self._toggle_password_visibility)
        self.password_edit.addAction(self.password_visibility_action, QLineEdit.ActionPosition.TrailingPosition)

        self.username_label = QLabel(tr("username_label"))
        self.username_label.setStyleSheet("font-weight: 600; font-size: 10pt;")
        
        self.password_label = QLabel(tr("password_label"))
        self.password_label.setStyleSheet("font-weight: 600; font-size: 10pt;")
        
        form_layout.addRow(self.username_label, self.username_edit)
        form_layout.addRow(self.password_label, self.password_edit)

        right_layout.addLayout(form_layout)

        # ========== Buttons ==========
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        # Cancel button (left)
        self.btn_cancel = ModernButton("Cancel", ModernButton.TERTIARY)
        self.btn_cancel.set_icon("close", size=(20, 20))
        self.btn_cancel.set_compact(False)
        self.btn_cancel.setMinimumHeight(40)
        self.btn_cancel.clicked.connect(self.reject)
        
        # Login button (right)
        self.btn_login = ModernButton("Sign In", ModernButton.PRIMARY)
        self.btn_login.set_icon("login", size=(20, 20))
        self.btn_login.set_compact(False)
        self.btn_login.setMinimumHeight(40)
        self.btn_login.clicked.connect(self.attempt_login)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_login)
        right_layout.addLayout(btn_layout)

        # ========== Spacer to push footer to bottom ==========
        right_layout.addStretch()

        # ========== Footer at bottom ==========
        self.footer_label = QLabel("© 2026 KAY Point of Sales · Secure workspace")
        self.footer_label.setObjectName("loginFooter")
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.footer_label)

        # ---------- Add to Main Layout ----------
        main_layout.addWidget(left_widget, 0)  # Fixed size
        main_layout.addWidget(right_widget, 1)  # Stretch

        self.setLayout(main_layout)
        self.username_edit.setFocus()
        lang.language_changed.connect(self.retranslateUi)
        
        # Apply theme after all widgets are created
        self._apply_theme()

    def _on_theme_changed(self, theme_name):
        """Handle theme change"""
        self._is_dark = is_dark_theme()
        self._apply_theme()
        self._update_button_icons()

    def _update_button_icons(self):
        """Update button icons when theme changes"""
        self.btn_login.set_icon("login", size=(20, 20))
        self.btn_cancel.set_icon("close", size=(20, 20))
        icon_name = "visibility_off" if self.password_visibility_action.isChecked() else "visibility"
        from ui.themes.theme_manager import get_themed_icon
        self.password_visibility_action.setIcon(get_themed_icon(icon_name, size=(18, 18)))

    def _toggle_password_visibility(self, visible):
        self.password_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )
        self.password_visibility_action.setToolTip("Hide password" if visible else "Show password")
        self._update_button_icons()

    def _apply_theme(self):
        """Apply theme-aware styles"""
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors['bg']}; color: {colors['text']};
                font-family: "Segoe UI", "Myanmar Text", "Noto Sans Myanmar";
            }}
            QWidget#left_widget {{
                background-color: {colors['card_bg']};
                border-right: 1px solid {colors['border']};
            }}
            QWidget#right_widget {{ background-color: {colors['bg']}; }}
            QLabel#brandMark {{
                background-color: {colors['progress_bg']}; color: white;
                border-radius: 12px; font-size: 17pt; font-weight: 900;
            }}
            QLabel#brandName {{ color: {colors['text']}; font-size: 18pt; font-weight: 800; }}
            QLabel#heroTitle {{ color: {colors['text']}; font-size: 21pt; font-weight: 750; }}
            QLabel#heroSubtitle {{ color: {colors['text_secondary']}; font-size: 10pt; }}
            QLabel#loginTitle {{ color: {colors['text']}; font-size: 20pt; font-weight: 750; }}
            QLabel#loginSubtitle {{ color: {colors['text_secondary']}; font-size: 9.5pt; }}
            QLabel#loginFooter {{ color: {colors['text_secondary']}; font-size: 8.5pt; }}
            QLineEdit#loginInput {{
                background-color: {colors['input_bg']}; color: {colors['text']};
                border: 1px solid {colors['input_border']}; border-radius: 9px;
                padding: 9px 13px; min-height: 22px; font-size: 10pt;
            }}
            QLineEdit#loginInput:hover {{ border-color: {colors['border']}; }}
            QLineEdit#loginInput:focus {{ border: 1px solid {colors['border_hover']}; }}
            QLineEdit#loginInput::placeholder {{ color: {colors['text_secondary']}; }}
        """)
        label_style = f"font-weight:600;font-size:9.5pt;color:{colors['text_secondary']};"
        self.username_label.setStyleSheet(label_style)
        self.password_label.setStyleSheet(label_style)
        self.username_edit.setStyleSheet("")
        self.password_edit.setStyleSheet("")
        self.btn_login.update_theme()
        self.btn_cancel.update_theme()
        self._update_button_icons()

    def retranslateUi(self):
        self.setWindowTitle(tr("login_title"))
        self.username_edit.setPlaceholderText(tr("enter_username"))
        self.password_edit.setPlaceholderText(tr("enter_password"))
        self.username_label.setText(tr("username_label"))
        self.password_label.setText(tr("password_label"))
        
        if lang.get_current() == "my":
            self.title_label.setText("ပြန်လည်ကြိုဆိုပါတယ်")
            self.subtitle_label.setText("KAY Point of Sales သို့ ဆက်လက်ဝင်ရောက်ပါ")
            self.hero_title.setText("သင့်လုပ်ငန်းအတွက် Workspace တစ်ခုတည်း။")
            self.hero_subtitle.setText("အရောင်း၊ ကုန်လက်ကျန်နှင့် အစီရင်ခံစာများကို တစ်နေရာတည်းတွင် စီမံပါ။")
            self.btn_login.setText("ဝင်မည်")
            self.btn_cancel.setText("မလုပ်တော့ပါ")
        else:
            self.title_label.setText("Welcome back")
            self.subtitle_label.setText("Sign in to continue to KAY Point of Sales")
            self.hero_title.setText("Your business, one workspace.")
            self.hero_subtitle.setText("Sales, inventory and reports—ready for your next working day.")
            self.btn_login.setText("Sign In")
            self.btn_cancel.setText("Cancel")
        
        # Update button icons
        self._update_button_icons()
        
        # Apply theme after language change
        self._apply_theme()

    def attempt_login(self):
        try:
            username = self.username_edit.text().strip()
            password = self.password_edit.text()

            if not username or not password:
                QMessageBox.warning(self, tr("error"), tr("enter_username_password"))
                return

            conn = connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, password_hash, role, full_name, salt, force_password_change FROM users WHERE username=?", (username,))
            user = cursor.fetchone()
            conn.close()

            if not user:
                QMessageBox.warning(self, tr("login_failed_title"), tr("login_failed"))
                return

            user_id, db_username, stored_hash, role, full_name, salt, force_change = user

            # Verify password
            if salt:
                input_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 100000).hex()
                password_ok = (input_hash == stored_hash)
            else:
                input_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), b'salt_123', 100000).hex()
                password_ok = (input_hash == stored_hash)

            if not password_ok:
                QMessageBox.warning(self, tr("login_failed_title"), tr("login_failed"))
                return

            if salt is None or force_change == 1:
                reply = QMessageBox.question(
                    self,
                    tr("password_expired"),
                    tr("password_expired_message"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    from ui.change_password_dialog import ChangePasswordDialog
                    dialog = ChangePasswordDialog(user_id, db_username, self, old_password=password)
                    if dialog.exec():
                        self.user_info = {
                            "id": user_id,
                            "username": db_username,
                            "role": role,
                            "full_name": full_name or db_username
                        }
                        self.accept()
                    return
                else:
                    QMessageBox.warning(self, tr("login_failed_title"), tr("must_change_password"))
                    return

            self.user_info = {
                "id": user_id,
                "username": db_username,
                "role": role,
                "full_name": full_name or db_username
            }
            self.accept()

        except Exception as e:
            error_message = (tr("unexpected_error") or "Unexpected error").format(e=str(e))
            QMessageBox.critical(self, tr("login_error"), error_message)
    
    def keyPressEvent(self, event):
        """Handle Enter key to login"""
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.attempt_login()
        else:
            super().keyPressEvent(event)
    
    def showEvent(self, event):
        """Apply theme when dialog becomes visible"""
        self._apply_theme()
        super().showEvent(event)
