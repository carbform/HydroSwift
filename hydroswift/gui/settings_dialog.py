"""
HydroSwift GUI - Settings Dialog

Provides a dialog for configuring application preferences
and default settings.
"""

from __future__ import annotations

from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QGridLayout, QFileDialog,
    QSpinBox, QCheckBox, QTabWidget, QWidget, QComboBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class SettingsDialog(QDialog):
    """Dialog for application settings and preferences."""

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("HydroSwift Settings")
        self.setGeometry(200, 200, 600, 500)
        self.setModal(True)
        
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the settings dialog UI."""
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Title
        title = QLabel("Preferences")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        layout.addWidget(title)
        
        # Tab widget for different settings categories
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # General settings tab
        general_widget = self._create_general_tab()
        tabs.addTab(general_widget, "General")
        
        # Download settings tab
        download_widget = self._create_download_tab()
        tabs.addTab(download_widget, "Download")
        
        # API settings tab
        api_widget = self._create_api_tab()
        tabs.addTab(api_widget, "API")
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        buttons_layout.addWidget(reset_btn)
        
        buttons_layout.addStretch()
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)
        
        layout.addLayout(buttons_layout)

    def _create_general_tab(self) -> QWidget:
        """Create the General settings tab."""
        
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Output directory group
        output_group = QGroupBox("Output")
        output_layout = QGridLayout()
        
        output_layout.addWidget(QLabel("Output Directory:"), 0, 0)
        self.output_path = QLineEdit()
        self.output_path.setText("output")
        output_layout.addWidget(self.output_path, 0, 1)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_output_dir)
        output_layout.addWidget(browse_btn, 0, 2)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        # Theme group
        theme_group = QGroupBox("Theme")
        theme_layout = QGridLayout()
        
        theme_layout.addWidget(QLabel("Theme:"), 0, 0)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        theme_layout.addWidget(self.theme_combo, 0, 1)
        
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)
        
        # Startup group
        startup_group = QGroupBox("Startup")
        startup_layout = QVBoxLayout()
        
        self.start_maximized = QCheckBox("Start window maximized")
        self.start_maximized.setChecked(False)
        startup_layout.addWidget(self.start_maximized)
        
        self.show_tips = QCheckBox("Show tips on startup")
        self.show_tips.setChecked(True)
        startup_layout.addWidget(self.show_tips)
        
        startup_group.setLayout(startup_layout)
        layout.addWidget(startup_group)
        
        layout.addStretch()
        return widget

    def _create_download_tab(self) -> QWidget:
        """Create the Download settings tab."""
        
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # Download options group
        options_group = QGroupBox("Download Options")
        options_layout = QGridLayout()
        
        options_layout.addWidget(QLabel("Default Format:"), 0, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["csv", "excel", "parquet"])
        options_layout.addWidget(self.format_combo, 0, 1)
        
        options_layout.addWidget(QLabel("Request Delay (seconds):"), 1, 0)
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setValue(1)
        self.delay_spinbox.setMaximum(60)
        options_layout.addWidget(self.delay_spinbox, 1, 1)
        
        options_layout.addWidget(QLabel("Connection Timeout (seconds):"), 2, 0)
        self.timeout_spinbox = QSpinBox()
        self.timeout_spinbox.setValue(30)
        self.timeout_spinbox.setMaximum(300)
        options_layout.addWidget(self.timeout_spinbox, 2, 1)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Default behaviors group
        behavior_group = QGroupBox("Default Behaviors")
        behavior_layout = QVBoxLayout()
        
        self.auto_merge = QCheckBox("Auto-merge files after download")
        self.auto_merge.setChecked(True)
        behavior_layout.addWidget(self.auto_merge)
        
        self.include_metadata = QCheckBox("Include metadata in exports")
        self.include_metadata.setChecked(True)
        behavior_layout.addWidget(self.include_metadata)
        
        self.confirm_overwrite = QCheckBox("Ask before overwriting files")
        self.confirm_overwrite.setChecked(True)
        behavior_layout.addWidget(self.confirm_overwrite)
        
        behavior_group.setLayout(behavior_layout)
        layout.addWidget(behavior_group)
        
        layout.addStretch()
        return widget

    def _create_api_tab(self) -> QWidget:
        """Create the API settings tab."""
        
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        
        # WRIS settings group
        wris_group = QGroupBox("WRIS (India Water Resources Information System)")
        wris_layout = QGridLayout()
        
        wris_layout.addWidget(QLabel("Default Basin:"), 0, 0)
        self.default_basin = QComboBox()
        self.default_basin.addItems([
            "Godavari", "Krishna", "Narmada", "Mahanadi",
            "Brahmani and Baitarni", "Cauvery"
        ])
        wris_layout.addWidget(self.default_basin, 0, 1)
        
        wris_layout.addWidget(QLabel("Default Variable:"), 1, 0)
        self.default_variable = QComboBox()
        self.default_variable.addItems([
            "discharge", "water_level", "rainfall",
            "temperature", "humidity", "solar_radiation"
        ])
        wris_layout.addWidget(self.default_variable, 1, 1)
        
        wris_layout.addWidget(QLabel("Default Date Range (days):"), 2, 0)
        self.date_range_spinbox = QSpinBox()
        self.date_range_spinbox.setValue(365)
        self.date_range_spinbox.setMaximum(10000)
        wris_layout.addWidget(self.date_range_spinbox, 2, 1)
        
        wris_group.setLayout(wris_layout)
        layout.addWidget(wris_group)
        
        # CWC settings group
        cwc_group = QGroupBox("CWC (Central Water Commission)")
        cwc_layout = QVBoxLayout()
        
        self.auto_refresh_cwc = QCheckBox("Auto-refresh CWC metadata on startup")
        self.auto_refresh_cwc.setChecked(False)
        cwc_layout.addWidget(self.auto_refresh_cwc)
        
        cwc_group.setLayout(cwc_layout)
        layout.addWidget(cwc_group)
        
        layout.addStretch()
        return widget

    def _browse_output_dir(self) -> None:
        """Browse for output directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            self.output_path.text()
        )
        if directory:
            self.output_path.setText(directory)

    def _reset_defaults(self) -> None:
        """Reset all settings to defaults."""
        self.output_path.setText("output")
        self.theme_combo.setCurrentText("Light")
        self.start_maximized.setChecked(False)
        self.show_tips.setChecked(True)
        
        self.format_combo.setCurrentText("csv")
        self.delay_spinbox.setValue(1)
        self.timeout_spinbox.setValue(30)
        self.auto_merge.setChecked(True)
        self.include_metadata.setChecked(True)
        self.confirm_overwrite.setChecked(True)
        
        self.default_basin.setCurrentText("Godavari")
        self.default_variable.setCurrentText("discharge")
        self.date_range_spinbox.setValue(365)
        self.auto_refresh_cwc.setChecked(False)

    def get_settings(self) -> dict:
        """Get all settings as a dictionary."""
        return {
            "output_dir": self.output_path.text(),
            "theme": self.theme_combo.currentText(),
            "start_maximized": self.start_maximized.isChecked(),
            "show_tips": self.show_tips.isChecked(),
            "format": self.format_combo.currentText(),
            "request_delay": self.delay_spinbox.value(),
            "connection_timeout": self.timeout_spinbox.value(),
            "auto_merge": self.auto_merge.isChecked(),
            "include_metadata": self.include_metadata.isChecked(),
            "confirm_overwrite": self.confirm_overwrite.isChecked(),
            "default_basin": self.default_basin.currentText(),
            "default_variable": self.default_variable.currentText(),
            "date_range_days": self.date_range_spinbox.value(),
            "auto_refresh_cwc": self.auto_refresh_cwc.isChecked(),
        }
