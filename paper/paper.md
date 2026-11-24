---
title: 'HydroSwift: Fast, Unified Workflows for Indian Hydrological Data'
tags:
  - Python
  - hydrology
  - water resources
  - India
  - open data
  - remote sensing
authors:
  - name: C. Sarat
    orcid: 0000-0002-5870-7557
    affiliation: 1
  - name: Debashish Dash
    affiliation: 1
  - name: Abhinav Kumar
    affiliation: 1
affiliations:
  - name: Water Resources Group, National Remote Sensing Centre, ISRO, Hyderabad 500037, India
    index: 1
date: 24 November 2026
bibliography: paper.bib
---

# Summary

The Simple Water Information Fetch Tool (`HydroSwift`) is an open-source Python package, command-line interface, and graphical workbench designed to automate the discovery, retrieval, standardization, and visualization of terrestrial hydrological data from public Indian portals. Hydrological observations—such as river discharge, water levels, reservoir storage, rainfall, groundwater levels, and allied meteorological parameters—are essential for catchment water budgeting, flood risk forecasting, climate impact assessments, and hydrological modeling. 

HydroSwift seamlessly integrates observation streams across:
1. The **National Water Data Portal** (NWDP, managed by the National Water Informatics Centre / NWIC on CKAN),
2. The **Central Water Commission Flood Forecasting System** (CWC FFS),
3. The **CWC Reservoir Storage Monitoring System** (CWC RSMS), and
4. The **India-WRIS REST API Catalog**.

HydroSwift organizes data access around a unified four-stage paradigm: **Find $\rightarrow$ Review $\rightarrow$ Get $\rightarrow$ Use**. It translates disparate upstream formats into consistent, provenance-tracked, tidy dataframes ready for scientific modeling and spatial analysis.

# Statement of need

Hydrologists, climate scientists, and practitioners in India routinely encounter substantial friction when assembling observational records from government repositories. Historically, data access has been fragmented across isolated portals:
* India-WRIS and NWDP [@nwic] historically provided bulk datasets across state and central agencies via heterogeneous CKAN DataStore structures and static batches.
* The Central Water Commission Flood Forecasting System provides real-time river stage telemetry, yet river discharge is not directly published as telemetry and requires hydraulic rating curves to compute from water levels [@patidar2024guardian].
* Critical reservoir storage time series have historically been locked in published weekly PDF bulletins or dynamic cryptographic handshakes on RSMS [@cwc].

Before HydroSwift, researchers were forced to write fragile, unmaintained web scrapers or perform repetitive manual downloads across dozens of portal webforms. These ad-hoc approaches hinder reproducibility, cannot scale to national multi-basin studies, and create significant barriers to building large-sample hydrological benchmarks such as CAMELS-IND [@mangukiya2025camels] and other recent compilations [@wrr2025].

HydroSwift solves these challenges by providing a standardized, resilient, and fully scriptable library. It abstracts network retries, pagination, date filtering, and format normalization into clean Python and CLI interfaces. Every download generates a cryptographically sound `manifest.json` recording query parameters, endpoints, record counts, and actual observation spans, establishing full data provenance for reproducible science.

# Functionality and Features

HydroSwift implements a cohesive end-to-end scientific pipeline:

* **Unified Discovery (`search`)**: Enables concurrent querying across all supported data sources using common physical variable names (e.g., `rainfall`, `water_level`, `discharge`, `groundwater_level`, `reservoir_storage`) and geographical filters (states, districts, major basins, and tributaries).
* **Provenance & Volume Review (`estimate`)**: Before initiating network-intensive downloads, HydroSwift inspects per-source query health (`source_status`), reports any dropped or truncated resources, and calculates server-reported record count estimates.
* **Resilient, Resumable Fetching (`fetch`)**: Downloads observations with progress callbacks, cancellation hooks, and automatic manifest resumption, eliminating redundant downloads of identical datasets.
* **Universal Tidy Standardization (`load`)**: Transforms heterogeneous raw records (CKAN tables, sub-daily telemetry, and REST JSON) into a single, standardized tidy long DataFrame (`time`, `value`, `variable`, `unit`, `station_id`, `station_name`, `lat`, `lon`, `source`, `agency`, `method`, `flag`). Physical units are normalized (e.g., mm, m, $\text{m}^3/\text{s}$, BCM, $^\circ\text{C}$).
* **Operational Flood Forecasting & Rating Curves**: For CWC river gauging stations, HydroSwift incorporates hydraulic rating curves calibrated under the GUARDIAN dataset methodology [@patidar2024guardian] to estimate river discharge ($\text{m}^3/\text{s}$) from river stage.
* **Reservoir Storage Monitoring (RSMS)**: Automates real-time daily storage snapshots across 180+ major national reservoirs and includes layout-preserving PDF table extraction to backfill decades of historical weekly bulletin archives.
* **Export, Hydrological Plotting & Map Layers (`merge`, `plot`, `map`)**: Directly compiles observations into compressed Parquet, geospatial GeoPackage (`*.gpkg`), or CSV formats. Generates rich hydrological figures including dual-axis hydrographs (stage & discharge), precipitation hyetographs, hydraulic rating curves ($H-Q$), and flow duration curves (FDCs) with CWC flood threshold alert lines (Warning, Danger, HFL). Produces standalone interactive Leaflet map layers with multi-basemap switching, marker clustering, flood alert highlights, and custom GeoJSON catchment overlays.
* **Single-Screen Workbench GUI**: HydroSwift includes an offscreen-tested PyQt5 desktop workbench providing interactive search filtering, provenance tracking, download progress bars, embedded plotting, and one-click station mapping.

# Modular Architecture

HydroSwift is architected into clean, decoupled layers:

1. **`hydroswift.core`**: Houses the engine orchestration (`search_catalog`, `fetch_catalog`, `manifest`), the universal tidy data model (`load`, unit normalizers, canonical vocabularies), and consolidated export and visualization utilities (`merge`, `plot`, `map`).
2. **`hydroswift.sources`**: Pluggable source adapters (`nwdp`, `cwc_ffs`, `cwc_rsms`, `wris_api`) implementing independent client protocols, authentication, and endpoint pagination.
3. **`hydroswift.gui`**: Single-screen reactive workbench implementing the Find-Review-Get-Use workflow.
4. **`hydroswift.experimental`**: Staged research components, including multi-source satellite altimetry validation linking Surface Water and Ocean Topography (SWOT) KaRIn passes with in-situ reservoir storage bulletins.

# State of the field

Existing hydrological software frameworks such as `dataRetrieval` for the USGS [@decicco2015dataretrieval] and `HyRiver` [@chegini2021hyriver] have demonstrated the transformative value of standardized programmatic data access for water science in the United States. `HydroSwift` provides an equivalent, robust open-source ecosystem dedicated to Indian water data, establishing reproducible pipelines from national portals to hydrological models.

# Acknowledgements

We acknowledge the National Water Informatics Centre (NWIC), the India Water Resources Information System (India-WRIS), and the Central Water Commission (CWC) for publishing open hydrological observations.

# References
