# HydroSwift GUI - Quick Reference Card

## 🚀 Getting Started

### Installation
```bash
# Standard installation with GUI
pip install -e .[gui]

# Full installation (all features)
pip install -e .[all]

# Development installation
pip install -r requirements-gui.txt
```

### Launch
```bash
hyswift-gui                          # Command-line
python -m swift_app.gui              # Module execution
bash scripts/launch_hyswift_gui.sh   # Quick-start script
```

---

## 📊 Tab-by-Tab Guide

### Tab 1: WRIS Data (📊)
**Purpose**: Discover and download India Water Resources data

- **Select Basin**: Godavari, Krishna, Narmada, etc.
- **Select Variable**: Discharge, water level, rainfall, temperature, etc.
- **Discover**: Find available stations
- **Download**: Retrieve data with selected parameters

**Outputs**: `output/wris/{basin}/{variable}/*.csv`

### Tab 2: CWC Stations (💧)
**Purpose**: Access Central Water Commission flood forecasting data

- **Browse Stations**: List of monitoring stations
- **Filter Basin**: Narrow down by region
- **Select Stations**: Multi-select from list
- **Download**: Retrieve water level data
- **Refresh Metadata**: Update station information

**Outputs**: `output/cwc/{basin}/stations/*.csv`

### Tab 3: Configuration (⚙️)
**Purpose**: Set download parameters and options

**Date Settings**:
- Start Date: Beginning of analysis period
- End Date: End of analysis period

**Format & Output**:
- Format: CSV / Excel / Parquet
- Output Directory: Where to save files
- Browse button: File dialog to select directory

**Options**:
- ☐ Overwrite existing files
- Request Delay: 0-60 seconds between API calls
- ☐ Merge downloaded files
- ☐ Include metadata

### Tab 4: Results (📈)
**Purpose**: View, analyze, and visualize downloaded data

- **Refresh Results**: Scan output directory
- **Plot Selected Data**: Time-series visualization
- **Export as GeoPackage**: Geospatial format
- Files List: Browse downloaded CSV files
- File Information: Details about selected file

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open output directory |
| `Ctrl+,` | Open settings |
| `Ctrl+Q` | Exit application |
| `F1` | Show API help |

---

## 🎨 User Interface Elements

### Status Bar (Bottom)
- Left side: Current operation status
- Right side: Progress percentage/message

### Logger Widget (Lower Panel)
- `[HH:MM:SS] Message` format
- **Color Codes**:
  - 🔵 Blue: Information
  - 🟢 Green: Success
  - 🟡 Orange: Warning
  - 🔴 Red: Error

### Buttons
- 🔍 Discover Stations
- ⬇️ Download Data
- 🔄 Refresh
- 📊 Plot
- 💾 Export
- Browse / Settings

---

## 📁 Output Directory Structure

```
output/
├── wris/
│   ├── Godavari/
│   │   ├── discharge/
│   │   │   ├── 001-STATION_discharge.csv
│   │   │   ├── 002-STATION_discharge.csv
│   │   │   └── merged_discharge.csv
│   │   └── water_level/
│   │       └── ...
│   ├── Krishna/
│   │   └── ...
│   └── ...
│
└── cwc/
    ├── Krishna/
    │   ├── stations/
    │   │   ├── 040-STATION.csv
    │   │   └── ...
    │   └── waterlevel.gpkg
    └── ...
```

---

## ⚙️ Settings (File → Settings)

### General Tab
- **Output Directory**: Default save location
- **Theme**: Light or Dark
- **Start maximized**: Window size on launch
- **Show tips**: Display help on startup

### Download Tab
- **Default Format**: CSV / Excel / Parquet
- **Request Delay**: 0-60 seconds (1 recommended)
- **Connection Timeout**: 5-300 seconds
- **Auto-merge**: Default merge behavior
- **Confirm Overwrite**: Ask before replacing files

### API Tab
- **Default Basin**: WRIS basin preset
- **Default Variable**: WRIS variable preset
- **Date Range**: Default days to retrieve (365 = 1 year)
- **Auto Refresh CWC**: Update metadata on startup

---

## 🔧 Common Tasks

### Download Discharge Data for Godavari (2023)
1. **WRIS Tab** → Basin: Godavari → Variable: Discharge → Discover
2. **Config Tab** → Start: 2023-01-01 → End: 2024-01-01 → Merge: ON
3. **WRIS Tab** → Download Selected Stations
4. **Results Tab** → Refresh Results → Plot to view

### Compare Multiple Basins
1. Repeat WRIS discovery for Godavari, Krishna, Narmada
2. Download each with merge enabled
3. Results tab shows all files
4. Plot any file for visualization

### Export for GIS Analysis
1. Download data (any source)
2. Go to Results tab
3. Click "Export as GeoPackage"
4. Opens `output/*/waterlevel.gpkg` (geospatial format)
5. Use in QGIS or GeoPandas

### Adjust Download Speed
1. File → Settings → Download Tab
2. Increase Request Delay (5-10 seconds for slower networks)
3. Adjust Connection Timeout if experiencing timeouts
4. Click OK

---

## 🐛 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| GUI won't start | Check PyQt5: `pip install --upgrade PyQt5` |
| Slow discovery | Use limit field, increase request delay |
| Download fails | Check internet, increase timeout in settings |
| Plot shows nothing | Ensure CSV has 'time' column and value data |
| Permission error | Check output folder permissions |
| Out of memory | Use parquet format, reduce date range |

---

## 📊 Data Formats

### CSV (Default) ✅ Recommended
- Compatible with Excel, Python, R
- Human-readable
- Easy to import
- No special tools required

### Excel
- Requires: `pip install openpyxl`
- Same as CSV but in .xlsx format
- Slower for large files

### Parquet
- Binary format
- Most efficient compression
- Best for big data
- Requires: `pip install pyarrow`

---

## 💡 Tips & Tricks

1. **Merge your downloads** for easier analysis → single file per variable
2. **Use CSV format** for fastest I/O and broad compatibility
3. **Set request delay** to 2-5 seconds to be respectful to API servers
4. **Create organized output dirs**: `output_2023/`, `output_2024/`, etc.
5. **Export to GeoPackage** for spatial analysis in QGIS
6. **Check logs** if errors occur - detailed information provided
7. **Save settings** once and they persist across sessions
8. **Use Configuration tab** before downloading multiple datasets

---

## 🔗 Related Resources

| Resource | Link |
|----------|------|
| Full Documentation | `docs/GUI_GUIDE.md` |
| Module README | `swift_app/gui/README.md` |
| Python API Guide | `docs/PYTHON_API_GUIDE.md` |
| CLI Usage | `docs/CLI_USAGE_GUIDE.md` |
| GitHub Repository | https://github.com/carbform/HydroSwift |
| ReadTheDocs | https://hydroswift.readthedocs.io/ |

---

## 📞 Need Help?

1. **First**: Check `docs/GUI_GUIDE.md` FAQ section
2. **Then**: Check GitHub Issues: https://github.com/carbform/HydroSwift/issues
3. **Report**: Open new issue with Python version, error message, and steps

---

## 🎯 Quick Reference - File Menu

```
File
├── Open Output Directory    (Ctrl+O)  → File manager
├── Settings                 (Ctrl+,)  → Preferences dialog
└── Exit                     (Ctrl+Q)  → Close application

Edit
└── Clear Log                          → Remove all log messages

Help
├── About HydroSwift                   → Version & credits
└── API Help                 (F1)      → Print Python API help
```

---

**Version**: HydroSwift GUI 1.0.0  
**Last Updated**: March 2026  
**License**: MIT
