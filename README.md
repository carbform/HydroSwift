# HydroSwift ⚡

![Tests](https://github.com/carbform/swift/actions/workflows/tests.yml/badge.svg)
[![Documentation](https://readthedocs.org/projects/hydroswift/badge/?version=latest)](https://hydroswift.readthedocs.io/)

**Fast, unified workflows for hydrological data.**

HydroSwift automates retrieval, processing, and visualization of hydrological observations from the [National Water Informatics Portal (NWDP, which now carries the former India-WRIS data)](https://nwdp.nwic.gov.in), the [CWC Flood Forecasting System](https://ffs.india-water.gov.in/), and the [CWC Reservoir Storage Monitoring System (RSMS)](https://rsms.cwc.gov.in/frameWork/web/public-dashboard). It supports river discharge, water levels, reservoir storage & capacities, SWOT KaRIn satellite water surface elevations, rainfall, temperature, humidity, solar radiation, sediment, groundwater, and atmospheric pressure datasets.

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

HydroSwift has one workflow, the same in Python, the CLI and the GUI: **Find -> Review -> Get -> Use**.

### Python

```python
import hydroswift as hs

cat = hs.search("rainfall", "Karnataka", period=("2020", "2022"))   # Find
cat.attrs["source_status"]      # Review: what each source answered (ok / failed / truncated, rows dropped)
hs.estimate(cat.head(3))        # Review: how many records? (exact for NWDP, "unknown" elsewhere)
run = hs.fetch(cat.head(3), output_dir="output", period=("2020", "2022"))   # Get (writes manifest.json)
data = hs.load(run)             # Use: one tidy table - time, value, variable, unit, station, source, method, flag
hs.merge(run, "output/all.parquet")   # or .csv / .gpkg
hs.plot(run, "output/plots")

# exact selection when you know what you want
hs.search("discharge", basin="Krishna", sources=["CWC"])     # exact basin, not substring
hs.search(ids=["001-CDBNG"], sources=["CWC"])                # exact catalog IDs

# Reservoirs (CWC RSMS)
hs.rsms.daily(output_path="output/cwc_rsms/daily_snapshot.csv")
hs.rsms.backfill(start_date="2025-05-15", output_csv="output/cwc_rsms/bulletin_backfill.csv")
hs.swot_reservoir_merge(reservoir_shp="reservoirs.shp", swot_observations="swot_obs.sqlite", gauge_source="gauge_cache/")
```

### Command line

```bash
hyswift search rainfall --where Karnataka --period 2020:2022 --save cat.json
hyswift get --from cat.json --rows 0,2 --period 2020:2022 --out output
hyswift show output                  # tidy summary of what was fetched
hyswift merge output all.parquet
hyswift plot output output/plots
hyswift rsms daily                   # reservoir tools
hyswift                              # no arguments: guided prompts (variable, place, period)
```

### What is stated, and what is assumed

Every catalog row has an `Inferred` column naming fields the source did **not** state (for example the variable
parsed from an NWDP dataset title, or the unknown coverage of a CWC station). CWC discharge exists only as a
rating-curve estimate from stage; it is labelled `rc_guardian_2024` in `method`. Each `fetch` writes a
`manifest.json` with the query, per-source status, endpoints, record counts, actual date spans and the TLS
verification setting (NWDP requests currently run with certificate verification disabled).

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
  manifest.json                      # every fetch; later runs add manifest_<timestamp>.json
  nwdp/<organization>/NWDP_*.csv
  cwc/<basin>/CWC_*.csv
  cwc_rsms/CWC_RSMS_daily_snapshot_*.csv
  plots/*.png                        # hs.plot
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
