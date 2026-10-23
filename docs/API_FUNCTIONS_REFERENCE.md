# API Functions Reference

This page lists the current public API exported by `import hydroswift`.

## Public entry points

### WRIS namespace

#### `hydroswift.wris.variables()`

Returns a WRIS variable lookup table.

#### `hydroswift.wris.basins(variable=None)`

Returns a WRIS basin table.

- `variable=None`: one row per basin
- `variable='discharge'` or a list: one row per `(basin, variable)` pair

#### `hydroswift.wris.stations(basin, variable, delay=0.25, state=None)`

Returns a WRIS station discovery table.

Parameters:

- `basin`: basin name, basin ID, list of them, or `'all'` for all WRIS basins
- `variable`: WRIS variable name/flag or list of them
- `delay`: delay between API requests in seconds
- `state`: currently unsupported for WRIS filtering; non-empty values raise an error

Returns a `SwiftTable` with station metadata and `.attrs` describing the source/table type.

#### `hydroswift.wris.download(basin=None, variable=None, *, station=None, stations=None, start_date='1950-01-01', end_date=None, output_dir='output', format='csv', overwrite=False, merge=False, plot=False, delay=0.25, quiet=False)`

Downloads WRIS time series for explicit basin/variable inputs.

Parameter notes:

- `basin` is required. Use `'all'` to download all 17 WRIS basins.
- `variable` is required.
- `station` and `stations` are aliases; provide only one.
- `format` is `csv` or `xlsx`.
- `merge=True` merges station files after download.
- `plot=True` generates plots after download.
- `delay` controls pacing of WRIS API requests.

---

### CWC namespace

#### `hydroswift.cwc.stations(station=None, basin=None, river=None, state=None, refresh=False)`

Returns CWC station metadata.

Parameters:

- `station`: station code or list of codes
- `basin`: basin filter, list of basin filters, or `'all'` for no filtering
- `river`: river filter
- `state`: state filter or list of state filters
- `refresh`: refresh station metadata from the live API before filtering

#### `hydroswift.cwc.basins(refresh=False)`

Returns basin summary counts derived from CWC station metadata.

Columns:

- `basin`
- `station_count`

#### `hydroswift.cwc.download(station=None, *, variable=None, rc_discharge=True, basin=None, start_date=None, end_date=None, output_dir='output', format='csv', overwrite=False, merge=False, plot=False, quiet=False, refresh=False, _name_by=None, _gpkg_group=None)`

Downloads CWC time series.

Normal user-facing parameters are:

- `station`
- `variable` (`water_level`/`wl` and `discharge`/`q`)
- `rc_discharge` (controls computation of discharge from RC curves)
- `basin` (use `'all'` for all CWC stations)
- `start_date`
- `end_date`
- `output_dir`
- `format`
- `overwrite`
- `merge`
- `plot`
- `quiet`
- `refresh`

Notes:

- CWC downloads include water level; discharge is RC-derived when requested and RC curves are available locally (`swift_app/RC.csv`).
- `rc_discharge` toggles this RC curve capability (default is `True`).
- If both `station` and `basin` are provided, HydroSwift downloads only matching stations.
- `_name_by` and `_gpkg_group` are internal dispatch parameters and should not be part of normal user code.

#### `hydroswift.cwc.refresh_metadata(write=False)`

Refreshes packaged metadata against `name-code.csv` using live lookups.

- `write=False`: return the refreshed table only
- `write=True`: also overwrite the packaged metadata file

---

### CWC Reservoirs & RSMS namespace (`hydroswift.rsms` / `hydroswift.cwc.reservoirs`)

#### `hydroswift.rsms.daily(output_path=None, timeout=15, max_reservoirs=None)`

Fetches the latest real-time daily reservoir storage, elevation, and capacity snapshot for 180+ major reservoirs monitored by CWC RSMS.

Parameters:

- `output_path`: Destination CSV path to append/write.
- `timeout`: HTTP timeout in seconds (default `15`).
- `max_reservoirs`: Optional limit for testing.

Returns: `SwiftTable` containing `reservoir_unique_id`, `reservoir_name`, `entry_date`, `storage_bcm`, `live_cap_bcm`, `gross_cap_bcm`, `cap_dsl_bcm`, `frl_meter`, `dsl_mtr`, `latitude`, `longitude`.

#### `hydroswift.rsms.bulletins(from_date='', to_date='', cache_file=None)`

Discovers published weekly bulletin PDF reports from the CWC RSMS portal.

Parameters:

