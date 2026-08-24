# ui/themes/dark_theme.py
# Dark Theme - အပြည့်အစုံ ပြင်ဆင်ချက်

DARK_THEME = """
/* ========== GLOBAL ========== */
* {
    font-family: "Segoe UI", "Myanmar Text", "Noto Sans Myanmar", "Pyidaungsu", "sans-serif";
    font-size: 10pt;
}

QWidget {
    background-color: #0d111b;
    color: #edf2ff;
}

QMainWindow {
    background-color: #0d111b;
}

/* ========== MENU BAR ========== */
QMenuBar {
    background-color: #111724;
    color: #edf2ff;
    padding: 4px 8px;
    font-weight: 500;
    border-bottom: 1px solid #293348;
}
QMenuBar::item {
    background-color: transparent;
    padding: 4px 12px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: #6675f5;
    color: white;
}

/* ========== MENU POPUP ========== */
QMenu {
    background-color: #151c2a;
    border: 1px solid #293348;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    background-color: transparent;
    padding: 6px 24px;
    color: #edf2ff;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #6675f5;
    color: white;
}
QMenu::separator {
    height: 1px;
    background-color: #293348;
    margin: 4px 8px;
}

/* ========== HEADER - Dark Theme ========== */
QFrame#header {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #5664df, stop:1 #4654c7);
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
    background-color: #111724;
    border-right: 1px solid #293348;
}

/* ============================================================
   ✅ COMBOBOX - DARK THEME FIX
   ============================================================ */
QComboBox {
    background-color: #293348;
    border: 1px solid #293348;
    border-radius: 4px;
    padding: 5px 8px;
    color: #edf2ff;
    min-height: 20px;
}
QComboBox:focus {
    border: 1px solid #6675f5;
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
    border-top: 4px solid #aab4c8;
    margin-right: 4px;
}

/* ✅ ComboBox Popup (Dropdown) - Dark Theme */
QComboBox QAbstractItemView {
    background-color: #151c2a !important;
    border: 1px solid #293348 !important;
    border-radius: 4px !important;
    color: #edf2ff !important;
    selection-background-color: #6675f5 !important;
    selection-color: white !important;
    outline: none !important;
    padding: 4px !important;
}

/* ✅ ComboBox Popup Items */
QComboBox QAbstractItemView::item {
    background-color: transparent !important;
    color: #edf2ff !important;
    padding: 6px 10px !important;
    border: none !important;
    border-radius: 2px !important;
    min-height: 24px !important;
}

/* ✅ ComboBox Popup Item - Hover */
QComboBox QAbstractItemView::item:hover {
    background-color: #293348 !important;
    color: #edf2ff !important;
}

/* ✅ ComboBox Popup Item - Selected */
QComboBox QAbstractItemView::item:selected {
    background-color: #6675f5 !important;
    color: white !important;
}

/* ============================================================
   ✅ DATE EDIT (DatePicker) - DARK THEME
   ============================================================ */
QDateEdit {
    background-color: #293348;
    border: 1px solid #293348;
    border-radius: 4px;
    padding: 5px 8px;
    color: #edf2ff;
    min-height: 20px;
    selection-background-color: #6675f5;
}
QDateEdit:focus {
    border: 1px solid #6675f5;
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
    border-top: 4px solid #aab4c8;
    margin-right: 4px;
}
QDateEdit:disabled {
    color: #657089;
}
QDateEdit::up-button, QDateEdit::down-button {
    background-color: transparent;
    border: none;
    width: 16px;
}
QDateEdit::up-button:hover, QDateEdit::down-button:hover {
    background-color: #192232;
    border-radius: 2px;
}

/* Calendar Popup - Dark Theme */
QDateEdit QCalendarWidget {
    background-color: #151c2a;
    border: 1px solid #293348;
    border-radius: 8px;
    min-width: 350px;
    min-height: 300px;
}

QDateEdit QCalendarWidget QWidget {
    background-color: #151c2a;
}

QDateEdit QCalendarWidget QAbstractItemView {
    background-color: #151c2a;
    border: none;
    border-radius: 4px;
    color: #edf2ff;
    selection-background-color: #6675f5;
    selection-color: white;
}

QDateEdit QCalendarWidget QTableView {
    background-color: #151c2a;
    border: none;
    outline: none;
}

QDateEdit QCalendarWidget QHeaderView::section {
    background-color: #111824;
    color: #aab4c8;
    padding: 8px;
    border: none;
    font-weight: 600;
}

QDateEdit QCalendarWidget QToolButton {
    background-color: transparent;
    color: #edf2ff;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: bold;
}
QDateEdit QCalendarWidget QToolButton:hover {
    background-color: #293348;
}
QDateEdit QCalendarWidget QToolButton::menu-indicator {
    image: none;
}

QDateEdit QCalendarWidget QSpinBox {
    background-color: #293348;
    border: 1px solid #293348;
    border-radius: 4px;
    color: #edf2ff;
}
QDateEdit QCalendarWidget QSpinBox:focus {
    border: 1px solid #6675f5;
}

/* Calendar Grid - Dark Theme */
QDateEdit QCalendarWidget QTableView {
    gridline-color: #293348;
}

QDateEdit QCalendarWidget QTableView::item {
    padding: 8px 4px;
    border-radius: 4px;
    background-color: transparent;
    color: #edf2ff;
    min-height: 34px;
    min-width: 40px;
}

QDateEdit QCalendarWidget QTableView::item:selected {
    background-color: #6675f5;
    color: white;
}

QDateEdit QCalendarWidget QTableView::item:hover {
    background-color: #293348;
    color: #edf2ff;
}

QDateEdit QCalendarWidget QTableView::item:disabled {
    color: #657089;
}

/* ========== SUMMARY CARDS ========== */
QFrame#summaryCard {
    background-color: #192232;
    border: 1px solid #293348;
    border-radius: 10px;
}
QFrame#summaryCard:hover {
    background-color: #293348;
    border-color: #6675f5;
}

QFrame#summaryCard QLabel {
    border: none;
    background: transparent;
    padding: 0px;
    margin: 0px;
}

QLabel#cardTitle {
    color: #aab4c8;
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
    background-color: #192232;
    border: 1px solid #293348;
    border-radius: 12px;
    padding: 8px;
}
#dashboardCard:hover {
    background-color: #293348;
    border: 1px solid #6675f5;
}
#cardTitle {
    color: #aab4c8;
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
    background-color: #6675f5;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: 500;
    min-width: 70px;
}
QPushButton:hover {
    background-color: #5664df;
}
QPushButton:pressed {
    background-color: #4654c7;
}
QPushButton:checked {
    background-color: #5664df;
    border: 1px solid #7983f5;
}
QPushButton:disabled {
    background-color: #293348;
    color: #657089;
}

QTableWidget QPushButton, QDialog QPushButton {
    background-color: #293348;
    color: #edf2ff;
    border-radius: 3px;
    padding: 4px 8px;
}
QTableWidget QPushButton:hover, QDialog QPushButton:hover {
    background-color: #6675f5;
    color: white;
}

/* ========== TABLES ========== */
QTableWidget {
    background-color: #151c2a;
    alternate-background-color: #192232;
    selection-background-color: #293348;
    selection-color: #edf2ff;
    gridline-color: #293348;
    border: 1px solid #293348;
    border-radius: 6px;
}
QHeaderView::section {
    background-color: #111824;
    padding: 8px;
    border: none;
    font-weight: 600;
    color: #aab4c8;
}
QTableWidget::item {
    padding: 6px;
}

/* ========== INPUT FIELDS ========== */
QLineEdit, QTextEdit {
    background-color: #293348;
    border: 1px solid #293348;
    border-radius: 4px;
    padding: 5px 8px;
    color: #edf2ff;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #6675f5;
}
QLineEdit::placeholder {
    color: #657089;
}

/* ========== SPIN BOX ========== */
QSpinBox, QDoubleSpinBox {
    background-color: #293348;
    border: 1px solid #293348;
    border-radius: 4px;
    padding: 5px 8px;
    color: #edf2ff;
    min-height: 20px;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #6675f5;
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
    background-color: #192232;
}

/* ========== TABS ========== */
QTabWidget::pane {
    background-color: #151c2a;
    border: 1px solid #293348;
    border-radius: 6px;
}
QTabBar::tab {
    background-color: transparent;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #aab4c8;
}
QTabBar::tab:selected {
    background-color: #293348;
    color: #ffffff;
    border-bottom: 2px solid #6675f5;
}
QTabBar::tab:hover:!selected {
    background-color: #192232;
    color: #edf2ff;
}

/* ========== GROUP BOX ========== */
QGroupBox {
    font-weight: 600;
    border: 1px solid #293348;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    background-color: #151c2a;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    background-color: #151c2a;
    color: #aab4c8;
}

/* ========== LABELS ========== */
QLabel {
    background-color: transparent;
    color: #edf2ff;
}

/* ========== STATUS BAR ========== */
QStatusBar {
    background-color: #111824;
    color: #aab4c8;
    border-top: 1px solid #293348;
}

/* ========== SCROLL BARS ========== */
QScrollBar:vertical {
    background: #151c2a;
    width: 12px;
    border-radius: 6px;
}
QScrollBar::handle:vertical {
    background: #293348;
    border-radius: 6px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #6675f5;
}
QScrollBar:horizontal {
    background: #151c2a;
    height: 12px;
    border-radius: 6px;
}
QScrollBar::handle:horizontal {
    background: #293348;
    border-radius: 6px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover {
    background: #6675f5;
}

/* ========== DIALOGS ========== */
QDialog {
    background-color: #151c2a;
}
QMessageBox {
    background-color: #151c2a;
}
QMessageBox QLabel {
    color: #edf2ff;
}
QMessageBox QPushButton {
    min-width: 70px;
    padding: 5px 12px;
}

/* ========== CHECKBOX & RADIO ========== */
QCheckBox, QRadioButton {
    spacing: 6px;
    color: #edf2ff;
    background-color: transparent;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
}
QCheckBox::indicator:unchecked {
    background-color: #293348;
    border: 1px solid #293348;
    border-radius: 3px;
}
QCheckBox::indicator:checked {
    background-color: #6675f5;
    border: 1px solid #6675f5;
    border-radius: 3px;
}
QRadioButton::indicator:unchecked {
    background-color: #293348;
    border: 1px solid #293348;
    border-radius: 8px;
}
QRadioButton::indicator:checked {
    background-color: #6675f5;
    border: 1px solid #6675f5;
    border-radius: 8px;
}

/* ========== PROGRESS BAR ========== */
QProgressBar {
    background-color: #293348;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #6675f5;
    border-radius: 4px;
}

/* ========== LIST WIDGET ========== */
QListWidget {
    background-color: #151c2a;
    border: 1px solid #293348;
    border-radius: 4px;
    color: #edf2ff;
}
QListWidget::item {
    padding: 4px 8px;
    border-radius: 4px;
}
QListWidget::item:selected {
    background-color: #6675f5;
    color: white;
}
QListWidget::item:hover {
    background-color: #293348;
}

/* ========== SCROLL AREA ========== */
QScrollArea {
    background-color: transparent;
    border: none;
}

/* ========== DISABLED STATE ========== */
QSpinBox:disabled, QDoubleSpinBox:disabled,
QComboBox:disabled, QLineEdit:disabled,
QDateEdit:disabled, QDateTimeEdit:disabled,
QPushButton:disabled {
    color: #657089;
}

/* ========== TOAST NOTIFICATION ========== */
QFrame#toastFrame {
    background-color: #192232;
    border-radius: 8px;
    padding: 12px 16px;
    border-left: 4px solid #6675f5;
}

/* ========== MAIN CONTAINER ========== */
QWidget#mainContainer {
    background-color: #0d111b;
}

/* ========== CONTENT AREA ========== */
QStackedWidget {
    background-color: #151c2a;
    border-radius: 12px;
}
"""
