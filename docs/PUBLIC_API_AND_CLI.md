# Public API and CLI Map

This page connects the current Python API, the CLI, and the example notebooks.

## 1. Which interface should you use?

### Use the Python API when you need:

- station or basin discovery tables
- DataFrame subsetting before download
- `hydroswift.fetch(...)`
- notebook workflows
- merge/plot pipelines controlled in code

### Use the CLI when you need:

- quick direct downloads
- reproducible shell commands
- a simple flag-based workflow

---

## 2. Notebook-backed usage map

The repository currently includes two example notebook pairs:

- `hydroswift_python_examples.ipynb`
- `hydroswift_cli_examples.ipynb`

The Python notebook emphasizes:

- `hydroswift.wris.basins(variable=...)`
- `hydroswift.wris.stations(...)`
- `hydroswift.cwc.basins()`
- `hydroswift.cwc.stations(...)`
- `hydroswift.fetch(...)`
- `hydroswift.wris.download(...)`
- `hydroswift.cwc.download(...)`
- `hydroswift.merge_only(...)`
- `hydroswift.plot_only(...)`

The CLI notebook emphasizes:

- `hyswift -b ... -q/-rf/-temp/...`
- `hyswift --merge-only --input-dir ...`
- `hyswift --plot-only --input-dir ...`
- `hyswift --cwc`
- `hyswift --cwc-station ...`
- `hyswift --cwc-basin ...`

---

## 3. Direct mapping table

| Task | Python API | CLI |
|---|---|---|
| Download WRIS discharge for a basin | `hydroswift.wris.download(basin='Godavari', variable='discharge')` | `hyswift -b Godavari -q` |
| Download multiple WRIS variables | `hydroswift.wris.download(basin='Krishna', variable=['discharge', 'rainfall', 'temperature'])` | `hyswift -b Krishna -q -rf -temp` |
| Discover WRIS stations before downloading | `hydroswift.wris.stations(basin='Godavari', variable='discharge')` | not directly exposed as a table workflow |
| Download from a WRIS station table | `hydroswift.fetch(wris_table, ...)` | not directly exposed |
| Download all CWC stations in a basin | `hydroswift.cwc.download(basin=['Krishna'])` | `hyswift --cwc-basin Krishna` |
| Download selected CWC stations | `hydroswift.cwc.download(station=['032-LGDHYD'])` | `hyswift --cwc-station 032-LGDHYD` |
| Discover CWC station metadata | `hydroswift.cwc.stations(...)` | `hyswift --list` gives only a summary, not the full table |
| Merge existing output | `hydroswift.merge_only(input_dir='output')` | `hyswift --merge-only --input-dir output` |
| Plot existing output | `hydroswift.plot_only(input_dir='output')` | `hyswift --plot-only --input-dir output` |
| Show help | `hydroswift.help()` / `hydroswift.cli_help()` | `hyswift -h` |
| Show citation | `hydroswift.cite()` | `hyswift --cite` |
| Coffee easter egg | `hydroswift.coffee()` | `hyswift --coffee` |

---

## 4. Differences in Python API vs CLI

### Python API supports table-native workflows

The Python API can pass rich tables between discovery and download:

```python
stations = hydroswift.wris.stations(basin="Godavari", variable="discharge")
subset = stations.head(5)
result = hydroswift.fetch(subset, merge=True)
```

That pattern does not have an equivalent CLI table object.

### CLI is optimised for direct commands

The CLI is best when you already know:

- the WRIS basin and dataset flags, or
- the CWC station/basin filters

---

## 5. Rules that apply across both interfaces

- WRIS supports multiple variables.
- CWC is a water-level workflow.
- Explicit namespace download methods use explicit values, not DataFrames.
- `fetch(...)` is the bridge for HydroSwift-generated tables.
- `merge_only(...)` and `plot_only(...)` work from existing output directories.
