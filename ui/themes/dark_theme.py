# ui/themes/dark_theme.py
# Dark Theme - အပြည့်အစုံ ပြင်ဆင်ချက်

DARK_THEME = """
/* ========== GLOBAL ========== */
* {
    font-family: "Segoe UI", "Pyidaungsu", "Myanmar Text", "Noto Sans Myanmar", "sans-serif";
    font-size: 10pt;
}

QWidget {
    background-color: #2f3136;
    color: #dcddde;
}

QMainWindow {
    background-color: #2f3136;
}

/* ========== MENU BAR ========== */
QMenuBar {
    background-color: #202225;
    color: #dcddde;
    padding: 4px 8px;
    font-weight: 500;
    border-bottom: 1px solid #40444b;
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
    background-color: #2f3136;
    border: 1px solid #40444b;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    background-color: transparent;
    padding: 6px 24px;
    color: #dcddde;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #5865f2;
    color: white;
}
QMenu::separator {
    height: 1px;
    background-color: #40444b;
    margin: 4px 8px;
}

/* ========== HEADER - Dark Theme ========== */
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
    background-color: #202225;
    border-right: 1px solid #40444b;
}

/* ============================================================
   ✅ COMBOBOX - DARK THEME FIX
   ============================================================ */
QComboBox {
    background-color: #40444b;
    border: 1px solid #40444b;
    border-radius: 4px;
    padding: 5px 8px;
    color: #dcddde;
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
    border-top: 4px solid #b9bbbe;
    margin-right: 4px;
}

/* ✅ ComboBox Popup (Dropdown) - Dark Theme */
QComboBox QAbstractItemView {
    background-color: #2f3136 !important;
    border: 1px solid #40444b !important;
    border-radius: 4px !important;
    color: #dcddde !important;
    selection-background-color: #5865f2 !important;
    selection-color: white !important;
    outline: none !important;
    padding: 4px !important;
}

/* ✅ ComboBox Popup Items */
QComboBox QAbstractItemView::item {
    background-color: transparent !important;
    color: #dcddde !important;
    padding: 6px 10px !important;
    border: none !important;
    border-radius: 2px !important;
    min-height: 24px !important;
}

/* ✅ ComboBox Popup Item - Hover */
QComboBox QAbstractItemView::item:hover {
    background-color: #40444b !important;
    color: #dcddde !important;
}

/* ✅ ComboBox Popup Item - Selected */
QComboBox QAbstractItemView::item:selected {
    background-color: #5865f2 !important;
    color: white !important;
}

/* ============================================================
   ✅ DATE EDIT (DatePicker) - DARK THEME
   ============================================================ */
QDateEdit {
    background-color: #40444b;
    border: 1px solid #40444b;
    border-radius: 4px;
    padding: 5px 8px;
    color: #dcddde;
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
    border-top: 4px solid #b9bbbe;
    margin-right: 4px;
}
QDateEdit:disabled {
    color: #72767d;
}
QDateEdit::up-button, QDateEdit::down-button {
    background-color: transparent;
    border: none;
    width: 16px;
}
QDateEdit::up-button:hover, QDateEdit::down-button:hover {
    background-color: #36393f;
    border-radius: 2px;
}

/* Calendar Popup - Dark Theme */
QDateEdit QCalendarWidget {
    background-color: #2f3136;
    border: 1px solid #40444b;
    border-radius: 8px;
    min-width: 350px;
    min-height: 300px;
}

QDateEdit QCalendarWidget QWidget {
    background-color: #2f3136;
}

QDateEdit QCalendarWidget QAbstractItemView {
    background-color: #2f3136;
    border: none;
    border-radius: 4px;
    color: #dcddde;
    selection-background-color: #5865f2;
    selection-color: white;
}

QDateEdit QCalendarWidget QTableView {
    background-color: #2f3136;
    border: none;
    outline: none;
}

QDateEdit QCalendarWidget QHeaderView::section {
    background-color: #202225;
    color: #b9bbbe;
    padding: 8px;
    border: none;
    font-weight: 600;
}

QDateEdit QCalendarWidget QToolButton {
    background-color: transparent;
    color: #dcddde;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: bold;
}
QDateEdit QCalendarWidget QToolButton:hover {
    background-color: #40444b;
}
QDateEdit QCalendarWidget QToolButton::menu-indicator {
    image: none;
}

QDateEdit QCalendarWidget QSpinBox {
    background-color: #40444b;
    border: 1px solid #40444b;
    border-radius: 4px;
    color: #dcddde;
}
QDateEdit QCalendarWidget QSpinBox:focus {
    border: 1px solid #5865f2;
}

/* Calendar Grid - Dark Theme */
QDateEdit QCalendarWidget QTableView {
    gridline-color: #40444b;
}

QDateEdit QCalendarWidget QTableView::item {
    padding: 8px 4px;
    border-radius: 4px;
    background-color: transparent;
    color: #dcddde;
    min-height: 34px;
    min-width: 40px;
}

QDateEdit QCalendarWidget QTableView::item:selected {
    background-color: #5865f2;
    color: white;
}

QDateEdit QCalendarWidget QTableView::item:hover {
    background-color: #40444b;
    color: #dcddde;
}

QDateEdit QCalendarWidget QTableView::item:disabled {
    color: #72767d;
}

/* ========== SUMMARY CARDS ========== */
QFrame#summaryCard {
    background-color: #36393f;
    border: 1px solid #40444b;
    border-radius: 10px;
}
QFrame#summaryCard:hover {
    background-color: #40444b;
    border-color: #5865f2;
}

QFrame#summaryCard QLabel {
    border: none;
    background: transparent;
    padding: 0px;
    margin: 0px;
}

QLabel#cardTitle {
    color: #b9bbbe;
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
    background-color: #36393f;
    border: 1px solid #40444b;
    border-radius: 12px;
    padding: 8px;
}
#dashboardCard:hover {
    background-color: #40444b;
    border: 1px solid #5865f2;
}
#cardTitle {
    color: #b9bbbe;
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
    background-color: #40444b;
    color: #72767d;
}

QTableWidget QPushButton, QDialog QPushButton {
    background-color: #40444b;
    color: #dcddde;
    border-radius: 3px;
    padding: 4px 8px;
}
QTableWidget QPushButton:hover, QDialog QPushButton:hover {
    background-color: #5865f2;
    color: white;
}

/* ========== TABLES ========== */
QTableWidget {
    background-color: #2f3136;
    alternate-background-color: #36393f;
    selection-background-color: #40444b;
    selection-color: #dcddde;
    gridline-color: #40444b;
    border: 1px solid #40444b;
    border-radius: 6px;
}
QHeaderView::section {
    background-color: #202225;
    padding: 8px;
    border: none;
    font-weight: 600;
    color: #b9bbbe;
}
QTableWidget::item {
    padding: 6px;
}

/* ========== INPUT FIELDS ========== */
QLineEdit, QTextEdit {
    background-color: #40444b;
    border: 1px solid #40444b;
    border-radius: 4px;
    padding: 5px 8px;
    color: #dcddde;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #5865f2;
}
QLineEdit::placeholder {
    color: #72767d;
}

/* ========== SPIN BOX ========== */
QSpinBox, QDoubleSpinBox {
    background-color: #40444b;
    border: 1px solid #40444b;
    border-radius: 4px;
    padding: 5px 8px;
    color: #dcddde;
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
    background-color: #36393f;
}

/* ========== TABS ========== */
QTabWidget::pane {
    background-color: #2f3136;
    border: 1px solid #40444b;
    border-radius: 6px;
}
QTabBar::tab {
    background-color: transparent;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #b9bbbe;
}
QTabBar::tab:selected {
    background-color: #40444b;
    color: #ffffff;
    border-bottom: 2px solid #5865f2;
}
QTabBar::tab:hover:!selected {
    background-color: #36393f;
    color: #dcddde;
}

/* ========== GROUP BOX ========== */
QGroupBox {
    font-weight: 600;
    border: 1px solid #40444b;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    background-color: #2f3136;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 8px;
    background-color: #2f3136;
    color: #b9bbbe;
}

/* ========== LABELS ========== */
QLabel {
    background-color: transparent;
    color: #dcddde;
}

/* ========== STATUS BAR ========== */
QStatusBar {
    background-color: #202225;
    color: #b9bbbe;
    border-top: 1px solid #40444b;
}

/* ========== SCROLL BARS ========== */
QScrollBar:vertical {
    background: #2f3136;
    width: 12px;
    border-radius: 6px;
}
QScrollBar::handle:vertical {
    background: #40444b;
    border-radius: 6px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #5865f2;
}
QScrollBar:horizontal {
    background: #2f3136;
    height: 12px;
    border-radius: 6px;
}
QScrollBar::handle:horizontal {
    background: #40444b;
    border-radius: 6px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover {
    background: #5865f2;
}

/* ========== DIALOGS ========== */
QDialog {
    background-color: #2f3136;
}
QMessageBox {
    background-color: #2f3136;
}
QMessageBox QLabel {
    color: #dcddde;
}
QMessageBox QPushButton {
    min-width: 70px;
    padding: 5px 12px;
}

/* ========== CHECKBOX & RADIO ========== */
QCheckBox, QRadioButton {
    spacing: 6px;
    color: #dcddde;
    background-color: transparent;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
}
QCheckBox::indicator:unchecked {
    background-color: #40444b;
    border: 1px solid #40444b;
    border-radius: 3px;
}
QCheckBox::indicator:checked {
    background-color: #5865f2;
    border: 1px solid #5865f2;
    border-radius: 3px;
}
QRadioButton::indicator:unchecked {
    background-color: #40444b;
    border: 1px solid #40444b;
    border-radius: 8px;
}
QRadioButton::indicator:checked {
    background-color: #5865f2;
    border: 1px solid #5865f2;
    border-radius: 8px;
}

/* ========== PROGRESS BAR ========== */
QProgressBar {
    background-color: #40444b;
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
    background-color: #2f3136;
    border: 1px solid #40444b;
    border-radius: 4px;
    color: #dcddde;
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
    background-color: #40444b;
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
    color: #72767d;
}

/* ========== TOAST NOTIFICATION ========== */
QFrame#toastFrame {
    background-color: #36393f;
    border-radius: 8px;
    padding: 12px 16px;
    border-left: 4px solid #5865f2;
}

/* ========== MAIN CONTAINER ========== */
QWidget#mainContainer {
    background-color: #2f3136;
}

/* ========== CONTENT AREA ========== */
QStackedWidget {
    background-color: #2f3136;
    border-radius: 12px;
}
"""