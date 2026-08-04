# core/exception_handler.py
"""
Global exception handlers.
"""

import sys
import threading
import traceback
from loguru import logger
from PyQt6.QtWidgets import QMessageBox


def setup_exception_handlers():
    """Setup global exception handlers."""
    sys.excepthook = handle_exception
    threading.excepthook = thread_exception_handler


def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler to prevent app crashes."""
    logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical("Unhandled exception")
    
    error_msg = str(exc_value)
    error_trace = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    
    # Safe errors (don't show dialog)
    safe_errors = [
        "No microphone found",
        "Input device not found",
        "PortAudio error",
        "Recording error",
        "Transcription timeout",
        "Speech recognition service error"
    ]
    
    is_audio_error = any(term.lower() in error_msg.lower() for term in safe_errors)
    
    if not is_audio_error or os.getenv('ZAY_DEBUG', '0') == '1':
        try:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Unexpected Error")
            
            if is_audio_error:
                msg.setText("Audio/Speech recognition error occurred.")
                msg.setInformativeText(f"{error_msg}\n\nThe application will continue running.")
            else:
                msg.setText("An unexpected error occurred.")
                msg.setInformativeText(f"{error_msg}\n\nThe application will continue running.")
            
            if len(error_trace) < 1000:
                msg.setDetailedText(error_trace)
            else:
                msg.setDetailedText(error_trace[:1000] + "\n... (truncated)")
            
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
        except:
            pass
    
    # Exit only for fatal errors
    fatal_errors = ["MemoryError", "SystemError", "Fatal"]
    if any(fe in exc_type.__name__ for fe in fatal_errors):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)


def thread_exception_handler(args):
    """Handle exceptions from threads."""
    logger.error(f"Thread exception: {args.exc_type.__name__}: {args.exc_value}")