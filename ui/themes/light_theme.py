# ui/themes/light_theme.py
# Light Theme - အပြည့်အစုံ ပြင်ဆင်ချက်

LIGHT_THEME = """
/* ========== GLOBAL ========== */
* {
    font-family: "Segoe UI", "Myanmar Text", "Pyidaungsu", "Noto Sans Myanmar", "sans-serif";
    font-size: 10pt;
}

QWidget {
    background-color: #f2f3f5;
    color: #2e3338;
}

QMainWindow {
    background-color: #f2f3f5;
}

/* ========== MENU BAR ========== */
QMenuBar {
    background-color: #ffffff;
    color: #2e3338;
    padding: 4px 8px;
    font-weight: 500;
    border-bottom: 1px solid #d0d3d9;
}
QMenuBar::item {
    background-color: transparent;
    padding: 4px 12px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: #5865f2;
    color: white;
}

/* ========== MENU POPUP ========== */
QMenu {
    background-color: #ffffff;
    border: 1px solid #d0d3d9;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    background-color: transparent;
    padding: 6px 24px;
    color: #2e3338;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #5865f2;
    color: white;
}
QMenu::separator {
    height: 1px;
    background-color: #d0d3d9;
    margin: 4px 8px;
}

/* ========== HEADER - Light Theme ========== */
QFrame#header {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4752c4, stop:1 #3c45a3);
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
    background-color: #ffffff;
    border-right: 1px solid #d0d3d9;
}

/* ============================================================
   ✅ COMBOBOX - LIGHT THEME FIX
   ============================================================ */
QComboBox {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px 8px;
    color: #2e3338;
    min-height: 20px;
}
QComboBox:hover {
    border: 1px solid #d0d3d9;
}
QComboBox:focus {
    border: 1px solid #5865f2;
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
    border-top: 4px solid #4a4f55;
    margin-right: 4px;
}

/* ✅ ComboBox Popup (Dropdown) - Light Theme */
QComboBox QAbstractItemView {
    background-color: #ffffff !important;
    border: 1px solid #d0d3d9 !important;
    border-radius: 8px !important;
    color: #2e3338 !important;
    selection-background-color: #5865f2 !important;
    selection-color: white !important;
    outline: none !important;
    padding: 4px !important;
}

/* ✅ ComboBox Popup Items */
QComboBox QAbstractItemView::item {
    background-color: transparent !important;
    color: #2e3338 !important;
    padding: 6px 10px !important;
    border: none !important;
    border-radius: 2px !important;
    min-height: 24px !important;
}

/* ✅ ComboBox Popup Item - Hover */
QComboBox QAbstractItemView::item:hover {
    background-color: #ebedef !important;
    color: #2e3338 !important;
}

/* ✅ ComboBox Popup Item - Selected */
QComboBox QAbstractItemView::item:selected {
    background-color: #5865f2 !important;
    color: white !important;
}

/* ============================================================
   ✅ DATE EDIT (DatePicker) - LIGHT THEME
   ============================================================ */
QDateEdit {
    background-color: #f8f9fa;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px 8px;
    color: #2e3338;
    min-height: 20px;
    selection-background-color: #5865f2;
}
QDateEdit:hover {
    border: 1px solid #d0d3d9;
}
QDateEdit:focus {
    border: 1px solid #5865f2;
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
    border-top: 4px solid #4a4f55;
    margin-right: 4px;
}
QDateEdit:disabled {
    color: #8e9297;
}
QDateEdit::up-button, QDateEdit::down-button {
    background-color: transparent;
    border: none;
    width: 16px;
}
QDateEdit::up-button:hover, QDateEdit::down-button:hover {
    background-color: #ebedef;
    border-radius: 2px;
}

/* Calendar Popup - Light Theme */
QDateEdit QCalendarWidget {
    background-color: #ffffff;
    border: 1px solid #d0d3d9;
    border-radius: 8px;
    min-width: 350px;
    min-height: 300px;
}

QDateEdit QCalendarWidget QWidget {
    background-color: #ffffff;
}

QDateEdit QCalendarWidget QAbstractItemView {
    background-color: #ffffff;
    border: none;
    border-radius: 4px;
    color: #2e3338;
    selection-background-color: #5865f2;
    selection-color: white;
}

QDateEdit QCalendarWidget QTableView {
    background-color: #ffffff;
    border: none;
    outline: none;
}

QDateEdit QCalendarWidget QHeaderView::section {
    background-color: #f2f3f5;
    color: #4a4f55;
    padding: 8px;
    border: none;
    font-weight: 600;
}

QDateEdit QCalendarWidget QToolButton {
    background-color: transparent;
    color: #2e3338;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: bold;
}
QDateEdit QCalendarWidget QToolButton:hover {
    background-color: #ebedef;
}
QDateEdit QCalendarWidget QToolButton::menu-indicator {
    image: none;
}

QDateEdit QCalendarWidget QSpinBox {
    background-color: #ffffff;
    border: 1px solid #d0d3d9;
    border-radius: 4px;
    color: #2e3338;
}
QDateEdit QCalendarWidget QSpinBox:focus {
    border: 1px solid #5865f2;
}

/* Calendar Grid - Light Theme */
QDateEdit QCalendarWidget QTableView {
    gridline-color: #d0d3d9;
}

QDateEdit QCalendarWidget QTableView::item {
    padding: 8px 4px;
    border-radius: 4px;
    background-color: transparent;
    color: #2e3338;
    min-height: 34px;
    min-width: 40px;
}

QDateEdit QCalendarWidget QTableView::item:selected {
    background-color: #5865f2;
    color: white;
}

QDateEdit QCalendarWidget QTableView::item:hover {
    background-color: #ebedef;
    color: #2e3338;
}

QDateEdit QCalendarWidget QTableView::item:disabled {
    color: #8e9297;
}

/* ========== SUMMARY CARDS ========== */
QFrame#summaryCard {
    background-color: #ffffff;
    border: 1px solid #d0d3d9;
    border-radius: 8px;
}
QFrame#summaryCard:hover {
    background-color: #f8f9fa;
    border-color: #5865f2;
}

QFrame#summaryCard QLabel {
    border: none;
    background: transparent;
    padding: 0px;
    margin: 0px;
}

QLabel#cardTitle {
    color: #4a4f55;
    font-size: 10pt;
    font-weight: normal;
    background: transparent;
    border: none;
    padding: 0px;
    margin: 0px;
}

QLabel#cardValue {
    color: #2e3338;
    font-size: 16pt;
    font-weight: bold;
    background: transparent;
    border: none;
    padding: 0px;
    margin: 0px;
}

/* ========== DASHBOARD CARDS ========== */
#dashboardCard {
    background-color: #ffffff;
    border: 1px solid #d0d3d9;
    border-radius: 8px;
    padding: 8px;
}
#dashboardCard:hover {
    background-color: #f8f9fa;
    border: 1px solid #5865f2;
}
#cardTitle {
    color: #4a4f55;
    font-size: 10pt;
    font-weight: normal;
}
#cardValue {
    color: #2e3338;
    font-size: 18pt;
    font-weight: bold;
}

/* ========== BUTTONS ========== */
QPushButton {
    background-color: #5865f2;
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
    background-color: #4752c4;
}
QPushButton:pressed {
    background-color: #3c45a3;
}
QPushButton:checked {
    background-color: #4752c4;
    border: 1px solid #7983f5;
}
QPushButton:disabled {
    background-color: #d0d3d9;
    color: #8e9297;
}

QTableWidget QPushButton, QDialog QPushButton {
    background-color: #ebedef;
    color: #2e3338;
    border-radius: 3px;
    padding: 4px 8px;
    min-height: 24px;
    max-height: 24px;
}
QTableWidget QPushButton:hover, QDialog QPushButton:hover {
    background-color: #5865f2;
    color: white;
}

/* ========== TABLES ========== */
QTableWidget {
    background-color: transparent;
    alternate-background-color: transparent;
    selection-background-color: #ebedef;
    selection-color: #2e3338;
    gridline-color: transparent;
    border: 1px solid #d0d3d9;
    border-radius: 12px;
}
QTableWidget::viewport {
    background-color: transparent;
    border-radius: 12px;
}
QHeaderView::section {
    background-color: #ebedef;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid #d0d3d9;
    font-weight: 600;
    color: #4a4f55;
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
    border-bottom: 1px solid #d0d3d9;
    background-color: transparent;
}
QTableWidget::item:selected, QTableWidget::item:hover {
    background-color: #ebedef;
    color: #2e3338;
}

/* ========== INPUT FIELDS ========== */
QLineEdit, QTextEdit {
    background-color: #f8f9fa;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px 8px;
    color: #2e3338;
}
QLineEdit:hover, QTextEdit:hover {
    border: 1px solid #d0d3d9;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #5865f2;
}
QLineEdit::placeholder {
    color: #8e9297;
}

/* ========== SPIN BOX ========== */
QSpinBox, QDoubleSpinBox {
    background-color: #f8f9fa;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px 8px;
    color: #2e3338;
    min-height: 20px;
}
QSpinBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #d0d3d9;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #5865f2;
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
    background-color: #ebedef;
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
    color: #4a4f55;
    font-weight: 600;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #5865f2;
    border: 1px solid #5865f2;
    padding: 7px 18px;
    font-weight: 700;
}
QTabBar::tab:hover:!selected {
    background-color: #ebedef;
    color: #2e3338;
    border-color: #d0d3d9;
}

/* ========== GROUP BOX ========== */
QGroupBox {
    font-weight: 600;
    border: 1px solid #d0d3d9;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    background-color: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    background-color: #ffffff;
    color: #4a4f55;
}

/* ========== LABELS ========== */
QLabel {
    background-color: transparent;
    color: #2e3338;
}

/* ========== STATUS BAR ========== */
QStatusBar {
    background-color: #edf2ff;
    color: #4a4f55;
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
    background-color: #8f8f8f;
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
    background-color: #8f8f8f;
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
    background-color: #ffffff;
}
QMessageBox {
    background-color: #ffffff;
}
QMessageBox QLabel {
    color: #2e3338;
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
    color: #2e3338;
    background-color: transparent;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
}
QCheckBox::indicator:unchecked {
    background-color: #ffffff;
    border: 1px solid #d0d3d9;
    border-radius: 3px;
}
QCheckBox::indicator:checked {
    background-color: #5865f2;
    border: 1px solid #5865f2;
    border-radius: 3px;
}
QRadioButton::indicator:unchecked {
    background-color: #ffffff;
    border: 1px solid #d0d3d9;
    border-radius: 8px;
}
QRadioButton::indicator:checked {
    background-color: #5865f2;
    border: 1px solid #5865f2;
    border-radius: 8px;
}

/* ========== PROGRESS BAR ========== */
QProgressBar {
    background-color: #ebedef;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #5865f2;
    border-radius: 4px;
}

/* ========== LIST WIDGET ========== */
QListWidget {
    background-color: #ffffff;
    border: 1px solid #d0d3d9;
    border-radius: 4px;
    color: #2e3338;
}
QListWidget::item {
    padding: 4px 8px;
    border-radius: 4px;
}
QListWidget::item:selected {
    background-color: #5865f2;
    color: white;
}
QListWidget::item:hover {
    background-color: #ebedef;
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
    color: #8e9297;
}

/* ========== TOAST NOTIFICATION ========== */
QFrame#toastFrame {
    background-color: #ffffff;
    border-radius: 8px;
    padding: 12px 16px;
    border-left: 4px solid #5865f2;
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
