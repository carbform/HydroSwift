# HydroSwift Dashboard - Quick Reference Card

## 🚀 Quick Launch

### Terminal
```bash
# Recommended command:
hyswift gui

# Or direct entry point:
hyswift-gui
```
Launches automatically in your browser at `http://localhost:8501`.

---

## 🧭 Navigation & Modules

| Module / Button | Purpose |
| :--- | :--- |
| **Hydrology Data** | Spatial scoping, cross-boundary catalog discovery, multi-format downloading, auto-zooming Leaflet map, and interactive time-series plots. |
| **Reservoir Status** | Dedicated CWC RSMS live bulletin, national reservoir storage KPIs, interactive Leaflet capacity map, and CSV export. |
| **Help** | Top action popover displaying workflow guides and CLI shortcuts. |
| **About** | Top action popover displaying author credits, official API endpoints, and disclaimer. |
| **Advanced** | Terminal panel at the bottom: `hyswift` console (localhost only) and source log. |
| **Dark Mode** | High-contrast dark theme toggle with instant stylesheet re-injection. |

---

## 🗺️ Hydrology Data Workflow

### 1. Boundary & Spatial Scope
* **Hydrological (Basin)**: Select from 22 official CWC River Basins (e.g. Cauvery, Ganga, Godavari, Krishna). The system cross-discovers constituent administrative state datasets from NWDP.
* **Administrative (State)**: Select from 36 Indian States & UTs. Automatically finds intersecting river basins.
* **All / Custom**: Free text location keyword.

### 2. Variable & Sources
* **Variable Dropdown**: `All Variables`, `Water level`, `Discharge`, `Rainfall`, `Groundwater level`, `Water quality`, or `Custom...`.
* **Sources**: Toggle CWC Flood Forecasting, India-WRIS OpenAPI, and NWDP Open Data.

### 3. Review & Select
* Check the per-source status shown after a search.
* Tick stations in the **Select Stations** view (nothing is pre-selected).

### 4. Download
* Choose format `csv`, `parquet`, `gpkg` or `json` (station files stay CSV; others add a combined file).
* Pick the folder with **Browse…**, then click **Download (n)**.
* **Cancel download** stops it; **Retry** repeats failed or incomplete items.

---

## 📊 Analyses (Visualize view)

Time series · Summary & data quality · Compare stations · Monthly pattern · Warning & danger exceedance · Flow duration curve · Rating curve · Rainfall · Groundwater.

---

## 🌊 Reservoir Status Module (CWC RSMS)

* **Fetch Live Status**: Retrieves live levels, FRL, DSL, and storage from CWC RSMS portal and GeoServer WFS.
* **KPI Metrics**: Monitored Reservoirs, Total Live Capacity (BCM), Current Storage Monitored (BCM and %), and Critical Reservoirs (<40%).
* **National Reservoir Map**: Interactive pins with storage percentage, capacity, and current water levels.
* **Export CSV**: Download complete national reservoir table with one click.
