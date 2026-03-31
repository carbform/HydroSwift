"""
HydroSwift GUI Module - README

This module provides a professional PyQt5-based graphical user interface for HydroSwift,
making it easy for non-technical users and researchers to discover, download, and visualize
hydrological data from WRIS and CWC portals.
"""

# HydroSwift GUI ⚡

A modern graphical user interface for HydroSwift, enabling interactive workflows for hydrological data retrieval.

## Features

### 🌍 **WRIS Data Discovery & Download**
- Interactive basin and variable selection
- Real-time station discovery from [India-WRIS](https://indiawris.gov.in/)
- Browse discovered stations in a table view
- Download selected stations with automatic merging
- Support for all WRIS variables: discharge, water level, rainfall, temperature, etc.

### 💧 **CWC Station Management**
- Browse Central Water Commission flood forecasting stations
- Filter by basin and station code
- Download water level and related data
- Auto-refresh CWC metadata
- Track download progress in real-time

### ⚙️ **Flexible Configuration**
- Date range selection with intuitive calendar picker
- Output format options: CSV, Excel, Parquet
- Request delay and timeout configuration
- Toggle automatic merging and metadata inclusion
- Overwrite protection with confirmation dialogs

### 📊 **Results Visualization**
- Browse downloaded files
- Interactive time-series plotting with matplotlib
- File information display
- Export to GeoPackage (geospatial format)
- Direct access to output directory

### 🎨 **Professional UI**
- Tabbed interface for organized workflows
- Real-time execution logging with color-coded levels
- Status bar showing current operation
- Progress indicators for long-running tasks
- Settings dialog for persistence

## Installation

### Option 1: Install with GUI support

```bash
# Clone the repository
git clone https://github.com/carbform/HydroSwift.git
cd HydroSwift

# Install with GUI dependencies
pip install -e .[gui]
```

### Option 2: Install all features including GUI

```bash
pip install -e .[all]
```

This installs the core library plus geospatial, visualization, and GUI support.

## Usage

### Launch the GUI

After installation, run:

```bash
# Command-line launcher
hyswift-gui

# Or run directly with Python
python -m swift_app.gui
```

### Typical Workflow

#### 1. **Discover Stations from WRIS**
   - Select a basin (e.g., Godavari)
   - Choose a variable (e.g., discharge)
   - Click "Discover Stations" to search
   - Review the list of available monitoring stations

#### 2. **Configure Download Parameters**
   - Switch to the "Configuration" tab
   - Set date range (start and end dates)
   - Choose output format (CSV recommended)
   - Set output directory
   - Toggle merge option (recommended for analysis)

#### 3. **Download Data**
   - Click "Download Selected Stations"
   - Watch progress in the execution log
   - Data is saved to the output directory

#### 4. **View and Analyze Results**
   - Switch to "Results & Visualization" tab
   - Click "Refresh Results" to see downloaded files
   - Select a file and click "Plot Selected Data" to visualize
   - Export to GeoPackage for geospatial analysis

## Module Structure

```
swift_app/gui/
├── __init__.py                 # Package initialization
├── app.py                      # Entry point and launcher
├── main_window.py              # Main GUI window and orchestration
├── panels.py                   # Tabbed panel components
│   ├── WRISDiscoveryPanel      # WRIS discovery & download
│   ├── CWCDownloadPanel        # CWC station download
│   ├── DownloadConfigPanel     # Download configuration
│   └── ResultsViewerPanel      # Results visualization
├── logger_widget.py            # Colored execution log widget
├── settings_dialog.py          # Settings and preferences dialog
└── README.md                   # This file
```

## Key Components

### Main Window (`main_window.py`)
Central application window that:
- Manages tabbed interface
- Handles menu bar and shortcuts
- Displays status and progress indicators
- Orchestrates signal connections between panels
- Manages application settings and preferences

### Panels (`panels.py`)
Four specialized panels for different workflows:
- **WRISDiscoveryPanel**: Discover and download from India-WRIS
- **CWCDownloadPanel**: Download from CWC flood forecasting system
- **DownloadConfigPanel**: Configure download parameters and date ranges
- **ResultsViewerPanel**: Browse and visualize downloaded data

### Logger Widget (`logger_widget.py`)
Colored text widget for execution logs with:
- Timestamp for each message
- Color-coded severity levels (info, success, warning, error)
- Automatic scrolling to latest messages
- Clear and section formatting

### Settings Dialog (`settings_dialog.py`)
Multi-tab preferences dialog covering:
- General settings (output dir, theme, startup)
- Download options (format, delay, timeout)
- API defaults (basin, variable, date range)

### Worker Threading (`panels.py`)
Background worker threads for:
- Station discovery (non-blocking UI)
- Data downloads (progress tracking)
- Metadata refresh (async operations)

## Code Examples

### Using the GUI programmatically

```python
from swift_app.gui.main_window import HydroSwiftGUI
from PyQt5.QtWidgets import QApplication
import sys

app = QApplication(sys.argv)
gui = HydroSwiftGUI()
gui.show()
sys.exit(app.exec_())
```

### Extending with custom panels

```python
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from swift_app.gui.main_window import HydroSwiftGUI

class CustomPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Custom functionality here"))
        self.setLayout(layout)

# Add to main window
window = HydroSwiftGUI()
window.tab_widget.addTab(CustomPanel(), "Custom")
window.show()
```

## Design Standards & Conventions

The GUI follows HydroSwift library conventions:

### **Integration with Core API**
- Uses existing `hydroswift` namespace functions
- Leverages `hydroswift.fetch()`, `hydroswift.wris.*`, `hydroswift.cwc.*`
- Respects all core library parameters and configurations

### **Naming Conventions**
- Panel classes: `{Name}Panel` (e.g., `WRISDiscoveryPanel`)
- Signal methods: `on_{action}` (e.g., `_on_discovery_complete`)
- Worker threads: `{task}_worker` (e.g., `_download_worker`)
- UI setup methods: `_setup_{component}` and `_create_{group}`

### **Error Handling**
- Try-except blocks with descriptive error messages
- Message boxes for critical errors
- Log messages for warnings and info
- Graceful degradation when dependencies missing

### **Async Operations**
- `QThread` for long-running tasks (downloads, discovery)
- Signals for communication between threads
- Progress indicators for user feedback
- Status messages for operation tracking

### **Data Flow**
1. **User Input** → UI components
2. **Signal Emission** → Status/result signals
3. **Worker Thread** → Background processing
4. **Signal Reception** → Slot handlers
5. **UI Update** → Widgets refresh with new data

## Dependencies

### Required for GUI
```
PyQt5>=5.15.0
PyQt5-stubs  # Type hints
```

### Inherited from core HydroSwift
```
requests
pandas
tqdm
openpyxl
matplotlib
```

### Optional (for full features)
```
geopandas          # Geospatial visualization
shapely            # Geospatial operations
rich               # Enhanced CLI output
```

## Development Guidelines

### Adding a New Panel

1. Create a new class inheriting from `QWidget` in `panels.py`
2. Define signals at class level (inherit from proper base)
3. Implement `_setup_ui()` for layout
4. Implement worker functions for async tasks
5. Connect signals to slots
6. Add tab to main window in `main_window.py`

```python
class CustomPanel(QWidget):
    status_changed = pyqtSignal(str)
    log_message = pyqtSignal(str, str)
    
    def __init__(self):
        super().__init__()
        self._setup_ui()
    
    def _setup_ui(self):
        # Initialize UI components
        pass
```

### Extending the Main Window

1. Add properties for new components
2. Create new panels in `_setup_ui()`
3. Connect signals in `_connect_signals()`
4. Add menu items in `_setup_menu_bar()`

### Following HydroSwift Standards

- Use existing `hydroswift.*` APIs instead of duplicating logic
- Respect dataset variable naming (discharge, water_level, etc.)
- Follow basin naming conventions from WRIS
- Mirror CLI options in GUI configuration
- Maintain logging and progress reporting

## Troubleshooting

### PyQt5 Installation Issues
```bash
# Linux/Debian
sudo apt-get install python3-pyqt5

# macOS
brew install pyqt5

# Or use pip with system dependencies
pip install --upgrade PyQt5
```

### Import Errors
```bash
# Ensure GUI dependencies installed
pip install -e .[gui]

# Verify installation
python -c "from PyQt5.QtWidgets import QApplication; print('OK')"
```

### HydroSwift API Not Found
```bash
# Ensure core library is installed
pip install -e .

# Verify core functionality
python -c "import hydroswift; hydroswift.help()"
```

## Performance Considerations

- **Long operations**: Use worker threads to prevent UI freezing
- **Logging**: Limit scroll area to 1000+ messages for memory
- **Large datasets**: Consider chunking downloads by date range
- **Network**: Implement configurable request delays
- **Memory**: Clear log periodically or implement rotating buffer

## Future Enhancements

Potential features for future versions:
- Real-time map visualization with folium/leaflet
- Advanced filtering and station search
- Batch operations with job scheduling
- Data quality indicators and metadata inspection
- Export to multiple formats (NetCDF, HDF5)
- Integration with cloud storage (S3, GCS)
- API key management and secure authentication
- Automated workflows and scheduling

## License

MIT License — see [LICENSE](../../LICENSE) for details

## Support

- **Documentation**: https://hydroswift.readthedocs.io/
- **GitHub Issues**: https://github.com/carbform/HydroSwift/issues
- **API Reference**: See `docs/API_FUNCTIONS_REFERENCE.md`
- **Examples**: See `docs/examples/`

## Acknowledgements

Built with:
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - Professional GUI framework
- [HydroSwift](https://github.com/carbform/HydroSwift) - Core hydrological data library
- [Pandas & Matplotlib](https://pandas.pydata.org/) - Data processing and visualization
- [GeoPandas & Shapely](https://geopandas.org/) - Geospatial analysis

---

**HydroSwift GUI v1.0.0** — Making hydrological data accessible to everyone ⚡
