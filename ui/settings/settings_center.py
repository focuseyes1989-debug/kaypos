from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtPrintSupport import QPrinterInfo
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from models.database import connect_db
from ui.settings.backup_reset_setting import BackupResetSettingWidget
from ui.settings.database_connection_setting import DatabaseConnectionSettingWidget
from ui.settings.general_setting import GeneralSettingWidget
from ui.settings.performance_setting import PerformanceSettingWidget
from ui.settings.print_setting import PrintSettingWidget
from ui.settings.receipt_setting import ReceiptSettingWidget
from ui.settings.regional_setting import RegionalSettingWidget
from ui.settings.restaurant_setting import RestaurantSettingWidget
from ui.settings.telegram_setting import TelegramSettingWidget
from ui.settings.update_setting import UpdateSettingWidget
from ui.settings.users_setting import UsersSettingWidget
from ui.settings.youtube_setting import YouTubeSettingWidget
from ui.settings.zkteco_setting import ZKTecoSettingWidget
from ui.themes.theme_manager import get_theme_colors, is_dark_theme, theme_manager
from utils.language import lang
from utils.permissions import Permission, PermissionManager


class SettingsOverviewCard(QPushButton):
    def __init__(self, title, value, action_text, parent=None):
        super().__init__(parent)
        self.title_label = title
        self.value_label = value
        self.action_label = action_text
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(92)
        self._apply_text()
        self.update_theme()

    def update_theme(self):
        colors = get_theme_colors()
        self.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                background: {colors.get('card_bg', '#ffffff')};
                border: 1px solid {colors.get('border', '#d9dee7')};
                border-radius: 8px;
                padding: 12px 14px;
                color: {colors.get('text', '#1f2937')};
            }}
            QPushButton:hover {{
                background: {colors.get('card_hover', colors.get('bg_hover', '#f8fafc'))};
                border-color: {colors.get('border_hover', '#4a6cf7')};
            }}
            QPushButton:disabled {{
                background: {colors.get('bg_hover', '#f3f4f6')};
                border-color: {colors.get('border', '#d9dee7')};
                color: {colors.get('text_secondary', '#6b7280')};
            }}
        """)

    def set_value(self, value):
        self.value_label = value
        self._apply_text()

    def _apply_text(self):
        self.setText(f"{self.title_label}\n{self.value_label}\n{self.action_label}")


class SettingsCenterWidget(QWidget):
    receipt_settings_changed = pyqtSignal()
    general_settings_changed = pyqtSignal()
    print_settings_changed = pyqtSignal()
    currency_changed = pyqtSignal()

    def __init__(self, current_user_role="admin", user_id=None, parent=None):
        super().__init__(parent)
        self.current_user_role = current_user_role
        self.user_id = user_id
        self.pages = []
        self.page_widgets = {}
        self.nav_items = {}
        self.overview_cards = {}
        self.setup_ui()
        self.build_pages()
        self.apply_style()
        self.apply_permissions()
        self.refresh_overview()
        theme_manager.theme_changed.connect(self.on_theme_changed)
        lang.language_changed.connect(self.retranslateUi)

    def setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("settingsCenterShell")
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("settingsCenterSidebar")
        sidebar.setFixedWidth(260)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 14, 14, 14)
        sidebar_layout.setSpacing(10)

        self.title_label = QLabel("Settings")
        self.title_label.setObjectName("settingsCenterTitle")
        sidebar_layout.addWidget(self.title_label)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search settings...")
        self.search_edit.textChanged.connect(self.filter_pages)
        sidebar_layout.addWidget(self.search_edit)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("settingsCenterNav")
        self.nav_list.currentRowChanged.connect(self.change_page)
        sidebar_layout.addWidget(self.nav_list, 1)

        self.permission_note = QLabel("")
        self.permission_note.setWordWrap(True)
        self.permission_note.setObjectName("settingsCenterPermissionNote")
        sidebar_layout.addWidget(self.permission_note)

        self.stack = QStackedWidget()
        self.stack.setObjectName("settingsCenterStack")

        shell_layout.addWidget(sidebar)
        shell_layout.addWidget(self.stack, 1)
        root.addWidget(shell)
        self.apply_style()

    def apply_style(self):
        colors = get_theme_colors()
        dark = is_dark_theme()
        bg = colors.get("bg", "#f3f6fb")
        card_bg = colors.get("card_bg", "#ffffff")
        card_hover = colors.get("card_hover", colors.get("bg_hover", "#f8fafc"))
        text = colors.get("text", "#111827")
        text_secondary = colors.get("text_secondary", "#6b7280")
        border = colors.get("border", "#d9dee7")
        border_hover = colors.get("border_hover", "#4a6cf7")
        input_bg = colors.get("input_bg", card_bg)
        input_border = colors.get("input_border", border)
        selected_bg = "#323a5f" if dark else "#e9efff"
        selected_text = "#ffffff" if dark else "#1f3fb7"

        self.setStyleSheet(f"""
            QFrame#settingsCenterShell {{
                background: {bg};
            }}
            QFrame#settingsCenterSidebar {{
                background: {card_bg};
                border-right: 1px solid {border};
            }}
            QLabel#settingsCenterTitle {{
                color: {text};
                font-size: 18pt;
                font-weight: 800;
                background: transparent;
            }}
            QLabel#settingsCenterPermissionNote {{
                color: {text_secondary};
                font-size: 9pt;
                background: transparent;
            }}
            QLineEdit {{
                background: {input_bg};
                border: 1px solid {input_border};
                border-radius: 6px;
                padding: 8px 10px;
                color: {text};
                selection-background-color: {border_hover};
            }}
            QLineEdit:focus {{
                border-color: {border_hover};
            }}
            QListWidget#settingsCenterNav {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget#settingsCenterNav::item {{
                min-height: 38px;
                padding: 8px 10px;
                border-radius: 6px;
                color: {text};
            }}
            QListWidget#settingsCenterNav::item:selected {{
                background: {selected_bg};
                color: {selected_text};
                font-weight: 700;
            }}
            QListWidget#settingsCenterNav::item:hover {{
                background: {card_hover};
            }}
            QStackedWidget#settingsCenterStack {{
                background: {bg};
            }}
        """)

        if hasattr(self, "overview_header"):
            self.overview_header.setStyleSheet(
                f"font-size: 18pt; font-weight: 800; color: {text}; background: transparent;"
            )
        for card in getattr(self, "overview_cards", {}).values():
            card.update_theme()

    def build_pages(self):
        self.add_page("overview", "Overview", "overview status quick summary", self.create_overview_page())

        self.general_payment_tab = self.create_general_section(["payments"])
        self.add_page("general_payments", "Payment Types", "payment method cash card mobile money", self.general_payment_tab)

        self.general_tax_discount_tab = self.create_general_section(["tax", "discount"])
        self.add_page("general_tax_discount", "Tax & Discount", "tax discount percentage fixed manual", self.general_tax_discount_tab)

        self.general_loyalty_tab = self.create_general_section(["loyalty"])
        self.add_page("general_loyalty", "Loyalty", "loyalty points reward expiry value", self.general_loyalty_tab)

        self.general_appearance_tab = self.create_general_section(["appearance"])
        self.add_page("general_appearance", "Appearance", "theme resolution sale mode system theme", self.general_appearance_tab)

        self.receipt_branding_tab = self.create_receipt_section(["business", "branding"])
        self.add_page("receipt_branding", "Business & Branding", "shop name phone address logo qr code", self.receipt_branding_tab)

        self.receipt_text_tab = self.create_receipt_section(["text"])
        self.add_page("receipt_text", "Receipt Text", "receipt header footer customer name", self.receipt_text_tab)

        self.receipt_template_tab = self.create_receipt_section(["template"])
        self.add_page("receipt_template", "Receipt Template", "template logo invoice subtotal tax thank you line width preview", self.receipt_template_tab)

        self.print_tab = PrintSettingWidget()
        self.add_page("print", "Print", "printer paper size print quality cash drawer receipt printer", self.print_tab)

        self.restaurant_tab = RestaurantSettingWidget()
        self.add_page("restaurant", "Restaurant", "restaurant tables dining takeaway", self.restaurant_tab)

        self.regional_tab = RegionalSettingWidget()
        self.add_page("regional", "Regional", "language currency region money", self.regional_tab)

        self.update_tab = UpdateSettingWidget(user_id=self.user_id)
        self.add_page("update", "Update", "version update launcher release", self.update_tab)

        self.telegram_tab = TelegramSettingWidget()
        self.add_page("telegram", "Telegram", "telegram bot token chat notification", self.telegram_tab)

        self.youtube_tab = YouTubeSettingWidget()
        self.add_page("youtube", "YouTube", "youtube customer display video", self.youtube_tab)

        self.performance_tab = PerformanceSettingWidget()
        self.add_page("performance", "Performance", "performance low end page size thumbnails debounce", self.performance_tab)

        self.database_connection_tab = DatabaseConnectionSettingWidget()
        self.add_page("database", "Database", "database connection cloud postgres sqlite", self.database_connection_tab)

        self.zkteco_tab = ZKTecoSettingWidget()
        self.add_page("zkteco", "ZKTeco Devices", "attendance fingerprint device ip port comm key mapping sync", self.zkteco_tab)

        if self.user_id and PermissionManager.user_has_permission(self.user_id, Permission.BACKUP):
            self.backup_tab = BackupResetSettingWidget(user_id=self.user_id)
            self.add_page("backup", "Backup & Reset", "backup restore factory reset danger admin", self.backup_tab)

        if self.user_id and PermissionManager.user_has_permission(self.user_id, Permission.VIEW_USERS):
            self.users_tab = UsersSettingWidget(user_id=self.user_id)
            self.add_page("users", "Users", "users roles permissions password admin", self.users_tab)

        for widget in (
            self.general_payment_tab,
            self.general_tax_discount_tab,
            self.general_loyalty_tab,
            self.general_appearance_tab,
        ):
            widget.settings_saved.connect(self.general_settings_changed)
        for widget in (
            self.receipt_branding_tab,
            self.receipt_text_tab,
            self.receipt_template_tab,
        ):
            widget.receipt_settings_changed.connect(self._on_receipt_settings_changed)
        self.print_tab.print_settings_changed.connect(self._on_print_settings_changed)
        self.regional_tab.currency_changed.connect(self.currency_changed)

        if self.nav_list.count():
            self.nav_list.setCurrentRow(0)

    def add_page(self, key, title, keywords, widget):
        item = QListWidgetItem(title)
        item.setData(Qt.ItemDataRole.UserRole, key)
        self.nav_list.addItem(item)
        self.nav_items[key] = item
        self.pages.append({"key": key, "title": title, "keywords": keywords, "widget": widget})
        self.page_widgets[key] = widget
        self.stack.addWidget(widget)

    def create_general_section(self, sections):
        widget = GeneralSettingWidget()
        widget.set_visible_sections(sections)
        return widget

    def create_receipt_section(self, sections):
        widget = ReceiptSettingWidget()
        widget.set_visible_sections(sections)
        return widget

    def create_overview_page(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24, 20, 24, 24)
        page_layout.setSpacing(14)

        self.overview_header = QLabel("Settings Overview")
        page_layout.addWidget(self.overview_header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        cards = [
            ("receipt_branding", "Receipt", "Logo, QR, template", "Open Receipt"),
            ("print", "Print", "Printer not selected", "Open Print"),
            ("regional", "Regional", "Language and currency", "Open Regional"),
            ("backup", "Backup", "Backup status", "Open Backup"),
            ("users", "Users", "Roles and permissions", "Open Users"),
            ("performance", "Performance", "Low-end mode", "Open Performance"),
        ]
        for index, (key, title, value, action) in enumerate(cards):
            card = SettingsOverviewCard(title, value, action)
            card.clicked.connect(lambda checked=False, page_key=key: self.select_page(page_key))
            self.overview_cards[key] = card
            grid.addWidget(card, index // 2, index % 2)
        page_layout.addLayout(grid)
        page_layout.addStretch()
        return page

    def select_page(self, key):
        item = self.nav_items.get(key)
        if item and not item.isHidden():
            self.nav_list.setCurrentItem(item)

    def change_page(self, row):
        if row < 0 or row >= self.stack.count():
            return
        self.stack.setCurrentIndex(row)

    def filter_pages(self, text):
        query = text.strip().lower()
        first_visible = None
        for index, page in enumerate(self.pages):
            item = self.nav_list.item(index)
            haystack = f"{page['title']} {page['keywords']}".lower()
            visible = not query or query in haystack
            item.setHidden(not visible)
            if visible and first_visible is None:
                first_visible = item
        if first_visible and (self.nav_list.currentItem() is None or self.nav_list.currentItem().isHidden()):
            self.nav_list.setCurrentItem(first_visible)

    def apply_permissions(self):
        if not self.user_id:
            return
        can_edit_settings = PermissionManager.user_has_permission(self.user_id, Permission.EDIT_SETTINGS)
        if can_edit_settings:
            self.permission_note.setText("")
            return

        self.permission_note.setText("Read-only: you do not have permission to edit settings.")
        read_only_keys = [
            "general_payments", "general_tax_discount", "general_loyalty", "general_appearance",
            "receipt_branding", "receipt_text", "receipt_template",
            "print", "restaurant", "regional", "telegram", "youtube", "performance", "database",
        ]
        for key in read_only_keys:
            widget = self.page_widgets.get(key)
            if widget:
                widget.setEnabled(False)
                widget.setToolTip("You don't have permission to edit settings")

    def refresh_overview(self):
        settings = self._load_settings()
        logo_status = "Logo set" if settings.get("shop_logo") else "Logo not set"
        qr_status = "QR set" if settings.get("shop_qr_code") else "QR not set"
        self._set_card_value("receipt_branding", f"{logo_status} | {qr_status}")

        printer = settings.get("receipt_printer_name") or "Windows default"
        self._set_card_value("print", printer)

        language = settings.get("language") or "en"
        currency = settings.get("currency") or "Kyats (Ks)"
        self._set_card_value("regional", f"{language} | {currency}")

        backup = "Auto backup on" if settings.get("auto_backup_enabled") == "1" else "Auto backup off"
        self._set_card_value("backup", backup)

        performance = "Low-end mode on" if settings.get("performance_low_end_mode") == "1" else "Standard mode"
        self._set_card_value("performance", performance)

        if "users" in self.overview_cards:
            self._set_card_value("users", "Manage accounts")

    def _set_card_value(self, key, value):
        card = self.overview_cards.get(key)
        if card:
            card.set_value(value)
            card.setEnabled(key in self.nav_items)

    def _load_settings(self):
        keys = [
            "shop_logo", "shop_qr_code", "receipt_printer_name", "language",
            "currency", "auto_backup_enabled", "performance_low_end_mode",
        ]
        values = {}
        try:
            conn = connect_db()
            cursor = conn.cursor()
            placeholders = ",".join("?" for _ in keys)
            cursor.execute(f"SELECT key, value FROM settings WHERE key IN ({placeholders})", keys)
            values = dict(cursor.fetchall())
            conn.close()
        except Exception:
            pass
        try:
            from services.network_printer_client import network_printer_settings

            network = network_printer_settings()
            if network.get("receipt_printer_mode") == "network":
                target = network.get("network_printer_name") or "not selected"
                values["receipt_printer_name"] = f"Network: {target}"
        except Exception:
            pass
        if not values.get("receipt_printer_name"):
            default_printer = QPrinterInfo.defaultPrinter()
            if not default_printer.isNull():
                values["receipt_printer_name"] = default_printer.printerName()
        return values

    def _on_receipt_settings_changed(self):
        self.refresh_overview()
        self.receipt_settings_changed.emit()

    def _on_print_settings_changed(self):
        self.refresh_overview()
        self.print_settings_changed.emit()

    def retranslateUi(self):
        self.title_label.setText("Settings")
        if lang.get_current() == "my":
            self.search_edit.setPlaceholderText("Setting များရှာရန်...")
        else:
            self.search_edit.setPlaceholderText("Search settings...")
        for page in self.pages:
            widget = page["widget"]
            if hasattr(widget, "retranslateUi"):
                widget.retranslateUi()
        if hasattr(self, "overview_header"):
            self.overview_header.setText("Settings Overview")

    def on_theme_changed(self, theme_name):
        self.apply_style()
        for page in self.pages:
            widget = page["widget"]
            for method_name in ("update_theme", "on_theme_changed", "apply_theme_style"):
                method = getattr(widget, method_name, None)
                if not callable(method):
                    continue
                try:
                    method(theme_name)
                except TypeError:
                    try:
                        method()
                    except Exception:
                        pass
                except Exception:
                    pass
                break
        self.update()

    def update_theme(self):
        self.on_theme_changed(theme_manager.get_current_theme())

    def showEvent(self, event):
        self.reload_settings()
        super().showEvent(event)

    def reload_settings(self):
        reloaders = [
            ("general_payment_tab", ["load_payment_types"]),
            ("general_tax_discount_tab", ["load_tax_settings", "load_discount_settings"]),
            ("general_loyalty_tab", ["load_loyalty_settings"]),
            ("general_appearance_tab", ["load_appearance_settings"]),
            ("receipt_branding_tab", ["load_receipt_settings"]),
            ("receipt_text_tab", ["load_receipt_settings"]),
            ("receipt_template_tab", ["load_receipt_settings"]),
            ("print_tab", ["load_print_settings"]),
            ("restaurant_tab", ["load_settings", "load_tables"]),
            ("regional_tab", ["load_currency_setting", "load_language_setting"]),
            ("update_tab", ["load_current_version"]),
            ("telegram_tab", ["load_settings"]),
            ("youtube_tab", ["load_settings"]),
            ("performance_tab", ["load_settings"]),
            ("database_connection_tab", ["load_settings"]),
        ]
        for attr, methods in reloaders:
            widget = getattr(self, attr, None)
            if not widget:
                continue
            for method_name in methods:
                method = getattr(widget, method_name, None)
                if callable(method):
                    try:
                        method()
                    except Exception:
                        pass
        self.refresh_overview()


class SettingsPage(SettingsCenterWidget):
    pass
