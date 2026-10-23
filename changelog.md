# Changelog

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