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

- `basin`: basin name, basin ID, or list of them
- `variable`: WRIS variable name/flag or list of them
- `delay`: delay between API requests in seconds
- `state`: currently unsupported for WRIS filtering; non-empty values raise an error

Returns a `SwiftTable` with station metadata and `.attrs` describing the source/table type.

#### `hydroswift.wris.download(basin=None, variable=None, *, station=None, stations=None, start_date='1950-01-01', end_date=None, output_dir='output', format='csv', overwrite=False, merge=False, plot=False, delay=0.25, quiet=False)`

Downloads WRIS time series for explicit basin/variable inputs.

Parameter notes:

- `basin` is required.
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
- `basin`: basin filter or list of basin filters
- `river`: river filter
- `state`: state filter or list of state filters
- `refresh`: refresh station metadata from the live API before filtering

#### `hydroswift.cwc.basins(refresh=False)`

Returns basin summary counts derived from CWC station metadata.

Columns:

- `basin`
- `station_count`

#### `hydroswift.cwc.download(station=None, *, basin=None, start_date=None, end_date=None, output_dir='output', format='csv', overwrite=False, merge=False, plot=False, quiet=False, refresh=False, _name_by=None, _gpkg_group=None)`

Downloads CWC water-level time series.

Normal user-facing parameters are:

- `station`
- `basin`
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

- CWC downloads are water-level only.
- If both `station` and `basin` are provided, HydroSwift downloads only matching stations.
- `_name_by` and `_gpkg_group` are internal dispatch parameters and should not be part of normal user code.

#### `hydroswift.cwc.refresh_metadata(write=False)`

Refreshes packaged metadata against `name-code.csv` using live lookups.

- `write=False`: return the refreshed table only
- `write=True`: also overwrite the packaged metadata file

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
- `variable`: WRIS variable subset; ignored in CWC mode

#### `hydroswift.plot_only(input_dir=None, output_dir=None, cwc=False, *, mode=None, variable=None, plot_svg=False, moving_average=None, window=None)`

Generates plots from existing HydroSwift outputs.

Parameters:

- `input_dir`: existing HydroSwift output directory
- `output_dir`: plot destination directory
- `cwc`: legacy boolean flag for CWC mode
- `mode`: preferred mode selector, `wris` or `cwc`
- `variable`: WRIS variable subset; ignored in CWC mode
- `plot_svg`: also write SVG output
- `moving_average`: enable moving average overlay, or pass a window value directly
- `window`: explicit moving average window size

---

### Utility helpers

#### `hydroswift.help()`

Prints Python API help text.

#### `hydroswift.cli_help()`

Prints the CLI parser help text.

#### `hydroswift.cite()`

Prints citation information.

#### `hydroswift.coffee()`

Prints the coffee-break banner.

---
