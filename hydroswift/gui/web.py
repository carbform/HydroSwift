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
from hydroswift.gui.app_style import get_credits_html, stylesheet
from hydroswift.gui.desktop import choose_folder
from hydroswift.gui import dock
from hydroswift.gui.console import (
    VIEW_ANALYSE,
    VIEW_FIND,
    VIEW_RESERVOIRS,
    VIEWS,
    Console,
    record,
    row_spec,
    search_command,
)
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


TABLE_HEIGHT = 300
MAP_HEIGHT = 420

# widget values that must survive runs which do not draw the widget
KEEP_KEYS = ("main_view", "filter_text", "advanced", "export_format", "dest_input",
             "layer_india", "layer_basins", "layer_aquifers", "boundary_mode", "sb_basin", "sb_state", "sb_custom",
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
        "main_view": VIEW_FIND,
        "layer_india": True,
        "layer_basins": True,
        "layer_aquifers": False,
        "export_format": "csv",
        "boundary_mode": "River basin",
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
        report["messages"].append(("info", "This download added no data; Analyse still shows the earlier one."))
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


def draw_progress(slot, job) -> None:
    snap = job.snapshot()
    reading = " · ".join(snap["pages"][:2]) or snap["latest"]
    stopping = "Cancelling, items in progress may finish first · " if job.cancelling else ""
    slot.progress(min(1.0, snap["done"] / max(snap["total"], 1)),
                  text=f"{stopping}{snap['done']} of {snap['total']} finished · {snap['seconds']} s · {reading}")


def render_job(job):
    """One row: progress and Cancel. Returns the placeholder to keep updating."""
    bar, stop = st.columns([8, 2])
    slot = bar.empty()
    draw_progress(slot, job)
    stop.button("Cancel download", on_click=job.cancel, disabled=job.cancelling, use_container_width=True)
    return slot


def follow(job, slot) -> None:
    """Update progress in place until the job ends, then draw the page with its results.

    The page is not redrawn meanwhile, so nothing jumps; any click simply starts a new run.
    """
    while job.running:
        draw_progress(slot, job)
        time.sleep(0.7)
    st.rerun()


def render_last_download(report) -> None:
    """One compact block, so the table below it hardly moves."""
    message_col, open_col, retry_col, details_col = st.columns([5, 2, 1.5, 1.5])
    for level, text in report["messages"]:
        getattr(message_col, level)(text)
    problems = report["problems"]
    tidy = st.session_state.get("tidy")
    if tidy is not None and not tidy.empty and st.session_state.get("main_view") != VIEW_ANALYSE:
        open_col.button("Open in Analyse →", type="primary", use_container_width=True,
                        on_click=lambda: st.session_state.update(main_view=VIEW_ANALYSE))
    if problems is None:
        return

    def retry():
        keys = set(zip(problems["source"].astype(str), problems["id"].astype(str)))
        start_download(pick_rows(report["table"], keys), period=report["period"],
                       output_dir=report["output_dir"], export_format=report["export_format"],
                       previous=report["run"])
        # keep the full request so a second retry can still find every row
        st.session_state["job"].full_table = report["table"]

    retry_col.button(f"Retry ({len(problems)})", on_click=retry, use_container_width=True,
                     help="Download the failed or incomplete items again.")
    with details_col.popover("Details", use_container_width=True):
        st.dataframe(problems[["source", "title", "status", "error"]], use_container_width=True, hide_index=True)


def _bulk_buttons(shown: pd.DataFrame, keys: list, selected: set) -> None:
    def choose(new_selection):
        st.session_state["selected"], st.session_state["editor_base"] = new_selection, None

    b1, b2, b3 = st.columns(3)
    b1.button(f"Select all shown ({len(shown)})", use_container_width=True, disabled=shown.empty,
              on_click=choose, args=(selected | set(keys),))
    b2.button("Unselect shown", use_container_width=True, disabled=shown.empty,
              on_click=choose, args=(selected - set(keys),))
    # never disabled: this row is drawn before the ticks of this run are read
    b3.button("Clear selection", use_container_width=True, on_click=choose, args=(set(),))


def render_selection(cat: pd.DataFrame) -> None:
    """Checkbox table. Only the ticked (Source, ID) keys are read back from it."""
    f1, f2 = st.columns([2, 3])
    words = f1.text_input("Filter", placeholder="Words in title, place or variable", key="filter_text")
    source_names = sorted(cat["Source"].unique())
    sources_key = f"filter_sources_{'_'.join(source_names)}"
    if sources_key not in st.session_state:  # not default=: the value is also restored from state
        st.session_state[sources_key] = source_names
    wanted = f2.multiselect("Sources shown", source_names, key=sources_key)
    shown = cat[text_filter(cat, words) & cat["Source"].isin(wanted)]
    keys = row_keys(shown)
    selected = st.session_state["selected"]

    table_slot, bulk_slot = st.container(), st.container()
    with bulk_slot:
        _bulk_buttons(shown, keys, selected)
    if shown.empty:
        table_slot.info("No rows match this filter.")
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
    edited = table_slot.data_editor(view, key=f"editor_{st.session_state['editor_version']}", hide_index=True,
                            disabled=[h for _, h in columns], use_container_width=True, height=TABLE_HEIGHT,
                            column_config={"Select": st.column_config.CheckboxColumn("Select", width="small")})
    ticked = {k for k, on in zip(keys, edited["Select"]) if on}
    st.session_state["selected"] = (selected - set(keys)) | ticked


def keep_slot() -> None:
    """Invisible content for a block that may otherwise stay empty.

    Streamlit 1.32's page drops empty blocks after a run, so later blocks shift by one on
    the next run: a ghost copy of the page, and once a blank screen.
    """
    st.markdown('<span class="hs-keep"></span>', unsafe_allow_html=True)


def render_topbar():
    """Brand, the three views, the Advanced switch and one menu, in a single row."""
    brand, nav, mode, menu = st.columns([1.6, 5.9, 2, 1.3])
    brand.markdown('<div class="brand hs-row">Hydro<span>Swift</span></div>', unsafe_allow_html=True)
    if st.session_state.get("main_view") not in VIEWS:
        st.session_state["main_view"] = VIEW_FIND
    view = nav.radio("View", VIEWS, key="main_view", horizontal=True, label_visibility="collapsed")
    advanced = mode.toggle("Advanced", key="advanced", help="Command console and source log, docked at the bottom.")
    with menu.popover("Menu", use_container_width=True):
        dark = st.toggle("Dark mode", key="dark")
        with st.expander("Help"):
            st.markdown(
                "1. **Search**: choose a river basin, state or keyword, a variable and years, then press **Search**.\n"
                "2. **Select**: tick stations in the table; the map beside it shows where they are.\n"
                "3. **Download**: press **Download** above the table. **Options** sets format, folder and size estimate.\n"
                "4. **Analyse**: time series, data quality, comparison, monthly pattern, warning/danger exceedance, "
                "flow duration, rating curve, rainfall and groundwater.\n"
                "5. **Reservoirs**: live storage for the major CWC-monitored reservoirs.\n"
                "6. **Advanced**: a terminal panel at the bottom with a `hyswift` command console and the source log."
            )
            st.caption("CLI command: `hyswift --help` · Documentation: [GitHub](https://github.com/carbform/HydroSwift)")

        with st.expander("About and disclaimer"):
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

    return view, advanced, dark


def render_search_bar():
    """Where, what and when in one row. Returns the period and whether it is invalid."""
    job = st.session_state.get("job")
    modes = ["River basin", "State / UT", "Keyword"]
    if st.session_state.get("boundary_mode") not in modes:
        st.session_state["boundary_mode"] = modes[0]

    c_mode, c_place, c_var, c_from, c_to, c_src, c_go = st.columns([1.9, 2.1, 1.9, 1, 1, 1.4, 1.5])
    with c_mode:
        st.markdown('<span class="hs-row-mark"></span>', unsafe_allow_html=True)
        boundary_mode = st.selectbox("Search by", modes, key="boundary_mode")

    selected_basin = selected_state = custom_loc = None
    with c_place:
        if boundary_mode == modes[0]:
            related = get_states_for_basin(st.session_state.get("sb_basin") or "")
            selected_basin = st.selectbox(
                "River Basin", ["All Basins"] + INDIAN_BASINS, key="sb_basin",
                help=f"States in this basin: {', '.join(related)}" if related else
                "Basin searches also find the NWDP datasets of the states in the basin.")
            st.session_state["active_basin"] = None if selected_basin == "All Basins" else selected_basin
        elif boundary_mode == modes[1]:
            related = get_basins_for_state(st.session_state.get("sb_state") or "")
            selected_state = st.selectbox(
                "State / Union Territory", ["All States"] + INDIAN_STATES, key="sb_state",
                help=f"Basins in this state: {', '.join(related)}" if related else None)
            st.session_state["active_state"] = None if selected_state == "All States" else selected_state
        else:
            custom_loc = st.text_input("Location keyword", key="sb_custom", placeholder="e.g. Bangalore, Ganga")

    with c_var:
        var_choice = st.selectbox("Variable", STANDARD_VARIABLES, key="sb_variable")
        if var_choice == "Custom...":
            query_var = st.text_input("Variable keyword", key="sb_custom_var", placeholder="e.g. sediment")
        else:
            query_var = "" if var_choice == "All Variables" else var_choice

    this_year = date.today().year
    start_year = c_from.number_input("From", min_value=1900, max_value=this_year, step=1, key="sb_start")
    end_year = c_to.number_input("To", min_value=1900, max_value=this_year, step=1, key="sb_end")
    period = (str(int(start_year)), str(int(end_year)))
    bad_period = start_year > end_year

    with c_src:
        st.markdown('<div class="field-label">Sources</div>', unsafe_allow_html=True)
        on = sum(bool(st.session_state.get(k)) for k in ("src_cwc", "src_wris", "src_nwdp"))
        with st.popover(f"{on} of 3", use_container_width=True):
            st.checkbox("CWC Flood Forecasting (FFS)", key="src_cwc", help="Telemetry stage and rating-curve discharge")
            st.checkbox("India-WRIS OpenAPI 3.0", key="src_wris", help="Official India-WRIS REST API")
            st.checkbox("NWDP Open Data", key="src_nwdp", help="Rainfall, groundwater and other open datasets")
    sources = [name for name, key in (("CWC", "src_cwc"), ("WRIS", "src_wris"), ("NWDP", "src_nwdp"))
               if st.session_state.get(key)]

    with c_go:
        st.markdown('<div class="field-label">&nbsp;</div>', unsafe_allow_html=True)
        clicked = st.button("Search", type="primary", use_container_width=True,
                            disabled=bad_period or job is not None)
    message = st.container()
    with message:
        keep_slot()
    if bad_period:
        message.error("The From year is after the To year.")
    if clicked and not sources:
        message.error("Turn on at least one data source.")
    elif clicked:
        b_filter = selected_basin if selected_basin and selected_basin != "All Basins" else None
        s_filter = selected_state if selected_state and selected_state != "All States" else None
        try:
            with message, st.spinner("Searching…"):
                cat = hs.search(query=query_var or None, location=custom_loc or s_filter or b_filter,
                                sources=sources, period=period, basin=b_filter, state=s_filter,
                                cross_boundary=True)
            st.session_state["catalog"] = cat
            record(st.session_state, search_command(query_var, custom_loc, b_filter, s_filter, sources, period),
                   f"{len(cat)} rows (search bar)")
            st.session_state.update(selected=set(), editor_base=None, run=None, tidy=None,
                                    last_download=None, estimate=None)
            st.rerun()
        except Exception as e:
            message.error(f"Search failed: {e}")
    return period, bad_period


def render_status(slot, cat, advanced: bool) -> None:
    """Counts for the search on screen, on one line, with a warning only when a source fell short."""
    if cat is None:
        return
    count = len(st.session_state["selected"])
    lines = source_status_lines(cat)
    icons = {"ok": "✓", "partial": "!", "failed": "✗"}
    pills = [f'<span class="metric-pill">Found <b>{len(cat):,}</b></span>',
             f'<span class="metric-pill">Selected <b>{count:,}</b></span>']
    pills += [f'<span class="metric-pill">{icons[x["level"]]} {x["text"]}</span>' for x in lines]
    tidy = st.session_state.get("tidy")
    if tidy is not None and not tidy.empty:
        pills.append(f'<span class="metric-pill">Records <b>{len(tidy):,}</b></span>')
    with slot.container():
        st.markdown(" ".join(pills), unsafe_allow_html=True)
        if any(x["level"] != "ok" for x in lines):
            where = "the Source log below" if advanced else "Advanced mode (Source log)"
            st.warning(f"Some sources failed or are partial, so results are incomplete. See {where}.")


def render_map(cat, dark: bool) -> None:
    title, toggles = st.columns([3, 1])
    title.markdown('<div class="panel-title">Map</div>', unsafe_allow_html=True)
    with toggles.popover("Layers", use_container_width=True):
        show_india = st.checkbox("India National Boundary", key="layer_india")
        show_basins = st.checkbox("CWC River Basins", key="layer_basins")
        show_aquifers = st.checkbox("Major Aquifers", key="layer_aquifers")
    active_b = st.session_state.get("active_basin") or "All India"
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

    target_bounds = get_basin_bounds(b_name) if (b_name and b_name != "All Basins") else None
    map_data = cat if cat is not None and not cat.empty else pd.DataFrame()
    try:
        hmap = create_map(map_data, output=None, basemap="osm", color_by="source", cluster=True,
                          bounds=target_bounds, geojson_layers=geojson_layers, title=f"HydroSwift · {active_b}")
        components.html(hmap.to_html(), height=MAP_HEIGHT, scrolling=False)
        if not map_data.empty:
            unmapped = int(pd.to_numeric(map_data["lat"], errors="coerce").isna().sum())
            if unmapped:
                st.caption(f"{unmapped:,} of {len(map_data):,} results have no coordinates (listed in the table only).")
    except Exception as e:
        st.info(f"The map could not be drawn: {e}")


def render_download_bar(slot, cat, period, bad_period) -> None:
    """Download and its options. Filled after the table, so it counts this run's ticks."""
    selected = st.session_state["selected"]
    count = len(selected)
    busy = st.session_state.get("job") is not None

    def begin():
        rows = row_spec(cat, st.session_state["selected"])
        record(st.session_state, f"get --rows {rows} --period {':'.join(period)}", "(Download button)")
        start_download(pick_rows(cat, st.session_state["selected"]), period=period,
                       output_dir=st.session_state.get("dest_input") or "output",
                       export_format=st.session_state.get("export_format", "csv"))

    if "dest_input" not in st.session_state:
        st.session_state["dest_input"] = st.session_state["download_dir"]

    with slot:
        main_col, options_col = st.columns([3, 2])
        # a callback, not "if clicked": the job must start exactly once
        main_col.button(f"Download ({count})", disabled=count == 0 or busy or bad_period, type="primary",
                        use_container_width=True, on_click=begin)
        with options_col.popover("Options", use_container_width=True):
            st.selectbox("Format", ["csv", "parquet", "gpkg", "json"], key="export_format",
                         help="Station files are saved as CSV; other formats add one combined file.")
            st.text_input("Download folder", key="dest_input")
            st.session_state["download_dir"] = st.session_state["dest_input"]

            def browse():
                chosen = choose_folder(start=st.session_state["dest_input"], title="Select download folder")
                if chosen:
                    st.session_state["dest_input"] = chosen

            st.button("Browse…", on_click=browse, use_container_width=True)
            est_clicked = st.button("Estimate size", disabled=count == 0 or busy, use_container_width=True)
            if est_clicked:
                try:
                    with st.spinner("Asking sources for record counts…"):
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
            if st.button("Save search results to JSON", use_container_width=True, disabled=cat is None):
                out = Path(st.session_state["download_dir"]) / "catalog.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                hs.save_catalog(cat, out)
                st.success(f"Saved to `{out}`")
        if count and any(src == "WRIS" for src, _ in selected) and period[1] > period[0]:
            st.caption("India-WRIS is slow over several years: one station can take minutes.")


def render_activity():
    """Progress of the running download, or the result of the last one."""
    with st.container():
        keep_slot()
        job = st.session_state.get("job")
        if job is not None:
            return render_job(job)
        if st.session_state.get("last_download"):
            render_last_download(st.session_state["last_download"])
    return None


def render_find(period, bad_period, advanced: bool, dark: bool):
    """Search results: pick on the left, see where on the right, download above the table."""
    cat = st.session_state.get("catalog")
    status_slot = st.empty()
    progress = render_activity()

    left, right = st.columns([6, 5])
    with left:
        st.markdown('<span class="hs-workspace"></span>', unsafe_allow_html=True)
        # a container, not st.empty: replacing the block on each run would close the Options popover
        bar_slot = st.container()
        with bar_slot:
            keep_slot()
        table_area = st.container()
        with table_area:
            if cat is None:
                st.info("Choose a place and years above, then press **Search**. "
                        "Stations appear here to tick and download.")
            elif cat.empty:
                st.info("The search found nothing. Widen the place, variable or years.")
            else:
                render_selection(cat)
        if cat is not None and not cat.empty:
            render_download_bar(bar_slot, cat, period, bad_period)
    with right:
        render_map(cat, dark)
    render_status(status_slot, cat, advanced)
    return progress


def main():
    st.set_page_config(page_title="HydroSwift · Hydrological Studio", layout="wide",
                       initial_sidebar_state="collapsed")
    init_session()
    # Streamlit forgets a widget's value on any run that does not draw it (another view, or a
    # download in progress). Re-assigning keeps these.
    for key in list(st.session_state):
        if key in KEEP_KEYS + dock.STATE_KEYS or str(key).startswith(("filter_sources_", "viz_")):
            st.session_state[key] = st.session_state[key]

    view, advanced, dark = render_topbar()
    st.markdown(stylesheet(dark), unsafe_allow_html=True)

    job = st.session_state.get("job")
    if job is not None and not job.running:
        full_table = getattr(job, "full_table", None)
        finish_download(job)
        if full_table is not None:
            st.session_state["last_download"]["table"] = full_table

    # A permanent slot (empty unless Advanced is on). The dock itself floats at the bottom.
    with st.container():
        keep_slot()
        if advanced:
            dock.render(run_console_command)

    # One fixed slot per view: Streamlit matches elements by position, and shifting blocks
    # between runs once left the page blank.
    find_slot, analyse_slot, reservoir_slot = st.container(), st.container(), st.container()
    for slot in (find_slot, analyse_slot, reservoir_slot):
        with slot:
            keep_slot()

    progress = None
    if view == VIEW_RESERVOIRS:
        with reservoir_slot:
            render_rsms_view(dark)
    elif view == VIEW_ANALYSE:
        with analyse_slot:
            progress = render_activity()
            tidy = st.session_state.get("tidy")
            if tidy is None or tidy.empty:
                st.info("Nothing to analyse yet. In **Find & download**, tick stations and press **Download**.")
            else:
                try:
                    from hydroswift.gui import visualize
                    visualize.render(tidy, dark, period=st.session_state.get("tidy_period"))
                except ImportError:
                    st.error("Plotting needs plotly: pip install hydroswift[gui]")
    else:
        with find_slot:
            period, bad_period = render_search_bar()
            progress = render_find(period, bad_period, advanced, dark)

    st.markdown(get_credits_html(dark), unsafe_allow_html=True)
    job = st.session_state.get("job")
    if job is not None:
        if progress is None:  # a view without a progress row: just wait for the job
            progress = st.empty()
        follow(job, progress)


if __name__ == "__main__":
    main()
