"""
Example usage of the Design System in PyQt6
"""

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QTabWidget,
    QGroupBox, QProgressBar, QStatusBar
)
from PyQt6.QtCore import Qt

from colors import COLORS, apply_theme_to_app, LIGHT_THEME_QSS

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("POS System - Design System Demo")
        self.setGeometry(100, 100, 900, 600)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Header
        header = QLabel("Design System Demo")
        header.setStyleSheet("font-size: 24px; font-weight: 600; color: #212529;")
        layout.addWidget(header)
        
        subtitle = QLabel("Using PyQt6 Color System")
        subtitle.setStyleSheet("color: #6C757D; margin-bottom: 20px;")
        layout.addWidget(subtitle)
        
        # Tab Widget
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Tab 1: Buttons Demo
        buttons_tab = QWidget()
        tabs.addTab(buttons_tab, "Buttons")
        buttons_layout = QVBoxLayout(buttons_tab)
        
        # Button group
        btn_group = QGroupBox("Button Variants")
        btn_group_layout = QVBoxLayout()
        btn_group.setLayout(btn_group_layout)
        
        # Primary button
        primary_btn = QPushButton("Primary Button")
        btn_group_layout.addWidget(primary_btn)
        
        # Secondary button
        secondary_btn = QPushButton("Secondary Button")
        secondary_btn.setProperty("secondary", True)
        btn_group_layout.addWidget(secondary_btn)
        
        # Success button
        success_btn = QPushButton("Success Button")
        success_btn.setProperty("success", True)
        btn_group_layout.addWidget(success_btn)
        
        # Warning button
        warning_btn = QPushButton("Warning Button")
        warning_btn.setProperty("warning", True)
        btn_group_layout.addWidget(warning_btn)
        
        # Danger button
        danger_btn = QPushButton("Danger Button")
        danger_btn.setProperty("danger", True)
        btn_group_layout.addWidget(danger_btn)
        
        buttons_layout.addWidget(btn_group)
        buttons_layout.addStretch()
        
        # Tab 2: Input Demo
        input_tab = QWidget()
        tabs.addTab(input_tab, "Inputs")
        input_layout = QVBoxLayout(input_tab)
        
        # Input group
        input_group = QGroupBox("Input Fields")
        input_group_layout = QVBoxLayout()
        input_group.setLayout(input_group_layout)
        
        # Line edit
        name_input = QLineEdit()
        name_input.setPlaceholderText("Enter your name...")
        input_group_layout.addWidget(QLabel("Name:"))
        input_group_layout.addWidget(name_input)
        
        # Combo box
        combo = QComboBox()
        combo.addItems(["Option 1", "Option 2", "Option 3"])
        input_group_layout.addWidget(QLabel("Select option:"))
        input_group_layout.addWidget(combo)
        
        input_layout.addWidget(input_group)
        input_layout.addStretch()
        
        # Tab 3: Table Demo
        table_tab = QWidget()
        tabs.addTab(table_tab, "Table")
        table_layout = QVBoxLayout(table_tab)
        
        # Table
        table = QTableWidget(5, 3)
        table.setHorizontalHeaderLabels(["Product", "Price", "Quantity"])
        
        # Sample data
        products = [
            ("Coffee", "$4.99", "2"),
            ("Tea", "$3.99", "5"),
            ("Juice", "$5.49", "3"),
            ("Water", "$1.99", "10"),
            ("Snacks", "$2.99", "7"),
        ]
        
        for row, (product, price, qty) in enumerate(products):
            table.setItem(row, 0, QTableWidgetItem(product))
            table.setItem(row, 1, QTableWidgetItem(price))
            table.setItem(row, 2, QTableWidgetItem(qty))
        
        table.resizeColumnsToContents()
        table_layout.addWidget(table)
        
        # Tab 4: Progress Demo
        progress_tab = QWidget()
        tabs.addTab(progress_tab, "Progress")
        progress_layout = QVBoxLayout(progress_tab)
        
        # Progress bars
        progress_group = QGroupBox("Progress Bars")
        progress_group_layout = QVBoxLayout()
        progress_group.setLayout(progress_group_layout)
        
        # Default progress
        default_progress = QProgressBar()
        default_progress.setValue(45)
        progress_group_layout.addWidget(QLabel("Default:"))
        progress_group_layout.addWidget(default_progress)
        
        # Success progress
        success_progress = QProgressBar()
        success_progress.setValue(75)
        success_progress.setProperty("success", True)
        progress_group_layout.addWidget(QLabel("Success:"))
        progress_group_layout.addWidget(success_progress)
        
        # Warning progress
        warning_progress = QProgressBar()
        warning_progress.setValue(50)
        warning_progress.setProperty("warning", True)
        progress_group_layout.addWidget(QLabel("Warning:"))
        progress_group_layout.addWidget(warning_progress)
        
        # Danger progress
        danger_progress = QProgressBar()
        danger_progress.setValue(90)
        danger_progress.setProperty("danger", True)
        progress_group_layout.addWidget(QLabel("Danger:"))
        progress_group_layout.addWidget(danger_progress)
        
        progress_layout.addWidget(progress_group)
        progress_layout.addStretch()
        
        # Status bar
        self.statusBar().showMessage("Ready")
        status_label = QLabel(f"System Colors: {len(COLORS.get_all_colors())} defined")
        self.statusBar().addPermanentWidget(status_label)

def main():
    app = QApplication(sys.argv)
    
    # Apply the theme
    apply_theme_to_app(app)
    
    # Alternative: use custom theme modifications
    # custom_qss = LIGHT_THEME_QSS + """
    #     QPushButton {
    #         border-radius: 10px;
    #         padding: 10px 20px;
    #     }
    # """
    # apply_theme_to_app(app, custom_qss)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
