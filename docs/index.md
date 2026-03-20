# HydroSwift ⚡

**Fast, unified workflows for hydrological data.**

HydroSwift is a Python toolkit for integrating, processing, and visualizing hydrological datasets at basin scale. It automates retrieval from [India-WRIS](https://indiawris.gov.in/) and the [CWC Flood Forecasting System](https://ffs.india-water.gov.in/) while preserving reproducible CLI and notebook workflows.

## Supported data sources

| Source | Variables |
|---|---|
| **India-WRIS** | Discharge, water level, rainfall, temperature, humidity, solar radiation, sediment, groundwater level, atmospheric pressure |
| **CWC FFS** | Water level |

## How HydroSwift is organised

HydroSwift exposes two main interfaces:

1. **Python API** via `import hydroswift`
2. **CLI** via `hyswift ...` or `python -m hydroswift ...`

The Python API offers two styles:

- **Explicit namespace downloads** — use `hydroswift.wris.download(...)` or `hydroswift.cwc.download(...)` when you already know the basin/station values.
- **Table-driven workflows** — discover basins or stations first, then pass those tables into `hydroswift.fetch(...)`.

## Quick start

### Python

```python
import hydroswift

stations = hydroswift.wris.stations(basin="Godavari", variable="discharge")
result = hydroswift.fetch(
    stations,
    start_date="2024-01-01",
    end_date="2024-01-10",
    merge=True,
)
```

### CLI

```bash
hyswift -b Godavari -q --start-date 2024-01-01 --end-date 2024-01-10 --merge
```

## Documentation

| Guide | Description |
|---|---|
| [Python API Guide](PYTHON_API_GUIDE.md) | Concepts, workflows, and examples |
| [CLI Usage Guide](CLI_USAGE_GUIDE.md) | Supported CLI flags and common command patterns |
| [API Functions Reference](API_FUNCTIONS_REFERENCE.md) | Signatures, parameters, and return shapes |
| [API ↔ CLI Map](PUBLIC_API_AND_CLI.md) | Side-by-side notebook, Python, and CLI mapping |

## Example notebooks

- [Python API Examples](examples/hydroswift_python_examples.ipynb) — full end-to-end workflows
- [CLI Examples](examples/hydroswift_cli_examples.ipynb) — `hyswift` command demonstrations

## Important usage rules

!!! note
    - Use `hydroswift.wris.download(...)` / `hydroswift.cwc.download(...)` for **explicit values only** (no DataFrames).
    - Use `hydroswift.fetch(table, ...)` for tables from `hydroswift.wris.stations(...)`, `hydroswift.cwc.stations(...)`, etc.
    - CWC downloads are **water-level only**.

## Output model

Downloaded station files are saved under an output directory, then optionally:

- merged into GeoPackages with `merge=True` or `hydroswift.merge_only(...)`
- plotted with `plot=True` or `hydroswift.plot_only(...)`

Post-processing helpers work from existing downloaded files without requiring basin/station arguments again.
