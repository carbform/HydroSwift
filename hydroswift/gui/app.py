"""
HydroSwift GUI Application Entry Point

This module provides the entry point for launching the HydroSwift GUI application.
It can be invoked directly or via the installed console script.
"""

from __future__ import annotations

import sys


def run_gui():
    """Launch the HydroSwift GUI application."""
    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:
        print(
            "Error: PyQt5 is required to use the HydroSwift GUI.\n"
            "Install it with: pip install hydroswift[gui]\n"
            "or: pip install PyQt5"
        )
        sys.exit(1)
    
    from .main_window import HydroSwiftGUI
    
    # Prevent uncaught Python exceptions from aborting the Qt loop with core dump
    import traceback
    def _safe_excepthook(exc_type, exc_value, exc_traceback):
        traceback.print_exception(exc_type, exc_value, exc_traceback)
    sys.excepthook = _safe_excepthook

    app = QApplication(sys.argv)
    app.setApplicationName("HydroSwift")
    app.setApplicationVersion("1.0.0")
    
    # Apply modern dark theme if available
    try:
        import qdarkstyle
        app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt5'))
    except ImportError:
        pass
        
    from PyQt5.QtGui import QFont
    # Use modern Sans-Serif font globally
    font = QFont("Segoe UI, Noto Sans, Ubuntu, sans-serif")
    font.setPointSize(11)
    app.setFont(font)
        
    window = HydroSwiftGUI()
    window.show()
    
    sys.exit(app.exec_())


def run_web():
    """Launch the modern HydroSwift Streamlit web dashboard."""
    from pathlib import Path
    try:
        import streamlit.web.cli as stcli
    except ImportError:
        print("Streamlit is required for the modern web dashboard. Install with: pip install streamlit")
        print("Falling back to desktop Qt GUI...")
        run_gui()
        return

    web_script = str(Path(__file__).parent / "web.py")
    sys.argv = ["streamlit", "run", web_script, "--server.headless=false", "--browser.gatherUsageStats=false"]
    sys.exit(stcli.main())


def main():
    """Console script entry point for `hyswift-gui`."""
    if "--qt" in sys.argv or "--desktop" in sys.argv:
        sys.argv = [a for a in sys.argv if a not in ("--qt", "--desktop")]
        run_gui()
    else:
        run_web()


if __name__ == "__main__":
    main()
