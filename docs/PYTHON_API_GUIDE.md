# Python API Guide

HydroSwift has one workflow: **Find -> Review -> Get -> Use**.

```python
import hydroswift as hs
```

## 1. Find: `hs.search`

```python
cat = hs.search(query=None, location=None, sources=None, *, period=None, ids=None, basin=None, state=None)
```

| Argument | Meaning |
|---|---|
| `query` | variable or keyword ("rainfall", "discharge", "ground water") |
| `location` | case-insensitive **substring** of the fields a source has: NWDP organization; CWC basin, state, district, river. The matching field is in `MatchedOn`. |
| `sources` | subset of `["NWDP", "CWC", "CWC-RSMS"]` |
| `period` | `("2020", "2022")`, `("2020-03-01", None)` or `"2020:2022"`. Rows with known coverage outside it are dropped (counted); rows with unknown coverage are kept and flagged `CoverageKnown=False`. |
| `ids` | exact catalog IDs |
| `basin`, `state` | exact (equality) filters; CWC only. NWDP is skipped with an explanation rather than ignoring the filter. |

The catalog columns are `Source, Title, Location, Variable, Resolution, ID, lat, lon, Unit, CoverageStart, CoverageEnd, CoverageKnown, Provider, Endpoint, MatchedOn, Inferred`.
`Inferred` lists fields the source did not state (e.g. `Variable,Resolution` parsed from an NWDP title).

## 2. Review

```python
cat.attrs["source_status"]   # per source: ok, complete, rows, error, note, endpoint, dropped{reason: count}
cat.attrs["partial"]         # True if any source failed or its listing was truncated
hs.estimate(cat)             # adds EstRecords / EstNote: exact server count for NWDP, None (unknown) for CWC
hs.save_catalog(cat, "cat.json"); cat = hs.load_catalog("cat.json")   # keeps provenance
```

Filter with ordinary pandas (`cat[cat.Source == "CWC"]`). Pass the filtered table to `fetch`; provenance in `attrs` may be lost by some pandas operations, in which case the manifest says "search provenance unavailable".

## 3. Get: `hs.fetch`

```python
run = hs.fetch(cat, output_dir="output", period=("2020", "2022"), format="csv",
               overwrite=False, rc_discharge=True, resume=True, progress=None, cancel=None)
```

Returns one row per item: `status` (`saved`, `skipped`, `empty`, `error`, `cancelled`), `path`, `records`, actual `start`/`end`, `error`, `method_note`. The manifest path is in `run.attrs["manifest"]`.

* NWDP has no server-side date filter, so the range is applied after download (`filtered_client_side=True`). Resources whose name states a period outside the range are not downloaded.
* CWC discharge is a rating-curve estimate from stage; `rc_discharge=False` fetches stage only.
* `resume=True` reuses a file only if an earlier manifest recorded the same ID **and** the same requested range.
* `progress(event)` receives dicts with `event` in `item_start`, `page`, `item_done`; `cancel` is a `threading.Event`. The engine never prints.

## 4. Use

```python
data = hs.load(run)          # or a manifest path, or an output directory
```

Columns: `time, value, variable, unit, station_id, station_name, source, lat, lon, method, flag, file`.
Variables: `rainfall, water_level, discharge, groundwater_level, reservoir_level, reservoir_storage, temperature, humidity, wind_speed, solar_radiation, atm_pressure, evaporation` (`hydroswift.tidy.VARIABLES`).
`method` is `observed` unless derived (e.g. `rc_guardian_2024`); `flag` carries caveats (unit not stated, groundwater depth-vs-elevation convention). Files that cannot be mapped are listed in `data.attrs["unmapped"]` with a reason.

```python
hs.merge(run, "output/all.parquet")    # .csv | .parquet | .gpkg (needs lat/lon)
hs.plot(run, "output/plots", variable="discharge")
```

## Reservoirs (CWC RSMS)

```python
hs.rsms.daily(output_path=...)        # latest-day storage snapshot
hs.rsms.bulletins(from_date=..., to_date=...)
hs.rsms.backfill(start_date="2025-05-15", output_csv=...)
hs.rsms.build_database(reservoir_shp=..., swot_observations=..., gauge_source=...)   # = hs.swot_reservoir_merge
```

## Removed names

Accessing a removed name (`hs.wris`, `hs.cwc`, `hs.nwdp`, `get_wris_data`, `get_cwc_data`, `merge_only`, `plot_only`, `swot_merge`, ...) raises an error naming its replacement.
