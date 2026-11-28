"""
HydroSwift GUI Application Entry Point

This module provides the entry point for launching the modern HydroSwift
Streamlit dashboard for hydrological discovery, visualization, and monitoring.
"""

from __future__ import annotations

import sys
from pathlib import Path


def run_web():
    """Launch the modern HydroSwift Streamlit web dashboard."""
    try:
        import streamlit.web.cli as stcli
    except ImportError:
        print(
            "Error: Streamlit is required to run the HydroSwift GUI.\n"
            "Install it with: pip install hydroswift[gui]\n"
            "or: pip install streamlit plotly"
        )
        sys.exit(1)

    web_script = str(Path(__file__).parent / "web.py")
    sys.argv = ["streamlit", "run", web_script, "--server.headless=false",
                "--server.address=localhost",  # local only: the dashboard can write files "--browser.gatherUsageStats=false",
                "--theme.base=light", "--theme.primaryColor=#2563eb"]
    sys.exit(stcli.main())


def main():
    """Console script entry point for `hyswift-gui`."""
    run_web()


if __name__ == "__main__":
    main()
