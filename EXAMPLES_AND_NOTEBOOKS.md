# Examples and Notebooks

HydroSwift ships two example notebooks inside `docs/examples/`:

## Included examples

- [Python API Examples](docs/examples/hydroswift_python_examples.ipynb) — covers discovery, download, merge, plot, CWC RSMS reservoir tracking, SWOT satellite harmonization, and full pipeline workflows using the Python API.
- [CLI Examples](docs/examples/hydroswift_cli_examples.ipynb) — demonstrates the `hyswift` command-line interface, including river gauge extraction, RSMS reservoir bulletins, and SWOT reservoir database building.

## Workflows demonstrated

1. **WRIS Hydrology**: Discovery, multi-variable download, and GeoPackage assembly for 17 river basins.
2. **CWC Flood Forecasting**: River stage and rating-curve-derived discharge across national forecasting stations.
3. **CWC RSMS Reservoirs**: Real-time daily storage snapshots and historical weekly bulletin PDF backfills for 180+ major reservoirs.
4. **SWOT Satellite Harmonization**: Satellite KaRIn WSE and gauge time series matching with reservoir shapefiles.

## Recommended reading order

1. Read the [Python API Guide](docs/PYTHON_API_GUIDE.md) before running the Python notebook.
2. Read the [CLI Usage Guide](docs/CLI_USAGE_GUIDE.md) before running the CLI notebook.
