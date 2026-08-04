# ui/widgets/no_wheel_spinbox.py
from PyQt6.QtWidgets import QDoubleSpinBox

class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """DoubleSpinBox with mouse wheel disabled and select all on focus"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def wheelEvent(self, event):
        """Override wheel event to do nothing"""
        event.ignore()
    
    def focusInEvent(self, event):
        """Select all text when focus received"""
        super().focusInEvent(event)
        self.selectAll()