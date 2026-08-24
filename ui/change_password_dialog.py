from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QMessageBox, QDialogButtonBox,
    QVBoxLayout, QLabel, QFrame,
)
from ui.themes.theme_manager import get_theme_colors, theme_manager
from models.database import connect_db
import hashlib
import os


class ChangePasswordDialog(QDialog):
    def __init__(self, user_id, username, parent=None, old_password: str | None = None):
        super().__init__(parent)
        self.user_id = user_id
        self.username = username
        self.setWindowTitle("Change Password")
        self.setModal(True)
        self.setMinimumWidth(480)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        title = QLabel("Change password")
        title.setObjectName("dialogTitle")
        subtitle = QLabel(f"Update the sign-in password for {username}.")
        subtitle.setObjectName("dialogSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("formCard")
        layout = QFormLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(14)
        self.old_password_input = QLineEdit()
        self.old_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        if old_password is not None:
            self.old_password_input.setText(old_password)
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Current Password:", self.old_password_input)
        layout.addRow("New Password:", self.new_password)
        layout.addRow("Confirm New Password:", self.confirm_password)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.change_password)
        buttons.rejected.connect(self.reject)
        root.addWidget(card)
        root.addWidget(buttons)

        theme_manager.theme_changed.connect(self._apply_theme)
        self._apply_theme()

    def _apply_theme(self, _theme_name=None):
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QDialog {{ background-color: {colors['bg']}; color: {colors['text']}; }}
            QLabel {{ color: {colors['text']}; background: transparent; }}
            QLabel#dialogTitle {{ font-size: 20px; font-weight: 700; }}
            QLabel#dialogSubtitle {{ color: {colors['text_secondary']}; font-size: 11px; }}
            QFrame#formCard {{
                background-color: {colors['card_bg']};
                border: 1px solid {colors['border']};
                border-radius: 12px;
            }}
            QLineEdit {{
                min-height: 38px;
                padding: 0 12px;
                color: {colors['text']};
                background-color: {colors['input_bg']};
                border: 1px solid {colors['input_border']};
                border-radius: 8px;
            }}
            QLineEdit:focus {{ border-color: {colors['border_hover']}; }}
            QPushButton {{ min-height: 36px; padding: 0 18px; border-radius: 8px; }}
        """)

    def change_password(self):
        old = self.old_password_input.text()
        new = self.new_password.text()
        confirm = self.confirm_password.text()
        if not old or not new:
            QMessageBox.warning(self, "Error", "Please fill all fields.")
            return
        if new != confirm:
            QMessageBox.warning(self, "Error", "New passwords do not match.")
            return
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash, salt FROM users WHERE id=?", (self.user_id,))
        stored_hash, salt = cursor.fetchone()
        # Verify old password
        if salt:
            old_hash = hashlib.pbkdf2_hmac('sha256', old.encode(), bytes.fromhex(salt), 100000).hex()
        else:
            # fallback for old users (only for verification)
            old_hash = hashlib.pbkdf2_hmac('sha256', old.encode(), b'salt_123', 100000).hex()
        if old_hash != stored_hash:
            QMessageBox.warning(self, "Error", "Current password is incorrect.")
            conn.close()
            return
        # Generate new salt and hash
        new_salt = os.urandom(32).hex()
        new_hash = hashlib.pbkdf2_hmac('sha256', new.encode(), bytes.fromhex(new_salt), 100000).hex()
        cursor.execute("UPDATE users SET password_hash=?, salt=?, force_password_change=0 WHERE id=?", 
                       (new_hash, new_salt, self.user_id))
        conn.commit()
        conn.close()
        QMessageBox.information(self, "Success", "Password changed successfully.")
        self.accept()
