"""
HydroSwift GUI - Main Application Window

This module provides the primary UI for HydroSwift, including:
- Workspace layout with tabbed interface
- Menu bar with file/help options
- Status bar for real-time feedback
- Unified workflow orchestration
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QStatusBar, QMenu, QMenuBar, QAction,
    QFileDialog, QMessageBox, QSplitter, QLabel, QPushButton
)
from PyQt5.QtCore import Qt, pyqtSignal, QThreadPool, QTimer
from PyQt5.QtGui import QIcon, QFont

from .panels import (
    WRISDiscoveryPanel,
    CWCDownloadPanel,
    DownloadConfigPanel,
    ResultsViewerPanel,
)
from .logger_widget import LoggerWidget
from .settings_dialog import SettingsDialog


class HydroSwiftGUI(QMainWindow):
    """Main HydroSwift GUI application window."""

    # Signals
    status_changed = pyqtSignal(str)
    download_started = pyqtSignal()
    download_completed = pyqtSignal(dict)

    def __init__(self, parent=None):
        """Initialize the HydroSwift GUI main window."""
        super().__init__(parent)
        
        self.setWindowTitle("HydroSwift ⚡ - Hydrological Data Retrieval")
        self.setGeometry(100, 100, 1400, 900)
        
        # Thread pool for background tasks
        self.thread_pool = QThreadPool()
        
        # Setup UI
        self._setup_ui()
        self._setup_menu_bar()
        self._setup_status_bar()
        self._connect_signals()
        
        # Initialize default output directory
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)

    def _setup_ui(self) -> None:
        """Setup the main user interface layout."""
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Create tab widget for different workflows
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Tab 1: WRIS Discovery & Download
        self.wris_panel = WRISDiscoveryPanel()
        self.tab_widget.addTab(self.wris_panel, "📊 WRIS Data")
        
        # Tab 2: CWC Download
        self.cwc_panel = CWCDownloadPanel()
        self.tab_widget.addTab(self.cwc_panel, "💧 CWC Stations")
        
        # Tab 3: Download Configuration
        self.config_panel = DownloadConfigPanel()
        self.tab_widget.addTab(self.config_panel, "⚙️ Configuration")
        
        # Tab 4: Results & Plotting
        self.results_panel = ResultsViewerPanel()
        self.tab_widget.addTab(self.results_panel, "📈 Results")
        
        # Logger widget at bottom
        logger_label = QLabel("Execution Log:")
        logger_font = QFont()
        logger_font.setPointSize(9)
        logger_label.setFont(logger_font)
        main_layout.addWidget(logger_label)
        
        self.logger_widget = LoggerWidget()
        self.logger_widget.setMaximumHeight(200)
        main_layout.addWidget(self.logger_widget)

    def _setup_menu_bar(self) -> None:
        """Setup the application menu bar."""
        
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        open_output_action = QAction("&Open Output Directory", self)
        open_output_action.setShortcut("Ctrl+O")
        open_output_action.triggered.connect(self._open_output_directory)
        file_menu.addAction(open_output_action)
        
        file_menu.addSeparator()
        
        settings_action = QAction("&Settings", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._show_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        clear_log_action = QAction("&Clear Log", self)
        clear_log_action.triggered.connect(self.logger_widget.clear)
        edit_menu.addAction(clear_log_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About HydroSwift", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        
        help_action = QAction("&API Help", self)
        help_action.setShortcut("F1")
        help_action.triggered.connect(self._show_api_help)
        help_menu.addAction(help_action)

    def _setup_status_bar(self) -> None:
        """Setup the application status bar."""
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)
        
        self.progress_label = QLabel("")
        self.status_bar.addPermanentWidget(self.progress_label)

    def _connect_signals(self) -> None:
        """Connect UI signals to slots."""
        
        # Wire panels to status updates
        self.wris_panel.status_changed.connect(self._update_status)
        self.cwc_panel.status_changed.connect(self._update_status)
        self.config_panel.status_changed.connect(self._update_status)
        
        # Wire log messages
        self.wris_panel.log_message.connect(self.logger_widget.append_log)
        self.cwc_panel.log_message.connect(self.logger_widget.append_log)
        self.config_panel.log_message.connect(self.logger_widget.append_log)
        self.results_panel.log_message.connect(self.logger_widget.append_log)
        
        # Wire download completion
        self.wris_panel.download_completed.connect(self._on_download_completed)

    def _update_status(self, message: str) -> None:
        """Update the status bar message."""
        self.status_label.setText(message)

    def _on_download_completed(self, result: dict) -> None:
        """Handle download completion."""
        self.logger_widget.append_log(
            f"✓ Download completed: {result.get('files_saved', 0)} files saved",
            level="success"
        )
        
        # Update results panel if new data available
        if result.get('output_dir'):
            self.results_panel.load_results(Path(result['output_dir']))

    def _open_output_directory(self) -> None:
        """Open the output directory in file manager."""
        try:
            cfg_out = None
            if hasattr(self, 'config_panel') and self.config_panel:
                cfg_out = self.config_panel.get_config().get('output_dir')
            path = Path(cfg_out) if cfg_out else self.output_dir
        except Exception:
            path = self.output_dir

        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        try:
            # Use subprocess with argument list to handle spaces in path
            subprocess.run(["xdg-open", str(path)], check=False)
        except Exception:
            # Fallback: quote the path for the shell
            os.system(f"xdg-open '{str(path)}'")

    def _show_settings(self) -> None:
        """Show the settings dialog."""
        dialog = SettingsDialog(self)
        if dialog.exec_():
            settings = dialog.get_settings()
            self._apply_settings(settings)

    def _apply_settings(self, settings: dict) -> None:
        """Apply settings to all panels."""
        self.output_dir = Path(settings.get('output_dir', 'output'))
        self.output_dir.mkdir(exist_ok=True)
        
        # Update panels with new settings
        self.wris_panel.set_output_dir(self.output_dir)
        self.cwc_panel.set_output_dir(self.output_dir)

        # Update configuration panel UI if present
        try:
            if hasattr(self, 'config_panel') and self.config_panel:
                if hasattr(self.config_panel, 'output_path'):
                    self.config_panel.output_path.setText(str(self.output_dir))
        except Exception:
            pass

        # Refresh results view to use updated output directory
        try:
            if hasattr(self, 'results_panel') and self.results_panel:
                self.results_panel.load_results(self.output_dir)
        except Exception:
            pass
        
        self.logger_widget.append_log(
            f"Settings updated. Output dir: {self.output_dir}",
            level="info"
        )

    def _show_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About HydroSwift",
            """<b>HydroSwift ⚡ v1.0.0</b>
            
