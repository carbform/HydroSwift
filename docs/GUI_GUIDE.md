# HydroSwift GUI guide

Start it with `hyswift-gui` (or `python -m swift_app.gui`). It needs PyQt5 (`pip install hydroswift[gui]`).

The GUI is one screen with four steps. It calls the same functions as Python and the command line
(`search`, `estimate`, `fetch`, `load`, `plot`, `merge`), so a result found here can be reproduced in a script.

## 1. Find

Fill in any of **Where**, **What** and **Period**, tick the sources you want and press **Search**.

* *Where* is a case-insensitive substring matched against each source's own fields (NWDP: organisation; CWC: basin, state, district, river). The **Matched on** column says which field matched.
* *Period* takes a year (`2020`) or a date (`2020-06-01`). A bare year as the end means the end of that year. Either side can be left blank.
* The **source status** line shows, per source, how many rows came back and whether the answer is complete. Hover a source for its endpoint, notes and what was dropped. If a source failed or was cut short, a banner says the results may be incomplete.

## 2. Review

The table shows what each source says about every item: variable, resolution, coverage, provider and a **Not stated by source** column listing fields HydroSwift had to assume. Coverage reads `unknown` when the source does not say; such items are never silently dropped.

Type in **Narrow these results** to filter what is shown without searching again. Select rows and press **Add selected to request** (or **Add all shown**).

## 3. Get

Your request is the list that will be downloaded.

* **Estimate size** asks NWDP for exact record counts. CWC does not report counts, so those stay blank rather than guessed. NWDP's portal cannot filter by date, so the period is applied after download and the file can be smaller than the estimate.
* **CWC discharge** is only available as a rating-curve estimate from stage; it is labelled as such in the data. Untick it for stage only.
* **Get data** shows progress per item; **Cancel** stops after the current page. Items already downloaded for the same request are reused unless you tick *Re-download existing*.

Every run writes a `manifest.json` into the output folder: the search, each source's status, the options and what happened to every item.

## 4. Use

The table lists each item's status, record count, actual date range and file. From here:

* **Plot** writes one PNG per station and variable (estimated series are labelled).
* **Merge to one file** writes a single tidy table (`.parquet`, `.csv` or `.gpkg`) with columns `time, value, variable, unit, station_id, station_name, source, lat, lon, method, flag, file`.
* **Open folder** opens the output directory.

## Known limits

* NWDP certificate verification is disabled by the portal's setup; the manifest records this.
* The NWDP text search is loose, so read the **Variable** column before choosing.
* CWC reservoir data (RSMS) is a latest-day snapshot only.
