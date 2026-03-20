# Changelog

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