# ui/themes/dark_theme.py
# Dark Theme - အပြည့်အစုံ ပြင်ဆင်ချက်

DARK_THEME = """
/* ========== GLOBAL ========== */
* {
    font-family: "Myanmar Text", "Pyidaungsu", "Noto Sans Myanmar", "Segoe UI", "sans-serif";
    font-size: 10pt;
}

QWidget {
    background-color: #262c36;
    color: #eef2f7;
}

QMainWindow {
    background-color: #262c36;
}

/* ========== MENU BAR ========== */
QMenuBar {
    background-color: #242a34;
    color: #eef2f7;
    padding: 4px 8px;
    font-weight: 500;
    border-bottom: 1px solid #3d4655;
}
QMenuBar::item {
    background-color: transparent;
    padding: 4px 12px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: #7482f5;
    color: white;
}

/* ========== MENU POPUP ========== */
QMenu {
    background-color: #2a303b;
    border: 1px solid #3d4655;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    background-color: transparent;
    padding: 6px 24px;
    color: #eef2f7;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #7482f5;
    color: white;
}
QMenu::separator {
    height: 1px;
    background-color: #3d4655;
    margin: 4px 8px;
}

/* ========== HEADER - Dark Theme ========== */
QFrame#header {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6d7df0, stop:1 #5b6bd8);
    border-bottom: none;
}

QFrame#header QLabel#title_label {
    color: white;
    font-size: 13pt;
    font-weight: bold;
    background: transparent;
}

QFrame#header QLabel#menu_bar_clock {
    color: white;
    font-size: 10pt;
    font-weight: 500;
    background: transparent;
}

QFrame#header QLabel#user_label {
    color: white;
    font-size: 10pt;
    font-weight: 500;
    background: transparent;
}

/* ========== SIDEBAR ========== */
QFrame#sidebar {
    background-color: #242a34;
    border-right: 1px solid #3d4655;
}

/* ============================================================
   ✅ COMBOBOX - DARK THEME FIX
   ============================================================ */
QComboBox {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px 8px;
    color: #eef2f7;
    min-height: 20px;
}
QComboBox:hover {
    border: 1px solid #4d596c;
}
QComboBox:focus {
    border: 1px solid #7482f5;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
    background: transparent;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 4px solid #c8d0dc;
    margin-right: 4px;
}

/* ✅ ComboBox Popup (Dropdown) - Dark Theme */
QComboBox QAbstractItemView {
    background-color: #2a303b !important;
    border: 1px solid #3d4655 !important;
    border-radius: 8px !important;
    color: #eef2f7 !important;
    selection-background-color: #7482f5 !important;
    selection-color: white !important;
    outline: none !important;
    padding: 4px !important;
}

/* ✅ ComboBox Popup Items */
QComboBox QAbstractItemView::item {
    background-color: transparent !important;
    color: #eef2f7 !important;
    padding: 6px 10px !important;
    border: none !important;
    border-radius: 2px !important;
    min-height: 24px !important;
}

/* ✅ ComboBox Popup Item - Hover */
QComboBox QAbstractItemView::item:hover {
    background-color: #3d4655 !important;
    color: #eef2f7 !important;
}

/* ✅ ComboBox Popup Item - Selected */
QComboBox QAbstractItemView::item:selected {
    background-color: #7482f5 !important;
    color: white !important;
}

/* ============================================================
   ✅ DATE EDIT (DatePicker) - DARK THEME
   ============================================================ */
QDateEdit {
    background-color: #343c4a;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px 8px;
    color: #eef2f7;
    min-height: 20px;
    selection-background-color: #7482f5;
}
QDateEdit:hover {
    border: 1px solid #4d596c;
}
QDateEdit:focus {
    border: 1px solid #7482f5;
}
QDateEdit::drop-down {
    border: none;
    width: 20px;
    background: transparent;
}
QDateEdit::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 4px solid #c8d0dc;
    margin-right: 4px;
}
QDateEdit:disabled {
    color: #9fa9b8;
}
QDateEdit::up-button, QDateEdit::down-button {
    background-color: transparent;
    border: none;
    width: 16px;
}
QDateEdit::up-button:hover, QDateEdit::down-button:hover {
    background-color: #2a303c;
    border-radius: 2px;
}

/* Calendar Popup - Dark Theme */
QDateEdit QCalendarWidget {
    background-color: #2a303b;
    border: 1px solid #3d4655;
    border-radius: 8px;
    min-width: 350px;
    min-height: 300px;
}

QDateEdit QCalendarWidget QWidget {
    background-color: #2a303b;
}

QDateEdit QCalendarWidget QAbstractItemView {
    background-color: #2a303b;
    border: none;
    border-radius: 4px;
    color: #eef2f7;
    selection-background-color: #7482f5;
    selection-color: white;
}

QDateEdit QCalendarWidget QTableView {
    background-color: #2a303b;
    border: none;
    outline: none;
}

QDateEdit QCalendarWidget QHeaderView::section {
    background-color: #262c36;
    color: #c8d0dc;
    padding: 8px;
    border: none;
    font-weight: 600;
}

QDateEdit QCalendarWidget QToolButton {
    background-color: transparent;
    color: #eef2f7;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: bold;
}
QDateEdit QCalendarWidget QToolButton:hover {
    background-color: #3d4655;
}
QDateEdit QCalendarWidget QToolButton::menu-indicator {
    image: none;
}

QDateEdit QCalendarWidget QSpinBox {
    background-color: #3d4655;
    border: 1px solid #3d4655;
    border-radius: 4px;
    color: #eef2f7;
}
QDateEdit QCalendarWidget QSpinBox:focus {
    border: 1px solid #7482f5;
}

/* Calendar Grid - Dark Theme */
QDateEdit QCalendarWidget QTableView {
    gridline-color: #3d4655;
}

QDateEdit QCalendarWidget QTableView::item {
    padding: 8px 4px;
    border-radius: 4px;
    background-color: transparent;
    color: #eef2f7;
    min-height: 34px;
    min-width: 40px;
}

QDateEdit QCalendarWidget QTableView::item:selected {
    background-color: #7482f5;
    color: white;
}

QDateEdit QCalendarWidget QTableView::item:hover {
    background-color: #3d4655;
    color: #eef2f7;
}

QDateEdit QCalendarWidget QTableView::item:disabled {
    color: #9fa9b8;
}

/* ========== SUMMARY CARDS ========== */
QFrame#summaryCard {
    background-color: #2a303c;
    border: 1px solid #3d4655;
    border-radius: 8px;
}
QFrame#summaryCard:hover {
    background-color: #3d4655;
    border-color: #7482f5;
}

QFrame#summaryCard QLabel {
    border: none;
    background: transparent;
    padding: 0px;
    margin: 0px;
}

QLabel#cardTitle {
    color: #c8d0dc;
    font-size: 10pt;
    font-weight: normal;
    background: transparent;
    border: none;
    padding: 0px;
    margin: 0px;
}

QLabel#cardValue {
    color: #ffffff;
    font-size: 16pt;
    font-weight: bold;
    background: transparent;
    border: none;
    padding: 0px;
    margin: 0px;
}

/* ========== DASHBOARD CARDS ========== */
#dashboardCard {
    background-color: #2a303c;
    border: 1px solid #3d4655;
    border-radius: 8px;
    padding: 8px;
}
#dashboardCard:hover {
    background-color: #3d4655;
    border: 1px solid #7482f5;
}
#cardTitle {
    color: #c8d0dc;
    font-size: 10pt;
    font-weight: normal;
}
#cardValue {
    color: #ffffff;
    font-size: 18pt;
    font-weight: bold;
}

/* ========== BUTTONS ========== */
QPushButton {
    background-color: #7482f5;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: 500;
    min-width: 70px;
    min-height: 24px;
    max-height: 24px;
}
QPushButton:hover {
    background-color: #6d7df0;
}
QPushButton:pressed {
    background-color: #5b6bd8;
}
QPushButton:checked {
    background-color: #6d7df0;
    border: 1px solid #aab3ff;
}
QPushButton:disabled {
    background-color: #3d4655;
    color: #9fa9b8;
}

QTableWidget QPushButton, QDialog QPushButton {
    background-color: #3d4655;
    color: #eef2f7;
    border-radius: 3px;
    padding: 4px 8px;
    min-height: 24px;
    max-height: 24px;
}
QTableWidget QPushButton:hover, QDialog QPushButton:hover {
    background-color: #7482f5;
    color: white;
}

/* ========== TABLES ========== */
QTableWidget {
    background-color: transparent;
    alternate-background-color: transparent;
    selection-background-color: #3d4655;
    selection-color: #eef2f7;
    gridline-color: transparent;
    border: 1px solid #3d4655;
    border-radius: 12px;
}
QTableWidget::viewport {
    background-color: transparent;
    border-radius: 12px;
}
QHeaderView::section {
    background-color: #3d4655;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid #3d4655;
    font-weight: 600;
    color: #c8d0dc;
}
QHeaderView::section:first {
    border-top-left-radius: 12px;
}
QHeaderView::section:last {
    border-top-right-radius: 12px;
}
QTableWidget::item {
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid #3d4655;
    background-color: transparent;
}
QTableWidget::item:selected, QTableWidget::item:hover {
    background-color: #3d4655;
    color: #eef2f7;
}

/* ========== INPUT FIELDS ========== */
QLineEdit, QTextEdit {
    background-color: #343c4a;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px 8px;
    color: #eef2f7;
}
QLineEdit:hover, QTextEdit:hover {
    border: 1px solid #4d596c;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #7482f5;
}
QLineEdit::placeholder {
    color: #9fa9b8;
}

/* ========== SPIN BOX ========== */
QSpinBox, QDoubleSpinBox {
    background-color: #343c4a;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px 8px;
    color: #eef2f7;
    min-height: 20px;
}
QSpinBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #4d596c;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #7482f5;
}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    background-color: transparent;
    width: 20px;
    border: none;
    margin: 1px;
    border-radius: 2px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #2a303c;
}

/* ========== TABS ========== */
QTabWidget,
QTabBar {
    background-color: transparent;
    border: none;
}
QTabWidget::pane {
    background-color: transparent;
    border: none;
    border-radius: 0px;
    top: 0px;
}
QTabWidget::tab-bar {
    left: 0px;
}
QTabBar::tab {
    background-color: transparent;
    padding: 7px 18px;
    margin: 4px 4px 4px 0px;
    border: 1px solid transparent;
    border-radius: 8px;
    color: #c8d0dc;
    font-weight: 600;
}
QTabBar::tab:selected {
    background-color: #2a303b;
    color: #7482f5;
    border: 1px solid #7482f5;
    padding: 7px 18px;
    font-weight: 700;
}
QTabBar::tab:hover:!selected {
    background-color: #2a303c;
    color: #eef2f7;
    border-color: #3d4655;
}

/* ========== GROUP BOX ========== */
QGroupBox {
    font-weight: 600;
    border: 1px solid #3d4655;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    background-color: #2a303b;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    background-color: #2a303b;
    color: #c8d0dc;
}

/* ========== LABELS ========== */
QLabel {
    background-color: transparent;
    color: #eef2f7;
}

/* ========== STATUS BAR ========== */
QStatusBar {
    background-color: #242a34;
    color: #eef2f7;
    border: none;
}
QStatusBar::item {
    border: none;
    background: transparent;
}
QStatusBar QWidget,
QStatusBar QLabel {
    background: transparent;
    border: none;
}

/* ========== SCROLL BARS ========== */
QScrollBar:vertical {
    background-color: transparent;
    width: 10px;
    border-radius: 0px;
    border: none;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background-color: #8d929c;
    border: none;
    border-radius: 3px;
    min-height: 20px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background-color: #5865F2;
}
QScrollBar:horizontal {
    background-color: transparent;
    height: 10px;
    border-radius: 0px;
    border: none;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background-color: #8d929c;
    border: none;
    border-radius: 3px;
    min-width: 20px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #5865F2;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    height: 0px;
    border: none;
    background: transparent;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
    border: none;
}
QScrollBar::up-arrow, QScrollBar::down-arrow,
QScrollBar::left-arrow, QScrollBar::right-arrow {
    image: none;
    width: 0px;
    height: 0px;
}

/* ========== DIALOGS ========== */
QDialog {
    background-color: #2a303b;
}
QMessageBox {
    background-color: #2a303b;
}
QMessageBox QLabel {
    color: #eef2f7;
    min-width: 280px;
    min-height: 38px;
    padding: 2px 0px;
}
QMessageBox QPushButton {
    min-width: 86px;
    min-height: 24px;
    max-height: 24px;
    padding: 4px 16px;
}

/* ========== CHECKBOX & RADIO ========== */
QCheckBox, QRadioButton {
    spacing: 6px;
    color: #eef2f7;
    background-color: transparent;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
}
QCheckBox::indicator:unchecked {
    background-color: #3d4655;
    border: 1px solid #3d4655;
    border-radius: 3px;
}
QCheckBox::indicator:checked {
    background-color: #7482f5;
    border: 1px solid #7482f5;
    border-radius: 3px;
}
QRadioButton::indicator:unchecked {
    background-color: #3d4655;
    border: 1px solid #3d4655;
    border-radius: 8px;
}
QRadioButton::indicator:checked {
    background-color: #7482f5;
    border: 1px solid #7482f5;
    border-radius: 8px;
}

/* ========== PROGRESS BAR ========== */
QProgressBar {
    background-color: #3d4655;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #7482f5;
    border-radius: 4px;
}

/* ========== LIST WIDGET ========== */
QListWidget {
    background-color: #2a303b;
    border: 1px solid #3d4655;
    border-radius: 4px;
    color: #eef2f7;
}
QListWidget::item {
    padding: 4px 8px;
    border-radius: 4px;
}
QListWidget::item:selected {
    background-color: #7482f5;
    color: white;
}
QListWidget::item:hover {
    background-color: #3d4655;
}

/* ========== SCROLL AREA ========== */
QScrollArea {
    background-color: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget,
QScrollArea QWidget#qt_scrollarea_viewport {
    background-color: transparent;
    border: none;
}

/* ========== DISABLED STATE ========== */
QSpinBox:disabled, QDoubleSpinBox:disabled,
QComboBox:disabled, QLineEdit:disabled,
QDateEdit:disabled, QDateTimeEdit:disabled,
QPushButton:disabled {
    color: #9fa9b8;
}

/* ========== TOAST NOTIFICATION ========== */
QFrame#toastFrame {
    background-color: #2a303c;
    border-radius: 8px;
    padding: 12px 16px;
    border-left: 4px solid #7482f5;
}

/* ========== MAIN CONTAINER ========== */
QWidget#mainContainer {
    background-color: transparent;
}

/* ========== CONTENT AREA ========== */
QStackedWidget {
    background-color: transparent;
    border-radius: 0px;
}
"""

