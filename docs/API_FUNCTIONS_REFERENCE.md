# API Functions Reference

| Function | Purpose |
|---|---|
| `search(query, location, sources, *, period, ids, basin, state)` | Find datasets and stations across NWDP, CWC and CWC-RSMS; returns a catalog with `attrs["source_status"]` and `attrs["partial"]`. |
| `estimate(catalog, *, network=True)` | Add `EstRecords`/`EstNote` (exact for NWDP, unknown elsewhere). |
| `fetch(catalog, *, output_dir, period, start_date, end_date, format, overwrite, rc_discharge, resume, progress, cancel)` | Download rows, write `manifest.json`, return per-item results. |
| `load(run)` | Tidy long table from a fetch result, manifest or output directory. |
| `merge(run, output)` | Write the tidy table to `.csv`, `.parquet` or `.gpkg`. |
| `plot(run, output_dir, *, variable, max_series)` | One PNG per station and variable. |
| `save_catalog(catalog, path)` / `load_catalog(path)` | Persist a catalog with its provenance (JSON). |
| `refresh_cwc_stations()` | Re-download the CWC station table (about 2 minutes). |
| `rsms.daily / bulletins / backfill / build_database` | CWC reservoir tools. |
| `swot_reservoir_merge(...)` | Unified SWOT + in-situ reservoir database (GPKG, SQLite, Parquet). |
| `help()`, `cli_help()`, `cite()`, `coffee()` | Utilities. |

See the [Python API Guide](PYTHON_API_GUIDE.md) for arguments and behaviour.
