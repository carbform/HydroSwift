# Changelog

## Unreleased — unified engine (breaking)
**One workflow: Find -> Review -> Get -> Use** (`search` -> `estimate` -> `fetch` -> `load`).
- New engine (`swift_app/engine.py`): fixed catalog schema; NWDP, CWC flood-forecasting and CWC RSMS adapters; per-source status (`attrs['source_status']`, `attrs['partial']`); `Inferred` column; `manifest.json` for every fetch.
- NWDP: search now pages through all results and reports errors/truncation instead of returning "no data"; dates are parsed as DD-MM-YYYY (they were being read month-first); coverage is taken from the resource name; the date range is applied to every download; empty resources are counted, not dropped silently.
- `search(period=, ids=, basin=, state=)`; exact filters alongside the substring `location`.
- `estimate()`, progress callback and cancel event on `fetch()`, resume only when the same ID and requested range are already in a manifest.
- `load()` returns one tidy long table with a fixed variable vocabulary and units; files that do not fit are reported, never guessed. `merge()` (csv/parquet/gpkg) and `plot()` are built on it.
- CWC: rating-curve discharge is on by default and labelled as estimated; data are written under `cwc/<basin>/`.
- New CLI: `hyswift search | get | show | merge | plot | rsms`, guided mode when run without arguments.
- GUI: the CWC expert tab and emoji labels are removed (emoji rendering crashed Qt on some systems); the full GUI redesign follows.

**Removed** (accessing them raises an error that names the replacement): `get_wris_data`, `get_cwc_data`, `wris.*`, `cwc.*`, `nwdp.*`, `wris_stations`, `cwc_stations`, `merge_only`, `plot_only`, `swot_merge`, the flat CLI flags (`-b`, `-q`, `--cwc-basin`, `--merge`, `--plot-only`, ...) and the old interactive wizard. WRIS access had already been merged into NWDP upstream. The CWC station-metadata CSV export, per-basin GeoPackage merging and the WRIS/CWC `swot_merge` GeoPackage were dropped; the reservoir database builder (`swot_reservoir_merge`, `hyswift rsms build`) is kept.

## 1.1.0 — Arctic Amsterdam (RSMS & SWOT Reservoir Harmonization)
- **CWC RSMS Integration**: Added dedicated client (`swift_app.cwc_rsms`) for the Central Water Commission Reservoir Storage Monitoring System (`https://rsms.cwc.gov.in`).
- **AES-128 Cryptographic Engine**: Reverse-engineered dynamic secret-key handshake, AES-128-CBC payload encryption/decryption, and HMAC-SHA256 request signing for authenticated RSMS endpoints.
- **Daily Snapshot Tracker**: Added real-time tracking of 180+ major reservoirs via GeoServer WFS centroids and `api/getReservoir-details` (`hydroswift.rsms.daily` and CLI `--rsms-daily`).
- **Weekly Bulletin Archive & PDF Extractor**: Automated downloading and layout-preserving parsing of official CWC weekly reservoir bulletins (`hydroswift.rsms.bulletins`, `hydroswift.rsms.backfill`, CLI `--rsms-bulletins`, `--rsms-backfill`).
- **Unified SWOT & Gauge Database Pipeline**: Integrated multi-source harmonization linking SWOT KaRIn satellite passes ($\pm 3.5\text{ days}$) to in-situ gauge measurements and reservoir polygon shapefiles (`hydroswift.swot_reservoir_merge`, CLI `--swot-reservoir-merge`).
- **Automatic Data Hygiene Filters**: Integrated automated detection and rectification of transcription outliers (Manikdoh 10× clerical error and Rihand ft $\leftrightarrow$ m shift).
- **Multi-Format Storage**: Automated export to standardized GeoPackage (with spatial `reservoirs` layer and observation tables), SQLite DB with index optimizations, and compressed Parquet.

## 1.0.0 — Arctic Amsterdam
- Implement Background Logging with `hydroswift.log`
- Introduce `--quiet` mode for clean script/terminal integration
- `--coffee` mode now runs in background with quiet mode enabled
- Build exponential backoff logic for CWC API requests

## 0.4.1 — Delta Delhi - Hotfix/CLI updates
- Full CWC Output Standardization (matching WRIS API schema)
- Added dedicated `--list` argument for indexing available WRIS basins and finding CWC stations
- Removed deprecated `--stations` and `--geopackage` flags to declutter workflow
- Migrated GeoPackage building logic directly into `--merge` for WRIS and CWC
- Basin name input via `-b` can now accept corresponding index numbers
- Added non-blocking animated `--coffee` flag
- Fixed missing variables and import dependencies

## 0.4.0 — Delta Delhi
- Basin auto-discovery
- Parallel station downloads
- Resume interrupted downloads
- GeoPackage export
- CLI improvements

## 0.3.0 — Cryo Copenhagen
- WRIS API reverse engineering
- Initial API download implementation