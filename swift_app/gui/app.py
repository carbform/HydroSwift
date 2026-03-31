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
    
    app = QApplication(sys.argv)
    app.setApplicationName("HydroSwift")
    app.setApplicationVersion("1.0.0")
    
    window = HydroSwiftGUI()
    window.show()
    
    sys.exit(app.exec_())


def main():
    """Console script entry point."""
    run_gui()


if __name__ == "__main__":
    main()
