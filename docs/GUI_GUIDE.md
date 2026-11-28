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

## Layout

A single top bar holds the three views (**Find & download**, **Analyse**, **Reservoirs**), the **Advanced** switch and a **Menu** (dark mode, help, about). There is no sidebar.

## Find & download

1. **Search row**: *Search by* river basin, state or keyword; the place; the variable; **From** and **To** years; **Sources**; **Search**.
2. **Results table** (left): tick stations; filter by words or source; **Select all shown**, **Unselect shown**, **Clear selection**. Nothing is selected automatically.
3. **Download (n)** (above the table): runs in the background with progress, **Cancel download**, and **Retry** for failed or incomplete items. **Options** holds the format (`csv`, `parquet`, `gpkg`, `json`; station files stay CSV), the download folder, **Estimate size** and **Save search results to JSON**.
4. **Map** (right): stations by source; **Layers** toggles the India boundary, CWC basins and major aquifers. In narrow windows the map moves below the table.
   * **India National Boundary**: official survey boundary (clicks disabled so markers are never shadowed).
   * **CWC River Basins**: Central Water Commission major basin polygons; the map zooms to the chosen basin.
   * **Major Aquifers**: CGWB / India-WRIS hydrogeological aquifer systems.
   * Markers are coloured by source and sit in their own pane (`stationPane`), so popups stay clickable.

Each source's count is shown above the results; failed or partial sources raise a warning. Details are in the **Source log** of Advanced mode.

## Analyse
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
