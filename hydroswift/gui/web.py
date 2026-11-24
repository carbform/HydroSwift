"""Modern, responsive web dashboard for HydroSwift built with Streamlit.

Features:
- Unified Find -> Review -> Get -> Use workflow
- Interactive Leaflet map with layer controls, marker clustering, and flood alerts
- Specialized hydrological visualizers:
  * Dual-axis Stage-Discharge hydrographs
  * Empirical hydraulic rating curves (H-Q)
  * Hyetographs and mass curves
  * Flow duration curves (FDCs)
- Live CWC RSMS reservoir tracking
- One-click exports to Parquet, GeoPackage (.gpkg), and CSV
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import hydroswift as hs
from hydroswift.core.mapping import create_map, SOURCE_COLORS


def set_custom_theme():
    st.set_page_config(
        page_title="HydroSwift ⚡ Hydrological Platform",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        .main-header {
            font-size: 26px;
            font-weight: 800;
            color: #1e293b;
            margin-bottom: 2px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .sub-header {
            font-size: 13px;
            color: #64748b;
            margin-bottom: 16px;
        }
        .metric-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 12px 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        .source-pill {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            color: white;
            margin-right: 4px;
        }
        .alert-box {
            padding: 10px 14px;
            border-radius: 6px;
            margin-bottom: 12px;
            font-size: 13px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_session():
    if "catalog" not in st.session_state:
        st.session_state["catalog"] = None
    if "basket" not in st.session_state:
        st.session_state["basket"] = None
    if "run" not in st.session_state:
        st.session_state["run"] = None
    if "tidy" not in st.session_state:
        st.session_state["tidy"] = None


def render_sidebar():
    st.sidebar.markdown("### ⚡ **HydroSwift**")
    st.sidebar.caption("Unified Workflows for Indian Hydrological Data")
    st.sidebar.markdown("---")

    st.sidebar.markdown("#### 1. Data Sources")
    cwc_on = st.sidebar.checkbox("CWC Flood Forecasting", value=True, help="Real-time river stage & rating-curve discharge")
    wris_on = st.sidebar.checkbox("India-WRIS OpenAPI 3.0", value=True, help="Official REST API for 14 physical variables")
    nwdp_on = st.sidebar.checkbox("NWDP Open Data", value=True, help="CKAN portal historical bulk archives")
    rsms_on = st.sidebar.checkbox("CWC RSMS Reservoirs", value=False, help="Daily storage bulletin snapshot for 180+ major dams")

    sources = []
    if cwc_on: sources.append("CWC")
    if wris_on: sources.append("WRIS")
    if nwdp_on: sources.append("NWDP")
    if rsms_on: sources.append("CWC-RSMS")

    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 2. Search Criteria")

    var_options = [
        "water_level", "discharge", "rainfall", "groundwater_level",
        "reservoir_storage", "temperature", "humidity", "wind_speed", "solar_radiation"
    ]
    query = st.sidebar.selectbox("Variable / Parameter", options=var_options, index=0)
    location = st.sidebar.text_input("Location / River Basin", value="Krishna", help="e.g. Krishna, Godavari, Ganga, Karnataka, Kadapa")

    col_s, col_e = st.sidebar.columns(2)
    start_date = col_s.date_input("Start Date", value=pd.to_datetime("2024-06-01"))
    end_date = col_e.date_input("End Date", value=pd.to_datetime("2024-06-15"))

    search_clicked = st.sidebar.button("🔍 Search Datasets", use_container_width=True, type="primary")

    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 3. Output Options")
    out_format = st.sidebar.selectbox("File Format", ["csv", "parquet", "xlsx", "json"], index=0)
    out_dir = st.sidebar.text_input("Output Directory", value="output")

    if search_clicked:
        if not sources:
            st.sidebar.error("Please select at least one data source.")
        else:
            with st.spinner("Searching multi-source catalogs..."):
                try:
                    cat = hs.search(
                        query=query,
                        location=location.strip() if location else None,
                        sources=sources,
                        period=(str(start_date), str(end_date)),
                    )
                    st.session_state["catalog"] = cat
                    st.sidebar.success(f"Found {len(cat)} items across {len(sources)} sources.")
                except Exception as e:
                    st.sidebar.error(f"Search failed: {e}")

    return {
        "sources": sources,
        "query": query,
        "location": location,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "format": out_format,
        "out_dir": out_dir,
    }


def render_map_view(df: pd.DataFrame, title: str):
    col_map_opts1, col_map_opts2, col_map_opts3 = st.columns([2, 2, 2])
    basemap = col_map_opts1.selectbox("Basemap Style", ["osm", "carto-light", "carto-dark", "satellite"], index=1)
    color_by = col_map_opts2.selectbox("Color Markers By", ["source", "status"], index=0)
    cluster = col_map_opts3.checkbox("Enable Marker Clustering", value=True)

    try:
        hmap = create_map(
            df,
            output=None,
            basemap=basemap,
            color_by=color_by,
            cluster=cluster,
            title=title,
        )
        components.html(hmap.to_html(), height=620, scrolling=False)
    except Exception as e:
        st.warning(f"Could not render map: {e}")


def render_visualizer():
    st.markdown("### 📊 Hydrological Time-Series & Hydraulic Visualizer")

    # Sample demo data if user has not downloaded yet
    if st.session_state["tidy"] is None or st.session_state["tidy"].empty:
        st.info("💡 No fetched dataset loaded in current session. Generating a live hydrograph preview...")
        times = pd.date_range("2024-06-01", periods=120, freq="6h")
        t_arr = np.linspace(0, 4 * np.pi, 120)
        h = 560.0 + 4.5 * np.sin(t_arr) + np.random.normal(0, 0.2, 120)
        q = 35.0 * np.maximum(0, h - 558.0)**1.75
        rain = np.maximum(0, np.random.exponential(2.5, 120) - 2.0)

        demo_df = pd.DataFrame({
            "time": list(times) * 3,
            "value": list(h) + list(q) + list(rain),
            "variable": ["water_level"] * 120 + ["discharge"] * 120 + ["rainfall"] * 120,
            "unit": ["m"] * 120 + ["m3/s"] * 120 + ["mm"] * 120,
            "station_id": ["001-CDBNG"] * 360,
            "station_name": ["Shimoga"] * 360,
            "source": ["CWC"] * 360,
            "lat": [13.9269] * 360,
            "lon": [75.5850] * 360,
            "method": ["observed"] * 120 + ["rc_guardian_2024"] * 120 + ["observed"] * 120,
            "flag": [None] * 360,
            "file": ["preview.csv"] * 360,
        })
        active_df = demo_df
    else:
        active_df = st.session_state["tidy"]

    col_v1, col_v2 = st.columns([2, 4])
    plot_kind = col_v1.radio(
        "Hydrological Visualization Kind",
        options=[
            "Dual-Axis Hydrograph (Stage & Discharge)",
            "Stage-Discharge Rating Curve (H-Q)",
            "Precipitation Hyetograph & Mass Curve",
            "Flow Duration Curve (FDC)",
            "Time Series View",
        ],
        index=0,
    )

    stations = active_df["station_name"].dropna().unique().tolist()
    sel_station = col_v1.selectbox("Station", stations, index=0) if stations else None

    sub = active_df if not sel_station else active_df[active_df["station_name"] == sel_station]

    import plotly.graph_objects as go

    if "Dual-Axis Hydrograph" in plot_kind:
        gw = sub[sub["variable"] == "water_level"].sort_values("time")
        gq = sub[sub["variable"] == "discharge"].sort_values("time")

        fig = go.Figure()
        if not gw.empty:
            fig.add_trace(go.Scatter(
                x=pd.to_datetime(gw["time"]), y=pd.to_numeric(gw["value"]),
                name="River Stage (m)", line=dict(color="#1d4ed8", width=2),
                yaxis="y1"
            ))
            # Threshold lines
            fig.add_hline(y=566.7, line_dash="dash", line_color="#f59e0b", annotation_text="Warning Level (566.7m)")
            fig.add_hline(y=567.25, line_dash="dash", line_color="#ef4444", annotation_text="Danger Level (567.25m)")

        if not gq.empty:
            fig.add_trace(go.Scatter(
                x=pd.to_datetime(gq["time"]), y=pd.to_numeric(gq["value"]),
                name="Discharge (m³/s)", line=dict(color="#059669", width=2),
                yaxis="y2"
            ))

        fig.update_layout(
            title=f"{sel_station} - Dual-Axis River Stage & Discharge Hydrograph",
            xaxis=dict(title="Observation Time"),
            yaxis=dict(title="Stage [m]", titlefont=dict(color="#1d4ed8"), tickfont=dict(color="#1d4ed8")),
            yaxis2=dict(title="Discharge [m³/s]", titlefont=dict(color="#059669"), tickfont=dict(color="#059669"), overlaying="y", side="right"),
            template="plotly_white",
            hovermode="x unified",
            height=500,
        )
        col_v2.plotly_chart(fig, use_container_width=True)

    elif "Rating Curve" in plot_kind:
        gw = sub[sub["variable"] == "water_level"].sort_values("time")
        gq = sub[sub["variable"] == "discharge"].sort_values("time")
        if gw.empty or gq.empty:
            col_v2.warning("Selected station does not have concurrent water level and discharge.")
        else:
            merged = pd.merge_asof(
                gw[["time", "value"]].rename(columns={"value": "h"}),
                gq[["time", "value"]].rename(columns={"value": "q"}),
                on="time", direction="nearest"
            ).dropna()

            h_vals = pd.to_numeric(merged["h"]).values
            q_vals = pd.to_numeric(merged["q"]).values
            poly = np.polyfit(h_vals, q_vals, 2)
            h_line = np.linspace(h_vals.min(), h_vals.max(), 100)
            q_line = np.polyval(poly, h_line)

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=h_vals, y=q_vals, mode="markers", name="Observed H-Q Pairs", marker=dict(color="#2563eb", size=8)))
            fig.add_trace(go.Scatter(x=h_line, y=q_line, mode="lines", name="Calibrated Rating Curve", line=dict(color="#dc2626", width=2.5)))

            fig.update_layout(
                title=f"{sel_station} - Stage-Discharge Rating Curve (H-Q)<br><sup>Fit: Q = {poly[0]:.2f}H² + {poly[1]:.2f}H + {poly[2]:.2f}</sup>",
                xaxis_title="River Stage / Water Level [m]",
                yaxis_title="Discharge [m³/s]",
                template="plotly_white",
                height=500,
            )
            col_v2.plotly_chart(fig, use_container_width=True)

    elif "Hyetograph" in plot_kind:
        gr = sub[sub["variable"] == "rainfall"].sort_values("time")
        if gr.empty:
            col_v2.warning("No rainfall data for selected station.")
        else:
            t = pd.to_datetime(gr["time"])
            v = pd.to_numeric(gr["value"]).fillna(0)
            cum = v.cumsum()

            fig = go.Figure()
            fig.add_trace(go.Bar(x=t, y=v, name="Rainfall (mm)", marker_color="#0284c7", yaxis="y1"))
            fig.add_trace(go.Scatter(x=t, y=cum, name="Cumulative Mass Curve (mm)", line=dict(color="#0f172a", width=2, dash="dash"), yaxis="y2"))

            fig.update_layout(
                title=f"{sel_station} - Precipitation Hyetograph & Mass Curve",
                xaxis_title="Time",
                yaxis=dict(title="Precipitation [mm]", titlefont=dict(color="#0284c7")),
                yaxis2=dict(title="Cumulative [mm]", titlefont=dict(color="#0f172a"), overlaying="y", side="right"),
                template="plotly_white",
                height=500,
            )
            col_v2.plotly_chart(fig, use_container_width=True)

    elif "Flow Duration Curve" in plot_kind:
        gq = sub[sub["variable"] == "discharge"].sort_values("time")
        if gq.empty:
            col_v2.warning("No discharge data for selected station.")
        else:
            vals = pd.to_numeric(gq["value"]).dropna().sort_values(ascending=False).values
            n = len(vals)
            p = (np.arange(1, n + 1) / (n + 1)) * 100.0

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=p, y=vals, mode="lines", name="FDC", line=dict(color="#059669", width=2.5)))
            fig.update_yaxes(type="log", title="Discharge [m³/s] (log scale)")
            fig.update_xaxes(title="Exceedance Probability [%]")
            fig.update_layout(title=f"{sel_station} - Flow Duration Curve (FDC)", template="plotly_white", height=500)
            col_v2.plotly_chart(fig, use_container_width=True)

    else:
        var = col_v1.selectbox("Variable", active_df["variable"].unique().tolist())
        sub_var = sub[sub["variable"] == var].sort_values("time")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=pd.to_datetime(sub_var["time"]), y=pd.to_numeric(sub_var["value"]), mode="lines", name=var, line=dict(color="#2563eb", width=1.5)))
        fig.update_layout(title=f"{sel_station} - {var.replace('_', ' ').title()}", template="plotly_white", height=500)
        col_v2.plotly_chart(fig, use_container_width=True)


def main():
    set_custom_theme()
    init_session()

    params = render_sidebar()

    st.markdown('<div class="main-header">⚡ HydroSwift Hydrological Platform</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Automated Discovery • Tidy Standardization • Hydrological Analytics • Geospatial Mapping</div>', unsafe_allow_html=True)

    cat = st.session_state["catalog"]

    # Top KPI Metrics if search has been executed
    if cat is not None and not cat.empty:
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Discovered Stations", f"{len(cat):,}")
        sources_found = cat["Source"].unique().tolist()
        col_m2.metric("Active Sources", f"{len(sources_found)} ({', '.join(sources_found)})")
        coords_n = int(cat[["lat", "lon"]].notna().all(axis=1).sum())
        col_m3.metric("Mapped Geometries", f"{coords_n:,} / {len(cat):,}")
        prov = cat.attrs.get("source_status", [])
        partial_n = sum(1 for s in prov if not s.get("ok", True) or not s.get("complete", True))
        col_m4.metric("Source Health", "Optimal" if partial_n == 0 else f"{partial_n} Caveats")

    # Primary View Tabs
    tab_map, tab_table, tab_viz, tab_rsms = st.tabs([
        "🗺️ Interactive Map Layers",
        "📋 Catalog & Basket",
        "📊 Hydrological Visualizer",
        "🌊 CWC Reservoirs (RSMS)"
    ])

    with tab_map:
        if cat is not None and not cat.empty:
            render_map_view(cat, title=f"HydroSwift Stations: {params['location'] or 'All India'}")
        else:
            st.info("Search for stations in the left sidebar to generate the interactive geospatial map.")
            try:
                from hydroswift.sources.cwc_ffs import load_station_table
                preview_df = load_station_table(refresh=False).head(35)
                st.caption("Displaying default national river gauging station network:")
                render_map_view(preview_df, title="National Hydrological Monitoring Network")
            except Exception:
                pass

    with tab_table:
        if cat is not None and not cat.empty:
            st.markdown("#### Discovered Station Records")
            cols = ["Source", "Title", "Location", "Variable", "Resolution", "ID", "lat", "lon", "Provider"]
            present_cols = [c for c in cols if c in cat.columns]
            st.dataframe(cat[present_cols], use_container_width=True, height=360)

            col_act1, col_act2, col_act3 = st.columns([2, 2, 2])
            if col_act1.button("🧺 Add All to Basket"):
                st.session_state["basket"] = cat.copy()
                st.success(f"Added {len(cat)} items to download basket.")

            if st.session_state["basket"] is not None:
                basket = st.session_state["basket"]
                st.markdown(f"**Current Basket: {len(basket)} items**")
                if col_act2.button("⬇️ Fetch Basket Data"):
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    def progress_cb(ev):
                        idx = ev.get("index", 0)
                        tot = ev.get("total", len(basket))
                        if tot > 0:
                            progress_bar.progress(min(1.0, idx / tot))
                        status_text.text(f"Fetching: {ev.get('title', '')} ({idx}/{tot})")

                    with st.spinner("Downloading observations from data sources..."):
                        res = hs.fetch(
                            basket,
                            output_dir=params["out_dir"],
                            period=(params["start_date"], params["end_date"]),
                            format=params["format"],
                            progress=progress_cb,
                        )
                        st.session_state["run"] = res
                        st.session_state["tidy"] = hs.load(res)
                        st.success(f"Successfully downloaded {len(res)} items to '{params['out_dir']}'.")
        else:
            st.info("Execute a search using the sidebar to browse matching stations.")

    with tab_viz:
        render_visualizer()

    with tab_rsms:
        st.markdown("### 🌊 Real-Time National Reservoir Storage Tracker")
        st.caption("CWC Reservoir Storage Monitoring System (RSMS): 180+ Major National Dams")
        if st.button("Fetch Today's RSMS Daily Storage Bulletin"):
            with st.spinner("Querying CWC RSMS portal..."):
                try:
                    rsms_df = hs.rsms.daily()
                    if rsms_df is not None and not rsms_df.empty:
                        st.dataframe(rsms_df, use_container_width=True)
                        st.session_state["rsms_daily"] = rsms_df
                    else:
                        st.warning("No reservoir data returned from portal.")
                except Exception as e:
                    st.error(f"RSMS query failed: {e}")


if __name__ == "__main__":
    main()
