# HydroSwift Dashboard - Quick Reference Card

## 🚀 Quick Launch

### Terminal
```bash
# Recommended command:
hyswift gui

# Or direct entry point:
hyswift-gui
```
Launches automatically in your browser at `http://localhost:8501`.

---

## 🧭 Navigation

| Control | Purpose |
| :--- | :--- |
| **Find & download** | Search row, station table and map on one screen. |
| **Analyse** | Analyses of the downloaded data. |
| **Reservoirs** | CWC RSMS storage bulletin and map. |
| **Advanced** | Terminal panel at the bottom: `hyswift` console (localhost only) and source log. |
| **Menu** | Dark mode, help, about and disclaimer. |

## 🗺️ Workflow

1. Choose place, variable and years, then **Search**.
2. Tick stations in the table.
3. **Download (n)**; use **Options** for format and folder.
4. **Open in Analyse →**.

---

## 📊 Analyses (Analyse view)

Time series · Summary & data quality · Compare stations · Monthly pattern · Warning & danger exceedance · Flow duration curve · Rating curve · Rainfall · Groundwater.

---

## 🌊 Reservoir Status Module (CWC RSMS)

* **Fetch Live Status**: Retrieves live levels, FRL, DSL, and storage from CWC RSMS portal and GeoServer WFS.
* **KPI Metrics**: Monitored Reservoirs, Total Live Capacity (BCM), Current Storage Monitored (BCM and %), and Critical Reservoirs (<40%).
* **National Reservoir Map**: Interactive pins with storage percentage, capacity, and current water levels.
* **Export CSV**: Download complete national reservoir table with one click.
