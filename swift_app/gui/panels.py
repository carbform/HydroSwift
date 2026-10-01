"""
HydroSwift GUI - Panel Components

Provides tabbed panels for WRIS discovery, CWC download,
configuration, and results visualization.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

import pandas as pd
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QCheckBox, QSpinBox, QDateEdit,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QGroupBox, QGridLayout, QProgressBar, QScrollArea, QTabWidget,
    QMessageBox, QFileDialog, QTextEdit, QSplitter, QAbstractItemView,
)
from PyQt5.QtCore import Qt, pyqtSignal, QDate, QThread, pyqtSlot, QTimer
from PyQt5.QtGui import QFont, QColor

try:
    import hydroswift
    HYDROSWIFT_AVAILABLE = True
except ImportError:
    HYDROSWIFT_AVAILABLE = False


class WorkerThread(QThread):
    """Background worker thread for long-running operations."""
    
    finished = pyqtSignal()
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    result_ready = pyqtSignal(dict)

    def __init__(self, task_func, *args, **kwargs):
        super().__init__()
        self.task_func = task_func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.task_func(*self.args, **self.kwargs)
            self.result_ready.emit(result or {})
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class WRISDiscoveryPanel(QWidget):
    """Panel for WRIS station discovery and download."""
    
    status_changed = pyqtSignal(str)
    log_message = pyqtSignal(str, str)  # message, level
    download_completed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.output_dir = Path("output")
        self.discovered_stations = None
        self.worker_thread = None
        
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the WRIS discovery panel UI."""
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Title
        title = QLabel("WRIS (India Water Resources Information System)")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Discovery section
        discover_group = self._create_discovery_group()
        layout.addWidget(discover_group)
        
        # Stations discovered table
        layout.addWidget(QLabel("Discovered Stations:"))
        self.stations_table = QTableWidget()
        self.stations_table.setColumnCount(5)
        self.stations_table.setHorizontalHeaderLabels(
            ["Station Code", "River", "Basin", "Latitude", "Longitude"]
        )
        # Allow multi-row selection for batch downloads
        self.stations_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.stations_table.setSelectionMode(QAbstractItemView.MultiSelection)
        self.stations_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.stations_table)
        
        # Download controls
        download_layout = QHBoxLayout()
        
        self.download_btn = QPushButton("⬇️ Download Selected Stations")
        self.download_btn.clicked.connect(self._start_download)
        self.download_btn.setEnabled(False)
        download_layout.addWidget(self.download_btn)
        
        self.merge_checkbox = QCheckBox("Merge files after download")
        self.merge_checkbox.setChecked(True)
        download_layout.addWidget(self.merge_checkbox)
        
        select_all_btn = QPushButton("Select All Stations")
        select_all_btn.clicked.connect(lambda: self.stations_table.selectAll())
        download_layout.addWidget(select_all_btn)

        clear_sel_btn = QPushButton("Clear Selection")
        clear_sel_btn.clicked.connect(lambda: self.stations_table.clearSelection())
        download_layout.addWidget(clear_sel_btn)
        
        layout.addLayout(download_layout)
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    def _create_discovery_group(self) -> QGroupBox:
        """Create the station discovery search group."""
        
        group = QGroupBox("Station Discovery")
        layout = QGridLayout()
        
        # Basin selection
        layout.addWidget(QLabel("Basin:"), 0, 0)
        self.basin_combo = QComboBox()
        self._populate_basins()
        layout.addWidget(self.basin_combo, 0, 1)
        
        # Variable selection (multi-select)
        layout.addWidget(QLabel("Variables:"), 0, 2)
        self.variable_list = QListWidget()
        self.variable_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self._populate_variables()
        # Put the list and a small control button in a vertical container
        var_widget = QWidget()
        var_vlayout = QVBoxLayout()
        var_vlayout.setContentsMargins(0, 0, 0, 0)
        var_vlayout.addWidget(self.variable_list)
        select_all_btn = QPushButton("Select All")
        select_all_btn.setToolTip("Select all variables")
        select_all_btn.clicked.connect(self._select_all_variables)
        var_vlayout.addWidget(select_all_btn)
        var_widget.setLayout(var_vlayout)
        layout.addWidget(var_widget, 0, 3)
        
        # State selection (optional)
        layout.addWidget(QLabel("State (Optional):"), 1, 0)
        self.state_combo = QComboBox()
        self.state_combo.addItem("All States")
        layout.addWidget(self.state_combo, 1, 1)
        
        # Number of stations limit
        layout.addWidget(QLabel("Limit (stations):"), 1, 2)
        self.limit_spinbox = QSpinBox()
        self.limit_spinbox.setValue(0)  # 0 = unlimited
        self.limit_spinbox.setMaximum(1000)
        layout.addWidget(self.limit_spinbox, 1, 3)
        
        # Discover button
        self.discover_btn = QPushButton("🔍 Discover Stations")
        self.discover_btn.clicked.connect(self._discover_stations)
        layout.addWidget(self.discover_btn, 2, 0, 1, 4)
        
        group.setLayout(layout)
        return group

    def _populate_basins(self) -> None:
        """Populate basin dropdown from WRIS data."""
        if HYDROSWIFT_AVAILABLE:
            try:
                basins = hydroswift.wris.basins()
                if isinstance(basins, pd.DataFrame) and 'basin' in basins.columns:
                    basin_names = basins['basin'].unique().tolist()
                    self.basin_combo.addItems(basin_names)
            except Exception as e:
                self.log_message.emit(f"Error loading basins: {str(e)}", "error")
        else:
            self.basin_combo.addItems(["Godavari", "Krishna", "Narmada", "Brahmani"])

    def _populate_variables(self) -> None:
        """Populate variable dropdown from WRIS data."""
        if HYDROSWIFT_AVAILABLE:
            try:
                vars_df = hydroswift.wris.variables()
                if isinstance(vars_df, pd.DataFrame):
                    var_names = vars_df.get('canonical_name', []).unique().tolist()
                    self.variable_list.clear()
                    for v in var_names:
                        item = QListWidgetItem(str(v))
                        item.setSelected(True)
                        self.variable_list.addItem(item)
            except Exception as e:
                self.log_message.emit(f"Error loading variables: {str(e)}", "error")
        else:
            self.variable_list.clear()
            for v in [
                "discharge", "water_level", "rainfall", 
                "temperature", "humidity", "solar_radiation"
            ]:
                item = QListWidgetItem(v)
                item.setSelected(True)
                self.variable_list.addItem(item)

    def _select_all_variables(self) -> None:
        """Select all variables in the list."""
        for i in range(self.variable_list.count()):
            item = self.variable_list.item(i)
            item.setSelected(True)

    def _discover_stations(self) -> None:
        """Discover stations based on selected criteria."""
        if not HYDROSWIFT_AVAILABLE:
            QMessageBox.warning(self, "Error", "HydroSwift module not available")
            return
        
        self.status_changed.emit("Discovering stations...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(0)  # Indeterminate progress
        
        basin = self.basin_combo.currentText()
        variables = [it.text() for it in self.variable_list.selectedItems()]
        if not variables:
            QMessageBox.warning(self, "Error", "Please select at least one variable")
            self.progress_bar.setVisible(False)
            return

        self.worker_thread = WorkerThread(
            self._discover_stations_worker,
            basin,
            variables
        )
        self.worker_thread.result_ready.connect(self._on_discovery_complete)
        self.worker_thread.error.connect(self._on_discovery_error)
        self.worker_thread.start()

    def _discover_stations_worker(self, basin: str, variables: List[str]) -> dict:
        """Worker function for station discovery."""
        try:
            stations = hydroswift.wris.stations(basin=basin, variable=variables)
            return {"stations": stations, "basin": basin, "variable": variables}
        except Exception as e:
            raise Exception(f"Station discovery failed: {str(e)}")

    @pyqtSlot(dict)
    def _on_discovery_complete(self, result: dict) -> None:
        """Handle discovery completion."""
        self.progress_bar.setVisible(False)
        
        try:
            stations = result.get("stations")
            if isinstance(stations, pd.DataFrame):
                # Keep the full discovered stations (one row per basin-variable-station)
                self.discovered_stations = stations
                # Display a deduplicated station list for selection
                self._populate_stations_table(stations)
                self.download_btn.setEnabled(True)

                unique_count = len(stations["station_code"].dropna().unique())
                vars_str = (
                    ", ".join(result.get("variable"))
                    if isinstance(result.get("variable"), list)
                    else str(result.get("variable"))
                )
                self.status_changed.emit(f"Found {unique_count} stations")
                self.log_message.emit(
                    f"✓ Discovered {unique_count} stations for {result.get('basin')} - {vars_str}",
                    "success",
                )
        except Exception as e:
            self.log_message.emit(f"Error processing results: {str(e)}", "error")

    @pyqtSlot(str)
    def _on_discovery_error(self, error: str) -> None:
        """Handle discovery error."""
        self.progress_bar.setVisible(False)
        self.status_changed.emit("Station discovery failed")
        self.log_message.emit(error, "error")
        QMessageBox.critical(self, "Discovery Error", error)

    def _populate_stations_table(self, stations: pd.DataFrame) -> None:
        """Populate stations table with discovered data."""
        # Show one row per unique station_code for user selection. Keep
        # the full `stations` DataFrame in `self.discovered_stations` for download.
        display_df = stations.drop_duplicates(subset=["station_code"]).reset_index(drop=True)
        self.stations_table.setRowCount(len(display_df))

        for idx, row in display_df.iterrows():
            for col_idx, col_name in enumerate([
                "station_code", "river", "basin", "latitude", "longitude"
            ]):
                if col_name in display_df.columns:
                    value = str(row[col_name])
                    item = QTableWidgetItem(value)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.stations_table.setItem(idx, col_idx, item)

    def _start_download(self) -> None:
        """Start downloading selected stations."""
        if self.discovered_stations is None or self.discovered_stations.empty:
            QMessageBox.warning(self, "Error", "No stations selected")
            return
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(0)
        self.status_changed.emit("Downloading data...")
        
        basin = self.basin_combo.currentText()
        # Determine selected station codes from the display table (rows)
        selected_rows = {item.row() for item in self.stations_table.selectedItems()}
        if selected_rows:
            selected_codes = []
            for r in sorted(selected_rows):
                item = self.stations_table.item(r, 0)
                if item:
                    selected_codes.append(item.text())
            stations_to_download = self.discovered_stations[
                self.discovered_stations["station_code"].isin(selected_codes)
            ]
        else:
            # No explicit selection → download all discovered
            stations_to_download = self.discovered_stations

        # Prefer output directory from the Download Configuration panel if available
        out_dir = self.output_dir
        try:
            main_win = self.window()
            if hasattr(main_win, "config_panel") and main_win.config_panel:
                cfg = main_win.config_panel.get_config()
                od = cfg.get("output_dir")
                if od:
                    out_dir = Path(od)
        except Exception:
            out_dir = self.output_dir

        out_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = out_dir

        self.worker_thread = WorkerThread(
            self._download_worker,
            stations_to_download,
            basin,
            [it.text() for it in self.variable_list.selectedItems()],
            out_dir,
            self.merge_checkbox.isChecked()
        )
        self.worker_thread.result_ready.connect(self._on_download_complete)
        self.worker_thread.error.connect(self._on_download_error)
        self.worker_thread.start()

    def _download_worker(
        self,
        stations: pd.DataFrame,
        basin: str,
        variables: List[str],
        output_dir: Path,
        merge: bool,
    ) -> dict:
        """Worker function for downloading data."""
        try:
            # Use hydroswift API to download
            result = hydroswift.fetch(
                stations,
                merge=merge,
                output_dir=str(output_dir),
                overwrite=False
            )
            return {
                "success": True,
                "files_saved": len(stations),
                "output_dir": str(output_dir),
                "basin": basin,
                "variables": variables,
            }
        except Exception as e:
            raise Exception(f"Download failed: {str(e)}")

    @pyqtSlot(dict)
    def _on_download_complete(self, result: dict) -> None:
        """Handle download completion."""
        self.progress_bar.setVisible(False)
        self.status_changed.emit("Download completed")
        
        self.log_message.emit(
            f"✓ Downloaded {result.get('files_saved')} files to {result.get('output_dir')}",
            "success"
        )
        
        self.download_completed.emit(result)

    @pyqtSlot(str)
    def _on_download_error(self, error: str) -> None:
        """Handle download error."""
        self.progress_bar.setVisible(False)
        self.status_changed.emit("Download failed")
        self.log_message.emit(error, "error")
        QMessageBox.critical(self, "Download Error", error)

    def set_output_dir(self, output_dir: Path) -> None:
        """Set the output directory."""
        self.output_dir = output_dir


class CWCDownloadPanel(QWidget):
    """Panel for CWC (Central Water Commission) data download."""
    
    status_changed = pyqtSignal(str)
    log_message = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.output_dir = Path("output")
        self.selected_stations = []
        
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the CWC download panel UI."""
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Title
        title = QLabel("CWC (Central Water Commission Flood Forecasting System)")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Selection group
        select_group = self._create_selection_group()
        layout.addWidget(select_group)
        
        # Stations list
        layout.addWidget(QLabel("Available Stations:"))
        self.stations_list = QListWidget()
        self._load_cwc_stations()
        layout.addWidget(self.stations_list)
        
        # Download controls
        download_layout = QHBoxLayout()
        
        self.download_btn = QPushButton("⬇️ Download Selected Stations")
        self.download_btn.clicked.connect(self._start_download)
        download_layout.addWidget(self.download_btn)
        
        self.merge_checkbox = QCheckBox("Merge files after download")
        self.merge_checkbox.setChecked(True)
        download_layout.addWidget(self.merge_checkbox)
        
        download_layout.addStretch()
        layout.addLayout(download_layout)
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    def _create_selection_group(self) -> QGroupBox:
        """Create station selection group."""
        
        group = QGroupBox("Station Selection")
        layout = QGridLayout()
        
        # Basin filter
        layout.addWidget(QLabel("Basin (Optional):"), 0, 0)
        self.basin_combo = QComboBox()
        self.basin_combo.addItem("All Basins")
        self.basin_combo.addItems(["Krishna", "Godavari", "Narmada", "Mahanadi"])
        layout.addWidget(self.basin_combo, 0, 1)
        
        # Refresh metadata button
        refresh_btn = QPushButton("🔄 Refresh Metadata")
        refresh_btn.clicked.connect(self._refresh_metadata)
        layout.addWidget(refresh_btn, 0, 2)
        
        group.setLayout(layout)
        return group

    def _load_cwc_stations(self) -> None:
        """Load CWC stations list."""
        if HYDROSWIFT_AVAILABLE:
            try:
                stations = hydroswift.cwc.stations()
                if isinstance(stations, pd.DataFrame):
                    for idx, row in stations.iterrows():
                        code = row.get('code', '')
                        name = row.get('station_name', '')
                        basin = row.get('basin', '')
                        
                        item_text = f"{code} - {name} ({basin})"
                        item = QListWidgetItem(item_text)
                        item.setData(Qt.UserRole, code)
                        self.stations_list.addItem(item)
            except Exception as e:
                self.log_message.emit(f"Error loading CWC stations: {str(e)}", "error")
        else:
            # Fallback with sample stations
            for station in ["040-CDJAPR", "032-LGDHYD", "043-GODAVARI", "041-KRISHNA"]:
                item = QListWidgetItem(station)
                item.setData(Qt.UserRole, station)
                self.stations_list.addItem(item)

    def _refresh_metadata(self) -> None:
        """Refresh CWC metadata."""
        self.status_changed.emit("Refreshing CWC metadata...")
        
        if HYDROSWIFT_AVAILABLE:
            try:
                hydroswift.cwc.refresh_metadata(write=False)
                self.log_message.emit("✓ Metadata refreshed", "success")
                self._load_cwc_stations()
            except Exception as e:
                self.log_message.emit(f"Error refreshing metadata: {str(e)}", "error")

    def _start_download(self) -> None:
        """Start downloading selected CWC stations."""
        selected_items = self.stations_list.selectedItems()
        
        if not selected_items:
            QMessageBox.warning(self, "Error", "Please select at least one station")
            return
        
        stations = [item.data(Qt.UserRole) for item in selected_items]
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(0)
        self.status_changed.emit(f"Downloading {len(stations)} CWC stations...")
        
        # Prefer output directory from the Download Configuration panel if available
        out_dir = self.output_dir
        try:
            main_win = self.window()
            if hasattr(main_win, "config_panel") and main_win.config_panel:
                cfg = main_win.config_panel.get_config()
                od = cfg.get("output_dir")
                if od:
                    out_dir = Path(od)
        except Exception:
            out_dir = self.output_dir

        out_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = out_dir

        worker = WorkerThread(
            self._download_worker,
            stations,
            out_dir,
            self.merge_checkbox.isChecked()
        )
        worker.result_ready.connect(self._on_download_complete)
        worker.error.connect(self._on_download_error)
        worker.start()

    def _download_worker(
        self,
        stations: List[str],
        output_dir: Path,
        merge: bool
    ) -> dict:
        """Worker function for CWC download."""
        try:
            result = hydroswift.cwc.download(
                station=stations,
                merge=merge,
                output_dir=str(output_dir),
                overwrite=False
            )
            
            return {
                "success": True,
                "files_saved": len(stations),
                "output_dir": str(output_dir)
            }
        except Exception as e:
            raise Exception(f"CWC download failed: {str(e)}")

    @pyqtSlot(dict)
    def _on_download_complete(self, result: dict) -> None:
        """Handle download completion."""
        self.progress_bar.setVisible(False)
        self.status_changed.emit("CWC download completed")
        
        self.log_message.emit(
            f"✓ Downloaded {result.get('files_saved')} CWC stations",
            "success"
        )

    @pyqtSlot(str)
    def _on_download_error(self, error: str) -> None:
        """Handle download error."""
        self.progress_bar.setVisible(False)
        self.status_changed.emit("CWC download failed")
        self.log_message.emit(error, "error")
        QMessageBox.critical(self, "CWC Download Error", error)

    def set_output_dir(self, output_dir: Path) -> None:
        """Set the output directory."""
        self.output_dir = output_dir


class DownloadConfigPanel(QWidget):
    """Panel for configuring download parameters."""
    
    status_changed = pyqtSignal(str)
    log_message = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the configuration panel UI."""
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Title
        title = QLabel("Download Configuration")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Date range group
        date_group = self._create_date_group()
        layout.addWidget(date_group)
        
        # Format and output group
        format_group = self._create_format_group()
        layout.addWidget(format_group)
        
        # Options group
        options_group = self._create_options_group()
        layout.addWidget(options_group)
        
        # Info text
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setMaximumHeight(150)
        info_text.setPlainText(
            "Download Configuration Guide:\n\n"
            "• Date Range: Select the period for data retrieval\n"
            "• Format: CSV is standard; EXCEL requires openpyxl\n"
            "• Overwrite: Replace existing files in output directory\n"
            "• Request Delay: Add delay between API requests (in seconds)\n"
            "• Merge: Combine data from multiple stations into single files"
        )
        layout.addWidget(info_text)
        
        layout.addStretch()

    def _create_date_group(self) -> QGroupBox:
        """Create date range selection group."""
        
        group = QGroupBox("Date Range")
        layout = QGridLayout()
        
        # Start date
        layout.addWidget(QLabel("Start Date:"), 0, 0)
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate(2020, 1, 1))
        layout.addWidget(self.start_date, 0, 1)
        
        # End date
        layout.addWidget(QLabel("End Date:"), 1, 0)
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        layout.addWidget(self.end_date, 1, 1)
        
        group.setLayout(layout)
        return group

    def _create_format_group(self) -> QGroupBox:
        """Create format and output group."""
        
        group = QGroupBox("Output Format & Directory")
        layout = QGridLayout()
        
        # Format
        layout.addWidget(QLabel("Format:"), 0, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["csv", "excel", "parquet"])
        layout.addWidget(self.format_combo, 0, 1)
        
        # Output directory
        layout.addWidget(QLabel("Output Directory:"), 1, 0)
        output_layout = QHBoxLayout()
        self.output_path = QLineEdit()
        self.output_path.setText("output")
        output_layout.addWidget(self.output_path)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_output_dir)
        output_layout.addWidget(browse_btn)
        layout.addLayout(output_layout, 1, 1)
        
        group.setLayout(layout)
        return group

    def _create_options_group(self) -> QGroupBox:
        """Create additional options group."""
        
        group = QGroupBox("Download Options")
        layout = QGridLayout()
        
        # Overwrite checkbox
        self.overwrite_checkbox = QCheckBox("Overwrite existing files")
        self.overwrite_checkbox.setChecked(False)
        layout.addWidget(self.overwrite_checkbox, 0, 0)
        
        # Request delay
        layout.addWidget(QLabel("Request Delay (sec):"), 0, 1)
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setValue(1)
        self.delay_spinbox.setMaximum(60)
        layout.addWidget(self.delay_spinbox, 0, 2)
        
        # Merge checkbox
        self.merge_checkbox = QCheckBox("Merge downloaded files")
        self.merge_checkbox.setChecked(True)
        layout.addWidget(self.merge_checkbox, 1, 0)
        
        # Metadata checkbox
        self.metadata_checkbox = QCheckBox("Include metadata")
        self.metadata_checkbox.setChecked(True)
        layout.addWidget(self.metadata_checkbox, 1, 1)
        
        group.setLayout(layout)
        return group

    def _browse_output_dir(self) -> None:
        """Browse for output directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            self.output_path.text()
        )
        if directory:
            self.output_path.setText(directory)
            self.log_message.emit(f"Output directory: {directory}", "info")

    def get_config(self) -> dict:
        """Get current configuration as dictionary."""
        return {
            "start_date": self.start_date.date().toString("yyyy-MM-dd"),
            "end_date": self.end_date.date().toString("yyyy-MM-dd"),
            "format": self.format_combo.currentText(),
            "output_dir": self.output_path.text(),
            "overwrite": self.overwrite_checkbox.isChecked(),
            "delay": self.delay_spinbox.value(),
            "merge": self.merge_checkbox.isChecked(),
            "metadata": self.metadata_checkbox.isChecked(),
        }


class ResultsViewerPanel(QWidget):
    """Panel for viewing and plotting downloaded results."""
    
    log_message = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.results_dir = Path("output")
        
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the results viewer panel UI."""
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Title
        title = QLabel("Results & Visualization")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 Refresh Results")
        refresh_btn.clicked.connect(self._refresh_results)
        controls_layout.addWidget(refresh_btn)
        
        plot_btn = QPushButton("📊 Plot Selected Data")
        plot_btn.clicked.connect(self._plot_selected)
        controls_layout.addWidget(plot_btn)
        
        export_btn = QPushButton("💾 Export as Geospatial (GeoPackage)")
        export_btn.clicked.connect(self._export_geospatial)
        controls_layout.addWidget(export_btn)
        
        layout.addLayout(controls_layout)
        
        # Files list
        layout.addWidget(QLabel("Downloaded Files:"))
        self.files_list = QListWidget()
        layout.addWidget(self.files_list)
        
        # Info panel
        layout.addWidget(QLabel("File Information:"))
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(200)
        layout.addWidget(self.info_text)

    def load_results(self, results_dir: Path) -> None:
        """Load results from a directory."""
        self.results_dir = results_dir
        self._refresh_results()

    def _refresh_results(self) -> None:
        """Refresh the results list."""
        self.files_list.clear()
        # Prefer output directory from Download Configuration panel if available
        results_dir = self.results_dir
        try:
            main_win = self.window()
            if hasattr(main_win, 'config_panel') and main_win.config_panel:
                cfg = main_win.config_panel.get_config()
                od = cfg.get('output_dir')
                if od:
                    results_dir = Path(od)
        except Exception:
            results_dir = self.results_dir

        if not results_dir.exists():
            self.info_text.setText("No results directory found.")
            return

        csv_files = list(results_dir.rglob("*.csv"))
        
        if not csv_files:
            self.info_text.setText("No CSV files found in results directory.")
            return
        
        for file_path in csv_files[:50]:  # Limit to 50 files
            item = QListWidgetItem(file_path.name)
            item.setData(Qt.UserRole, str(file_path))
            self.files_list.addItem(item)
        
        self.log_message.emit(
            f"Found {len(csv_files)} result files",
            "info"
        )

    def _plot_selected(self) -> None:
        """Plot selected data file."""
        current_item = self.files_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Error", "Please select a file to plot")
            return
        
        file_path = Path(current_item.data(Qt.UserRole))
        
        self.log_message.emit(f"Plotting {file_path.name}...", "info")
        
        try:
            import matplotlib.pyplot as plt
            
            # Read file while skipping any metadata comment header lines
            from io import StringIO

            with open(file_path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()

            # Find first non-comment line (header)
            header_idx = 0
            for i, line in enumerate(lines):
                if not line.lstrip().startswith("#"):
                    header_idx = i
                    break

            content = "".join(lines[header_idx:])
            df = pd.read_csv(StringIO(content))
            
            if 'time' in df.columns and len(df.columns) > 2:
                # Parse times, coerce invalid values, and sort chronologically
                df['time'] = pd.to_datetime(df['time'], errors='coerce')
                df = df.dropna(subset=['time']).sort_values('time').reset_index(drop=True)
                
                # Find the value column (not time, lat, lon, code)
                value_col = None
                for col in df.columns:
                    if col not in ['time', 'lat', 'lon', 'station_code', 'latitude', 'longitude']:
                        value_col = col
                        break
                
                if value_col:
                    import matplotlib.dates as mdates

                    # Prepare data
                    x = df['time']
                    y = df[value_col]

                    # Compute a reasonable bar width (in days) from median time delta
                    try:
                        median_delta = x.diff().median()
                        if pd.isna(median_delta) or median_delta.total_seconds() == 0:
                            width_days = 0.8
                        else:
                            width_days = (median_delta / pd.Timedelta(days=1)) * 0.8
                    except Exception:
                        width_days = 0.8

                    # Convert datetimes to matplotlib numeric format (days) and plot bars
                    # Use .dt.to_pydatetime() on a Series to get array of python datetimes
                    try:
                        x_num = mdates.date2num(x.dt.to_pydatetime())
                    except Exception:
                        # Fallback: convert via numpy datetime64 -> datetime
                        x_num = mdates.date2num(pd.to_datetime(x).to_pydatetime())
                    fig, ax = plt.subplots(figsize=(12, 6))
                    ax.bar(x_num, y, width=width_days, align='center')
                    ax.xaxis_date()
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                    ax.set_title(f"{file_path.stem}")
                    ax.set_xlabel("Time")
                    ax.set_ylabel(value_col.replace('_', ' ').title())
                    ax.grid(True, alpha=0.3)
                    fig.autofmt_xdate()
                    plt.tight_layout()
                    plt.show()
                    self.log_message.emit("✓ Plot displayed", "success")
        except Exception as e:
            self.log_message.emit(f"Error plotting: {str(e)}", "error")

    def _export_geospatial(self) -> None:
        """Export results as GeoPackage."""
        if not HYDROSWIFT_AVAILABLE:
            QMessageBox.warning(self, "Error", "GeoPackage export requires geopandas")
            return
        
        try:
            # This would integrate with hydroswift's geospatial export
            self.log_message.emit(
                "GeoPackage export: Use hydroswift.plot_only(...) with --gpkg flag",
                "info"
            )
        except Exception as e:
            self.log_message.emit(f"Error exporting: {str(e)}", "error")