- `from_date`: Start date filter (YYYY-MM-DD).
- `to_date`: End date filter (YYYY-MM-DD).
- `cache_file`: Optional JSON path to cache discovered catalog.

Returns: `SwiftTable` of bulletin metadata.

#### `hydroswift.rsms.backfill(start_date='2025-05-15', end_date=None, output_csv=None, bulletin_dir='output/cwc/bulletins')`

Downloads and parses tabular reservoir records from historical weekly bulletin PDFs into a consolidated time series.

Parameters:

- `start_date`: Start date filter (default `'2025-05-15'`).
- `end_date`: Optional end date filter.
- `output_csv`: Destination CSV path.
- `bulletin_dir`: Local directory to store downloaded bulletin PDFs.

Returns: `SwiftTable` of bulletin observation records (`reservoir_name`, `frl_m`, `water_level_m`, `live_cap_bcm`, `current_storage_bcm`, `date`).

#### `hydroswift.swot_reservoir_merge(reservoir_shp, swot_observations, gauge_source, output_gpkg=None, output_sqlite=None, output_parquet=None, cwc_metadata=None, tolerance_days=3.5, fix_anomalies=True)`

Harmonizes SWOT KaRIn satellite water surface elevations, in-situ gauge measurements, and reservoir polygon shapefiles into unified multi-format outputs.

Parameters:

- `reservoir_shp`: Path to reservoir polygon shapefile or GeoPackage.
- `swot_observations`: Path to SQLite DB, GeoPackage, or DataFrame of SWOT satellite passes.
- `gauge_source`: Directory of gauge CSVs (`<reservoir_id>.csv`), single CSV file, or DataFrame.
- `output_gpkg`: Output GeoPackage path (layers: `reservoirs`, `swot_observations`, `gauge_timeseries`, `unified_timeseries`).
- `output_sqlite`: Output SQLite path (indexed tables).
- `output_parquet`: Output Parquet path (fast columnar unified time series).
- `cwc_metadata`: Optional metadata table with FRL, DSL, capacities.
- `tolerance_days`: Temporal matching window in days (default `3.5`).
- `fix_anomalies`: Automatically fix transcription outliers (Manikdoh 10× decimal typo, Rihand ft $\leftrightarrow$ m shift). Default `True`.

Returns: Dictionary of output paths and observation metrics.

---

### Unified download helper

#### `hydroswift.fetch(stations, *, output_dir='output', start_date='1950-01-01', end_date=None, format='csv', overwrite=False, merge=False, plot=False, quiet=False, delay=0.25, refresh=False)`

Downloads data from a HydroSwift table.

Accepted table inputs:

- `hydroswift.wris.stations(...)`
- `hydroswift.wris.basins(variable=...)`
- `hydroswift.cwc.stations(...)`
- `hydroswift.cwc.basins(...)`

Dispatch behavior:

- WRIS station table with `station_code` → station-level WRIS download
- WRIS basin table with `basin` and `variable` → basin/variable dispatch
- CWC station table with `code` → station-level CWC download
- CWC basin table with `basin` → per-basin CWC station expansion and download

---

### Post-processing helpers

#### `hydroswift.merge_only(input_dir=None, output_dir=None, *, mode=None, variable=None)`

Merges previously downloaded station files into GeoPackages.

Parameters:

- `input_dir`: directory containing existing HydroSwift output
- `output_dir`: where merged GeoPackages should be written; optional
- `mode`: `wris` or `cwc`
- `variable`: WRIS variable subset; ignored in CWC mode (CWC merge reads all available CWC fields)

#### `hydroswift.plot_only(input_dir=None, output_dir=None, cwc=False, *, mode=None, variable=None, plot_svg=False, moving_average=None, window=None)`

Generates plots from existing HydroSwift outputs.

Parameters:

- `input_dir`: existing HydroSwift output directory
- `output_dir`: plot destination directory
- `cwc`: legacy boolean flag for CWC mode
- `mode`: preferred mode selector, `wris` or `cwc`
- `variable`: WRIS variable subset; ignored in CWC mode (CWC plotting reads all available CWC fields)
- `plot_svg`: also write SVG output
- `moving_average`: enable moving average overlay, or pass a window value directly
- `window`: explicit moving average window size

---

### Utility helpers

#### `hydroswift.help()`

Prints Python API help text.

#### `hydroswift.cli_help()`

Prints the CLI parser help text.

<!-- #### `hydroswift.cite()`

Prints citation information. -->

#### `hydroswift.coffee()`

Prints the coffee-break banner.

---
