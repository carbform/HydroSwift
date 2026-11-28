# HydroSwift CLI Usage Guide

HydroSwift provides a fast, robust command-line interface (`hyswift`) that mirrors the same **Find $\rightarrow$ Review $\rightarrow$ Get $\rightarrow$ Use** workflow available in Python and the Web Studio.

---

## Command Overview

```bash
# Guided interactive prompt mode
hyswift

# Launch modern Web Studio
hyswift gui
hyswift-gui

# Search catalogs across CWC, WRIS, and NWDP
hyswift search rainfall --where Karnataka --period 2020:2024 --save cat.json
hyswift search discharge --basin Cauvery --sources CWC --save cauvery.json

# Download data from saved catalog
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

## 1. `search`
Search across observational networks and open data portals:
```bash
hyswift search [query] [--where TEXT] [--basin NAME] [--state NAME] [--ids ID1,ID2] [--sources CWC WRIS NWDP] [--period YYYY:YYYY] [--estimate] [--save FILE] [--limit N]
```

* `query`: Variable keyword (e.g. `rainfall`, `discharge`, `water level`, `groundwater`).
* `--where TEXT`: Free-form location keyword matched against station names and locations.
* `--basin NAME`: Exact official CWC River Basin name (e.g. `Cauvery`, `Ganga`, `Godavari`, `Krishna`). Automatically cross-discovers constituent state open datasets.
* `--state NAME`: Exact Indian State or Union Territory name.
* `--sources`: One or more data sources (`CWC`, `WRIS`, `NWDP`).
* `--period`: Temporal span as `START:END` (e.g. `2020:2024` or `2021-01-01:2023-12-31`).
* `--estimate`: Queries exact record count estimates from supporting providers (NWDP).
* `--save FILE`: Saves the discovered catalog along with full search provenance into JSON.

### Station statistics

A folder reads only its newest manifest; name a `manifest*.json` to pick a run.

```bash
hyswift stats output/manifest.json        # coverage, gaps, min/mean/max per station
hyswift stats output/manifest.json --freq monthly --out monthly.csv
```

---

## 2. `get`
Download selected catalog items to disk:
```bash
hyswift get --from FILE [--rows SPEC] [--period P] [--out DIR] [--format csv|parquet|gpkg|json] [--overwrite]
```

* `--from FILE`: Path to a JSON catalog saved by `hyswift search`.
* `--rows SPEC`: Indices to download, e.g. `0,1,2` or range `0:10`.
* `--out DIR`: Output folder (default: `output`).
* `--format`: File format for downloads (`csv`, `parquet`, `gpkg`, `json`).
* Every fetch writes a `manifest.json` recording query parameters, per-item status, record counts, and timestamps.

---

## 3. `show`, `merge`, `plot`
Inspect, harmonize, and visualize downloaded observations:

* **`hyswift show PATH`**:
  Prints a clean tabular summary of downloaded tidy data (variables, units, station counts, record counts, and date spans).
* **`hyswift merge PATH OUTPUT`**:
  Harmonizes downloaded station files into one unified tidy table (`.parquet`, `.csv`, or `.gpkg`).
* **`hyswift plot PATH [DIR] [--variable V]`**:
  Generates publication-quality hydrograph plots for each station and variable into the target plot folder.

`PATH` can be an output folder (automatically picks the latest manifest) or a specific `manifest.json`.

---

## 4. `gui`
Launch the modern Streamlit web dashboard:
```bash
hyswift gui
```
Opens the browser studio at `http://localhost:8501`.

---

## 5. `rsms`
Central Water Commission (CWC) Reservoir Storage Monitoring System tools:
```bash
# Fetch latest daily reservoir bulletin for ~180 national reservoirs
hyswift rsms daily [--out CSV]

# Backfill historical bulletins
hyswift rsms backfill [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--out CSV]

# Build harmonized reservoir geodatabase (SWOT satellite + in-situ gauge)
hyswift rsms build --reservoir-shp PATH --swot-db PATH --gauge-cache PATH [--out-dir DIR]
```
