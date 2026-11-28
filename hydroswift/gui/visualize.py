"""The Visualize view: station analyses drawn from the tidy table.

The numbers come from ``hydroswift.core.analysis``; this module only draws them.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from hydroswift.core import analysis
from hydroswift.gui.plotdata import flood_thresholds, is_estimated, rating_pairs, series, station_options

VIEWS = ["Time series", "Summary & data quality", "Compare stations", "Monthly pattern",
         "Warning & danger exceedance", "Flow duration curve", "Rating curve", "Rainfall", "Groundwater"]
AGGREGATIONS = ["As reported", "daily", "monthly", "annual"]
LABELS = {"water_level": "Water level", "gauge_height": "Gauge height (local zero)",
          "discharge": "Discharge", "rainfall": "Rainfall", "groundwater_level": "Groundwater level",
          "reservoir_level": "Reservoir level", "reservoir_storage": "Reservoir storage"}
COLORS = ["#2563eb", "#059669", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#be185d", "#4b5563"]
# widget keys that must survive while another view is on screen
STATE_KEYS = ("viz_station", "viz_kind", "viz_agg", "viz_gauge_zero", "viz_spike", "viz_compare",
              "viz_variable", "viz_invert", "viz_level")


def label(variable: str) -> str:
    return LABELS.get(variable, str(variable).replace("_", " ").capitalize())


def _keep_valid(key: str, options: list) -> None:
    """A remembered choice that no longer exists (new data) would make Streamlit raise."""
    if key in st.session_state and st.session_state[key] not in options:
        del st.session_state[key]


def _pick_variable(data: pd.DataFrame) -> str:
    names = {label(v): v for v in sorted(data["variable"].dropna().unique())}
    _keep_valid("viz_variable", list(names))
    return names[st.selectbox("Variable", list(names), key="viz_variable")]


def _layout(fig, title: str, dark: bool, height: int = 460, slider: bool = False):
    fig.update_layout(title=title, template="plotly_dark" if dark else "plotly_white", height=height,
                      font=dict(family="IBM Plex Mono, monospace"), margin=dict(l=40, r=40, t=50, b=40),
                      legend=dict(orientation="h", y=-0.25 if slider else -0.18))
    if slider:
        fig.update_xaxes(rangeslider_visible=True)
    st.plotly_chart(fig, use_container_width=True)


def _table(df: pd.DataFrame, name: str) -> None:
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Download table (CSV)", df.to_csv(index=False).encode("utf-8"),
                       file_name=f"{name}.csv", mime="text/csv", key=f"dl_{name}")


def _screened(data: pd.DataFrame) -> pd.DataFrame:
    """Apply the quality filters chosen on screen, always saying how many rows they remove."""
    flagged = int(analysis.screen(data).sum())
    c1, c2 = st.columns([3, 2])
    drop_zero = c1.checkbox(f"Exclude {flagged:,} gauge-zero readings", key="viz_gauge_zero",
                            disabled=flagged == 0,
                            help="Stage equal to the station's gauge zero: usually a dry gauge or no reading.")
    spike = c2.number_input("Exclude spikes larger than (0 = off)", min_value=0.0, step=0.5, key="viz_spike",
                            help="Difference from the median of the five surrounding readings, in the data's unit.")
    mask = analysis.screen(data, gauge_zero=drop_zero, spike_limit=spike or None)
    if mask.any():
        st.caption(f"{int(mask.sum()):,} of {len(data):,} readings are excluded from what is shown below.")
    elif flagged and not drop_zero:
        st.warning(f"{flagged:,} readings equal the gauge zero and are included. Tick the box to exclude them.")
    return data[~mask]


def _levels(data: pd.DataFrame):
    """Stage series and its axis name: sea-level elevation, else height above the local zero."""
    stage = series(data, "water_level", "reservoir_level")
    if not stage.empty:
        return stage, "Water level (m)", True
    return series(data, "gauge_height"), "Gauge height above local zero (m)", False


def time_series(data, title, dark):
    aggregation = st.radio("Aggregation", AGGREGATIONS, horizontal=True, key="viz_agg")
    stage, stage_name, has_datum = _levels(data)
    q = series(data, "discharge")
    if stage.empty and q.empty:
        st.info("No water level or discharge series for this station. Try Rainfall or Groundwater.")
        return
    q_name = "Discharge (m³/s)"
    if not q.empty and is_estimated(q).any():
        q_name = "Discharge, estimated from stage (m³/s)"
    if aggregation != "As reported":
        stage = analysis.resample(stage, aggregation) if not stage.empty else stage
        q = analysis.resample(q, aggregation) if not q.empty else q
        st.caption(f"{aggregation.capitalize()} means. Periods without readings are left blank.")

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if not stage.empty:
        fig.add_trace(go.Scatter(x=stage["time"], y=stage["value"], name=stage_name,
                                 line=dict(color="#2563eb", width=1.8)), secondary_y=False)
        styles = {"Warning Level": ("#f59e0b", "dash"), "Danger Level": ("#dc2626", "dot")}
        for name, level in (flood_thresholds(data) if has_datum else {}).items():
            color, dash = styles[name]
            # an invisible point keeps the threshold inside the axis range
            fig.add_trace(go.Scatter(x=[stage["time"].iloc[0]], y=[level], mode="markers", marker=dict(opacity=0),
                                     showlegend=False, hoverinfo="skip"), secondary_y=False)
            fig.add_hline(y=level, line=dict(color=color, dash=dash),
                          annotation_text=f"{name}: {level:g} m", secondary_y=False)
    if not q.empty:
        fig.add_trace(go.Scatter(x=q["time"], y=q["value"], name=q_name, line=dict(color="#059669", width=1.8)),
                      secondary_y=True)
    fig.update_layout(hovermode="x unified")
    fig.update_yaxes(title_text=stage_name, secondary_y=False)
    fig.update_yaxes(title_text=q_name, secondary_y=True)
    _layout(fig, title, dark, height=520, slider=True)


def summary_view(data, title, dark, period=None):
    table = analysis.summary(data)
    shown = table.drop(columns=["source", "station_id", "station_name"])
    st.markdown("**Statistics per variable**")
    _table(shown.round(3), "station_summary")
    st.caption("completeness_pct_of_record counts days between the first and last reading. "
               "The chart below counts whole calendar years, including requested years with no data.")
    wanted = None
    if period:
        from hydroswift.core.engine import parse_period
        low, high = parse_period(period)
        wanted = (int(low[:4]), int(high[:4])) if low and high else None
    years = analysis.yearly_completeness(data, years=wanted)
    if not years.empty:
        fig = go.Figure()
        for i, (variable, group) in enumerate(years.groupby("variable")):
            fig.add_trace(go.Bar(x=group["year"].astype(str), y=group["completeness_pct"], name=label(variable),
                                 marker_color=COLORS[i % len(COLORS)]))
        fig.update_yaxes(title_text="Days with data (%)", range=[0, 100])
        _layout(fig, "Completeness by calendar year", dark, height=320)


def compare(tidy, options, dark):
    variable = _pick_variable(tidy)
    have = [name for name, mask in options.items() if (tidy[mask]["variable"] == variable).any()]
    if "viz_compare" in st.session_state:
        st.session_state["viz_compare"] = [n for n in st.session_state["viz_compare"] if n in have]
    else:
        st.session_state["viz_compare"] = have[:4]
    chosen = st.multiselect("Stations", have, key="viz_compare")
    aggregation = st.radio("Aggregation", AGGREGATIONS, horizontal=True, key="viz_agg")
    if not chosen:
        st.info("Pick at least one station.")
        return
    parts = {name: series(tidy[options[name]], variable) for name in chosen}
    units = {str(u) for part in parts.values() for u in part["unit"].dropna().unique()}
    if len(units) > 1:
        st.error(f"These stations report different units ({', '.join(sorted(units))}); they cannot share an axis.")
        return
    if variable == "water_level":
        st.caption("Levels are elevations at each site, so compare the shape and timing rather than the height.")
    fig = go.Figure()
    for i, (name, part) in enumerate(parts.items()):
        if aggregation != "As reported":
            part = analysis.resample(part, aggregation)
        estimated = " (estimated)" if "method" in part and is_estimated(part).any() else ""
        fig.add_trace(go.Scatter(x=part["time"], y=part["value"], name=name + estimated,
                                 line=dict(color=COLORS[i % len(COLORS)], width=1.5)))
    fig.update_yaxes(title_text=f"{label(variable)} ({', '.join(units)})")
    _layout(fig, f"{label(variable)} by station", dark, height=500, slider=True)


def monthly(data, title, dark):
    variable = _pick_variable(data)
    part = series(data, variable)
    daily = analysis.resample(part, "daily")
    summed = variable in analysis.SUMMED_VARIABLES
    table = analysis.monthly_pattern(part)
    fig = go.Figure()
    if summed:
        fig.add_trace(go.Bar(x=[f"{y}-{m:02d}" for y, m in zip(table["year"], table["month"])], y=table["value"],
                             name="Monthly total", marker_color="#38bdf8"))
    else:
        fig.add_trace(go.Box(x=daily["time"].dt.month, y=daily["value"], name="Daily means",
                             marker_color="#2563eb", boxpoints="outliers"))
        fig.update_xaxes(title_text="Month", tickmode="linear", dtick=1)
    _layout(fig, f"{title} · {label(variable)}", dark, height=420)
    if table["years"].max() < 2:
        st.caption("Only one year per month: the departure from normal is zero by definition and says nothing.")
    _table(table.round(3), "monthly_pattern")


def exceedance(data, title, dark):
    stage, _, has_datum = _levels(data)
    levels = flood_thresholds(data) if has_datum else {}
    if stage.empty or not levels:
        st.info("This needs a CWC station with water levels and published warning or danger levels.")
        return
    _keep_valid("viz_level", list(levels))
    choice = st.radio("Threshold", list(levels), horizontal=True, key="viz_level")
    level = levels[choice]
    events = analysis.threshold_events(stage, level)
    m1, m2, m3 = st.columns(3)
    m1.metric("Events above", f"{len(events)}")
    m2.metric("Total hours above", f"{events['hours'].sum():,.0f}")
    m3.metric("Highest reading", f"{stage['value'].max():.2f} m", f"{stage['value'].max() - level:+.2f} m vs level",
              delta_color="inverse")
    st.caption(f"{choice} = {level:g} m. Durations come from reading times; a silence over 48 h ends an event, "
               "so gaps in the record can hide or split events.")
    if events.empty:
        st.success("No reading above this level in the downloaded period.")
    else:
        _table(events, "threshold_events")


def flow_duration(data, title, dark):
    flow = series(data, "discharge")
    if flow.empty:
        st.warning("No discharge series found for this station to construct an FDC.")
        return
    if is_estimated(flow).any():
        st.caption("Discharge here is estimated from stage via a rating curve, not observed.")
    curve = analysis.duration_curve(flow)
    st.caption(f"Built from {len(curve):,} daily mean values.")
    fig = go.Figure(go.Scatter(x=curve["exceedance_pct"], y=curve["value"], name="Daily discharge",
                               line=dict(color="#059669", width=2)))
    for p, color in [(10, "#ef4444"), (50, "#3b82f6"), (90, "#f59e0b")]:
        value = float(np.interp(p, curve["exceedance_pct"], curve["value"]))
        fig.add_trace(go.Scatter(x=[p], y=[value], mode="markers+text", text=[f"Q{p}"], textposition="top right",
                                 name=f"Q{p} = {value:,.1f}", marker=dict(color=color, size=8)))
    fig.update_layout(xaxis_title="Exceedance probability (%)", yaxis_title="Discharge (m³/s)", yaxis_type="log")
    _layout(fig, f"{title} · Flow duration", dark)


def rating(data, title, dark):
    pairs = rating_pairs(data)
    if len(pairs) < 3:
        q = series(data, "discharge")
        if not q.empty and is_estimated(q).all():
            st.warning("No rating curve: this station's discharge is itself estimated from stage by a rating "
                       "curve, so fitting it would only reproduce that curve. Observed discharge is needed.")
        else:
            st.warning("Insufficient synchronized Stage and observed Discharge pairs to fit a rating curve.")
        return
    h, q = pairs["value_stage"].values, pairs["value_q"].values
    fig = go.Figure(go.Scatter(x=h, y=q, mode="markers", name="Observations",
                               marker=dict(color="#3b82f6", size=7, opacity=0.8)))
    h0 = h.min() - 0.05
    b, log_a = np.polyfit(np.log(np.maximum(h - h0, 0.01)), np.log(np.maximum(q, 0.001)), 1)
    grid = np.linspace(h.min(), h.max(), 100)
    fig.add_trace(go.Scatter(x=grid, y=np.exp(log_a) * np.maximum(grid - h0, 0.01) ** b, mode="lines",
                             name=f"Q = {np.exp(log_a):.2f}(h - {h0:.2f})^{b:.2f}", line=dict(color="#ef4444")))
    fig.update_layout(xaxis_title="Stage (m)", yaxis_title="Discharge (m³/s)")
    _layout(fig, f"{title} · Stage-discharge", dark)
    st.caption(f"{len(pairs)} pairs. The offset h0 is fixed just below the lowest stage, not fitted: "
               "treat this as a first look, not a design curve.")


def rainfall(data, title, dark):
    rain = series(data, "rainfall")
    if rain.empty:
        st.warning("No rainfall series found for this station.")
        return
    aggregation = st.radio("Aggregation", AGGREGATIONS, horizontal=True, key="viz_agg")
    if aggregation != "As reported":
        rain = analysis.resample(rain, aggregation)
        st.caption(f"{aggregation.capitalize()} totals. Days without readings are not filled, so totals can be low.")
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=rain["time"], y=rain["value"], name="Rainfall (mm)", marker_color="#38bdf8"),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=rain["time"], y=rain["value"].cumsum(), name="Cumulative (mm)",
                             line=dict(color="#f59e0b", width=2)), secondary_y=True)
    fig.update_yaxes(title_text="Rainfall (mm)", autorange="reversed", secondary_y=False)
    fig.update_yaxes(title_text="Cumulative (mm)", secondary_y=True)
    _layout(fig, f"{title} · Rainfall", dark, slider=True)


def groundwater(data, title, dark):
    gw = series(data, "groundwater_level")
    if gw.empty:
        st.warning("No groundwater level observations found for this station.")
        return
    units = gw["unit"].dropna()
    unit = str(units.iloc[0]) if not units.empty else "m"
    invert = st.checkbox("Invert Y-axis (depth below ground level convention)", key="viz_invert")
    fig = go.Figure(go.Scatter(x=gw["time"], y=gw["value"], mode="lines+markers", name="Groundwater level",
                               line=dict(color="#0284c7", width=2), marker=dict(size=4)))
    fig.add_hline(y=gw["value"].mean(), line=dict(color="#94a3b8", dash="dash"),
                  annotation_text=f"Mean: {gw['value'].mean():.2f} {unit}")
    fig.update_layout(yaxis_title=f"Level / depth ({unit})", hovermode="x unified")
    if invert:
        fig.update_yaxes(autorange="reversed")
    _layout(fig, f"{title} · Groundwater", dark)
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Min", f"{gw['value'].min():.2f} {unit}")
    g2.metric("Mean", f"{gw['value'].mean():.2f} {unit}")
    g3.metric("Max", f"{gw['value'].max():.2f} {unit}")
    g4.metric("Range", f"{gw['value'].max() - gw['value'].min():.2f} {unit}")


def render(tidy: pd.DataFrame, dark: bool, period=None) -> None:
    options = station_options(tidy)
    c1, c2 = st.columns([3, 2])
    _keep_valid("viz_kind", VIEWS)
    kind = c2.selectbox("Analysis", VIEWS, key="viz_kind")
    try:
        if kind == "Compare stations":
            compare(_screened(tidy), options, dark)
            return
        _keep_valid("viz_station", list(options))
        station = c1.selectbox("Station", list(options), key="viz_station")
        data = tidy[options[station]].sort_values("time", kind="stable")
        data = _screened(data)
        if data.empty:
            st.warning("The filters exclude every reading.")
            return
        if kind == "Summary & data quality":
            summary_view(data, station, dark, period)
            return
        {"Time series": time_series, "Monthly pattern": monthly,
         "Warning & danger exceedance": exceedance, "Flow duration curve": flow_duration,
         "Rating curve": rating, "Rainfall": rainfall, "Groundwater": groundwater}[kind](data, station, dark)
    except Exception as e:
        st.error(f"Could not draw this analysis: {e}")
