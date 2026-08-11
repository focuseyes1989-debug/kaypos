# core/environment.py
"""
Environment setup for application startup.
"""

import os
import sys
import warnings


def setup_environment():
    """Setup environment variables and paths."""
    
    # ✅ Fix PyQt6 import for frozen executable
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
        if app_dir not in sys.path:
            sys.path.insert(0, app_dir)
        
        if hasattr(sys, '_MEIPASS'):
            meipass_dir = sys._MEIPASS
            if meipass_dir not in sys.path:
                sys.path.insert(0, meipass_dir)
    
    # ✅ Fix matplotlib
    
    # ✅ High DPI scaling
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "Round"
    
    # ✅ Windows DPI awareness
    # Qt 6 sets Windows DPI awareness when QApplication is created. Calling
    # the Windows DPI API here can make Qt print an Access is denied warning.


def setup_matplotlib():
    """Configure matplotlib lazily without importing pyplot during startup."""
    try:
        os.environ['MPLBACKEND'] = 'QtAgg'
        
        cache_dir = os.path.join(
            os.path.expanduser('~'), 
            'AppData', 'Local', 'Temp', 'matplotlib_cache'
        )
        os.environ['MPLCONFIGDIR'] = cache_dir
        os.environ['PYTHONWARNINGS'] = 'ignore'
        
        os.makedirs(cache_dir, exist_ok=True)
        
        warnings.filterwarnings("ignore", category=ImportWarning)
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        warnings.filterwarnings("ignore", category=UserWarning)
        
        try:
            print("✅ Matplotlib initialized successfully")
        except Exception as e:
            print(f"⚠️ Matplotlib init warning: {e}")
            
    except Exception as e:
        print(f"⚠️ Matplotlib fix error: {e}")
