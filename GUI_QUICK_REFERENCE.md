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

### 3. Discovery Pop-Up Modal
* Pops up automatically when **Search & Discover** completes.
* Use shortcuts: `Select All`, `First 10 Stations`, or `View on Map`.

### 4. Top Download Action Bar
* Located at the top of the main area.
* Choose format: `csv`, `parquet`, `gpkg`, `json`.
* Target folder with **Browse…** OS folder picker dialog.
* Click **Download Selected ({count})**.

---

## 📊 Visualizer Plot Types (Tab: Visualize)

| Plot Type | Description |
| :--- | :--- |
| **Stage & Discharge Hydrograph** | Dual-axis synchronized water level (m) and discharge (m³/s) with Warning & Danger levels. |
| **Stage-Discharge Rating Curve (H-Q)** | Power-law rating curve fit ($Q = a(h - h_0)^b$) on synchronized stage-discharge observations. |
| **Rainfall Hyetograph & Mass Curve** | Inverted rainfall bar chart paired with cumulative precipitation mass curve. |
| **Flow Duration Curve (FDC)** | Exceedance probability curve with marked $Q_{10}$, $Q_{50}$, and $Q_{90}$ flow metrics. |
| **Groundwater Level Hydrograph** | Groundwater level time series with mean reference line, optional inverted Y-axis toggle (mbgl depth convention), and Min/Mean/Max/Fluctuation KPIs. |

---

## 🌊 Reservoir Status Module (CWC RSMS)

* **Fetch Live Status**: Retrieves live levels, FRL, DSL, and storage from CWC RSMS portal and GeoServer WFS.
* **KPI Metrics**: Monitored Reservoirs, Total Live Capacity (BCM), Current Storage Monitored (BCM and %), and Critical Reservoirs (<40%).
* **National Reservoir Map**: Interactive pins with storage percentage, capacity, and current water levels.
* **Export CSV**: Download complete national reservoir table with one click.
