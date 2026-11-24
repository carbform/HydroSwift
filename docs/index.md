# HydroSwift ⚡

**Fast, unified workflows for hydrological data.**

HydroSwift is a Python toolkit for integrating, processing, and visualizing hydrological datasets at basin scale. It automates retrieval from the [National Water Informatics Portal (NWDP, now carrying the former India-WRIS data)](https://nwdp.nwic.gov.in), the [CWC Flood Forecasting System](https://ffs.india-water.gov.in/), the [CWC Reservoir Storage Monitoring System (RSMS)](https://rsms.cwc.gov.in/frameWork/web/public-dashboard), and satellite altimetry pipelines like SWOT KaRIn while preserving reproducible CLI and notebook workflows.

## Supported data sources

| Source | Variables |
|---|---|
| **NWDP (ex India-WRIS)** | Discharge, water level, rainfall, temperature, humidity, solar radiation, sediment, groundwater level, atmospheric pressure |
| **CWC FFS** | River water level; RC-derived discharge (when local RC curves are available) |
| **CWC RSMS** | Reservoir water level, current live storage, gross capacity, dead storage level (DSL), FRL |
| **SWOT Satellite** | KaRIn water surface elevation (WSE), lake/reservoir surface area, and quality flags |

## How HydroSwift is organised

HydroSwift exposes two main interfaces:

1. **Python API** via `import hydroswift`
2. **CLI** via `hyswift ...` or `python -m hydroswift ...`

Both follow one workflow, **Find -> Review -> Get -> Use**: `search` shows what exists and where it comes from (including failures and what was inferred), `estimate` shows how big it is, `fetch` downloads with a manifest, and `load` returns one tidy table.

## Quick start

### Python

```python
import hydroswift as hs

cat = hs.search("rainfall", "Karnataka", period=("2020", "2022"))
print(cat.attrs["source_status"])
run = hs.fetch(cat.head(2), output_dir="output", period=("2020", "2022"))
data = hs.load(run)
```

### CLI

```bash
hyswift search rainfall --where Karnataka --period 2020:2022 --save cat.json
hyswift get --from cat.json --rows 0,1 --period 2020:2022 --out output
hyswift show output
```

## Documentation

| Guide | Description |
|---|---|
| [Python API Guide](PYTHON_API_GUIDE.md) | Concepts, workflows, and examples |
| [CLI Usage Guide](CLI_USAGE_GUIDE.md) | Supported CLI flags and common command patterns |
| [API Functions Reference](API_FUNCTIONS_REFERENCE.md) | Signatures, parameters, and return shapes |
| [API ↔ CLI Map](PUBLIC_API_AND_CLI.md) | Side-by-side notebook, Python, and CLI mapping |

## Important usage rules

!!! note
    - CWC discharge exists only as a rating-curve estimate from stage, using GUARDIAN RC coefficients in `swift_app/RC.csv` (Patidar et al., 2024, <https://doi.org/10.1038/s41597-024-03923-8>). It is labelled `rc_guardian_2024` in the `method` column.
    - NWDP has no server-side date filter, so the period is applied after download; resources whose name states a period outside the request are skipped.
    - Every fetch writes `manifest.json` (query, per-source status, endpoints, record counts, actual date spans, TLS verification setting).

!!! warning "Example notebooks"
    The notebooks in `docs/examples/` were written for the removed `wris`/`cwc` interfaces and have not yet been updated to the new workflow.
