# HydroSwift

[![Tests](https://github.com/carbform/HydroSwift/actions/workflows/tests.yml/badge.svg)](https://github.com/carbform/HydroSwift/actions)
[![Documentation](https://readthedocs.org/projects/hydroswift/badge/?version=latest)](https://hydroswift.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

**Fast, unified workflows for hydrological data discovery, aggregation, and visualization across India.**

HydroSwift automates cross-boundary search, retrieval, standardization, and visualization of hydrological and meteorological observations across major Indian water data platforms:
* **Central Water Commission (CWC) Flood Forecasting System**: Real-time telemetry water level stage and rating-curve discharge estimates.
* **Central Water Commission (CWC) Reservoir Storage Monitoring System (RSMS)**: Live capacity and storage monitoring for ~180 major national reservoirs.
* **India-WRIS OpenAPI 3.0**: Official REST endpoints for national hydro-meteorological networks.
* **National Water Data Portal (NWDP / CKAN)**: Open datasets for groundwater monitoring wells, rainfall, and climate parameters.

---

## Key Features

* **Subtle Neobrutal Web Dashboard**: Launch an interactive dashboard (`hyswift-gui` or `hyswift gui`) with publication-grade monospace styling, official GeoJSON boundaries (India National Survey, CWC River Basins, Major Aquifers), and dedicated panes preventing click shadowing.
* **Dual Boundary Scoping & Cross-Discovery**: Query by hydrological river basin (CWC Basins) or administrative state (Indian States & UTs); queries automatically cross-discover constituent open datasets.
* **Rich Hydrological Visualizers**:
  * **Stage & Discharge Hydrographs**: Dual-axis synchronized water level and discharge with warning & danger thresholds.
  * **Stage-Discharge Rating Curves (H-Q)**: Logarithmic curve fitting ($Q = a(h - h_0)^b$) on observed pairs.
  * **Rainfall Hyetographs**: Inverted precipitation bars paired with cumulative mass curves.
  * **Flow Duration Curves (FDC)**: Exceedance probability curves with key percentiles ($Q_{10}, Q_{50}, Q_{90}$).
  * **Groundwater Level Hydrographs**: Water level and depth-to-water hydrographs with mean reference lines and optional inverted Y-axis (mbgl depth convention).
* **Unified Data Model**: Normalizes disparate vendor formats and timestamp conventions into one tidy table (`time`, `value`, `variable`, `unit`, `station_id`, `station_name`, `source`, `method`, `flag`).
* **Multi-Format Export**: Export datasets into CSV, Parquet, GeoPackage, or JSON with automated download manifests (`manifest.json`).

---

## Installation

```bash
git clone https://github.com/carbform/HydroSwift.git
cd HydroSwift

# Core package
pip install -e .

# With modern Web GUI & Interactive Visualization (Streamlit + Plotly)
pip install -e ".[gui]"

# Full installation (Geospatial + GUI + CLI)
pip install -e ".[all]"
```

Verify installation:
```bash
hyswift --version
```

---

## Quick Start

### 1. Modern Web Dashboard

Launch the browser studio:
```bash
hyswift gui
# or directly:
hyswift-gui
```
The studio opens automatically at `http://localhost:8501`, featuring:
* **Hydrology Data**: Spatial scope selector (River Basin vs. State), variable filter, interactive auto-zooming Leaflet map, discovery pop-up modal, top download action bar, and visualizer.
* **Reservoir Status**: Dedicated live bulletin and interactive storage map for ~180 CWC monitored reservoirs.
* **Help & About**: Built-in workflow guides, links to official government APIs, and statutory disclaimer.

---

### 2. Python API

HydroSwift follows one intuitive workflow: **Find $\rightarrow$ Review $\rightarrow$ Get $\rightarrow$ Use**.

```python
import hydroswift as hs

# 1. FIND: Search across CWC, WRIS, and NWDP catalogs
cat = hs.search("rainfall", location="Karnataka", period=("2020", "2024"))
# Or by exact CWC River Basin
cat_basin = hs.search("discharge", basin="Cauvery", sources=["CWC"])

# 2. REVIEW: Check source provenance, status, and estimated records
print(cat.attrs["source_status"])
print(hs.estimate(cat.head(5)))

# 3. GET: Fetch data into local destination folder with progress tracking
run = hs.fetch(cat.head(10), output_dir="output", period=("2020", "2024"))

# 4. USE: Load into unified tidy DataFrame
tidy = hs.load(run)
print(tidy[["time", "station_name", "variable", "value", "unit"]].head())

# Export or plot
hs.merge(run, "output/karnataka_rainfall.parquet")
hs.plot(run, output_dir="output/plots")

# 5. CWC RSMS Live Reservoirs
res_df = hs.rsms.daily(output_path="output/reservoirs_today.csv")
print(res_df[["reservoir_name", "storage_bcm", "live_cap_bcm", "storage_pct"]].head())
```

---

### 3. Command Line Interface (CLI)

```bash
# Guided interactive prompt mode
hyswift

# Search catalog by variable and boundary
hyswift search rainfall --where Karnataka --period 2020:2024 --save cat.json
hyswift search discharge --basin Cauvery --sources CWC --save cauvery.json

# Download data from catalog
hyswift get --from cat.json --rows 0:5 --out output

# Tidy summary and unified merge
hyswift show output
hyswift merge output output/merged.parquet

# Generate summary hydrograph plots
hyswift plot output output/plots

# Real-time CWC Reservoir Storage bulletin
hyswift rsms daily
```

---

## Output Structure

```
output/
  manifest.json                      # Provenance, query, and download metadata
  nwdp/<organization>/NWDP_*.csv     # NWDP station observations
  cwc/<basin>/CWC_*.csv              # CWC FFS river stage and discharge
  wris/<basin>/WRIS_*.csv            # India-WRIS station series
  cwc_rsms/daily_snapshot_*.csv      # CWC RSMS reservoir storage tables
  plots/*.png                        # Generated summary plots
```

---

## Documentation

Full documentation is available at **[hydroswift.readthedocs.io](https://hydroswift.readthedocs.io/)**:
* [Python API Guide](docs/PYTHON_API_GUIDE.md)
* [CLI Usage Guide](docs/CLI_USAGE_GUIDE.md)
* [Web GUI Guide](docs/GUI_GUIDE.md)
* [API Functions Reference](docs/API_FUNCTIONS_REFERENCE.md)
* [Example Notebooks](docs/examples/)

---

## Authors & Credits

* **carbform** — [carbform.github.io](https://carbform.github.io) · [GitHub: @carbform](https://github.com/carbform)
* **Bharath Reddy** — [GitHub: @bharathk113](https://github.com/bharathk113)

---

## Official Government APIs & Data Sources

* [Central Water Commission (CWC) Flood Forecasting System (FFS)](https://ffs.india-water.gov.in/)
* [Central Water Commission (CWC) Reservoir Storage Monitoring System (RSMS)](http://waris.cwc.gov.in/)
* [India Water Resources Information System (India-WRIS OpenAPI 3.0)](https://indiawris.gov.in/)
* [National Water Data Portal (NWDP / data.gov.in)](https://data.gov.in/)

---

## Disclaimer

HydroSwift is an independent, open-source scientific software suite for hydrological data aggregation and visualization. It is not affiliated with, endorsed by, or an official product of the Ministry of Jal Shakti, Central Water Commission (CWC), or National Informatics Centre (NIC). Hydrological data accessed via public endpoints is provided "as is" for research and monitoring purposes. Please consult official government portals for statutory advisories and flood warnings.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
