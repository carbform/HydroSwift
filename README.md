# HydroSwift ⚡

![Tests](https://github.com/carbform/swift/actions/workflows/tests.yml/badge.svg)
[![Documentation](https://readthedocs.org/projects/hydroswift/badge/?version=latest)](https://hydroswift.readthedocs.io/)

**Fast, unified workflows for hydrological data.**

HydroSwift automates retrieval, processing, and visualization of hydrological observations from [India-WRIS](https://nwic.in/wris/#/timeseriesdata), the [CWC Flood Forecasting System](https://ffs.india-water.gov.in/), and the [CWC Reservoir Storage Monitoring System (RSMS)](https://rsms.cwc.gov.in/frameWork/web/public-dashboard). It supports river discharge, water levels, reservoir storage & capacities, SWOT KaRIn satellite water surface elevations, rainfall, temperature, humidity, solar radiation, sediment, groundwater, and atmospheric pressure datasets.

---

## Installation

```bash
git clone https://github.com/carbform/HydroSwift.git
cd swift
pip install -e .          # core
pip install -e .[all]     # with plotting + geospatial extras
```

Verify:

```bash
hyswift --version
```

---

## Quick Start

### Python API

```python
import hydroswift

# Discover → download → merge in one step (WRIS)
stations = hydroswift.wris.stations(basin="Godavari", variable="discharge")
hydroswift.fetch(stations, start_date="2024-01-01", end_date="2024-03-31", merge=True)

# Or download directly when you already know the inputs (CWC river gauges)
hydroswift.cwc.download(station=["040-CDJAPR", "032-LGDHYD"], merge=True)

# Fetch real-time daily reservoir storage & level snapshots (CWC RSMS)
hydroswift.rsms.daily(output_path="output/cwc/rsms_daily_snapshots.csv")

# Backfill historical CWC weekly bulletin reports (180+ reservoirs)
hydroswift.rsms.backfill(start_date="2025-05-15", output_csv="output/cwc/cwc_bulletin_backfill.csv")

# Harmonize SWOT satellite passes with in-situ gauges into a unified GeoPackage
hydroswift.swot_reservoir_merge(
    reservoir_shp="reservoirs.shp",
    swot_observations="swot_obs.sqlite",
    gauge_source="gauge_cache/",
    output_gpkg="output/reservoir_geodb/unified_reservoir_swot_gauge.gpkg",
)

# Discover datasets from the NWDP CKAN API (by State/Organization or Theme)
nwdp_datasets = hydroswift.nwdp.datasets(query="Ground Water", org="Karnataka GW")
hydroswift.fetch(nwdp_datasets) # Bulk download all matches!

# Download arbitrary tabular data from the NWDP CKAN API using a resource ID
hydroswift.nwdp.download(
    resource_id="00ee62df-76d2-4431-85dd-a5da3bfc36f0", 
    filters={"State": "Karnataka", "District": "Bengaluru Urban"}
)
```

### Interactive Wizard (Beginner Friendly)

If you are new to HydroSwift, simply type `hyswift` in your terminal without any arguments to launch the step-by-step interactive mode:

```bash
hyswift
```

### Expert CLI

For advanced users and automated scripts, you can pass arguments directly:

```bash
hyswift -b Godavari -q --merge                          # WRIS discharge
hyswift -b Krishna -q -rf -temp                         # multiple variables
hyswift --cwc-basin Krishna Godavari                    # CWC water level
hyswift --plot-only --input-dir output --plot-svg       # generate plots

# CWC Reservoirs (RSMS) & SWOT Harmonization
hyswift --rsms-daily --output-dir output                # Live daily reservoir snapshot
hyswift --rsms-backfill --start-date 2025-05-15         # Scrape & parse bulletin PDFs
hyswift --swot-reservoir-merge \
  --reservoir-shp reservoirs.shp \
  --swot-db swot_obs.sqlite \
  --gauge-cache gauge_cache/                            # Build unified GPKG, SQLite & Parquet

# NWDP CKAN API Commands
hyswift --nwdp-state "Karnataka GW" --nwdp-query "Ground Water"   # Bulk download via search
hyswift --nwdp-resource 00ee62df-76d2-4431-85dd-a5da3bfc36f0 \
        --nwdp-filters '{"State":"Karnataka"}'                  # Direct download via ID
```

---

## Documentation

Full docs are available at **[hydroswift.readthedocs.io](https://hydroswift.readthedocs.io/)**, including:

- [Python API Guide](docs/PYTHON_API_GUIDE.md)
- [CLI Usage Guide](docs/CLI_USAGE_GUIDE.md)
- [API Functions Reference](docs/API_FUNCTIONS_REFERENCE.md)
- [Example Notebooks](docs/examples/)

---

## Output Structure

```
output/
  wris/<basin>/<variable>/*.csv
  wris/<basin>/*.gpkg
  cwc/<basin>/stations/*.csv
  cwc/cwc_waterlevel*.gpkg
  cwc/rsms_daily_snapshots.csv
  cwc/cwc_bulletin_backfill.csv
  cwc/bulletins/*.pdf
  reservoir_geodb/
    unified_reservoir_swot_gauge.gpkg
    unified_reservoir_swot_gauge.sqlite
    unified_reservoir_timeseries.parquet
```

---

## Data Sources

- [India Water Resources Information System (WRIS)](https://nwic.in/wris/#/timeseriesdata)
- [Central Water Commission (CWC) Flood Forecasting System](https://ffs.india-water.gov.in/)
- [Central Water Commission (CWC) Reservoir Storage Monitoring System (RSMS)](https://rsms.cwc.gov.in/frameWork/web/public-dashboard)
- [SWOT KaRIn Satellite Reservoir & Lake Elevations](https://swot.jpl.nasa.gov/)

<!-- ## Citation

If you use HydroSwift in your research, please cite:

Sarat, C., Dash, D., & Kumar, A. (2026).
HydroSwift: Automated Retrieval of Hydrological Station Data from India-WRIS and CWC Portals.
Journal of Open Source Software. -->

## License

MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgements

Built with [pandas](https://pandas.pydata.org/), [geopandas](https://geopandas.org/), [matplotlib](https://matplotlib.org/), and [requests](https://docs.python-requests.org/).
