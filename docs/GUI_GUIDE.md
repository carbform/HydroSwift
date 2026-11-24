# HydroSwift Web Dashboard Guide

The HydroSwift Dashboard is a modern, publication-grade hydrological analysis studio built on Streamlit with a clean, high-contrast subtle neobrutal aesthetic (IBM Plex Mono typography, tactile controls, and hairline borders).

Start the studio from the command line:
```bash
hyswift gui
# or directly:
hyswift-gui
```
The studio launches automatically in your browser at `http://localhost:8501`.

---

## Top Navigation & Modular Architecture

HydroSwift decouples station-level observational discovery from national reservoir storage tracking via a top-level module switcher:

1. **Hydrology Data**: Spatial boundary search, catalog discovery, multi-format downloading, auto-zooming Leaflet map, and interactive visualizers.
2. **Reservoir Status**: Central Water Commission (CWC) Real-Time Reservoir Storage Monitoring System (RSMS) live bulletin and national capacity map.
3. **Help & About**: Instant popovers in the top header with step-by-step workflow guides, official government API links, author profiles, and statutory disclaimers.
4. **Dark Mode Toggle**: High-contrast dark theme toggle with instant stylesheet re-injection.

---

## Module 1: Hydrology Data

### 1. Sidebar Boundary & Scope
* **Hydrological (Basin)**: Query by official CWC River Basin (e.g., Cauvery, Ganga, Godavari, Krishna, Narmada, Mahanadi). The engine automatically cross-discovers constituent administrative state datasets from NWDP.
* **Administrative (State)**: Query by Indian State or Union Territory (e.g., Karnataka, Maharashtra, Odisha). Intersecting river basins are automatically identified.
* **All / Custom**: Free-form keyword search across rivers, districts, and station locations.

### 2. Hydrological Variables & Data Sources
* **Variable Dropdown**: Filter by *Water level*, *Discharge*, *Rainfall*, *Groundwater level*, *Water quality*, *All Variables*, or specify a custom keyword.
* **Data Sources**:
  * **CWC Flood Forecasting System (FFS)**: Real-time river water levels and rating-curve discharge.
  * **India-WRIS OpenAPI 3.0**: Official REST API endpoints for national observation networks.
  * **NWDP Open Data**: CKAN open data portal for groundwater monitoring wells, rainfall, and climate parameters.
* **Search & Discover**: Triggers catalog discovery across all enabled sources and constituent spatial boundaries.

### 3. Discovery Pop-Up Modal
Upon completing catalog search, an automatic pop-up modal card appears:
* Shows total datasets & stations discovered.
* Batch selection shortcuts: **Select All**, **First 10 Stations**, **View on Map**, and **Close Pop-up**.
* Catalog preview table displaying Source, Title, Location, Variable, and Temporal Resolution.

### 4. Top Download Action Bar
Located directly at the top of the main screen (not hidden in the sidebar):
* **Download Selected**: One-click primary download trigger for all selected stations.
* **Format Selector**: Export directly to `csv`, `parquet`, `gpkg` (GeoPackage), or `json`.
* **Destination Folder**: Configurable target folder path with a native **Browse…** OS directory picker button (`choose_folder`).
* **Live Progress**: Progress bar reporting completed downloads, per-file record counts, and provenance logging to `manifest.json`.

---

## Main Workspace Tabs

### Tab 1: Map Layers
Interactive auto-zooming Leaflet map powered by official vector shapefiles:
* **Official Overlays**:
  * **India National Boundary**: Official survey boundary of India (interactive clicks disabled so markers are never shadowed).
  * **CWC River Basins**: Central Water Commission major basin polygons with automated auto-zoom bounding box fitting.
  * **Major Aquifers**: CGWB / India-WRIS hydrogeological aquifer systems.
* **Marker Coloring**: Automatically color-coded by source (CWC: blue, WRIS: green, NWDP: orange).
* **Dedicated Map Panes**: Station and reservoir markers sit in `stationPane` (`zIndex: 650`), ensuring marker popups are unconditionally clickable without polygon interference.

### Tab 2: Discovered Catalog
* Search and filter table with keyword searching.
* Shows Source, Station Title, Location, Variable, Resolution, Temporal Coverage, and Provider.
* Quick selection shortcuts: *First 5 Stations*, *First 10 Stations*, *Add Filtered*, *Select All*.
* Export catalog summary directly to `catalog.json`.

### Tab 3: Visualize
Publication-grade interactive plots rendered with Plotly:
1. **Stage & Discharge Hydrograph**: Synchronized dual-axis plot showing river stage (meters) on the primary axis and discharge (m³/s) on the secondary axis, with Warning Level and Danger Level threshold lines.
2. **Stage-Discharge Rating Curve (H-Q)**: Fitted power-law curve ($Q = a(h - h_0)^b$) over synchronized stage-discharge observation pairs.
3. **Rainfall Hyetograph & Mass Curve**: Inverted bar chart showing precipitation hyetograph paired with cumulative mass curve.
4. **Flow Duration Curve (FDC)**: Logarithmic discharge exceedance probability curve with marked $Q_{10}$ (high flow), $Q_{50}$ (median flow), and $Q_{90}$ (low flow) percentiles.
5. **Groundwater Level Hydrograph**: Hydrograph of groundwater depth and water table fluctuations with mean water table reference line, optional inverted Y-axis toggle (mbgl depth convention), and KPI metrics (**Min Level**, **Mean Level**, **Max Level**, **Fluctuation Range**).

---

## Module 2: Reservoir Status (CWC RSMS)

Dedicated national reservoir storage monitoring module:
* **Fetch Live Status**: Retrieves real-time storage bulletins for ~180 major Indian reservoirs from the CWC RSMS portal and GeoServer WFS layer.
* **National Storage KPIs**:
  * Total Monitored Reservoirs
  * Total Live Storage Capacity (BCM)
  * Current Live Storage Monitored (BCM and % of capacity)
  * Critical Reservoirs (<40% live capacity)
* **Interactive National Reservoir Map**: Pins reservoirs across India with popup details including Full Reservoir Level (FRL), Dead Storage Level (DSL), Current Storage, and live capacity percentage.
* **Data Table & CSV Export**: Searchable table of all monitored reservoirs with one-click `Export CSV` download.

---

## Help, About & Credits Footer

* **Help Popover**: Quick reference workflow guide available from the top navigation bar.
* **About Popover**: Project overview, author profiles, and official API references.
* **Credits Footer**: Permanent links to [carbform](https://github.com/carbform) ([carbform.github.io](https://carbform.github.io)) and [Bharatkreddy](https://github.com/Bharatkreddy), official government API documentation, and statutory disclaimer.
