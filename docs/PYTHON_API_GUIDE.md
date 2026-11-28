# Python API Guide

HydroSwift provides a clean, unified Python API following the four-stage workflow: **Find $\rightarrow$ Review $\rightarrow$ Get $\rightarrow$ Use**.

```python
import hydroswift as hs
```

---

## 1. Find: `hs.search`

Discover observations across CWC, India-WRIS, and NWDP:

```python
cat = hs.search(
    query=None,
    location=None,
    sources=None,
    *,
    period=None,
    ids=None,
    basin=None,
    state=None,
    cross_boundary=True,
)
```

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `query` | `str` | Variable or physical parameter (e.g. `"rainfall"`, `"discharge"`, `"water level"`, `"groundwater level"`). |
| `location` | `str` | Free-form substring matched against station titles, rivers, and locations. |
| `sources` | `list[str]` | Subset of `["CWC", "WRIS", "NWDP"]`. Defaults to all. |
| `period` | `tuple` or `str` | Temporal bounds: `("2020", "2024")`, `("2021-01-01", "2023-12-31")`, or `"2020:2024"`. |
| `basin` | `str` | Exact official CWC River Basin name (e.g. `"Cauvery"`, `"Ganga"`, `"Godavari"`). |
| `state` | `str` | Exact Indian State or Union Territory name (e.g. `"Karnataka"`, `"Odisha"`). |
| `cross_boundary` | `bool` | When `True` (default), querying a river basin automatically cross-discovers constituent state open datasets (e.g., NWDP). |
| `ids` | `list[str]` | List of exact catalog station IDs to retrieve. |

**Returned Catalog Structure**:
A pandas DataFrame containing:
`Source, Title, Location, Variable, Resolution, ID, lat, lon, Unit, CoverageStart, CoverageEnd, CoverageKnown, Provider, Endpoint, MatchedOn, Inferred`.

---

## 2. Review: Provenance & Estimation

Inspect search results and verify server-side record estimates:

```python
# Check per-source execution provenance
cat.attrs["source_status"]   # per-source: ok, complete, rows, error, note, endpoint
cat.attrs["partial"]         # True if any source encountered warnings or partial returns

# Estimate exact record counts (available on supporting sources like NWDP)
estimated = hs.estimate(cat.head(10))

# Save & reload discovered catalogs with full provenance
hs.save_catalog(cat, "output/catalog.json")
loaded_cat = hs.load_catalog("output/catalog.json")
```

---

## 3. Get: `hs.fetch`

Download observations from the catalog into local storage:

```python
run = hs.fetch(
    cat,
    output_dir="output",
    period=("2020", "2024"),
    format="csv",             # "csv", "parquet", "gpkg", "json"
    overwrite=False,
    rc_discharge=True,        # include CWC rating-curve discharge estimates
    workers=4,
    progress=None,            # callback function receiving item_start, page, item_done
    cancel=None,              # threading.Event for non-blocking cancellation
)
```

**Returned Run Summary**:
A DataFrame with one record per downloaded station: `status` (`saved`, `skipped`, `empty`, `error`), `path`, `records`, actual `start`/`end`, and provenance links to `manifest.json`.

---

## 4. Use: `hs.load`, `hs.merge`, `hs.plot`

Load downloaded data into a standardized, tidy structure:

```python
# 1. Load into unified tidy DataFrame
tidy = hs.load(run)  # or hs.load("output") / hs.load("output/manifest.json")
print(tidy[["time", "station_name", "variable", "value", "unit"]].head())

# 2. Merge all stations into a single analytics file
hs.merge(run, "output/unified_observations.parquet")  # supports .parquet, .csv, .gpkg

# 3. Generate publication-quality summary plots
hs.plot(run, output_dir="output/plots")
```

**Tidy DataFrame Schema**:
* `time`: Standardized UTC/IST datetime timestamp.
* `value`: Numerical observation measurement.
* `variable`: Standardized parameter name (`water_level`, `discharge`, `rainfall`, `groundwater_level`, `reservoir_level`, `reservoir_storage`, etc.).
* `unit`: Normalized physical unit (`m`, `m3/s`, `mm`, `BCM`, `degC`).
* `station_id`, `station_name`: Unique station identifiers.
* `source`: Data source provider (`CWC`, `WRIS`, `NWDP`).
* `lat`, `lon`: Coordinates for geospatial mapping.
* `method`: `observed` or `rc_guardian_2024` (for stage-derived discharge).
* `flag`: Quality flags (e.g. groundwater depth vs elevation convention).

---

## 5. CWC RSMS National Reservoirs API

Query real-time storage status for ~180 major Indian reservoirs:

```python
# Daily snapshot bulletin from CWC RSMS portal
res_df = hs.rsms.daily(output_path="output/cwc_rsms/daily_snapshot.csv")
print(res_df[["reservoir_name", "storage_bcm", "live_cap_bcm", "storage_pct"]].head())

# Backfill historical bulletins
hs.rsms.backfill(start_date="2025-05-15", end_date="2025-06-01", output_csv="output/bulletins.csv")

# Harmonize SWOT satellite elevations with in-situ reservoir storage
hs.swot_reservoir_merge(
    reservoir_shp="reservoirs.shp",
    swot_observations="swot_obs.sqlite",
    gauge_source="gauge_cache/",
    output_gpkg="output/unified_reservoir_swot_gauge.gpkg",
)
```

## Station statistics and aggregation

```python
stats = hs.summary(run)              # completeness, longest gap, min/median/mean/max per series
monthly = hs.resample(run, "monthly")  # rainfall summed; levels and discharge averaged
```
