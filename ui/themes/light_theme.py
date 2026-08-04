# ui/themes/light_theme.py
# Light Theme - အပြည့်အစုံ ပြင်ဆင်ချက်

LIGHT_THEME = """
/* ========== GLOBAL ========== */
* {
    font-family: "Segoe UI", "Pyidaungsu", "Myanmar Text", "Noto Sans Myanmar", "sans-serif";
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
    background-color: #ffffff;
    border: 1px solid #d0d3d9;
    border-radius: 4px;
    padding: 5px 8px;
    color: #2e3338;
    min-height: 20px;
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
    border-radius: 4px !important;
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
    background-color: #ffffff;
    border: 1px solid #d0d3d9;
    border-radius: 4px;
    padding: 5px 8px;
    color: #2e3338;
    min-height: 20px;
    selection-background-color: #5865f2;
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
    border-radius: 10px;
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
    border-radius: 12px;
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
}
QTableWidget QPushButton:hover, QDialog QPushButton:hover {
    background-color: #5865f2;
    color: white;
}

/* ========== TABLES ========== */
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f8f9fa;
    selection-background-color: #ebedef;
    selection-color: #2e3338;
    gridline-color: #d0d3d9;
    border: 1px solid #d0d3d9;
    border-radius: 6px;
}
QHeaderView::section {
    background-color: #f2f3f5;
    padding: 8px;
    border: none;
    font-weight: 600;
    color: #4a4f55;
}
QTableWidget::item {
    padding: 6px;
}

/* ========== INPUT FIELDS ========== */
QLineEdit, QTextEdit {
    background-color: #ffffff;
    border: 1px solid #d0d3d9;
    border-radius: 4px;
    padding: 5px 8px;
    color: #2e3338;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #5865f2;
}
QLineEdit::placeholder {
    color: #8e9297;
}

/* ========== SPIN BOX ========== */
QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    border: 1px solid #d0d3d9;
    border-radius: 4px;
    padding: 5px 8px;
    color: #2e3338;
    min-height: 20px;
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
QTabWidget::pane {
    background-color: #ffffff;
    border: 1px solid #d0d3d9;
    border-radius: 6px;
}
QTabBar::tab {
    background-color: transparent;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #4a4f55;
}
QTabBar::tab:selected {
    background-color: #f2f3f5;
    color: #2e3338;
    border-bottom: 2px solid #5865f2;
}
QTabBar::tab:hover:!selected {
    background-color: #ebedef;
    color: #2e3338;
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
    background-color: #ffffff;
    color: #4a4f55;
    border-top: 1px solid #d0d3d9;
}

/* ========== SCROLL BARS ========== */
QScrollBar:vertical {
    background: #f2f3f5;
    width: 12px;
    border-radius: 6px;
}
QScrollBar::handle:vertical {
    background: #d0d3d9;
    border-radius: 6px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #5865f2;
}
QScrollBar:horizontal {
    background: #f2f3f5;
    height: 12px;
    border-radius: 6px;
}
QScrollBar::handle:horizontal {
    background: #d0d3d9;
    border-radius: 6px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover {
    background: #5865f2;
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
}
QMessageBox QPushButton {
    min-width: 70px;
    padding: 5px 12px;
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
    background-color: #f2f3f5;
}

/* ========== CONTENT AREA ========== */
QStackedWidget {
    background-color: #f2f3f5;
    border-radius: 12px;
}
"""