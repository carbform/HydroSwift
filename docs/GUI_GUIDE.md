# HydroSwift GUI User & Developer Guide

## Overview

The HydroSwift GUI provides an intuitive, professional interface for discovering, downloading, and visualizing hydrological data from India's WRIS and CWC systems. It handles the complexity of the underlying APIs while presenting a clean, organized interface suitable for researchers, water resource managers, and developers.

## Table of Contents

1. [Installation](#installation)
2. [Getting Started](#getting-started)
3. [Features & Workflows](#features--workflows)
4. [Configuration](#configuration)
5. [For Developers](#for-developers)
6. [Architecture](#architecture)
7. [API Integration](#api-integration)
8. [FAQ & Troubleshooting](#faq--troubleshooting)

---

## Installation

### Prerequisites

- Python 3.9 or higher
- pip or conda

### Standard Installation

```bash
# Clone repository
git clone https://github.com/carbform/HydroSwift.git
cd HydroSwift

# Install with GUI support
pip install -e .[gui]
```

### Full Installation (All Features)

```bash
# Includes GUI, geospatial analysis, and visualization
pip install -e .[all]
```

### Development Installation

```bash
# For contributing to the GUI
pip install -e .[all]
pip install pytest pytest-qt  # For testing
```

### Verify Installation

```bash
# Launch the GUI
hyswift-gui

# Or run directly
python -m swift_app.gui
```

---

## Getting Started

### Launching the Application

```bash
hyswift-gui
```

Your default browser may open, or a new window will appear with the HydroSwift interface.

### First-Time Setup

1. **Check Settings** (File → Settings)
   - Set your preferred output directory (default: `./output`)
   - Adjust request delay if network is slow (default: 1 second)
   - Choose default format (CSV recommended)

2. **Explore Available Data**
   - Go to "WRIS Data" tab
   - Select a basin (e.g., "Godavari")
   - Choose a variable (e.g., "discharge")
   - Click "Discover Stations"

3. **Download Your First Dataset**
   - Configure date range in "Configuration" tab
   - Enable "Merge files" for easier analysis
   - Click "Download Selected Stations"
   - Monitor progress in the log pane

4. **View Results**
   - Switch to "Results" tab
   - Click "Refresh Results"
   - Select a file and click "Plot Selected Data"

---

## Features & Workflows

### Workflow 1: WRIS Data Discovery and Download

**Scenario**: You need discharge data for Godavari basin stations from 2023.

1. **Navigate to WRIS Data Tab**
   - Basin: Select "Godavari"
   - Variable: Select "discharge"
   - Limit: Leave as 0 (unlimited)

2. **Discover Stations**
   - Click "🔍 Discover Stations"
   - Wait for the search to complete
   - Review discovered stations in the table

3. **Configure Download** (Configuration Tab)
   - Start Date: 2023-01-01
   - End Date: 2024-01-01
   - Format: CSV
   - Output: output/
   - Check "Merge files after download"

4. **Download**
   - Return to WRIS Data tab
   - Click "⬇️ Download Selected Stations"
   - Monitor progress in the log

5. **Results**
   - Files saved to `output/wris/Godavari/discharge/`
   - If merged: `output/wris/Godavari/{date}_merged.csv`

### Workflow 2: CWC Water Level Monitoring

**Scenario**: Track water levels across multiple CWC monitoring stations.

1. **Navigate to CWC Stations Tab**
   - Optional: Filter by basin

2. **Select Stations**
   - Click on stations in the list
   - Multiple selections possible

3. **Download**
   - Click "⬇️ Download Selected Stations"
   - Configure merge and metadata options

4. **Analyze**
   - Switch to Results tab
   - Plot individual station time-series
   - Export to GeoPackage for spatial analysis

### Workflow 3: Batch Processing Multiple Basins

1. **WRIS Data Tab**: Discover for Godavari
2. **Download** with merge enabled
3. **Switch tabs**: Discover for Krishna
4. **Download** with merge enabled
5. **Results Tab**: 
   - View files from both basins
   - Plot and compare time-series

---

## Configuration

### Download Configuration Tab

#### Date Range
- **Start Date**: Beginning of analysis period
- **End Date**: End of analysis period
- **Tip**: Longer ranges may take more time to download

#### Output Format
- **CSV** (default): Compatible with Excel, Python, R
- **Excel**: Requires openpyxl library
- **Parquet**: Efficient binary format for large datasets

#### Output Directory
- Click "Browse..." to select folder
- Default: `./output`
- Subdirectories created automatically:
  - `output/wris/{basin}/{variable}/`
  - `output/cwc/{basin}/stations/`

#### Download Options

| Option | Default | Purpose |
|--------|---------|---------|
| Overwrite | Off | Skip existing files |
| Request Delay | 1 sec | Prevent server overload |
| Merge | On | Combine station files |
| Metadata | On | Include station info |

### Application Settings (File → Settings)

#### General Tab
- **Output Directory**: Default save location
- **Theme**: Light/Dark mode
- **Startup**: Maximize on start, show tips

#### Download Tab
- **Default Format**: CSV/Excel/Parquet
- **Request Delay**: 0-60 seconds
- **Connection Timeout**: 5-300 seconds
- **Auto-merge**: Default merge behavior
- **Confirm Overwrite**: Ask before replacing files

#### API Tab
- **Default Basin**: WRIS basin to preselect
- **Default Variable**: WRIS variable to preselect
- **Date Range**: Default days to retrieve
- **Auto Refresh CWC**: Check metadata on startup

---

## For Developers

### Extending the GUI

#### Adding a Custom Panel

Edit `swift_app/gui/panels.py`:

```python
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import pyqtSignal

class CustomAnalysisPanel(QWidget):
    status_changed = pyqtSignal(str)
    log_message = pyqtSignal(str, str)  # message, level
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Custom Analysis Tools"))
        self.setLayout(layout)
```

Then register in `main_window.py`:

```python
def _setup_ui(self):
    # ... existing tabs ...
    self.custom_panel = CustomAnalysisPanel()
    self.tab_widget.addTab(self.custom_panel, "📋 Analysis")
    
    # Connect signals
    self.custom_panel.log_message.connect(self.logger_widget.append_log)
```

#### Implementing Async Tasks

```python
from swift_app.gui.panels import WorkerThread

def _start_computation(self):
    self.worker = WorkerThread(self._compute_worker, param1, param2)
    self.worker.result_ready.connect(self._on_computation_complete)
    self.worker.error.connect(self._on_computation_error)
    self.worker.start()

def _compute_worker(self, param1, param2):
    # Long-running operation
    result = expensive_computation(param1, param2)
    return {"data": result}

def _on_computation_complete(self, result):
    self.logger_widget.append_log(f"Done: {result}", "success")
```

### Testing the GUI

```bash
# Install test dependencies
pip install pytest pytest-qt

# Run GUI tests
pytest tests/test_gui_panels.py -v
```

Example test:

```python
from PyQt5.QtWidgets import QApplication
from swift_app.gui.panels import WRISDiscoveryPanel

def test_wris_panel_creation(qtbot):
    panel = WRISDiscoveryPanel()
    qtbot.addWidget(panel)
    assert panel.basin_combo.count() > 0
```

### Code Style

- Follow PEP 8 conventions
- Use type hints: `def method(self, param: str) -> None:`
- Document with docstrings following NumPy style
- Signal names: `action_completed`, `error_occurred`
- Slot names: `_on_action_completed`

---

## Architecture

### Component Hierarchy

```
HydroSwiftGUI (Main Window)
├── MenuBar
│   ├── File (Open Output, Settings, Exit)
│   ├── Edit (Clear Log)
│   └── Help (About, API Help)
│
├── TabWidget
│   ├── WRISDiscoveryPanel
│   │   ├── Discovery Controls
│   │   ├── Stations Table
│   │   └── Download Controls
│   │
│   ├── CWCDownloadPanel
│   │   ├── Station Selection
│   │   ├── Stations List
│   │   └── Download Controls
│   │
│   ├── DownloadConfigPanel
│   │   ├── Date Range GrOUP
│   │   ├── Format/Output Group
│   │   └── Options Group
│   │
│   └── ResultsViewerPanel
│       ├── Control Buttons
│       ├── Files List
│       └── Info Panel
│
├── LoggerWidget
│   └── Color-coded text display
│
└── StatusBar
    ├── Status message
    └── Progress indicator
```

### Signal Flow

```
User Action (UI)
    ↓
Signal Emitted
    ↓
Slot Handles
    ↓
Worker Thread Created (if async)
    ↓
Background Processing
    ↓
Result/Error Signal
    ↓
UI Updated
```

### Data Flow

```
WRIS/CWC API
    ↓
HydroSwift Core Library
    ↓
GUI Worker Thread
    ↓
Signal Emission
    ↓
Panel Slot
    ↓
UI Update & Logging
```

---

## API Integration

### Using HydroSwift Core from GUI

The GUI uses the existing HydroSwift API:

```python
# Station discovery
stations = hydroswift.wris.stations(
    basin="Godavari",
    variable="discharge"
)

# Data download (table-driven)
hydroswift.fetch(
    stations,
    start_date="2023-01-01",
    end_date="2024-01-01",
    merge=True,
    output_dir="output"
)

# CWC download
hydroswift.cwc.download(
    station=["040-CDJAPR", "032-LGDHYD"],
    merge=True
)

# Plotting
hydroswift.plot_only(
    input_dir="output",
    plot_svg=True
)
```

### Error Handling

All GUI operations wrap HydroSwift calls with try-except:

```python
try:
    result = hydroswift.wris.stations(basin=basin, variable=var)
    self.logger_widget.append_log(f"Found {len(result)} stations", "success")
except Exception as e:
    self.logger_widget.append_log(str(e), "error")
    QMessageBox.critical(self, "Error", str(e))
```

### Configuration Mapping

GUI settings → HydroSwift arguments:

| GUI Setting | HydroSwift Parameter |
|-------------|---------------------|
| Start Date | `start_date` |
| End Date | `end_date` |
| Merge | `merge=True` |
| Output Dir | `output_dir` |
| Overwrite | `overwrite=True` |
| Format | `format="csv"` |

---

## FAQ & Troubleshooting

### Q: The GUI won't start

**A**: Check PyQt5 installation:
```bash
pip install --upgrade PyQt5==5.15.7
```

### Q: Discovery takes too long

**A**: 
- Increase request delay in Settings
- Try limiting results with the "Limit" field
- Use smaller date ranges in Configuration

### Q: Downloads fail with "Connection Error"

**A**:
- Check internet connection
- Increase "Connection Timeout" in Settings
- Try again later (API might be down)

### Q: Large downloads are slow

**A**:
- Download for shorter date ranges first
- Use format="parquet" for larger datasets
- Increase request delay in settings if getting rate-limited

### Q: How do I use downloaded data in Python?

**A**:
```python
import pandas as pd
df = pd.read_csv("output/wris/Godavari/discharge/station_data.csv")
print(df.head())
df.plot(x='time', y='q')  # 'q' is discharge column
```

### Q: Can I run both CLI and GUI?

**A**: Yes! Use different output directories:
```bash
# CLI in terminal 1
hyswift -b Godavari -q --merge --output-dir output_cli

# GUI in terminal 2
hyswift-gui
```

### Q: How do I contribute to the GUI?

**A**: 
1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Make changes following code style
4. Test: `pytest tests/test_gui*`
5. Submit pull request

### Q: How do I report bugs?

**A**: Open an issue on [GitHub](https://github.com/carbform/HydroSwift/issues) with:
- Python version
- PyQt5 version
- OS and version
- Steps to reproduce
- Error message/screenshot

### Q: Is the GUI faster than the CLI?

**A**: They use the same underlying API, so speed is equivalent. The GUI provides:
- Better user experience for discovery
- Real-time progress feedback
- Integrated visualization
- Easier configuration management

---

## Performance Tips

1. **Use CSV format** for faster I/O
2. **Enable merging** only when needed
3. **Limit date ranges** for large basins
4. **Set appropriate request delay** (1-5 seconds)
5. **Monitor memory** when plotting large files
6. **Close unused tabs** to save memory
7. **Clear log periodically** if running long sessions

---

## Security Considerations

- **No credentials stored**: Both CLI and GUI are stateless
- **API keys**: Pass via environment variables if needed
- **Data privacy**: Downloaded data stored locally only
- **Network**: Uses HTTPS for all API calls

---

## Related Documentation

- **Python API Guide**: `docs/PYTHON_API_GUIDE.md`
- **CLI Usage Guide**: `docs/CLI_USAGE_GUIDE.md`
- **API Functions Reference**: `docs/API_FUNCTIONS_REFERENCE.md`
- **Main README**: `README.md`

---

**Last Updated**: March 2026  
**Version**: HydroSwift GUI 1.0.0  
**License**: MIT
