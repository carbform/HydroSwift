# Python API Guide

This guide documents the current Python API exposed by:

```python
import hydroswift
```

It reflects the implementation in `hydroswift.api` and the workflows demonstrated in `hydroswift_python_examples.ipynb`.

## 1. Core API model

HydroSwift has two complementary Python workflows.

### A. Explicit download workflow

Use the source-specific namespaces when you already know your inputs.

- `hydroswift.wris.download(...)`
- `hydroswift.cwc.download(...)`

### B. Table-driven workflow

Use helper methods to discover basins/stations, then pass the resulting table to:

- `hydroswift.fetch(...)`

This is the workflow most emphasized by the example notebook because it is reproducible and lets you inspect metadata before downloading.

---

## 2. WRIS namespace

### `hydroswift.wris.variables()`

Returns a `SwiftTable` describing the WRIS variables supported by HydroSwift.

Columns include:

- `flag`
- `dataset_code`
- `folder`
- `canonical_name`
- `aliases`

Example:

```python
hydroswift.wris.variables()
```

Supported canonical variables currently map to these CLI/API names:

- `discharge`
- `water_level`
- `atm_pressure`
- `rainfall`
- `temperature`
- `humidity`
- `solar_radiation`
- `sediment`
- `groundwater_level`

### `hydroswift.wris.basins(variable=None)`

Returns a WRIS basin table.

#### Without `variable`

You get one row per basin.

```python
basins = hydroswift.wris.basins()
```

#### With `variable`

You get one row per `(basin, variable)` pair, which makes the table directly usable with `hydroswift.fetch(...)`.

```python
basins = hydroswift.wris.basins(variable=["sediment", "water_level"])
```

This pattern is shown in the Python examples notebook.

### `hydroswift.wris.stations(basin, variable, delay=0.25, state=None)`

Discovers WRIS station metadata for one or more basin/variable combinations.

```python
stations = hydroswift.wris.stations(
    basin=["Godavari", "Narmada"],
    variable=["solar", "sediment"],
)
```

Notes:

- `variable` is required.
- `state` is **not supported** for WRIS station filtering; passing it raises a `ValueError`.
- The returned table includes `source/type` metadata in `.attrs`, which `hydroswift.fetch(...)` uses later.

Typical columns include:

- `station_code`
- `station_name`
- `latitude`
- `longitude`
- `river`
- `basin`
- `variable`

### `hydroswift.wris.download(...)`

Use this for explicit WRIS downloads.

```python
gdf = hydroswift.wris.download(
    basin=["Krishna", "Tapi"],
    variable=["discharge", "solar"],
    start_date="2024-01-01",
    end_date="2024-03-31",
    output_dir="output",
    format="csv",
    overwrite=False,
    merge=True,
    plot=False,
    delay=0.25,
    quiet=False,
)
```

Key points:

- `basin` is required.
- `variable` is required.
- `station` and `stations` are aliases; provide only one of them.
- Inputs must be explicit strings/ints/lists, **not DataFrames**.
- Basin values may be names like `"Krishna"` or WRIS numeric basin IDs such as `6`.

Example with station filtering:

```python
hydroswift.wris.download(
    basin="Godavari",
    variable="discharge",
    station=["SOME_STATION_CODE"],
)
```

---

## 3. CWC namespace

CWC support is focused on **water-level** time series and metadata.

### `hydroswift.cwc.stations(station=None, basin=None, river=None, state=None, refresh=False)`

Returns CWC station metadata.

```python
stations = hydroswift.cwc.stations(
    basin=["Narmada", "Tapi"],
    state=["Gujarat", "Maharashtra"],
)
```

Filters can be combined.

Common columns include:

- `code`
- `name`
- `basin`
- `river`
- `state`

`refresh=True` tells HydroSwift to refresh metadata from the live CWC API first, then apply filters.

### `hydroswift.cwc.basins(refresh=False)`

Builds a basin summary table from the CWC station metadata.

```python
basins = hydroswift.cwc.basins()
```

Returned columns:

- `basin`
- `station_count`

This table is fetch-ready for basin-driven CWC download dispatch.

### `hydroswift.cwc.download(...)`

Use this for explicit CWC downloads.

```python
gdf = hydroswift.cwc.download(
    basin=["Narmada", "Tapi"],
    start_date="2024-01-01",
    end_date="2024-01-07",
    output_dir="output",
    format="csv",
    overwrite=False,
    merge=True,
    plot=False,
    quiet=False,
    refresh=False,
)
```

Or download specific stations:

```python
hydroswift.cwc.download(
    station=["040-CDJAPR", "032-LGDHYD"],
    start_date="2024-01-01",
    end_date="2024-01-07",
)
```

Behavior notes:

- `station` is optional.
- `basin` is optional.
- If both are provided, HydroSwift downloads the intersection.
- Table-like inputs should go to `hydroswift.fetch(...)`, not `hydroswift.cwc.download(...)`.
- Internal parameters like `_name_by` and `_gpkg_group` exist for internal dispatch; they are not normal user-facing API controls.

