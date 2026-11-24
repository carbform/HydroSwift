"""Minimal, publication-grade web dashboard for HydroSwift built with Streamlit.

Design Language:
- Monospace hairline-border aesthetic of carbsat / nisar-ls-viz (IBM Plex Mono).
- Dual Boundary Selection: Hydrological (CWC Basins) vs. Administrative (Indian States).
- Automatic cross-boundary discovery: basin queries discover NWDP state datasets.
- Interactive Leaflet mapping with official shapefiles (India Boundary, CWC Basins, Major Aquifers).
- Native OS folder selection dialog for downloading datasets.
- Dedicated CWC RSMS Reservoir Storage interactive map & analytics.
- Feature-rich hydrological visualizers (Stage-Discharge Hydrographs, H-Q Rating Curves,
  Hyetographs, and Flow Duration Curves).
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure fresh in-memory modules under persistent Streamlit servers
for _mod in [
    "hydroswift.core.boundaries",
    "hydroswift.core.mapping",
    "hydroswift.sources.cwc_rsms.client",
    "hydroswift.sources.cwc_rsms",
]:
    if _mod in sys.modules:
        try:
            importlib.reload(sys.modules[_mod])
        except Exception:
            pass

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import hydroswift as hs

# Standard Hydrological Variables
STANDARD_VARIABLES: List[str] = [
    "All Variables",
    "Water level",
    "Discharge",
    "Rainfall",
    "Groundwater level",
    "Reservoir storage",
    "Water quality",
    "Custom...",
]

from hydroswift.core.boundaries import (
    INDIAN_BASINS,
    INDIAN_STATES,
    canonical_basin,
    get_basin_bounds,
    get_basins_for_state,
    get_states_for_basin,
    load_aquifers_geojson,
    load_basin_geojson,
    load_india_boundary_geojson,
)
from hydroswift.core.mapping import SOURCE_COLORS, create_map
from hydroswift.gui.app_style import CREDITS, sidebar_brand, stylesheet
from hydroswift.gui.desktop import choose_folder


def init_session():
    defaults = {
        "catalog": None,
        "basket": None,
        "run": None,
        "tidy": None,
        "dark": False,
        "active_basin": None,
        "active_state": None,
        "download_dir": "output",
        "rsms_daily": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def main():
    st.set_page_config(
        page_title="HydroSwift · Hydrological Studio",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_session()

    # Dark mode toggle at top right
    top_col, mode_col = st.columns([10, 2])
    dark = mode_col.toggle("Dark mode", value=st.session_state.get("dark", False), key="dark_mode_toggle")
    st.session_state["dark"] = dark
    st.markdown(stylesheet(dark), unsafe_allow_html=True)

    with top_col:
        st.markdown(
            '<div style="font-size: 1.55rem; font-weight: 700; letter-spacing: -0.02em; padding-top: 0.2rem;">'
            '<span>Hydro</span><span style="color: #38bdf8;">Swift</span>'
            '<span style="font-size: 0.8rem; font-weight: 400; color: #6b7a89; margin-left: 0.8rem; '
            'letter-spacing: 0.08em; text-transform: uppercase;">Unified Hydrological Discovery & Visualization</span>'
            '</div>',
            unsafe_allow_html=True,
        )

    # -------------------------------------------------------------------------
    # Sidebar: 1 · Boundary & Scope, 2 · Sources, 3 · Download
    # -------------------------------------------------------------------------
    with st.sidebar:
        st.markdown(sidebar_brand(dark), unsafe_allow_html=True)

        st.header("1 · Boundary & Scope")
        boundary_mode = st.radio(
            "Boundary Type",
            ["Hydrological (Basin)", "Administrative (State)", "All / Custom"],
            index=0,
            horizontal=True,
            help="Hydrological queries search CWC/WRIS river basins and cross-discover constituent NWDP state data.",
        )

        selected_basin = None
        selected_state = None
        custom_loc = None

        if boundary_mode == "Hydrological (Basin)":
            basin_choices = ["All Basins"] + INDIAN_BASINS
            basin_idx = 0
            if st.session_state.get("active_basin") in basin_choices:
                basin_idx = basin_choices.index(st.session_state["active_basin"])
            selected_basin = st.selectbox("River Basin", basin_choices, index=basin_idx)
            if selected_basin and selected_basin != "All Basins":
                st.session_state["active_basin"] = selected_basin
                constituent_states = get_states_for_basin(selected_basin)
                if constituent_states:
                    st.caption(f"📍 **Constituent States**: {', '.join(constituent_states)}")
            else:
                st.session_state["active_basin"] = None

        elif boundary_mode == "Administrative (State)":
            state_choices = ["All States"] + INDIAN_STATES
            state_idx = 0
            if st.session_state.get("active_state") in state_choices:
                state_idx = state_choices.index(st.session_state["active_state"])
            selected_state = st.selectbox("State / Union Territory", state_choices, index=state_idx)
            if selected_state and selected_state != "All States":
                st.session_state["active_state"] = selected_state
                intersecting_basins = get_basins_for_state(selected_state)
                if intersecting_basins:
                    st.caption(f"🌊 **Intersecting Basins**: {', '.join(intersecting_basins)}")
            else:
                st.session_state["active_state"] = None
        else:
            custom_loc = st.text_input("Custom Location / Keyword", placeholder="e.g. Bangalore, Ganga, Godavari")

        # Hydrological Variable Dropdown
        var_choice = st.selectbox(
            "Hydrological Variable",
            STANDARD_VARIABLES,
            index=0,
            help="Filter by physical variable or select 'All Variables' for all observations.",
        )
        if var_choice == "Custom...":
            query_var = st.text_input("Specify Variable Keyword", placeholder="e.g. sediment, evaporation")
        elif var_choice == "All Variables":
            query_var = ""
        else:
            query_var = var_choice

        # Date range
        dcol1, dcol2 = st.columns(2)
        start_year = dcol1.text_input("Start Year", value="2020", placeholder="YYYY")
        end_year = dcol2.text_input("End Year", value="2024", placeholder="YYYY")

        st.header("2 · Data Sources")
        cwc_on = st.checkbox("CWC Flood Forecasting (FFS)", value=True, help="Live telemetry stage & rating-curve discharge")
        wris_on = st.checkbox("India-WRIS OpenAPI 3.0", value=True, help="Official India-WRIS REST API (telemetry & obs)")
        nwdp_on = st.checkbox("NWDP Open Data", value=True, help="India-WRIS CKAN open datasets (rainfall, groundwater)")
        rsms_on = st.checkbox("CWC Reservoirs (RSMS)", value=True, help="National reservoir storage monitoring bulletin")

        sources = []
        if cwc_on:
            sources.append("CWC")
        if wris_on:
            sources.append("WRIS")
        if nwdp_on:
            sources.append("NWDP")
        if rsms_on:
            sources.append("CWC-RSMS")

        # Search Trigger
        if st.button("Search & Discover", type="primary", use_container_width=True):
            if not sources:
                st.error("Please enable at least one data source.")
            else:
                with st.spinner("Discovering stations and catalog items..."):
                    period = (start_year, end_year) if start_year and end_year else None
                    b_filter = selected_basin if selected_basin and selected_basin != "All Basins" else None
                    s_filter = selected_state if selected_state and selected_state != "All States" else None
                    loc_filter = custom_loc if custom_loc else (s_filter or b_filter)

                    try:
                        cat = hs.search(
                            query=query_var or None,
                            location=loc_filter,
                            sources=sources,
                            period=period,
                            basin=b_filter,
                            state=s_filter,
                            cross_boundary=True,
                        )
                        st.session_state["catalog"] = cat
                        if len(cat) > 10:
                            st.session_state["basket"] = cat.head(10).copy()
                            st.info(f"Discovered {len(cat):,} items. Added first 10 to download list (customize in Catalog tab).")
                        else:
                            st.session_state["basket"] = cat.copy()
                            st.success(f"Discovered {len(cat):,} catalog items.")
                        st.session_state["run"] = None
                        st.session_state["tidy"] = None
                    except Exception as e:
                        st.error(f"Discovery error: {e}")

        # Download Section with Native OS Folder Dialog
        st.header("3 · Download")
        basket = st.session_state.get("basket")
        cat_current = st.session_state.get("catalog")
        basket_len = len(basket) if basket is not None else 0
        total_discovered = len(cat_current) if cat_current is not None else 0
        st.caption(f"**Items to download**: {basket_len:,} (of {total_discovered:,} discovered)")

        # Folder picker
        st.markdown("**Download Folder**")
        fcol1, fcol2 = st.columns([3, 1])
        cur_dir = st.session_state.get("download_dir", "output")
        dest_dir = fcol1.text_input("Folder Path", value=cur_dir, label_visibility="collapsed", key="folder_path_input")
        st.session_state["download_dir"] = dest_dir
        if fcol2.button("📁 Browse", help="Open native operating system folder dialog"):
            chosen = choose_folder(start=dest_dir, title="Select HydroSwift Download Folder")
            if chosen:
                st.session_state["download_dir"] = chosen
                st.rerun()

        export_format = st.selectbox("Export Format", ["csv", "parquet", "gpkg", "json"], index=0)

        if st.button(f"⬇️ Download Data ({basket_len})", disabled=(basket_len == 0), type="primary", use_container_width=True):
            prog_bar = st.progress(0.0, text=f"Downloading {basket_len} items...")
            status_text = st.empty()

            import threading
            cancel_ev = threading.Event()

            # Attach Streamlit context to background threads to prevent missing ScriptRunContext
            st_ctx = None
            try:
                from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
                st_ctx = get_script_run_ctx()
            except Exception:
                pass

            completed = 0
            def on_progress(evt):
                nonlocal completed
                if evt.get("event") == "item_done":
                    completed += 1
                    pct = min(1.0, max(0.0, completed / max(basket_len, 1)))
                    t = evt.get("title") or evt.get("id") or "Station"
                    s = evt.get("status") or "done"
                    recs = evt.get("records")
                    r_str = f" ({recs:,} rows)" if recs else ""
                    try:
                        if st_ctx is not None:
                            try:
                                add_script_run_ctx(threading.current_thread(), st_ctx)
                            except Exception:
                                pass
                        prog_bar.progress(pct, text=f"[{completed}/{basket_len}] {t} → {s}{r_str}")
                        status_text.caption(f"Downloaded {completed} of {basket_len} items ({s})")
                    except Exception:
                        pass

            try:
                period = (start_year, end_year) if start_year and end_year else None
                run = hs.fetch(
                    basket,
                    output_dir=st.session_state.get("download_dir", "output"),
                    period=period,
                    format=export_format if export_format in ("csv", "json") else "csv",
                    progress=on_progress,
                    cancel=cancel_ev,
                    workers=4,
                    max_records=50000,
                )
                st.session_state["run"] = run
                tidy = hs.load(run)
                st.session_state["tidy"] = tidy
                prog_bar.progress(1.0, text=f"Completed {len(run):,} downloads.")
                st.success(f"Fetched {len(run):,} files ({len(tidy):,} observation rows) into `{st.session_state.get('download_dir')}`.")
            except Exception as e:
                st.error(f"Download failed: {e}")

        if basket_len > 0:
            if st.button("Clear Selection", use_container_width=True):
                st.session_state["basket"] = None
                st.rerun()

    # -------------------------------------------------------------------------
    # Main View: Metric Pills & Tabs
    # -------------------------------------------------------------------------
    cat = st.session_state.get("catalog")
    tidy = st.session_state.get("tidy")
    active_b = st.session_state.get("active_basin") or "All India"

    # Status Pills Bar
    pills = [
        f'<span class="metric-pill">Boundary: <b>{active_b}</b></span>',
        f'<span class="metric-pill">Discovered: <b>{len(cat) if cat is not None else 0:,}</b></span>',
        f'<span class="metric-pill">Selected: <b>{basket_len:,}</b></span>',
    ]
    if tidy is not None and not tidy.empty:
        pills.append(f'<span class="metric-pill">Records: <b>{len(tidy):,}</b></span>')
        pills.append(f'<span class="metric-pill">Stations: <b>{tidy["station_id"].nunique():,}</b></span>')

    st.markdown(" ".join(pills), unsafe_allow_html=True)
    st.markdown('<div style="height: 0.6rem;"></div>', unsafe_allow_html=True)

    tab_map, tab_catalog, tab_plots, tab_rsms = st.tabs([
        "🗺️ Map Layers",
        "📋 Discovered Catalog",
        "📊 Hydrological Visualizer",
        "🌊 CWC Reservoirs",
    ])

    # -------------------------------------------------------------------------
    # TAB 1: Map Layers with Auto-Zoom & Official Shapefile Overlays
    # -------------------------------------------------------------------------
    with tab_map:
        mcol1, mcol2 = st.columns([3, 1])
        basemap = mcol1.selectbox(
            "Basemap Style",
            ["osm", "topo", "satellite", "opentopo"],
            index=0,
            format_func=lambda x: {
                "osm": "OpenStreetMap",
                "topo": "Esri Topographic",
                "satellite": "Esri World Imagery (Satellite)",
                "opentopo": "OpenTopoMap",
            }[x],
        )
        color_by = mcol2.selectbox("Color Markers By", ["source", "status"], index=0)

        # Official shapefile overlay toggles
        lcol1, lcol2, lcol3 = st.columns(3)
        show_india = lcol1.checkbox("🇮🇳 India National Boundary", value=True, help="Official survey boundary of India")
        show_basins = lcol2.checkbox("🌊 CWC River Basins", value=True, help="Official Central Water Commission basin boundaries")
        show_aquifers = lcol3.checkbox("🪨 Major Aquifers", value=False, help="India-WRIS / CGWB hydrogeological aquifer systems")

        # Prepare official GeoJSON layers
        geojson_layers = []

        if show_india:
            ind_geo = load_india_boundary_geojson()
            if ind_geo.get("features"):
                geojson_layers.append({
                    "name": "India Boundary",
                    "geojson": ind_geo,
                    "interactive": False,
                    "style": {"color": "#374151" if not dark else "#9ca3af", "weight": 2.2, "fillOpacity": 0.0},
                })

        b_name = st.session_state.get("active_basin")
        if show_basins:
            if b_name and b_name != "All Basins":
                b_geo = load_basin_geojson(b_name)
                if b_geo.get("features"):
                    geojson_layers.append({
                        "name": f"Basin: {b_name}",
                        "geojson": b_geo,
                        "style": {"color": "#2563eb", "weight": 2.2, "fillColor": "#3b82f6", "fillOpacity": 0.20},
                    })
            else:
                all_basins = load_basin_geojson("all")
                if all_basins.get("features"):
                    geojson_layers.append({
                        "name": "CWC River Basins",
                        "geojson": all_basins,
                        "style": {"color": "#3b82f6", "weight": 1.4, "fillColor": "#60a5fa", "fillOpacity": 0.06},
                    })

        if show_aquifers:
            aq_geo = load_aquifers_geojson()
            if aq_geo.get("features"):
                geojson_layers.append({
                    "name": "Major Aquifers",
                    "geojson": aq_geo,
                    "style": {"color": "#059669", "weight": 1.2, "fillColor": "#10b981", "fillOpacity": 0.15},
                })

        # Calculate bounding box for auto-zoom
        target_bounds = get_basin_bounds(b_name) if (b_name and b_name != "All Basins") else None

        # Build interactive map
        map_data = cat if cat is not None and not cat.empty else pd.DataFrame()
        try:
            hmap = create_map(
                map_data,
                output=None,
                basemap=basemap,
                color_by=color_by,
                cluster=True,
                bounds=target_bounds,
                geojson_layers=geojson_layers,
                title=f"HydroSwift · {active_b}",
            )
            components.html(hmap.to_html(), height=580, scrolling=False)
        except Exception as e:
            st.info(f"Interactive Map initialized. Discovered stations with coordinates will appear here. (Info: {e})")

    # -------------------------------------------------------------------------
    # TAB 2: Catalog & Download Selection
    # -------------------------------------------------------------------------
    with tab_catalog:
        if cat is None or cat.empty:
            st.info("No catalog items discovered yet. Use **Search & Discover** in the sidebar to search.")
        else:
            st.markdown(f"**Discovered Datasets & Stations ({len(cat):,})**")

            # Quick search filter inside the table
            n_txt = st.text_input("Filter results table", placeholder="Type keywords to filter displayed rows...")
            display_df = cat.copy()
            if n_txt:
                mask = display_df.astype(str).apply(lambda row: row.str.contains(n_txt, case=False).any(), axis=1)
                display_df = display_df[mask]

            cols_to_show = [c for c in ["Source", "Title", "Location", "Variable", "Resolution", "CoverageStart", "CoverageEnd", "Provider"] if c in display_df.columns]
            st.dataframe(display_df[cols_to_show], use_container_width=True, height=420)

            # Simplified Selection Actions
            st.markdown("**Selection Actions**")
            bcol1, bcol2, bcol3, bcol4 = st.columns(4)
            if bcol1.button("⚡ First 5 Stations", use_container_width=True):
                st.session_state["basket"] = display_df.head(5).copy()
                st.success("Download list set to first 5 items.")
                st.rerun()

            if bcol2.button("⚡ First 10 Stations", use_container_width=True):
                st.session_state["basket"] = display_df.head(10).copy()
                st.success("Download list set to first 10 items.")
                st.rerun()

            if bcol3.button(f"➕ Add Filtered ({len(display_df)})", use_container_width=True):
                if st.session_state.get("basket") is None:
                    st.session_state["basket"] = display_df.copy()
                else:
                    st.session_state["basket"] = pd.concat([st.session_state["basket"], display_df]).drop_duplicates(subset=["Source", "ID"])
                st.success(f"Download list updated: {len(st.session_state['basket'])} items.")
                st.rerun()

            if bcol4.button(f"📦 Select All ({len(cat)}) Items", use_container_width=True):
                st.session_state["basket"] = cat.copy()
                st.success(f"Download list set to all {len(cat)} items.")
                st.rerun()

            if st.button("Save Discovered Catalog to JSON"):
                out_p = Path(st.session_state.get("download_dir", "output")) / "catalog.json"
                out_p.parent.mkdir(parents=True, exist_ok=True)
                hs.save_catalog(cat, out_p)
                st.success(f"Saved catalog to `{out_p}`")

    # -------------------------------------------------------------------------
    # TAB 3: Hydrological Visualizer
    # -------------------------------------------------------------------------
    with tab_plots:
        if tidy is None or tidy.empty:
            st.info("Fetch data first using **Download Data** in the sidebar to visualize time series.")
        else:
            pcol1, pcol2 = st.columns([3, 2])
            stations = sorted(tidy["station_name"].dropna().unique().tolist())
            if not stations:
                stations = sorted(tidy["station_id"].dropna().unique().tolist())

            st_pick = pcol1.selectbox("Select Station", stations)
            plot_type = pcol2.selectbox(
                "Plot Type",
                ["Stage & Discharge Hydrograph", "Stage-Discharge Rating Curve (H-Q)", "Rainfall Hyetograph", "Flow Duration Curve (FDC)"],
            )

            st_data = tidy[tidy["station_name"] == st_pick] if st_pick in tidy["station_name"].values else tidy[tidy["station_id"] == st_pick]
            st_data = st_data.sort_values("time").copy()

            try:
                import plotly.graph_objects as go
                from plotly.subplots import make_subplots

                if plot_type == "Stage & Discharge Hydrograph":
                    fig = make_subplots(specs=[[{"secondary_y": True}]])
                    stage = st_data[st_data["variable"].str.lower().str.contains("water|stage|level", na=False)]
                    q = st_data[st_data["variable"].str.lower().str.contains("discharge|flow", na=False)]

                    if not stage.empty:
                        fig.add_trace(
                            go.Scatter(x=stage["time"], y=stage["value"], name="Stage (m)", line=dict(color="#2563eb", width=2)),
                            secondary_y=False,
                        )
                        wl_warn = stage.get("warning_level")
                        if wl_warn is not None and not stage["warning_level"].isna().all():
                            fig.add_hline(y=stage["warning_level"].iloc[0], line=dict(color="#f59e0b", dash="dash"), annotation_text="Warning Level")
                        wl_dang = stage.get("danger_level")
                        if wl_dang is not None and not stage["danger_level"].isna().all():
                            fig.add_hline(y=stage["danger_level"].iloc[0], line=dict(color="#dc2626", dash="dot"), annotation_text="Danger Level")

                    if not q.empty:
                        fig.add_trace(
                            go.Scatter(x=q["time"], y=q["value"], name="Discharge (m³/s)", line=dict(color="#059669", width=2)),
                            secondary_y=True,
                        )

                    fig.update_layout(
                        title=f"{st_pick} · Stage & Discharge Hydrograph",
                        template="plotly_dark" if dark else "plotly_white",
                        font=dict(family="IBM Plex Mono, monospace"),
                        height=480,
                        margin=dict(l=40, r=40, t=50, b=40),
                        hovermode="x unified",
                    )
                    fig.update_yaxes(title_text="Water Level (m)", secondary_y=False)
                    fig.update_yaxes(title_text="Discharge (m³/s)", secondary_y=True)
                    st.plotly_chart(fig, use_container_width=True)

                elif plot_type == "Stage-Discharge Rating Curve (H-Q)":
                    stage = st_data[st_data["variable"].str.lower().str.contains("water|stage|level", na=False)].dropna(subset=["value"])
                    q = st_data[st_data["variable"].str.lower().str.contains("discharge|flow", na=False)].dropna(subset=["value"])
                    merged_hq = pd.merge(stage[["time", "value"]], q[["time", "value"]], on="time", suffixes=("_stage", "_q")).dropna()

                    if len(merged_hq) < 3:
                        st.warning("Insufficient synchronized Stage and Discharge observation pairs to fit a rating curve.")
                    else:
                        h = merged_hq["value_stage"].values
                        q_vals = merged_hq["value_q"].values
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(x=h, y=q_vals, mode="markers", name="Observations", marker=dict(color="#3b82f6", size=7, opacity=0.8)))

                        try:
                            h0 = min(h) - 0.05
                            dh = np.maximum(h - h0, 0.01)
                            log_dh, log_q = np.log(dh), np.log(np.maximum(q_vals, 0.001))
                            p = np.polyfit(log_dh, log_q, 1)
                            b, a = p[0], np.exp(p[1])
                            h_model = np.linspace(min(h), max(h), 100)
                            q_model = a * np.maximum(h_model - h0, 0.01) ** b
                            fig.add_trace(go.Scatter(x=h_model, y=q_model, mode="lines", name=f"Fit: Q = {a:.2f}(h - {h0:.2f})^{b:.2f}", line=dict(color="#ef4444", width=2)))
                        except Exception:
                            pass

                        fig.update_layout(
                            title=f"{st_pick} · Stage-Discharge Rating Curve (H-Q)",
                            xaxis_title="Stage (m)",
                            yaxis_title="Discharge (m³/s)",
                            template="plotly_dark" if dark else "plotly_white",
                            font=dict(family="IBM Plex Mono, monospace"),
                            height=480,
                        )
                        st.plotly_chart(fig, use_container_width=True)

                elif plot_type == "Rainfall Hyetograph":
                    rain = st_data[st_data["variable"].str.lower().str.contains("rain|precip", na=False)].dropna(subset=["value"])
                    if rain.empty:
                        st.warning("No rainfall series found for this station.")
                    else:
                        cum_rain = rain["value"].cumsum()
                        fig = make_subplots(specs=[[{"secondary_y": True}]])
                        fig.add_trace(go.Bar(x=rain["time"], y=rain["value"], name="Precipitation (mm)", marker_color="#38bdf8"), secondary_y=False)
                        fig.add_trace(go.Scatter(x=rain["time"], y=cum_rain, name="Cumulative Mass Curve (mm)", line=dict(color="#f59e0b", width=2)), secondary_y=True)
                        fig.update_yaxes(title_text="Rainfall (mm)", autorange="reversed", secondary_y=False)
                        fig.update_yaxes(title_text="Cumulative (mm)", secondary_y=True)
                        fig.update_layout(
                            title=f"{st_pick} · Rainfall Hyetograph & Mass Curve",
                            template="plotly_dark" if dark else "plotly_white",
                            font=dict(family="IBM Plex Mono, monospace"),
                            height=480,
                        )
                        st.plotly_chart(fig, use_container_width=True)

                elif plot_type == "Flow Duration Curve (FDC)":
                    flow = st_data[st_data["variable"].str.lower().str.contains("discharge|flow", na=False)].dropna(subset=["value"])
                    if flow.empty:
                        st.warning("No discharge series found for this station to construct an FDC.")
                    else:
                        sorted_q = np.sort(flow["value"].values)[::-1]
                        ranks = np.arange(1, len(sorted_q) + 1)
                        ep = (ranks / (len(sorted_q) + 1)) * 100.0
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(x=ep, y=sorted_q, mode="lines", name="Discharge Exceedance", line=dict(color="#059669", width=2)))
                        for p_val, col in [(10, "#ef4444"), (50, "#3b82f6"), (90, "#f59e0b")]:
                            idx = int(np.argmin(np.abs(ep - p_val)))
                            fig.add_trace(go.Scatter(x=[p_val], y=[sorted_q[idx]], mode="markers+text", name=f"Q{p_val} ({sorted_q[idx]:.1f})", text=[f"Q{p_val}"], textposition="top right", marker=dict(color=col, size=8)))
                        fig.update_layout(
                            title=f"{st_pick} · Flow Duration Curve (FDC)",
                            xaxis_title="Exceedance Probability (%)",
                            yaxis_title="Discharge (m³/s)",
                            yaxis_type="log",
                            template="plotly_dark" if dark else "plotly_white",
                            font=dict(family="IBM Plex Mono, monospace"),
                            height=480,
                        )
                        st.plotly_chart(fig, use_container_width=True)

            except Exception as e:
                st.error(f"Plotting error: {e}")

    # -------------------------------------------------------------------------
    # TAB 4: Dedicated CWC RSMS Reservoir Tracking & Map Visualizer
    # -------------------------------------------------------------------------
    with tab_rsms:
        st.markdown("### 🌊 National Reservoir Storage Bulletin (CWC RSMS)")
        st.caption("Live storage levels, full reservoir levels (FRL), and current capacity for ~180 major Indian reservoirs.")

        r_btn_col, r_refresh_col = st.columns([3, 1])
        fetch_clicked = r_btn_col.button("🌊 Fetch & Visualize Live Reservoirs on Map", type="primary", use_container_width=True)
        if r_refresh_col.button("🔄 Refresh Reservoir Status", use_container_width=True):
            st.session_state["rsms_daily"] = None
            fetch_clicked = True

        if fetch_clicked or st.session_state.get("rsms_daily") is not None:
            if st.session_state.get("rsms_daily") is None:
                with st.spinner("Connecting to CWC RSMS portal & retrieving reservoir levels..."):
                    try:
                        rsms_df = hs.rsms.daily()
                        st.session_state["rsms_daily"] = rsms_df
                        st.success(f"Successfully retrieved status for {len(rsms_df)} monitored reservoirs.")
                    except Exception as e:
                        st.error(f"RSMS bulletin retrieval error: {e}")

            rsms_data = st.session_state.get("rsms_daily")
            if rsms_data is not None and not rsms_data.empty:
                df_calc = rsms_data.copy()
                if "storage_bcm" not in df_calc.columns:
                    df_calc["storage_bcm"] = np.nan
                valid_storage = df_calc.dropna(subset=["storage_bcm"])
                total_cap = float(df_calc["live_cap_bcm"].sum())
                total_cur = float(valid_storage["storage_bcm"].sum()) if not valid_storage.empty else 0.0
                nat_pct = (total_cur / total_cap * 100.0) if total_cap > 0 else 0.0

                df_calc["storage_pct"] = np.where(
                    df_calc["live_cap_bcm"] > 0,
                    (df_calc["storage_bcm"] / df_calc["live_cap_bcm"]) * 100.0,
                    np.nan,
                )
                critical_count = len(df_calc[df_calc["storage_pct"] < 40.0])

                # Metric cards
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Monitored Reservoirs", f"{len(df_calc)}")
                m2.metric("Total Live Capacity", f"{total_cap:.1f} BCM")
                m3.metric("Live Storage Monitored", f"{total_cur:.1f} BCM", f"{nat_pct:.1f}%")
                m4.metric("Critical Reservoirs (<40%)", f"{critical_count}")

                st.markdown("#### 🗺️ Interactive National Reservoir Storage Map")
                res_geojson_layers = []
                ind_geo = load_india_boundary_geojson()
                if ind_geo.get("features"):
                    res_geojson_layers.append({
                        "name": "India Boundary",
                        "geojson": ind_geo,
                        "interactive": False,
                        "style": {"color": "#4b5563" if not dark else "#9ca3af", "weight": 2.0, "fillOpacity": 0.0},
                    })

                res_bounds = [[8.0, 68.0], [36.0, 96.0]]
                res_map = create_map(
                    df_calc,
                    output=None,
                    basemap="osm",
                    color_by="status",
                    cluster=False,
                    bounds=res_bounds,
                    geojson_layers=res_geojson_layers,
                    title="CWC RSMS National Reservoir Storage",
                )
                components.html(res_map.to_html(), height=560, scrolling=False)

                st.markdown("#### 📋 Monitored Reservoirs Table")
                search_res = st.text_input("Filter reservoirs table", placeholder="Type reservoir name or ID...")
                view_df = df_calc.copy()
                if search_res:
                    view_df = view_df[view_df.astype(str).apply(lambda row: row.str.contains(search_res, case=False).any(), axis=1)]

                disp_cols = [c for c in ["reservoir_unique_id", "reservoir_name", "storage_bcm", "live_cap_bcm", "gross_cap_bcm", "storage_pct", "frl_meter", "entry_date"] if c in view_df.columns]
                st.dataframe(view_df[disp_cols], use_container_width=True, height=350)

                csv_bytes = view_df.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Download Reservoirs CSV", data=csv_bytes, file_name="cwc_rsms_reservoirs.csv", mime="text/csv")
        else:
            st.info("Click **🌊 Fetch & Visualize Live Reservoirs on Map** above to retrieve real-time reservoir storage status and view national capacity pins on the map.")

    # Footer
    st.markdown(CREDITS, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
