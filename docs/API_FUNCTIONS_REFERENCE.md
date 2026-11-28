# API Functions Reference

| Function | Module | Purpose |
| :--- | :--- | :--- |
| `search(query, location, sources, *, period, ids, basin, state, cross_boundary)` | `hydroswift` | Discover stations and datasets across CWC, WRIS, and NWDP; returns a catalog with full provenance (`attrs["source_status"]` and `attrs["partial"]`). |
| `estimate(catalog, *, network=True)` | `hydroswift` | Query exact server-side record estimates from supporting sources (NWDP). |
| `fetch(catalog, *, output_dir, period, format, overwrite, rc_discharge, resume, workers, progress, cancel)` | `hydroswift` | Download observations concurrently, generate `manifest.json`, and return a run summary DataFrame. |
| `load(run)` | `hydroswift` | Convert downloaded files into a unified tidy long-table DataFrame. |
| `merge(run, output)` | `hydroswift` | Write the unified tidy DataFrame to `.parquet`, `.csv`, or `.gpkg`. |
| `plot(run, output_dir, *, variable, max_series)` | `hydroswift` | Generate publication-grade summary hydrograph PNGs for downloaded stations. |
| `save_catalog(catalog, path)` / `load_catalog(path)` | `hydroswift` | Persist or reload a discovered catalog along with its full search provenance. |
| `create_map(df, output, basemap, color_by, cluster, bounds, geojson_layers)` | `hydroswift.core.mapping` | Create an interactive Leaflet map with official boundaries and dedicated z-index panes. |
| `rsms.daily(output_path)` | `hydroswift.rsms` | Retrieve live daily storage levels for ~180 major Indian reservoirs. |
| `rsms.bulletins(date)` / `rsms.backfill(...)` | `hydroswift.rsms` | Retrieve or historical backfill CWC national reservoir storage bulletins. |
| `swot_reservoir_merge(...)` | `hydroswift.experimental.swot` | Harmonize SWOT satellite altimetry water surface elevations with in-situ reservoir storage. |
| `help()`, `cli_help()`, `cite()`, `coffee()` | `hydroswift` | Utilities, citation metadata, and CLI reference. |

See the [Python API Guide](PYTHON_API_GUIDE.md) and [Web GUI Guide](GUI_GUIDE.md) for detailed workflows.

## Analysis

| Function | Description |
| :--- | :--- |
| `hydroswift.summary(run)` | Per-series statistics, completeness of the record span, longest gap, gauge-zero count. |
| `hydroswift.resample(run, freq)` | `daily`, `monthly` or `annual` values; rainfall summed, others averaged. |
