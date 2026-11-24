"""HydroSwift interactive and layered geospatial mapping module.

Generates self-contained, publication-ready interactive Leaflet maps with:
- Multi-source station marker clustering (NWDP, CWC, CWC-RSMS, WRIS)
- Basemap switcher (OpenStreetMap, CartoDB Light, CartoDB Dark, Esri Satellite)
- CWC Flood warning / danger alert level highlights
- Observation popups with latest telemetry readings and provenance
- Custom GeoJSON / Shapefile / GeoPackage catchment and basin layer overlays
- Seamless embedding in Jupyter notebooks via `_repr_html_()`.
"""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

SOURCE_COLORS = {
    "NWDP": "#2563eb",       # Blue
    "CWC": "#059669",        # Emerald green
    "CWC-RSMS": "#7c3aed",   # Violet
    "WRIS": "#d97706",       # Amber
    "DEFAULT": "#4b5563",    # Slate gray
}

ALERT_COLORS = {
    "danger": "#dc2626",     # Crimson red
    "warning": "#f59e0b",    # Amber yellow
    "normal": "#10b981",     # Green
}


class HydroMap:
    """Container for interactive HydroSwift Leaflet map."""

    def __init__(
        self,
        html_content: str,
        path: Optional[Union[str, Path]] = None,
        stations_count: int = 0,
        bounds: Optional[List[List[float]]] = None,
    ):
        self.html = html_content
        self.path = str(path) if path else None
        self.stations_count = stations_count
        self.bounds = bounds

    def save(self, path: Union[str, Path]) -> str:
        """Save map to HTML file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.html, encoding="utf-8")
        self.path = str(p)
        return str(p)

    def to_html(self) -> str:
        """Return raw HTML string."""
        return self.html

    def _repr_html_(self) -> str:
        """Display interactively in Jupyter notebooks via an isolated iframe."""
        b64 = base64.b64encode(self.html.encode("utf-8")).decode("utf-8")
        return (
            f'<iframe src="data:text/html;base64,{b64}" width="100%" height="560" '
            f'frameborder="0" style="border: 1px solid #e5e7eb; border-radius: 8px; '
            f'box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);"></iframe>'
        )

    def __repr__(self) -> str:
        if self.path:
            return f"<HydroMap: {self.stations_count} station(s) saved to '{self.path}'>"
        return f"<HydroMap: {self.stations_count} station(s)>"


def _extract_stations(data: Any) -> List[Dict[str, Any]]:
    """Normalise catalog, tidy, or fetch DataFrame to a list of station dicts."""
    from .tidy import TIDY_COLUMNS, load as _load

    if isinstance(data, (str, Path)):
        p = Path(data)
        if p.is_dir() or p.name.endswith(".json"):
            data = _load(p)

    if not isinstance(data, pd.DataFrame) or data.empty:
        return []

    # Check for CWC station metadata table for threshold enrichment
    cwc_meta_lookup = {}
    try:
        from hydroswift.sources.cwc_ffs import load_station_table
        meta_df = load_station_table(refresh=False)
        for _, r in meta_df.iterrows():
            code = str(r.get("code", "")).strip().lower()
            if code:
                cwc_meta_lookup[code] = {
                    "river": r.get("river"),
                    "basin": r.get("basin"),
                    "state": r.get("state"),
                    "district": r.get("district"),
                    "warning_level": r.get("warning_level"),
                    "danger_level": r.get("danger_level"),
                    "hfl": r.get("hfl"),
                    "hfl_date": r.get("hfl_date"),
                }
    except Exception:
        pass

    stations = []

    # Format 1: Tidy DataFrame (from hs.load())
    if set(TIDY_COLUMNS).issubset(data.columns):
        grouped = data.groupby("station_id", dropna=False)
        for sid, g in grouped:
            lat = g["lat"].dropna().iloc[0] if g["lat"].notna().any() else None
            lon = g["lon"].dropna().iloc[0] if g["lon"].notna().any() else None
            if pd.isna(lat) or pd.isna(lon):
                continue

            name = g["station_name"].dropna().iloc[0] if g["station_name"].notna().any() else str(sid or "Unknown")
            src = g["source"].dropna().iloc[0] if g["source"].notna().any() else "Unknown"
            vars_list = sorted(set(g["variable"].dropna().astype(str)))
            units_list = sorted(set(g["unit"].dropna().astype(str)))

            # Latest reading
            g_sorted = g.sort_values("time")
            latest_row = g_sorted.iloc[-1]
            latest_val = latest_row["value"] if pd.notna(latest_row["value"]) else None
            latest_time = str(latest_row["time"]) if pd.notna(latest_row["time"]) else None
            latest_var = str(latest_row["variable"]) if pd.notna(latest_row["variable"]) else ""
            latest_unit = str(latest_row["unit"]) if pd.notna(latest_row["unit"]) else ""

            # Check thresholds from CWC table
            meta = cwc_meta_lookup.get(str(sid or "").strip().lower(), {})
            wl_warn = meta.get("warning_level")
            wl_danger = meta.get("danger_level")

            alert_status = "normal"
            if latest_var == "water_level" and pd.notna(latest_val):
                if pd.notna(wl_danger) and float(latest_val) >= float(wl_danger):
                    alert_status = "danger"
                elif pd.notna(wl_warn) and float(latest_val) >= float(wl_warn):
                    alert_status = "warning"

            stations.append({
                "id": str(sid or "unknown"),
                "name": str(name),
                "lat": float(lat),
                "lon": float(lon),
                "source": str(src),
                "variable": ", ".join(vars_list),
                "units": ", ".join(units_list),
                "records": len(g),
                "start": str(g["time"].min()),
                "end": str(g["time"].max()),
                "latest_value": float(latest_val) if latest_val is not None else None,
                "latest_time": latest_time,
                "latest_var": latest_var,
                "latest_unit": latest_unit,
                "alert_status": alert_status,
                "basin": meta.get("basin") or "",
                "river": meta.get("river") or "",
                "state": meta.get("state") or "",
                "warning_level": float(wl_warn) if pd.notna(wl_warn) else None,
                "danger_level": float(wl_danger) if pd.notna(wl_danger) else None,
                "hfl": float(meta.get("hfl")) if pd.notna(meta.get("hfl")) else None,
            })
        return stations

    # Format 2: Catalog DataFrame (from hs.search())
    if "ID" in data.columns and "lat" in data.columns and "lon" in data.columns:
        valid = data.dropna(subset=["lat", "lon"])
        for _, r in valid.iterrows():
            sid = str(r.get("ID", ""))
            meta = cwc_meta_lookup.get(sid.strip().lower(), {})
            wl_warn = meta.get("warning_level")
            wl_danger = meta.get("danger_level")

            stations.append({
                "id": sid,
                "name": str(r.get("Title") or sid),
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
                "source": str(r.get("Source", "Unknown")),
                "location": str(r.get("Location", "")),
                "variable": str(r.get("Variable", "")),
                "units": str(r.get("Unit", "")),
                "resolution": str(r.get("Resolution", "")),
                "provider": str(r.get("Provider", "")),
                "basin": meta.get("basin") or str(r.get("_basin") or ""),
                "river": meta.get("river") or str(r.get("_river") or ""),
                "state": meta.get("state") or str(r.get("_state") or ""),
                "warning_level": float(wl_warn) if pd.notna(wl_warn) else None,
                "danger_level": float(wl_danger) if pd.notna(wl_danger) else None,
                "hfl": float(meta.get("hfl")) if pd.notna(meta.get("hfl")) else None,
                "alert_status": "normal",
            })
        return stations

    return stations


def _read_geojson_layer(layer_input: Any) -> Optional[Dict[str, Any]]:
    """Convert layer input (file path, GeoDataFrame, dict) to GeoJSON dict."""
    if isinstance(layer_input, dict):
        return layer_input

    if isinstance(layer_input, (str, Path)):
        p = Path(layer_input)
        if not p.exists():
            return None
        ext = p.suffix.lower()
        if ext in (".geojson", ".json"):
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return None
        # Shapefile / GPKG via geopandas if available
        try:
            import geopandas as gpd
            gdf = gpd.read_file(p)
            return json.loads(gdf.to_json())
        except Exception:
            return None

    # GeoDataFrame object
    if hasattr(layer_input, "to_json"):
        try:
            return json.loads(layer_input.to_json())
        except Exception:
            return None

    return None


def create_map(
    data: Any,
    output: Optional[Union[str, Path]] = "output/map.html",
    *,
    basemap: str = "osm",
    color_by: str = "source",
    cluster: bool = True,
    alert_highlight: bool = True,
    geojson_layers: Optional[List[Union[str, Path, Any]]] = None,
    title: str = "HydroSwift Hydrological Stations",
    center: Optional[Tuple[float, float]] = None,
    zoom: Optional[int] = None,
) -> HydroMap:
    """Create a publication-ready interactive Leaflet map from catalog or tidy data.

    Parameters
    ----------
    data : DataFrame, str, or Path
        Search catalog DataFrame, tidy DataFrame from `hs.load()`, or output folder.
    output : str or Path, optional
        Destination HTML file path (default: "output/map.html"). If None, map is not saved to disk.
    basemap : str
        Default basemap: 'osm' (OpenStreetMap), 'carto-light', 'carto-dark', or 'satellite'.
    color_by : str
        Marker coloring mode: 'source' (by data source) or 'status' (normal/warning/danger).
    cluster : bool
        Whether to enable Leaflet marker clustering (recommended for >50 stations).
    alert_highlight : bool
        Whether to pulse/highlight markers exceeding Warning or Danger flood levels.
    geojson_layers : list of str, Path, or GeoDataFrame, optional
        Catchment boundaries, basin vectors, or stream reaches to overlay on the map.
    title : str
        Header title on map controls.
    center : tuple of (lat, lon), optional
        Initial map center coordinates. Automatically fitted to station bounds if None.
    zoom : int, optional
        Initial zoom level (1-18). Automatically computed if None.

    Returns
    -------
    HydroMap
        Interactive map object with `.save()`, `.to_html()`, and Jupyter `_repr_html_()`.
    """
    stations = _extract_stations(data)
    if not stations:
        raise ValueError("No stations with geographic coordinates (lat/lon) found in input data.")

    # Compute bounding box
    lats = [s["lat"] for s in stations]
    lons = [s["lon"] for s in stations]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    bounds = [[min_lat, min_lon], [max_lat, max_lon]]
    c_lat = (min_lat + max_lat) / 2 if center is None else center[0]
    c_lon = (min_lon + max_lon) / 2 if center is None else center[1]
    initial_zoom = zoom or 6

    # Parse external GeoJSON layers
    parsed_layers = []
    if geojson_layers:
        for idx, lyr in enumerate(geojson_layers, 1):
            gjson = _read_geojson_layer(lyr)
            if gjson:
                name = getattr(lyr, "name", None) or (Path(lyr).stem if isinstance(lyr, (str, Path)) else f"Layer {idx}")
                parsed_layers.append({"name": str(name), "geojson": gjson})

    # Prepare JSON payload
    stations_json = json.dumps(stations, default=str)
    layers_json = json.dumps(parsed_layers, default=str)
    bounds_json = json.dumps(bounds)
    source_colors_json = json.dumps(SOURCE_COLORS)
    alert_colors_json = json.dumps(ALERT_COLORS)

    # Count by source
    counts: Dict[str, int] = {}
    for s in stations:
        src = s.get("source", "Other")
        counts[src] = counts.get(src, 0) + 1
    pill_badges = " ".join(
        f'<span style="background:{SOURCE_COLORS.get(src, "#4b5563")};color:#fff;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;">{html.escape(src)}: {n}</span>'
        for src, n in sorted(counts.items())
    )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />
  <style>
    body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
    #map {{ width: 100%; height: 100%; background: #f3f4f6; }}
    .header-panel {{
      position: absolute; top: 12px; left: 60px; z-index: 1000;
      background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(8px);
      padding: 10px 16px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.12);
      max-width: 450px; pointer-events: auto;
    }}
    .header-title {{ font-size: 15px; font-weight: 700; color: #111827; margin: 0 0 6px 0; display: flex; align-items: center; gap: 6px; }}
    .header-badges {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }}
    .search-box {{
      margin-top: 8px; width: 100%; padding: 6px 10px; border: 1px solid #d1d5db;
      border-radius: 6px; font-size: 12px; box-sizing: border-box; outline: none;
    }}
    .search-box:focus {{ border-color: #2563eb; box-shadow: 0 0 0 2px rgba(37,99,235,0.2); }}
    .custom-popup {{ font-size: 12px; line-height: 1.4; color: #374151; }}
    .popup-title {{ font-size: 14px; font-weight: 700; color: #111827; margin-bottom: 2px; }}
    .popup-sub {{ font-size: 11px; color: #6b7280; margin-bottom: 8px; }}
    .popup-table {{ width: 100%; border-collapse: collapse; margin-top: 4px; }}
    .popup-table td {{ padding: 3px 0; border-bottom: 1px solid #f3f4f6; }}
    .popup-table td.label {{ color: #6b7280; width: 40%; font-weight: 500; }}
    .popup-table td.val {{ text-align: right; font-weight: 600; color: #111827; }}
    .alert-pill {{ display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700; text-transform: uppercase; color: #fff; }}
    .alert-danger {{ background: #dc2626; }}
    .alert-warning {{ background: #f59e0b; }}
    .alert-normal {{ background: #10b981; }}
    .pulse-danger {{ animation: pulse-red 1.5s infinite; }}
    @keyframes pulse-red {{
      0% {{ transform: scale(1); opacity: 1; }}
      50% {{ transform: scale(1.3); opacity: 0.6; }}
      100% {{ transform: scale(1); opacity: 1; }}
    }}
  </style>
</head>
<body>
  <div id="map"></div>
  <div class="header-panel">
    <div class="header-title">⚡ {html.escape(title)}</div>
    <div class="header-badges">{pill_badges}</div>
    <input type="text" id="stationSearch" class="search-box" placeholder="🔍 Search station name or code..." />
  </div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
  <script>
    const stations = {stations_json};
    const customLayers = {layers_json};
    const bounds = {bounds_json};
    const sourceColors = {source_colors_json};
    const alertColors = {alert_colors_json};
    const colorMode = "{color_by}";
    const clusterEnabled = {"true" if cluster else "false"};

    // Basemaps
    const osm = L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
      maxZoom: 19, attribution: "© OpenStreetMap contributors"
    }});
    const cartoLight = L.tileLayer("https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png", {{
      maxZoom: 20, attribution: "© CartoDB, © OpenStreetMap"
    }});
    const cartoDark = L.tileLayer("https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png", {{
      maxZoom: 20, attribution: "© CartoDB, © OpenStreetMap"
    }});
    const satellite = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}", {{
      maxZoom: 19, attribution: "© Esri"
    }});

    const baseMaps = {{
      "OpenStreetMap": osm,
      "CartoDB Light": cartoLight,
      "CartoDB Dark": cartoDark,
      "Satellite (Esri)": satellite
    }};

    let defaultLayer = osm;
    if ("{basemap}" === "carto-light") defaultLayer = cartoLight;
    if ("{basemap}" === "carto-dark") defaultLayer = cartoDark;
    if ("{basemap}" === "satellite") defaultLayer = satellite;

    const map = L.map("map", {{
      layers: [defaultLayer],
      center: [{c_lat}, {c_lon}],
      zoom: {initial_zoom}
    }});

    if (bounds && bounds[0][0] !== bounds[1][0]) {{
      map.fitBounds(bounds, {{ padding: [60, 60] }});
    }}

    L.control.scale({{ metric: true, imperial: false }}).addTo(map);

    // Grouping markers by Source
    const sourceGroups = {{}};
    const markerIndex = {{}};

    stations.forEach(s => {{
      const src = s.source || "Other";
      if (!sourceGroups[src]) {{
        sourceGroups[src] = clusterEnabled ? L.markerClusterGroup({{
          showCoverageOnHover: false,
          maxClusterRadius: 40
        }}) : L.layerGroup();
      }}

      // Marker color
      let mColor = sourceColors[src] || sourceColors["DEFAULT"];
      if (colorMode === "status" && s.alert_status) {{
        mColor = alertColors[s.alert_status] || mColor;
      }}

      let rad = 7;
      let strokeColor = "#ffffff";
      if (s.alert_status === "danger") {{
        mColor = "#dc2626";
        rad = 9;
      }} else if (s.alert_status === "warning") {{
        mColor = "#f59e0b";
        rad = 8;
      }}

      const marker = L.circleMarker([s.lat, s.lon], {{
        radius: rad,
        fillColor: mColor,
        color: strokeColor,
        weight: 1.5,
        opacity: 1,
        fillOpacity: 0.85
      }});

      // Popup content
      let alertBadge = "";
      if (s.alert_status === "danger") {{
        alertBadge = '<span class="alert-pill alert-danger">Danger Exceeded</span>';
      }} else if (s.alert_status === "warning") {{
        alertBadge = '<span class="alert-pill alert-warning">Warning Level</span>';
      }}

      let rows = "";
      if (s.basin) rows += `<tr><td class="label">Basin</td><td class="val">${{s.basin}}</td></tr>`;
      if (s.river) rows += `<tr><td class="label">River</td><td class="val">${{s.river}}</td></tr>`;
      if (s.state) rows += `<tr><td class="label">State</td><td class="val">${{s.state}}</td></tr>`;
      if (s.variable) rows += `<tr><td class="label">Variable</td><td class="val">${{s.variable}}</td></tr>`;
      if (s.latest_value !== undefined && s.latest_value !== null) {{
        rows += `<tr><td class="label">Latest (${{s.latest_time ? s.latest_time.slice(0,10) : ''}})</td><td class="val">${{s.latest_value}} ${{s.latest_unit || ''}}</td></tr>`;
      }}
      if (s.warning_level) rows += `<tr><td class="label">Warning Level</td><td class="val">${{s.warning_level}} m</td></tr>`;
      if (s.danger_level) rows += `<tr><td class="label">Danger Level</td><td class="val">${{s.danger_level}} m</td></tr>`;
      if (s.records) rows += `<tr><td class="label">Records</td><td class="val">${{s.records.toLocaleString()}}</td></tr>`;

      const popupHtml = `
        <div class="custom-popup">
          <div class="popup-title">${{s.name}} ${{alertBadge}}</div>
          <div class="popup-sub">ID: <code>${{s.id}}</code> • <strong>${{src}}</strong></div>
          <table class="popup-table">${{rows}}</table>
        </div>
      `;
      marker.bindPopup(popupHtml);

      sourceGroups[src].addLayer(marker);
      markerIndex[s.id.toLowerCase()] = marker;
      markerIndex[s.name.toLowerCase()] = marker;
    }});

    // Add source groups to map
    const overlayMaps = {{}};
    Object.keys(sourceGroups).forEach(src => {{
      sourceGroups[src].addTo(map);
      overlayMaps[`Stations: ${{src}}`] = sourceGroups[src];
    }});

    // Add custom GeoJSON overlay layers
    customLayers.forEach(lyr => {{
      const geoLayer = L.geoJSON(lyr.geojson, {{
        style: {{
          color: "#3b82f6",
          weight: 2,
          opacity: 0.7,
          fillColor: "#60a5fa",
          fillOpacity: 0.15
        }},
        onEachFeature: function(feature, layer) {{
          if (feature.properties) {{
            let content = "<div style='font-size:12px;'><strong>Layer: " + lyr.name + "</strong><br/>";
            for (let k in feature.properties) {{
              content += k + ": " + feature.properties[k] + "<br/>";
            }}
            content += "</div>";
            layer.bindPopup(content);
          }}
        }}
      }}).addTo(map);
      overlayMaps[lyr.name] = geoLayer;
    }});

    L.control.layers(baseMaps, overlayMaps, {{ collapsed: true }}).addTo(map);

    // Search bar logic
    const searchInput = document.getElementById("stationSearch");
    searchInput.addEventListener("input", function(e) {{
      const query = e.target.value.trim().toLowerCase();
      if (!query) return;
      for (let key in markerIndex) {{
        if (key.includes(query)) {{
          const m = markerIndex[key];
          map.setView(m.getLatLng(), Math.max(map.getZoom(), 11));
          m.openPopup();
          break;
        }}
      }}
    }});
  </script>
</body>
</html>
"""

    hmap = HydroMap(html_content=html_content, path=output, stations_count=len(stations), bounds=bounds)
    if output:
        hmap.save(output)
    return hmap


map_data = create_map
