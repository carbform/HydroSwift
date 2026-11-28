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

### 3. Search Results
After a search, each source shows how many items it returned, and whether it failed or was partial. The details are in the **Source log** of Advanced mode. Nothing is selected automatically.

### 4. Download Bar
Located at the top of the main screen:
* **Download (n)**: Downloads the ticked stations in the background, with progress, **Cancel download**, and **Retry** for failed or incomplete items.
* **Estimate size**: Asks sources for record counts (only NWDP reports them).
* **Format Selector**: Station files are saved as CSV; `parquet`, `gpkg` or `json` also writes one combined file.
* **Destination Folder**: Target folder, with a **Browse…** OS directory picker.

---

## Main Workspace Views

### View 1: Map Layers
Interactive auto-zooming Leaflet map powered by official vector shapefiles:
* **Official Overlays**:
  * **India National Boundary**: Official survey boundary of India (interactive clicks disabled so markers are never shadowed).
  * **CWC River Basins**: Central Water Commission major basin polygons with automated auto-zoom bounding box fitting.
  * **Major Aquifers**: CGWB / India-WRIS hydrogeological aquifer systems.
* **Marker Coloring**: Automatically color-coded by source (CWC: blue, WRIS: green, NWDP: orange).
* **Dedicated Map Panes**: Station and reservoir markers sit in `stationPane` (`zIndex: 650`), ensuring marker popups are unconditionally clickable without polygon interference.

### View 2: Select Stations
* Tick individual stations; filter by words or by source.
* **Select all shown**, **Unselect shown**, **Clear selection**.
* Shows where each row matched and which fields the source did not state.
* **Save search results to JSON**.

### View 3: Visualize
Pick a station and an analysis:
* **Time series**: stage and discharge with CWC warning/danger lines; as reported, daily, monthly or annual; range slider.
* **Summary & data quality**: statistics, completeness, longest gap, gauge-zero count.
* **Compare stations**: one variable across stations.
* **Monthly pattern**: spread by month (totals for rainfall) and departure from that month's average.
* **Warning & danger exceedance**: events with start, end, hours and peak, timed from reading timestamps.
* **Flow duration curve**: from daily mean discharge.
* **Rating curve**: observed discharge only; estimated discharge is never fitted.
* **Rainfall** and **Groundwater**.

Readings equal to the station's gauge zero, and spikes above a limit you set, can be excluded; the page says how many.

---

## Advanced Mode

Turn on **Advanced** (top right) for a terminal panel docked at the bottom of the window. **Source log** shows what each source returned, skipped or assumed; **Console** takes commands that update the page above:

```text
search --basin Cauvery --source CWC --period 2024:2024
select 0,1
get
plot muthankera --kind exceedance
stats --freq monthly --out monthly.csv
```

Type `help` for the full list. Searches and downloads made with the mouse are logged as commands. It is not a system shell. It runs only when the dashboard listens on localhost (the default for `hyswift-gui`).

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
* **Credits Footer**: Permanent links to [carbform](https://github.com/carbform) ([carbform.github.io](https://carbform.github.io)) and [Bharath Reddy](https://github.com/bharathk113), official government API documentation, and statutory disclaimer.
