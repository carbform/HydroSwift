# CLI Usage Guide

```bash
hyswift search rainfall --where Karnataka --period 2020:2022 --save cat.json
hyswift get --from cat.json --rows 0,2 --period 2020:2022 --out output
hyswift show output
hyswift merge output all.parquet
hyswift plot output output/plots
hyswift rsms daily
hyswift                      # guided prompts
```

## `search`
`hyswift search [query] [--where TEXT] [--basin NAME] [--state NAME] [--ids A,B] [--source NWDP|CWC|CWC-RSMS ...] [--period P] [--estimate] [--save FILE] [--limit N]`

Prints a per-source status block (ok / FAILED / PARTIAL, rows dropped and why, notes) and then the table.
`--where` is a substring; `--basin`/`--state`/`--ids` are exact. `--save` keeps the catalog together with its provenance.
Exit code 1 if the result is empty because a source failed.

## `get`
`hyswift get --from FILE [--rows 0,2-5] [--period P] [--out DIR] [--format csv|xlsx|json] [--overwrite] [--no-rc-discharge]`

Rows are numbered from 0 as printed by `search`. Prints progress per item and the manifest path; exit code 1 if any item failed.

## `show`, `merge`, `plot`
`show PATH` summarises the tidy data (source, variable, unit, method, rows, stations, span) and lists unmapped files.
`merge PATH OUTPUT` writes `.csv`, `.parquet` or `.gpkg`. `plot PATH [DIR] [--variable V]` writes one PNG per station and variable.
`PATH` is an output directory (newest manifest) or a `manifest*.json`.

## `rsms`
`rsms daily [--out CSV]`, `rsms backfill [--start D] [--end D] [--out CSV] [--bulletin-dir DIR]`,
`rsms build --reservoir-shp P --swot-db P --gauge-cache P [--out-dir DIR]`.

## Removed
The old flat flags (`-b`, `-q`, `-rf`, `--cwc-basin`, `--merge`, `--plot-only`, `--nwdp-*`, `--rsms-daily`, ...) and the old wizard are gone.