### `hydroswift.cwc.refresh_metadata(write=False)`

Refreshes packaged CWC metadata with `name-code.csv` using live lookups.

```python
meta = hydroswift.cwc.refresh_metadata(write=False)
```

This is a metadata maintenance helper, not part of the common download path.

---

## 4. Unified table-driven downloads with `hydroswift.fetch(...)`

`hydroswift.fetch(...)` is the main bridge between metadata discovery tables and actual downloads.

```python
hydroswift.fetch(
    stations,
    output_dir="output",
    start_date="2024-01-01",
    end_date="2024-01-10",
    merge=True,
)
```

### Acceptable inputs

Use tables returned by:

- `hydroswift.wris.stations(...)`
- `hydroswift.wris.basins(variable=...)`
- `hydroswift.cwc.stations(...)`
- `hydroswift.cwc.basins(...)`

### WRIS behavior

`fetch(...)` supports both:

- **station-level WRIS tables** with `station_code`
- **basin-level WRIS tables** with basin/variable combinations

Examples from the notebook:

```python
basins_wris = hydroswift.wris.basins(variable=["sediment", "water_level"])
subset = basins_wris[basins_wris["basin"].isin(["Cauvery", "Godavari"])]
result = hydroswift.fetch(subset, output_dir="data_fetch_wris", start_date="2024-04-01")
```

```python
stations = hydroswift.wris.stations(basin=["Godavari", "Narmada"], variable=["solar", "sediment"])
result = hydroswift.fetch(stations, output_dir="data_fetch_wris", start_date="2024-04-01")
```

### CWC behavior

`fetch(...)` supports both:

- **station-level CWC tables** with `code`
- **basin-level CWC tables** from `hydroswift.cwc.basins()`

Examples from the notebook:

```python
basins_cwc = hydroswift.cwc.basins()
subset = basins_cwc[basins_cwc["basin"].isin(["Narmada", "Tapi"])]
result = hydroswift.fetch(subset, output_dir="data_fetch_cwc", start_date="2024-04-01")
```

```python
stations_cwc = hydroswift.cwc.stations(basin=["Narmada", "Tapi"], state=["Gujarat", "Maharashtra"])
subset = stations_cwc[stations_cwc["name"].isin(["BODELI", "Bharuch"])]
result = hydroswift.fetch(subset, output_dir="data_fetch_cwc", start_date="2024-04-01")
```

### Parameters shared across fetch workflows

- `output_dir`
- `start_date`
- `end_date`
- `format`
- `overwrite`
- `merge`
- `plot`
- `quiet`
- `delay` for WRIS dispatch
- `refresh` for CWC metadata refresh before dispatch

---

## 5. Post-processing helpers

### `hydroswift.merge_only(input_dir=None, output_dir=None, *, mode=None, variable=None)`

Merges previously downloaded files into GeoPackages.

Examples from the notebook:

```python
hydroswift.merge_only(
    mode="cwc",
    input_dir="data_fetch_cwc",
    output_dir="merged_cwc",
)
```

```python
hydroswift.merge_only(
    mode="wris",
    input_dir="data_fetch_wris",
    output_dir="merged_wris",
    variable=["sediment", "water_level"],
)
```

Notes:

- `mode` may be `"wris"` or `"cwc"`.
- `variable` applies only to WRIS; CWC ignores it.
- If `output_dir` is omitted, the function attempts an in-memory merge path.

### `hydroswift.plot_only(...)`

Builds plots from existing HydroSwift outputs.

Notebook-aligned examples:

```python
hydroswift.plot_only(
    mode="cwc",
    input_dir="data_fetch_cwc",
    output_dir="plots_cwc",
    plot_svg=False,
)
```

```python
hydroswift.plot_only(
    mode="wris",
    input_dir="data_fetch_wris",
    output_dir="plots_wris",
    variable=["sediment", "water_level"],
    plot_svg=True,
)
```

Important parameters:

- `mode="wris"` or `mode="cwc"`
- `plot_svg`
- `moving_average`
- `window`

`moving_average=True` uses the default 30-sample window unless `window` is set.

---

## 6. Utility helpers

### `hydroswift.help()`

Prints the Python API help text.

### `hydroswift.cli_help()`

Prints the CLI parser help from Python.

### `hydroswift.cite()`

Prints the citation text.

### `hydroswift.coffee()`

Prints the coffee easter egg.

---

## 7. Practical workflow recommendations

### Recommended workflow for notebooks

1. Discover metadata with `hydroswift.wris.stations(...)`, `hydroswift.wris.basins(...)`, `hydroswift.cwc.stations(...)`, or `hydroswift.cwc.basins(...)`.
2. Inspect and subset the returned table.
3. Pass that table into `hydroswift.fetch(...)`.
4. Use `hydroswift.merge_only(...)` or `hydroswift.plot_only(...)` later if you deliberately disabled `merge` or `plot` during fetch.

### Recommended workflow for short scripts

Use explicit downloads when you already know the exact basin/station inputs:

- `hydroswift.wris.download(...)`
- `hydroswift.cwc.download(...)`

This avoids the discovery step.
