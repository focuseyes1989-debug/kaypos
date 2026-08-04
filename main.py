# main.py
import sys
import os
import signal

# ✅ Filter PyQt6 CSS warnings
from PyQt6.QtCore import qInstallMessageHandler


def qt_message_handler(_msg_type, _context, message):
    """
    Custom Qt message handler to filter out harmless warnings.
    """
    # Filter out "Unknown property cursor" warnings
    if "Unknown property cursor" in message:
        return
    
    # Filter out other common harmless warnings
    if "QPropertyAnimation::setTargetObject" in message:
        return
    
    if "QPropertyAnimation::setPropertyName" in message:
        return
    
    # Print all other messages
    print(f"Qt: {message}")


def signal_handler(_signum, _frame):
    """Handle Ctrl+C gracefully"""
    print("\nReceived interrupt signal, exiting...")
    sys.exit(0)


def main():
    """Main entry point."""
    # ✅ Install custom Qt message handler to filter warnings
    qInstallMessageHandler(qt_message_handler)
    
    # ✅ Setup signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        from app.application import Application
        app = Application()
        return_code = app.run()
        
        # ✅ Ensure complete exit
        if getattr(sys, 'frozen', False):
            os._exit(return_code)
        sys.exit(return_code)
        
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        if getattr(sys, 'frozen', False):
            os._exit(1)
        sys.exit(1)
    finally:
        print("Application shutdown.")


if __name__ == "__main__":
    main()