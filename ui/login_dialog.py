# ui/login_dialog.py
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFormLayout, QFrame, QWidget
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap, QColor, QFont
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
                preferred_width=860,
                preferred_height=520,
                min_width=720,
                min_height=460,
            )
            self.resize(dialog_width, dialog_height)
        else:
            self.resize(860, 520)
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
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # Market Image - Full height
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("""
            background: transparent;
            border: none;
        """)
        
        # Load market.png and scale to fill left column
        market_path = "assets/images/market.png"
        if os.path.exists(market_path):
            pixmap = QPixmap(market_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    400, 500,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
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
            self.image_label.setFixedSize(400, 500)
        
        left_layout.addWidget(self.image_label)

        # ---------- RIGHT COLUMN (Login Form) ----------
        right_widget = QWidget()
        right_widget.setObjectName("right_widget")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(10)
        right_layout.setContentsMargins(40, 40, 40, 20)

        # ========== Spacer to push content down ==========
        right_layout.addStretch()

        # ========== Logo and Title ==========
        logo_layout = QVBoxLayout()
        logo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Logo container - NO BORDER
        logo_container = QFrame()
        logo_container.setFixedSize(112, 112)
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
                scaled_pixmap = pixmap.scaled(104, 104, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                logo_label.setPixmap(scaled_pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_container_layout.addWidget(logo_label)
        
        logo_layout.addWidget(logo_container, alignment=Qt.AlignmentFlag.AlignCenter)

        # Title
        title_label = QLabel("KAY Point of Sales")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            font-size: 20pt; 
            font-weight: bold; 
            margin-top: 4px;
            letter-spacing: 1px;
        """)
        logo_layout.addWidget(title_label)

        # Subtitle
        subtitle_label = QLabel("Welcome back! Please login to your account")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("""
            font-size: 10pt; 
            color: #6c757d;
            margin-bottom: 4px;
        """)
        logo_layout.addWidget(subtitle_label)

        right_layout.addLayout(logo_layout)

        # ========== Form (Username / Password) ==========
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setHorizontalSpacing(15)

        self.username_edit = QLineEdit()
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
        self.btn_cancel = ModernButton(" Cancel", ModernButton.TERTIARY)
        self.btn_cancel.set_icon("close", size=(20, 20))
        self.btn_cancel.set_compact(False)
        self.btn_cancel.setMinimumHeight(40)
        self.btn_cancel.clicked.connect(self.reject)
        
        # Login button (right)
        self.btn_login = ModernButton(" Login", ModernButton.PRIMARY)
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
        footer_label = QLabel("© 2026 KAY Point of Sales. All rights reserved.")
        footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_label.setStyleSheet("""
            font-size: 8pt;
            color: #adb5bd;
            padding: 4px 0px;
        """)
        right_layout.addWidget(footer_label)

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

    def _apply_theme(self):
        """Apply theme-aware styles"""
        colors = get_theme_colors()
        is_dark = is_dark_theme()
        
        # Left column (image) - theme-aware background
        if is_dark:
            left_style = """
                QWidget#left_widget {
                    background-color: #2f3136;
                    border: none;
                }
            """
        else:
            left_style = """
                QWidget#left_widget {
                    background-color: #f8f9fa;
                    border: none;
                }
            """
        
        left_widget = self.findChild(QWidget, "left_widget")
        if left_widget:
            left_widget.setStyleSheet(left_style)
        
        # Right column
        if is_dark:
            right_style = """
                QWidget#right_widget {
                    background-color: #2f3136;
                    border: none;
                }
            """
        else:
            right_style = """
                QWidget#right_widget {
                    background-color: #ffffff;
                    border: none;
                }
            """
        
        right_widget = self.findChild(QWidget, "right_widget")
        if right_widget:
            right_widget.setStyleSheet(right_style)
        
        # Dialog background
        if is_dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #2f3136;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #ffffff;
                }
            """)
        
        # Update input fields
        if is_dark:
            input_style = """
                QLineEdit {
                    padding: 8px 14px;
                    border: 1px solid #40444b;
                    border-radius: 6px;
                    background: #36393f;
                    color: #dcddde;
                    font-size: 10pt;
                }
                QLineEdit:focus {
                    border-color: #5865f2;
                    border-width: 2px;
                }
                QLineEdit::placeholder {
                    color: #72767d;
                }
            """
        else:
            input_style = """
                QLineEdit {
                    padding: 8px 14px;
                    border: 1px solid #ced4da;
                    border-radius: 6px;
                    background: white;
                    color: #212529;
                    font-size: 10pt;
                }
                QLineEdit:focus {
                    border-color: #5865f2;
                    border-width: 2px;
                }
                QLineEdit::placeholder {
                    color: #6c757d;
                }
            """
        
        self.username_edit.setStyleSheet(input_style)
        self.password_edit.setStyleSheet(input_style)
        
        # Update labels
        if is_dark:
            label_style = "font-weight: 600; font-size: 10pt; color: #dcddde;"
        else:
            label_style = "font-weight: 600; font-size: 10pt; color: #212529;"
        
        self.username_label.setStyleSheet(label_style)
        self.password_label.setStyleSheet(label_style)
        
        # Update title labels
        for child in self.findChildren(QLabel):
            style = child.styleSheet()
            if "font-size: 20pt" in style or "font-weight: bold" in style:
                if is_dark:
                    child.setStyleSheet("""
                        font-size: 20pt; 
                        font-weight: bold; 
                        margin-top: 4px;
                        letter-spacing: 1px;
                        color: #dcddde;
                    """)
                else:
                    child.setStyleSheet("""
                        font-size: 20pt; 
                        font-weight: bold; 
                        margin-top: 4px;
                        letter-spacing: 1px;
                        color: #212529;
                    """)
            elif "color: #6c757d" in style or "color: #72767d" in style:
                if is_dark:
                    child.setStyleSheet("""
                        font-size: 10pt; 
                        color: #72767d;
                        margin-bottom: 4px;
                    """)
                else:
                    child.setStyleSheet("""
                        font-size: 10pt; 
                        color: #6c757d;
                        margin-bottom: 4px;
                    """)
            elif "color: #adb5bd" in style:
                if is_dark:
                    child.setStyleSheet("""
                        font-size: 8pt;
                        color: #72767d;
                        padding: 4px 0px;
                    """)
                else:
                    child.setStyleSheet("""
                        font-size: 8pt;
                        color: #adb5bd;
                        padding: 4px 0px;
                    """)
        
        # Update button icons
        self._update_button_icons()
        
        # Update buttons
        self.btn_login.update_theme()
        self.btn_cancel.update_theme()

    def retranslateUi(self):
        self.setWindowTitle(tr("login_title"))
        self.username_edit.setPlaceholderText(tr("enter_username"))
        self.password_edit.setPlaceholderText(tr("enter_password"))
        self.username_label.setText(tr("username_label"))
        self.password_label.setText(tr("password_label"))
        
        # Update button text
        self.btn_login.setText(" Login")
        self.btn_cancel.setText(" Cancel")
        
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