<p>Fast, unified workflows for hydrological data retrieval.</p>

<p><b>Data Sources:</b>
<ul>
<li>India Water Resources Information System (WRIS)</li>
<li>Central Water Commission (CWC) Flood Forecasting System</li>
</ul>
</p>

<p><b>Supported Variables:</b><br/>
Discharge, Water Level, Rainfall, Temperature, Humidity,
Solar Radiation, Sediment, Groundwater Level, Atmospheric Pressure</p>

<p><a href="https://github.com/carbform/HydroSwift">GitHub</a> | 
<a href="https://hydroswift.readthedocs.io/">Documentation</a></p>

<p>Built with PyQt5, Pandas, GeoPandas, and Matplotlib</p>"""
        )

    def _show_api_help(self) -> None:
        """Show Python API help."""
        try:
            import hydroswift
            hydroswift.help()
            self.logger_widget.append_log(
                "Python API help printed to console",
                level="info"
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Could not load API help: {str(e)}"
            )

    def closeEvent(self, event):
        """Handle application close event."""
        reply = QMessageBox.question(
            self,
            "Exit HydroSwift",
            "Are you sure you want to exit?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()


def main():
    """Launch the HydroSwift GUI application."""
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    app.setApplicationName("HydroSwift")
    app.setApplicationVersion("1.0.0")
    
    window = HydroSwiftGUI()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
