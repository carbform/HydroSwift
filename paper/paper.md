---
title: 'HydroSwift: Simple Water Information Fetch Tool'
tags:
  - Python
  - hydrology
  - water resources
  - India
  - open data
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
date: 12 March 2026
bibliography: paper.bib
---

# Summary

The Simple Water Information Fetch Tool (`HydroSwift`) is an open-source Python package and command-line interface designed to automate the retrieval of hydrological station data from public Indian portals. Hydrological data such as river discharge, water level, rainfall, and groundwater levels are critical for water resource management, climate change studies, and basic research in hydrology. Currently, HydroSwift supports data fetching from the India Water Resources Information System (India-WRIS) and the Central Water Commission (CWC) Flood Forecasting System. By automating the discovery of basins and stations, downloading time-series observations, and providing utilities for merging into geospatial formats, HydroSwift enables reproducible and efficient workflows for working with Indian hydrological data.

# Statement of need

Researchers and hydrological practitioners often face significant hurdles when acquiring observational data from centralized repositories in India. Currently, data access relies on portals such as the National Water Informatics Centre (NWIC) [@nwic], which require manual web navigation and repetitive downloads through interactive maps or forms. Furthermore, critical historical data like groundwater levels are often published as static PDF documents by agencies like the Central Ground Water Board [@cgwb_pdf], which are extremely difficult to parse automatically for large-scale analysis. This manual approach is highly prone to error, difficult to scale to multiple basins or variables, and fundamentally hinders reproducible research. 

While the NWIC and India-WRIS maintain Application Programming Interfaces (APIs), including Swagger UI endpoints, these backend services are primarily optimized for their own web applications. They lack structured programmatic wrappers, user-friendly documentation, and require complex workflows—such as GUI-based token generation for individual datasets, session cookie persistence, and managing undocumented payload structures. Such architectures are antithetical to the reproducible, shell-scriptable workflows necessary for bulk scientific analysis. 

`HydroSwift` was designed to bridge this gap, partly inspired by recent efforts to construct comprehensive sub-daily river discharge networks over India for the GUARDIAN dataset [@patidar2024guardian]. HydroSwift abstract away the complex session persistence, pagination, and undocumented API quirks of the government endpoints. It provides both a simple command-line interface for shell-based automation and a Python API for integration into larger analytical pipelines. Crucially, as the community leans towards relying on large-sample open datasets, HydroSwift will be immensely useful for continually updating and maintaining published hydrological datasets for Indian basins, such as CAMELS-IND [@mangukiya2025camels] and other recent large-scale hydrological compilations [@wrr2025]. 

# Functionality and Features

HydroSwift goes beyond simple data retrieval. It is designed as a comprehensive data processing utility tailored for hydrological analysis. 

**Data Retrieval**: The tool currently supports robust, parallelized fetching of nine critical terrestrial variables from the India-WRIS and CWC portals: 
* River Discharge
* River Water Level
* Rainfall
* Atmospheric Pressure
* Temperature
* Relative Humidity
* Solar Radiation
* Suspended Sediment
* Groundwater Levels

**Data Processing**: Downloading time series is only the first step in hydrological modeling workflows. HydroSwift natively includes data processing pipelines to merge individual, station-level CSVs into unified geospatial formats (GeoPackage `*.gpkg` files) by attaching geographic coordinates from station metadata. This allows researchers to immediately load entire basin networks into spatial tools like QGIS or GeoPandas.

**First-Cut Plotting**: To speed up exploratory data analysis (EDA), HydroSwift includes built-in hydrograph and time-series plotting utilities. Researchers can rapidly generate "first-cut" visualizations of the downloaded data directly from the CLI to visually inspect data continuity and identify hydrologic extremes before moving into complex modeling.

# State of the field

Existing mature software tools for hydrological data retrieval largely focus on generic global datasets or specific non-Indian agencies, such as the `dataRetrieval` ecosystem for the USGS [@decicco2015dataretrieval] and the `HyRiver` suite in Python [@chegini2021hyriver]. For Indian basins, researchers have historically resorted to writing one-off web scraping or API query scripts tailored to a single analysis. These scripts are rarely generalized, maintained, or tested. `HydroSwift` provides a stable, community-maintained interface equivalently robust to established international tools, natively handling the complex authentication, session persistence, and API pagination inherent in Indian systems like India-WRIS [@indiawris] and CWC [@cwc].

# Architecture

`HydroSwift` is structured into two main components:
1. **Core Download Engine**: Handles the HTTP interactions, API session management, retries, and data parsing (`api.py`, `cwc.py`, `download.py`). It employs exponential backoff for resilience against transient network failures.
2. **User Interface Layer**: Provides a robust Command Line Interface (`cli.py`) built with standard libraries, alongside a flexible Python API (`api_public.py`) that mirrors the CLI commands for programmatic use.

The project is designed to be easily extensible. New hydrological data portals can be integrated by subclassing or extending the base API client patterns, without needing to rewrite the CLI or exporting utilities. 

# Acknowledgements

We acknowledge the India Water Resources Information System (India-WRIS) and the Central Water Commission (CWC) for making hydrological data publicly accessible.

# References
