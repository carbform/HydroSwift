"""Minimal, publication-grade web dashboard for HydroSwift built with Streamlit.

Design Language:
- Monospace hairline-border aesthetic of carbsat / nisar-ls-viz (IBM Plex Mono).
- Top-level Decoupled Navigation: Hydrological Studio vs. Dedicated CWC Reservoirs (RSMS).
- Download bar with native OS directory chooser; background download with cancel and retry.
- Per-station selection and per-source search status.
- Dual Boundary Selection: Hydrological (CWC Basins) vs. Administrative (Indian States).
- Interactive Leaflet mapping with official shapefiles (India Boundary, CWC Basins, Major Aquifers).
- Isolated map panes preventing polygon click-shadowing over station/reservoir pins.
"""

from __future__ import annotations

import importlib
import os
import sys
import time
import warnings
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure fresh in-memory modules under persistent Streamlit servers
for _mod in [
    "hydroswift.core.boundaries",
    "hydroswift.core.mapping",
    "hydroswift.core.tidy",
    "hydroswift.core.analysis",
    "hydroswift.gui.plotdata",
    "hydroswift.gui.visualize",
    "hydroswift.gui.console",
    "hydroswift.gui.dock",
    "hydroswift.gui.model",
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
from hydroswift.gui.app_style import CREDITS, get_credits_html, sidebar_brand, stylesheet
from hydroswift.gui.desktop import choose_folder
from hydroswift.gui import dock
from hydroswift.gui.console import Console, record, row_spec, search_command
from hydroswift.gui.jobs import DownloadJob
from hydroswift.gui.model import (
    REVIEW_COLUMNS,
    combine_runs,
    needs_retry,
    pick_rows,
    review_value,
    row_keys,
    source_status_lines,
    summarise_fetch,
    text_filter,
    update_manifest,
)
from hydroswift.gui.plotdata import export_tidy


# widget values that must survive runs which do not draw the widget
KEEP_KEYS = ("main_view", "filter_text", "advanced", "boundary_mode", "sb_basin", "sb_state", "sb_custom",
             "sb_variable", "sb_custom_var", "sb_start", "sb_end", "src_cwc", "src_wris", "src_nwdp")


def init_session():
    defaults = {
        "catalog": None,
        "selected": set(),
        "editor_base": None,
        "editor_version": 0,
        "job": None,
        "last_download": None,
        "estimate": None,
        "run": None,
        "tidy": None,
        "dark": False,
        "active_basin": None,
        "active_state": None,
        "download_dir": "output",
        "rsms_daily": None,
        "active_view": "Hydrology Data",
        "boundary_mode": "Hydrological (Basin)",
        "console_history": [],
        "sb_basin": "All Basins",
        "sb_state": "All States",
        "sb_variable": "All Variables",
        "sb_start": 2020,
        "sb_end": 2024,
        "src_cwc": True,
        "src_wris": True,
        "src_nwdp": True,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def render_rsms_view(dark: bool):
    """Dedicated CWC National Reservoirs module, completely decoupled from station discovery."""
    st.markdown("## National Reservoirs (RSMS Live Storage)")
    st.caption("Central Water Commission Real-Time Reservoir Storage Monitoring System for ~180 major Indian reservoirs.")

    # Top Action Bar for Reservoirs
    r_top1, r_top2, r_top3 = st.columns([3, 1, 2])
    fetch_rsms = r_top1.button("Fetch Live Status", type="primary", use_container_width=True)
    refresh_rsms = r_top2.button("Refresh", use_container_width=True)

    fetch_rsms = fetch_rsms or st.session_state.pop("rsms_fetch", False)

    if refresh_rsms:
        st.session_state["rsms_daily"] = None
        fetch_rsms = True

    if fetch_rsms or st.session_state.get("rsms_daily") is not None:
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

            # Export button in top bar
            csv_bytes = df_calc.to_csv(index=False).encode("utf-8")
            r_top3.download_button("Export CSV", data=csv_bytes, file_name="cwc_rsms_reservoirs.csv", mime="text/csv", use_container_width=True)

            # Metric Cards
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Monitored Reservoirs", f"{len(df_calc)}")
            m2.metric("Total Live Capacity", f"{total_cap:.1f} BCM")
            m3.metric("Live Storage Monitored", f"{total_cur:.1f} BCM", f"{nat_pct:.1f}%")
            m4.metric("Critical Reservoirs (<40%)", f"{critical_count}")

            st.markdown("### National Reservoir Storage Map")
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
            components.html(res_map.to_html(), height=580, scrolling=False)

            st.markdown("### Monitored Reservoirs Table")
            search_res = st.text_input("Filter reservoirs table", placeholder="Type reservoir name or ID...")
            view_df = df_calc.copy()
            if search_res:
                view_df = view_df[view_df.astype(str).apply(lambda row: row.str.contains(search_res, case=False).any(), axis=1)]

            disp_cols = [c for c in ["reservoir_unique_id", "reservoir_name", "storage_bcm", "live_cap_bcm", "gross_cap_bcm", "storage_pct", "frl_meter", "entry_date"] if c in view_df.columns]
            st.dataframe(view_df[disp_cols], use_container_width=True, height=380)
    else:
        st.info("Click **Fetch Live Status** above to load and display live capacity pins for ~180 reservoirs across India.")


def start_download(table: pd.DataFrame, *, period, output_dir: str, export_format: str, previous=None,
                   rc_discharge: bool = True, overwrite: bool = False):
    """Start the background download; the page then polls it (see render_job)."""
    job = DownloadJob(table, fetch=hs.fetch, output_dir=output_dir, period=period, format="csv",
                      workers=4, max_records=50000, rc_discharge=rc_discharge, overwrite=overwrite)
    job.output_dir, job.export_format, job.previous, job.period = output_dir, export_format, previous, period
    st.session_state["job"] = job.start()
    st.session_state["last_download"] = None
    st.session_state["editor_base"] = None  # the table is not drawn while downloading


def run_console_command() -> None:
    """Form callback: runs before the page is drawn, so the page shows the result."""
    line = st.session_state.get("console_input", "")
    Console(st.session_state, search=hs.search, download=start_download).run(line)


def finish_download(job) -> None:
    """Turn a finished job into data and a summary that survives reruns."""
    st.session_state["job"] = None
    report = {"problems": None, "messages": [], "table": job.table, "period": job.period,
              "output_dir": job.output_dir, "export_format": job.export_format}
    st.session_state["last_download"] = report
    if job.error or job.result is None:
        report["messages"].append(("error", f"Download failed: {job.error}"))
        report["run"] = job.previous
        return
    run = combine_runs(job.previous, job.result)
    report["run"] = run
    if job.previous is not None and job.result.attrs.get("manifest"):
        try:
            update_manifest(job.result.attrs["manifest"], run)
        except Exception as e:
            report["messages"].append(("warning", f"The manifest lists only the retried items: {e}"))
    st.session_state["run"] = run
    problems = run[needs_retry(run)]
    report["problems"] = problems if not problems.empty else None
    report["messages"].append(("success" if problems.empty else "warning",
                               f"{summarise_fetch(run)}. Folder: `{job.output_dir}`"))
    try:
        tidy = hs.load(run)
    except Exception as e:
        report["messages"].append(("error", f"Files were saved but could not be read back: {e}"))
        return
    if tidy.empty and st.session_state.get("tidy") is not None and not st.session_state["tidy"].empty:
        # a cancelled or empty download must not take away data already on screen
        report["messages"].append(("info", "This download added no data; Visualize still shows the earlier one."))
        return
    st.session_state["tidy"] = tidy
    st.session_state["tidy_period"] = job.period
    if job.export_format == "csv":
        return
    if tidy.empty:
        report["messages"].append(("warning", f"No data to write as {job.export_format}."))
        return
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", UserWarning)
            out_path = export_tidy(tidy, job.output_dir, job.export_format)
        report["messages"].append(("success", f"Combined {job.export_format} file: `{out_path}`"))
        report["messages"] += [("warning", str(w.message)) for w in caught if issubclass(w.category, UserWarning)]
    except Exception as e:
        report["messages"].append(("error", f"Could not write the {job.export_format} file (CSV files were saved): {e}"))


def render_job(job) -> None:
    snap = job.snapshot()
    st.progress(min(1.0, snap["done"] / max(snap["total"], 1)),
                text=f"{snap['done']} of {snap['total']} items finished · {snap['seconds']} s · {snap['latest']}")
    for line in snap["pages"][:4]:
        st.caption(line)
    if job.cancelling:
        st.info("Cancelling. Items already being downloaded may finish first.")
    else:
        st.button("Cancel download", on_click=job.cancel)


def render_last_download(report) -> None:
    for level, text in report["messages"]:
        getattr(st, level)(text)
    problems = report["problems"]
    if problems is not None:
        st.dataframe(problems[["source", "title", "status", "error"]], use_container_width=True, hide_index=True)
        def retry():
            keys = set(zip(problems["source"].astype(str), problems["id"].astype(str)))
            start_download(pick_rows(report["table"], keys), period=report["period"],
                           output_dir=report["output_dir"], export_format=report["export_format"],
                           previous=report["run"])
            # keep the full request so a second retry can still find every row
            st.session_state["job"].full_table = report["table"]

        st.button(f"Retry {len(problems)} failed or incomplete", on_click=retry)


def render_source_status(cat: pd.DataFrame, advanced: bool) -> None:
    lines = source_status_lines(cat)
    icons = {"ok": "✓", "partial": "!", "failed": "✗"}
    st.markdown(" ".join(f'<span class="metric-pill">{icons[x["level"]]} {x["text"]}</span>' for x in lines),
                unsafe_allow_html=True)
    if any(x["level"] != "ok" for x in lines):
        where = "the Source log below" if advanced else "Advanced mode (Source log)"
        st.warning("Some sources failed or returned only part of their listing, so these results are "
                   f"incomplete. Details are in {where}.")


def render_selection(cat: pd.DataFrame) -> None:
    """Checkbox table. Only the ticked (Source, ID) keys are read back from it."""
    f1, f2 = st.columns([3, 2])
    words = f1.text_input("Filter", placeholder="Words in title, place or variable", key="filter_text")
    source_names = sorted(cat["Source"].unique())
    sources_key = f"filter_sources_{'_'.join(source_names)}"
    if sources_key not in st.session_state:  # not default=: the value is also restored from state
        st.session_state[sources_key] = source_names
    wanted = f2.multiselect("Sources shown", source_names, key=sources_key)
    shown = cat[text_filter(cat, words) & cat["Source"].isin(wanted)]
    keys = row_keys(shown)
    selected = st.session_state["selected"]

    def choose(new_selection):
        st.session_state["selected"], st.session_state["editor_base"] = new_selection, None

    b1, b2, b3 = st.columns(3)
    b1.button(f"Select all shown ({len(shown)})", use_container_width=True, disabled=shown.empty,
              on_click=choose, args=(selected | set(keys),))
    b2.button("Unselect shown", use_container_width=True, disabled=shown.empty,
              on_click=choose, args=(selected - set(keys),))
    # never disabled: this row is drawn before the ticks of this run are read
    b3.button("Clear selection", use_container_width=True, on_click=choose, args=(set(),))
    if shown.empty:
        st.info("No rows match this filter.")
        return

    # The editor's input stays fixed between ticks; it is rebuilt (new key) only when rows change.
    base = st.session_state["editor_base"]
    if (base is None or base["keys"] != keys
            or f"editor_{st.session_state['editor_version']}" not in st.session_state):
        st.session_state["editor_version"] += 1
        base = st.session_state["editor_base"] = {"keys": keys, "ticked": [k in selected for k in keys]}

    columns = [(c, h) for c, h in REVIEW_COLUMNS if c != "EstRecords"]
    view = pd.DataFrame({header: [review_value(shown, i, col) for i in shown.index] for col, header in columns})
    view.insert(0, "Select", base["ticked"])
    edited = st.data_editor(view, key=f"editor_{st.session_state['editor_version']}", hide_index=True,
                            disabled=[h for _, h in columns], use_container_width=True, height=420,
                            column_config={"Select": st.column_config.CheckboxColumn("Select", width="small")})
    ticked = {k for k, on in zip(keys, edited["Select"]) if on}
    st.session_state["selected"] = (selected - set(keys)) | ticked


def main():
    st.set_page_config(
        page_title="HydroSwift · Hydrological Studio",
        layout="wide",
        initial_sidebar_state="auto",
    )
    init_session()
    # Streamlit forgets a widget's value on any run that does not draw it (another view, or a
    # download in progress). Re-assigning keeps these.
    for key in list(st.session_state):
        if key in KEEP_KEYS + dock.STATE_KEYS or str(key).startswith(("filter_sources_", "viz_")):
            st.session_state[key] = st.session_state[key]

    # Dark mode toggle state
    if "dark" not in st.session_state:
        st.session_state["dark"] = False

    # Top Header Bar: Brand + View Switcher + Help + About + Dark Mode Toggle
    head_col, help_col, about_col, dark_col, mode_col = st.columns([4.6, 1.2, 1.3, 1.8, 1.8])
    with head_col:
        st.markdown(
            '<div style="font-size: 1.55rem; font-weight: 700; letter-spacing: -0.02em; padding-top: 0.15rem;">'
            '<span>Hydro</span><span style="color: #2563eb;">Swift</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        # Module Switcher: Hydrology Data vs. Reservoir Status
        view_modes = ["Hydrology Data", "Reservoir Status"]
        if st.session_state.get("active_view") not in view_modes:
            st.session_state["active_view"] = "Hydrology Data"

        active_view_choice = st.radio(
            "Module Switcher",
            view_modes,
            key="active_view",
            horizontal=True,
            label_visibility="collapsed",
        )
        is_rsms = (active_view_choice == "Reservoir Status")

    with help_col:
        with st.popover("Help", use_container_width=True):
            st.markdown("### Quick Guide & Help")
            st.markdown(
                "1. **Boundary & Scope**: Choose **River Basin** (Hydrological) or **State** (Administrative) in the sidebar. Queries automatically cross-discover constituent observations.\n"
                "2. **Physical Variable**: Filter by Water Level, Discharge, Rainfall, Groundwater, or all parameters.\n"
                "3. **Search & Discover**: Queries live telemetry and archive records across CWC, WRIS, and NWDP.\n"
                "4. **Select**: Tick stations in the **Select Stations** view.\n"
                "5. **Download**: Pick your local folder and download selected stations as CSV. Choosing Parquet, GeoPackage or JSON also writes one combined file in that format.\n"
                "6. **Visualize**: time series with aggregation, data quality, station comparison, monthly pattern, warning/danger exceedance, flow duration, rating curve, rainfall and groundwater.\n"
                "7. **Reservoir Status**: Switch to the dedicated top tab for live storage monitoring across ~180 major national reservoirs.\n"
                "8. **Advanced**: a terminal panel at the bottom with a `hyswift` command console and the source log."
            )
            st.caption("CLI command: `hyswift --help` · Documentation: [GitHub](https://github.com/carbform/HydroSwift)")

    with about_col:
        with st.popover("About", use_container_width=True):
            st.markdown("### About HydroSwift")
            st.markdown(
                "**HydroSwift** is an open-source hydrological data engine and visualization studio for Indian water resources.\n\n"
                "**Authors & Credits**:\n"
                "- **carbform** ([carbform.github.io](https://carbform.github.io) · [GitHub Profile](https://github.com/carbform))\n"
                "- **Bharath Reddy** ([GitHub Profile](https://github.com/bharathk113))\n"
                "- **Source Code**: [carbform/HydroSwift on GitHub](https://github.com/carbform/HydroSwift)\n\n"
                "**Official Data Sources & APIs**:\n"
                "- [CWC Flood Forecasting System (FFS)](https://ffs.india-water.gov.in/)\n"
                "- [CWC Reservoir Storage Monitoring System (RSMS)](http://waris.cwc.gov.in/)\n"
                "- [India-WRIS OpenAPI 3.0](https://indiawris.gov.in/)\n"
                "- [National Water Data Portal (NWDP / data.gov.in)](https://data.gov.in/)\n\n"
                "**Disclaimer**:\n"
                "HydroSwift is an independent scientific research software application. It is not affiliated with, endorsed by, "
                "or an official product of the Ministry of Jal Shakti, Central Water Commission (CWC), or National Informatics Centre (NIC). "
                "Data retrieved via public endpoints is provided 'as is'. Always refer to official government bulletins for statutory flood warnings."
            )

    with dark_col:
        dark = st.toggle("Dark mode", key="dark")
    with mode_col:
        advanced = st.toggle("Advanced", key="advanced",
                             help="Command console and source log, docked at the bottom.")

    st.markdown(stylesheet(dark), unsafe_allow_html=True)

    job = st.session_state.get("job")
    if job is not None and not job.running:
        full_table = getattr(job, "full_table", None)
        finish_download(job)
        if full_table is not None:
            st.session_state["last_download"]["table"] = full_table

    # A permanent slot (empty unless Advanced is on), drawn before any early return. The dock
    # itself floats at the bottom of the window.
    with st.container():
        if advanced:
            dock.render(run_console_command)

    # -------------------------------------------------------------------------
    # ROUTE 1: Dedicated CWC Reservoirs Module
    # -------------------------------------------------------------------------
    if is_rsms:
        with st.sidebar:
            st.markdown(sidebar_brand(dark), unsafe_allow_html=True)
            st.markdown("### CWC RSMS Module")
            st.caption("Real-Time Reservoir Storage Monitoring System operated by Central Water Commission.")
            st.info("This module operates independently from station search & catalog discovery.")
            # a callback: the view radio above already exists, so its value cannot be set afterwards
            st.button("Switch to Hydrology Data", use_container_width=True,
                      on_click=lambda: st.session_state.update(active_view="Hydrology Data"))

        render_rsms_view(dark)
        st.markdown(get_credits_html(dark), unsafe_allow_html=True)
        return

    # -------------------------------------------------------------------------
    # ROUTE 2: Hydrological Station Discovery & Visualization
    # -------------------------------------------------------------------------
    with st.sidebar:
        st.markdown(sidebar_brand(dark), unsafe_allow_html=True)

        st.header("1 · Boundary & Scope")
        boundary_modes = ["Hydrological (Basin)", "Administrative (State)", "All / Custom"]
        if st.session_state.get("boundary_mode") not in boundary_modes:
            st.session_state["boundary_mode"] = "Hydrological (Basin)"

        boundary_mode = st.radio(
            "Boundary Type",
            boundary_modes,
            key="boundary_mode",
            horizontal=True,
            help="Hydrological queries search CWC/WRIS river basins and cross-discover constituent NWDP state data.",
        )

        selected_basin = None
        selected_state = None
        custom_loc = None

        if boundary_mode == "Hydrological (Basin)":
            basin_choices = ["All Basins"] + INDIAN_BASINS
            selected_basin = st.selectbox("River Basin", basin_choices, key="sb_basin")
            if selected_basin and selected_basin != "All Basins":
                st.session_state["active_basin"] = selected_basin
                constituent_states = get_states_for_basin(selected_basin)
                if constituent_states:
                    st.caption(f"**Constituent States**: {', '.join(constituent_states)}")
            else:
                st.session_state["active_basin"] = None

        elif boundary_mode == "Administrative (State)":
            state_choices = ["All States"] + INDIAN_STATES
            selected_state = st.selectbox("State / Union Territory", state_choices, key="sb_state")
            if selected_state and selected_state != "All States":
                st.session_state["active_state"] = selected_state
                intersecting_basins = get_basins_for_state(selected_state)
                if intersecting_basins:
                    st.caption(f"**Intersecting Basins**: {', '.join(intersecting_basins)}")
            else:
                st.session_state["active_state"] = None
        else:
            custom_loc = st.text_input("Custom Location / Keyword", key="sb_custom",
                                       placeholder="e.g. Bangalore, Ganga, Godavari")

        # Hydrological Variable Dropdown
        var_choice = st.selectbox(
            "Hydrological Variable",
            STANDARD_VARIABLES,
            key="sb_variable",
            help="Filter by physical variable or select 'All Variables' for all observations.",
        )
        if var_choice == "Custom...":
            query_var = st.text_input("Specify Variable Keyword", key="sb_custom_var",
                                      placeholder="e.g. sediment, evaporation")
        elif var_choice == "All Variables":
            query_var = ""
        else:
            query_var = var_choice

        # Date range
        dcol1, dcol2 = st.columns(2)
        start_year = dcol1.number_input("Start Year", min_value=1900, max_value=date.today().year, step=1, key="sb_start")
        end_year = dcol2.number_input("End Year", min_value=1900, max_value=date.today().year, step=1, key="sb_end")
        period = (str(int(start_year)), str(int(end_year)))
        bad_period = start_year > end_year
        if bad_period:
            st.error("Start year is after end year.")

        st.header("2 · Data Sources")
        cwc_on = st.checkbox("CWC Flood Forecasting (FFS)", key="src_cwc", help="Live telemetry stage & rating-curve discharge")
        wris_on = st.checkbox("India-WRIS OpenAPI 3.0", key="src_wris", help="Official India-WRIS REST API (telemetry & obs)")
        nwdp_on = st.checkbox("NWDP Open Data", key="src_nwdp", help="India-WRIS CKAN open datasets (rainfall, groundwater)")

        sources = []
        if cwc_on:
            sources.append("CWC")
        if wris_on:
            sources.append("WRIS")
        if nwdp_on:
            sources.append("NWDP")

        # Search Trigger
        job = st.session_state.get("job")
        if st.button("Search & Discover", type="primary", use_container_width=True,
                     disabled=bad_period or job is not None):
            if not sources:
                st.error("Please enable at least one data source.")
            else:
                with st.spinner("Discovering stations and catalog items..."):
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
                        record(st.session_state, search_command(query_var, custom_loc, b_filter, s_filter,
                                                                sources, period), f"{len(cat)} rows (sidebar)")
                        st.session_state.update(selected=set(), editor_base=None, run=None, tidy=None,
                                                last_download=None, estimate=None)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Discovery error: {e}")

    # -------------------------------------------------------------------------
    # MAIN AREA. The action bar and counters are filled after the tabs, so they
    # reflect ticks made in this run.
    # -------------------------------------------------------------------------
    cat = st.session_state.get("catalog")
    total_discovered = len(cat) if cat is not None else 0
    job = st.session_state.get("job")

    # Every region gets one fixed slot. Streamlit 1.32 matches elements by position, and
    # its page crashed (blank screen) when a finished download shifted blocks around.
    action_bar = st.container()
    with st.container():
        if job is not None:
            render_job(job)
        elif st.session_state.get("last_download"):
            render_last_download(st.session_state["last_download"])
    pill_bar = st.empty()
    tidy = st.session_state.get("tidy")
    active_b = st.session_state.get("active_basin") or "All India"

    with st.container():
        if cat is not None:
            render_source_status(cat, advanced)
            if cat.empty:
                st.info("The search found nothing. Widen the place, variable or years.")

    def render_action_bar():
        selected = st.session_state["selected"]
        count = len(selected)
        pills = [
            f'<span class="metric-pill">Boundary: <b>{active_b}</b></span>',
            f'<span class="metric-pill">Found: <b>{total_discovered:,}</b></span>',
            f'<span class="metric-pill">Selected: <b>{count:,}</b></span>',
        ]
        if tidy is not None and not tidy.empty:
            pills.append(f'<span class="metric-pill">Records: <b>{len(tidy):,}</b></span>')
        pill_bar.markdown(" ".join(pills), unsafe_allow_html=True)

        with action_bar:
            dcol_btn, dcol_est, dcol_fmt, dcol_path, dcol_browse = st.columns([2.8, 3, 2, 3.6, 2])
            busy = st.session_state.get("job") is not None
            def begin():
                rows = row_spec(cat, st.session_state["selected"])
                record(st.session_state, f"get --rows {rows} --period {':'.join(period)}", "(Download button)")
                start_download(pick_rows(cat, st.session_state["selected"]), period=period,
                               output_dir=st.session_state.get("dest_input") or "output",
                               export_format=st.session_state.get("export_format", "csv"))

            # a callback, not "if clicked": the job must start exactly once
            dcol_btn.button(f"Download ({count})", disabled=count == 0 or busy or bad_period,
                            type="primary", use_container_width=True, on_click=begin)
            est_clicked = dcol_est.button("Estimate size", disabled=count == 0 or busy, use_container_width=True)
            if "export_format" not in st.session_state:
                st.session_state["export_format"] = st.session_state.get("last_format", "csv")
            export_format = dcol_fmt.selectbox("Format", ["csv", "parquet", "gpkg", "json"], label_visibility="collapsed",
                                               key="export_format",
                                               help="Station files are saved as CSV; other formats add one combined file.")
            st.session_state["last_format"] = export_format
            if "dest_input" not in st.session_state:
                st.session_state["dest_input"] = st.session_state["download_dir"]
            dest = dcol_path.text_input("Download folder", label_visibility="collapsed", key="dest_input")
            st.session_state["download_dir"] = dest

            def browse():
                chosen = choose_folder(start=st.session_state["dest_input"], title="Select HydroSwift Download Destination")
                if chosen:
                    st.session_state["dest_input"] = chosen

            dcol_browse.button("Browse…", on_click=browse, use_container_width=True)

            if cat is not None and count == 0:
                st.caption("Tick stations in the **Select Stations** view to download them.")
            if count and any(src == "WRIS" for src, _ in selected) and end_year > start_year:
                st.caption("India-WRIS is slow over several years: one station can take minutes.")
            if est_clicked:
                with st.spinner("Asking sources for record counts…"):
                    try:
                        est = hs.estimate(pick_rows(cat, selected))
                        known = pd.to_numeric(est["EstRecords"], errors="coerce")
                        text = (f"{int(known.sum()):,} records reported for {int(known.notna().sum())} items "
                                "(whole datasets, before the year filter)")
                        if known.isna().any():
                            text += f"; size unknown for {int(known.isna().sum())} items"
                        st.session_state["estimate"] = (frozenset(selected), text + ".")
                    except Exception as e:
                        st.error(f"Estimate failed: {e}")
            estimate = st.session_state.get("estimate")
            if estimate and estimate[0] == frozenset(selected):
                st.caption(estimate[1])

    if job is not None:
        # Maps and tables are heavy to redraw every second, so only progress is shown meanwhile.
        render_action_bar()
        st.markdown(get_credits_html(dark), unsafe_allow_html=True)
        for _ in range(8):  # overwrite elements left over from the previous page
            st.empty()
        time.sleep(1)
        st.rerun()

    # -------------------------------------------------------------------------
    # Main views: Map Layers, Select Stations, Visualize
    # -------------------------------------------------------------------------
    # Not st.tabs: in Streamlit 1.32 tabs jump back to the first one when the page above them
    # changes (every tick did that). A keyed radio remembers the view; each view has its own slot.
    view = st.radio("View", ["Map Layers", "Select Stations", "Visualize"], key="main_view",
                    horizontal=True, label_visibility="collapsed")
    map_slot, select_slot, plot_slot = st.container(), st.container(), st.container()

    # -------------------------------------------------------------------------
    # VIEW 1: Map Layers with Auto-Zoom & Official Shapefile Overlays
    # -------------------------------------------------------------------------
    if view == "Map Layers":
        with map_slot:
            # Official shapefile overlay toggles
            lcol1, lcol2, lcol3 = st.columns(3)
            show_india = lcol1.checkbox("India National Boundary", value=True, help="Official survey boundary of India")
            show_basins = lcol2.checkbox("CWC River Basins", value=True, help="Official Central Water Commission basin boundaries")
            show_aquifers = lcol3.checkbox("Major Aquifers", value=False, help="India-WRIS / CGWB hydrogeological aquifer systems")

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

            # Build interactive map (basemap defaults to osm, markers colored by data source)
            map_data = cat if cat is not None and not cat.empty else pd.DataFrame()
            try:
                hmap = create_map(
                    map_data,
                    output=None,
                    basemap="osm",
                    color_by="source",
                    cluster=True,
                    bounds=target_bounds,
                    geojson_layers=geojson_layers,
                    title=f"HydroSwift · {active_b}",
                )
                components.html(hmap.to_html(), height=580, scrolling=False)
                if not map_data.empty:
                    unmapped = int(pd.to_numeric(map_data["lat"], errors="coerce").isna().sum())
                    if unmapped:
                        st.caption(f"{unmapped:,} of {len(map_data):,} results have no coordinates and are not on the map; "
                                   "find them in Select Stations.")
            except Exception as e:
                st.info(f"Interactive Map initialized. Discovered stations with coordinates will appear here. (Info: {e})")

    # -------------------------------------------------------------------------
    # VIEW 2: Station selection
    # -------------------------------------------------------------------------
    if view == "Select Stations":
        with select_slot:
            if cat is None or cat.empty:
                st.info("Nothing to select yet. Use **Search & Discover** in the sidebar.")
            else:
                render_selection(cat)
                if st.button("Save search results to JSON"):
                    out_p = Path(st.session_state.get("download_dir", "output")) / "catalog.json"
                    out_p.parent.mkdir(parents=True, exist_ok=True)
                    hs.save_catalog(cat, out_p)
                    st.success(f"Saved catalog to `{out_p}`")

    render_action_bar()

    # -------------------------------------------------------------------------
    # VIEW 3: Visualize
    # -------------------------------------------------------------------------
    if view == "Visualize":
        with plot_slot:
            if tidy is None or tidy.empty:
                st.info("Select stations and press **Download** to analyse their time series.")
            else:
                try:
                    from hydroswift.gui import visualize
                    visualize.render(tidy, dark, period=st.session_state.get("tidy_period"))
                except ImportError:
                    st.error("Plotting needs plotly: pip install hydroswift[gui]")

    # Footer
    st.markdown(get_credits_html(dark), unsafe_allow_html=True)


if __name__ == "__main__":
    main()
