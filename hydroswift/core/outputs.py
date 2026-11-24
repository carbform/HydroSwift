"""Merge, feature-rich hydrological plotting, and geospatial mapping.

Built on the tidy ``load()`` table and catalog schemas:
- ``merge()``: writes tidy data to CSV, Parquet, or GeoPackage (.gpkg)
- ``plot()``: multi-kind hydrological visualization:
    * ``kind='timeseries'``: standard hydrograph with CWC warning/danger alert thresholds
    * ``kind='hydrograph'``: dual-axis stage & discharge (plus rainfall hyetograph)
    * ``kind='hyetograph'``: precipitation hyetograph with cumulative rainfall curve
    * ``kind='rating_curve'``: stage-discharge (H-Q) hydraulic rating curve with fitted power law
    * ``kind='compare'``: multi-station synchronized comparison
    * ``kind='fdc'``: flow duration curve with Q10, Q50, Q90 percentiles
    * ``interactive=True``: interactive Plotly HTML figures
- ``map()`` / ``create_map()``: publication-ready interactive Leaflet map layers
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from .mapping import create_map, HydroMap
from .tidy import TIDY_COLUMNS, load as _load


def _get_cwc_threshold_lookup() -> Dict[str, Dict[str, Any]]:
    """Return dict of station_code -> {warning_level, danger_level, hfl, river, basin}."""
    lookup = {}
    try:
        from hydroswift.sources.cwc_ffs import load_station_table
        table = load_station_table(refresh=False)
        for _, r in table.iterrows():
            code = str(r.get("code", "")).strip().lower()
            if code:
                lookup[code] = {
                    "name": r.get("name"),
                    "river": r.get("river"),
                    "basin": r.get("basin"),
                    "warning_level": r.get("warning_level"),
                    "danger_level": r.get("danger_level"),
                    "hfl": r.get("hfl"),
                }
    except Exception:
        pass
    return lookup


def merge(run, output="output/merged.parquet") -> pd.DataFrame:
    """Write the tidy table of *run* to .csv, .parquet or .gpkg and return it."""
    df = run if (isinstance(run, pd.DataFrame) and set(TIDY_COLUMNS).issubset(run.columns)) else _load(run)
    if df.empty:
        raise ValueError(f"Nothing to merge; unmapped files: {df.attrs.get('unmapped')}")
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    ext = out.suffix.lower()
    if ext == ".csv":
        df.to_csv(out, index=False)
    elif ext == ".parquet":
        df.to_parquet(out, index=False)
    elif ext == ".gpkg":
        import geopandas as gpd
        g = df.dropna(subset=["lat", "lon"])
        dropped = len(df) - len(g)
        if g.empty:
            raise ValueError("No rows have coordinates, so a GeoPackage cannot be written; use .csv or .parquet.")
        gdf = gpd.GeoDataFrame(g.copy(), geometry=gpd.points_from_xy(g["lon"], g["lat"]), crs="EPSG:4326")
        gdf["time"] = gdf["time"].astype(str)
        gdf.to_file(out, layer="hydroswift", driver="GPKG")
        if dropped:
            warnings.warn(f"{dropped} of {len(df)} rows have no coordinates and were not written to the GeoPackage.")
    else:
        raise ValueError(f"Unsupported output type {ext!r}; use .csv, .parquet or .gpkg")
    return df


def plot(
    run,
    output_dir: Optional[Union[str, Path]] = "output/plots",
    *,
    kind: str = "timeseries",
    variable: Optional[str] = None,
    station_id: Optional[str] = None,
    thresholds: bool = True,
    interactive: bool = False,
    max_series: int = 60,
    figsize: Optional[Tuple[float, float]] = None,
    dpi: int = 150,
) -> Union[List[str], Any]:
    """Feature-rich hydrological plotting for tidy observation datasets.

    Parameters
    ----------
    run : DataFrame, str, or Path
        Fetched results DataFrame, tidy DataFrame from `hs.load()`, or output folder.
    output_dir : str or Path, optional
        Folder to save generated plot files (default: 'output/plots'). If None,
        returns the generated Figure object(s) directly for inline notebook inspection.
    kind : str
        Type of hydrological visualization:
        - 'timeseries' (default): clean hydrograph per station with alert levels.
        - 'hydrograph': dual-axis plot combining river stage and discharge.
        - 'hyetograph': precipitation intensity bars with cumulative rainfall curve.
        - 'rating_curve': stage-discharge (H-Q) relationship with fitted hydraulic curve.
        - 'compare': multi-station comparison on a synchronized time axis.
        - 'fdc' or 'duration': flow duration curve with exceedance percentiles.
    variable : str, optional
        Filter to a single variable (e.g., 'water_level', 'discharge', 'rainfall').
    station_id : str, optional
        Filter to a specific station ID.
    thresholds : bool
        Whether to draw CWC Warning, Danger, and HFL threshold lines (default: True).
    interactive : bool
        If True, generate interactive Plotly HTML visualizations.
    max_series : int
        Maximum number of series to generate before warning and capping (default: 60).
    figsize : tuple, optional
        Matplotlib figure dimensions (width, height).
    dpi : int
        Resolution for saved PNG figures (default: 150).

    Returns
    -------
    list of str or Figure
        List of written file paths if output_dir is given, otherwise Figure object(s).
    """
    df = run if (isinstance(run, pd.DataFrame) and set(TIDY_COLUMNS).issubset(run.columns)) else _load(run)
    if variable:
        df = df[df["variable"] == variable]
    if station_id:
        df = df[df["station_id"].astype(str).str.lower() == str(station_id).strip().lower()]
    if df.empty:
        return []

    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Interactive Plotly workflow
    if interactive:
        return _plot_interactive(df, output_dir, kind=kind, thresholds=thresholds)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cwc_meta = _get_cwc_threshold_lookup() if thresholds else {}

    if kind == "hydrograph":
        return _plot_dual_hydrograph(df, output_dir, cwc_meta, thresholds, figsize, dpi)
    elif kind == "hyetograph":
        return _plot_hyetograph(df, output_dir, figsize, dpi)
    elif kind == "rating_curve":
        return _plot_rating_curve(df, output_dir, figsize, dpi)
    elif kind == "compare":
        return _plot_compare(df, output_dir, variable, figsize, dpi)
    elif kind in ("fdc", "duration"):
        return _plot_fdc(df, output_dir, figsize, dpi)
    else:
        return _plot_timeseries(df, output_dir, cwc_meta, thresholds, max_series, figsize, dpi)


# ---------------------------------------------------------------------------
# Specific Plot Implementations
# ---------------------------------------------------------------------------

def _plot_timeseries(df, output_dir, cwc_meta, thresholds, max_series, figsize, dpi):
    import matplotlib.pyplot as plt

    keys = df.groupby(["source", "station_id", "variable"], dropna=False).size().index.tolist()
    if len(keys) > max_series:
        warnings.warn(
            f"{len(keys)} series; plotting the first {max_series}. Filter with variable= or load() and plot yourself."
        )
        keys = keys[:max_series]

    paths, figures = [], []
    fig_size = figsize or (8, 3.2)

    for src, sid, var in keys:
        g = df[(df["source"] == src) & (df["variable"] == var)]
        g = g[g["station_id"].isna()] if pd.isna(sid) else g[g["station_id"] == sid]
        g = g.sort_values("time")
        if g.empty:
            continue

        fig, ax = plt.subplots(figsize=fig_size)
        t = pd.to_datetime(g["time"], errors="coerce")
        v = pd.to_numeric(g["value"], errors="coerce")

        line_color = "#1d4ed8" if var == "water_level" else ("#059669" if var == "discharge" else "#0284c7")
        ax.plot(t, v, color=line_color, lw=1.2, label=var.replace("_", " ").title())
        ax.grid(True, linestyle="--", alpha=0.4)

        unit = g["unit"].iloc[0] if g["unit"].notna().any() else ""
        name = g["station_name"].dropna().iloc[0] if g["station_name"].notna().any() else sid
        ax.set_title(f"{name} - {var} ({src})", fontsize=11, fontweight="bold")
        ax.set_ylabel(unit or "")

        # Draw CWC Flood thresholds for water level
        if thresholds and var == "water_level" and sid:
            meta = cwc_meta.get(str(sid).strip().lower(), {})
            wl_warn = meta.get("warning_level")
            wl_dang = meta.get("danger_level")
            hfl = meta.get("hfl")

            if pd.notna(wl_warn):
                ax.axhline(float(wl_warn), color="#f59e0b", linestyle="--", lw=1.1, label=f"Warning ({wl_warn}m)")
            if pd.notna(wl_dang):
                ax.axhline(float(wl_dang), color="#ef4444", linestyle="--", lw=1.2, label=f"Danger ({wl_dang}m)")
            if pd.notna(hfl):
                ax.axhline(float(hfl), color="#7f1d1d", linestyle=":", lw=1.2, label=f"HFL ({hfl}m)")

            if any(pd.notna(x) for x in (wl_warn, wl_dang, hfl)):
                ax.legend(loc="upper right", fontsize=8, framealpha=0.85)

        # Provenance method note
        methods = set(g["method"].dropna())
        if methods - {"observed"}:
            ax.text(0.01, 0.97, "estimated: " + ", ".join(sorted(methods - {"observed"})),
                    transform=ax.transAxes, va="top", fontsize=7, color="#4b5563")

        fig.tight_layout()

        if output_dir:
            safe = "".join(c if c.isalnum() else "_" for c in f"{src}_{sid}_{var}")
            p = Path(output_dir) / f"{safe}.png"
            fig.savefig(p, dpi=dpi)
            plt.close(fig)
            paths.append(str(p))
        else:
            figures.append(fig)

    return paths if output_dir else (figures[0] if len(figures) == 1 else figures)


def _plot_dual_hydrograph(df, output_dir, cwc_meta, thresholds, figsize, dpi):
    import matplotlib.pyplot as plt

    stations = df.groupby(["source", "station_id"], dropna=False).size().index.tolist()
    paths, figures = [], []
    fig_size = figsize or (9, 4.5)

    for src, sid in stations:
        sub = df[(df["source"] == src)]
        sub = sub[sub["station_id"].isna()] if pd.isna(sid) else sub[sub["station_id"] == sid]

        has_wl = (sub["variable"] == "water_level").any()
        has_q = (sub["variable"] == "discharge").any()

        if not (has_wl or has_q):
            continue

        name = sub["station_name"].dropna().iloc[0] if sub["station_name"].notna().any() else sid
        fig, ax1 = plt.subplots(figsize=fig_size)

        lines, labels = [], []

        if has_wl:
            gw = sub[sub["variable"] == "water_level"].sort_values("time")
            t_w = pd.to_datetime(gw["time"], errors="coerce")
            v_w = pd.to_numeric(gw["value"], errors="coerce")
            l1 = ax1.plot(t_w, v_w, color="#1d4ed8", lw=1.5, label="River Stage")
            ax1.fill_between(t_w, v_w.min(), v_w, color="#3b82f6", alpha=0.1)
            ax1.set_ylabel(f"Water Level [{gw['unit'].iloc[0] if gw['unit'].notna().any() else 'm'}]", color="#1d4ed8")
            ax1.tick_params(axis="y", labelcolor="#1d4ed8")
            lines.extend(l1)
            labels.append("Water Level")

            # Thresholds
            if thresholds and sid:
                meta = cwc_meta.get(str(sid).strip().lower(), {})
                wl_warn = meta.get("warning_level")
                wl_dang = meta.get("danger_level")
                if pd.notna(wl_warn):
                    ax1.axhline(float(wl_warn), color="#f59e0b", linestyle="--", lw=1.1, label=f"Warning ({wl_warn}m)")
                    labels.append(f"Warning ({wl_warn}m)")
                if pd.notna(wl_dang):
                    ax1.axhline(float(wl_dang), color="#ef4444", linestyle="--", lw=1.2, label=f"Danger ({wl_dang}m)")
                    labels.append(f"Danger ({wl_dang}m)")

        if has_q:
            gq = sub[sub["variable"] == "discharge"].sort_values("time")
            t_q = pd.to_datetime(gq["time"], errors="coerce")
            v_q = pd.to_numeric(gq["value"], errors="coerce")

            ax2 = ax1.twinx() if has_wl else ax1
            l2 = ax2.plot(t_q, v_q, color="#059669", lw=1.5, linestyle="-", label="Discharge")
            ax2.set_ylabel(f"Discharge [{gq['unit'].iloc[0] if gq['unit'].notna().any() else 'm3/s'}]", color="#059669")
            ax2.tick_params(axis="y", labelcolor="#059669")
            lines.extend(l2)
            labels.append("Discharge")

        ax1.grid(True, linestyle="--", alpha=0.35)
        ax1.set_title(f"{name} ({sid}) - Dual-Axis Hydrograph", fontsize=11, fontweight="bold")
        ax1.legend(loc="upper left", fontsize=8, framealpha=0.85)

        fig.tight_layout()

        if output_dir:
            safe = "".join(c if c.isalnum() else "_" for c in f"{src}_{sid}_hydrograph")
            p = Path(output_dir) / f"{safe}.png"
            fig.savefig(p, dpi=dpi)
            plt.close(fig)
            paths.append(str(p))
        else:
            figures.append(fig)

    return paths if output_dir else (figures[0] if len(figures) == 1 else figures)


def _plot_hyetograph(df, output_dir, figsize, dpi):
    import matplotlib.pyplot as plt

    rain_df = df[df["variable"] == "rainfall"]
    if rain_df.empty:
        return []

    paths, figures = [], []
    fig_size = figsize or (9, 4)

    for (src, sid), g in rain_df.groupby(["source", "station_id"], dropna=False):
        g = g.sort_values("time")
        t = pd.to_datetime(g["time"], errors="coerce")
        v = pd.to_numeric(g["value"], errors="coerce").fillna(0)

        fig, ax1 = plt.subplots(figsize=fig_size)
        ax2 = ax1.twinx()

        # Rainfall bars
        ax1.bar(t, v, width=0.8, color="#0284c7", alpha=0.75, label="Precipitation")
        ax1.set_ylabel("Rainfall [mm]", color="#0284c7")
        ax1.tick_params(axis="y", labelcolor="#0284c7")

        # Cumulative line
        cum_rain = v.cumsum()
        ax2.plot(t, cum_rain, color="#0f172a", lw=1.5, linestyle="--", label="Cumulative")
        ax2.set_ylabel("Cumulative Rainfall [mm]", color="#0f172a")

        name = g["station_name"].dropna().iloc[0] if g["station_name"].notna().any() else sid
        ax1.set_title(f"{name} ({sid}) - Hyetograph & Mass Curve", fontsize=11, fontweight="bold")
        ax1.grid(True, linestyle="--", alpha=0.35)

        fig.tight_layout()

        if output_dir:
            safe = "".join(c if c.isalnum() else "_" for c in f"{src}_{sid}_hyetograph")
            p = Path(output_dir) / f"{safe}.png"
            fig.savefig(p, dpi=dpi)
            plt.close(fig)
            paths.append(str(p))
        else:
            figures.append(fig)

    return paths if output_dir else (figures[0] if len(figures) == 1 else figures)


def _plot_rating_curve(df, output_dir, figsize, dpi):
    import matplotlib.pyplot as plt

    paths, figures = [], []
    fig_size = figsize or (7, 5)

    for (src, sid), g in df.groupby(["source", "station_id"], dropna=False):
        gw = g[g["variable"] == "water_level"].copy()
        gq = g[g["variable"] == "discharge"].copy()

        if gw.empty or gq.empty:
            continue

        gw["time"] = pd.to_datetime(gw["time"], errors="coerce")
        gq["time"] = pd.to_datetime(gq["time"], errors="coerce")
        gw = gw.dropna(subset=["time", "value"]).sort_values("time")
        gq = gq.dropna(subset=["time", "value"]).sort_values("time")

        merged = pd.merge_asof(
            gw[["time", "value"]].rename(columns={"value": "h"}),
            gq[["time", "value"]].rename(columns={"value": "q"}),
            on="time",
            direction="nearest",
            tolerance=pd.Timedelta("1h"),
        ).dropna()

        if len(merged) < 3:
            continue

        h = merged["h"].values
        q = merged["q"].values

        fig, ax = plt.subplots(figsize=fig_size)
        ax.scatter(h, q, color="#2563eb", alpha=0.7, edgecolors="none", s=25, label="Observed Stage-Discharge")

        # Fit curve (polynomial order 2)
        eq_text = ""
        try:
            poly = np.polyfit(h, q, 2)
            h_range = np.linspace(h.min(), h.max(), 100)
            q_fit = np.polyval(poly, h_range)
            ax.plot(h_range, q_fit, color="#dc2626", lw=1.8, linestyle="--", label="Fitted Rating Curve")

            # R-squared
            residuals = q - np.polyval(poly, h)
            ss_res = np.sum(residuals**2)
            ss_tot = np.sum((q - np.mean(q))**2)
            r2 = 1 - (ss_res / (ss_tot + 1e-8))
            eq_text = f"Q = {poly[0]:.2f}H² + {poly[1]:.2f}H + {poly[2]:.2f}\nR² = {r2:.3f}"
        except Exception:
            pass

        if eq_text:
            ax.text(
                0.05, 0.92, eq_text,
                transform=ax.transAxes,
                va="top",
                fontsize=8,
                bbox=dict(boxstyle="round,pad=0.4", fc="#ffffff", ec="#cbd5e1", alpha=0.9),
            )

        name = g["station_name"].dropna().iloc[0] if g["station_name"].notna().any() else sid
        ax.set_title(f"{name} ({sid}) - Rating Curve (H-Q)", fontsize=11, fontweight="bold")
        ax.set_xlabel("Water Level / River Stage [m]")
        ax.set_ylabel("River Discharge [m³/s]")
        ax.grid(True, linestyle="--", alpha=0.4)
        ax.legend(loc="lower right", fontsize=8)

        fig.tight_layout()

        if output_dir:
            safe = "".join(c if c.isalnum() else "_" for c in f"{src}_{sid}_rating_curve")
            p = Path(output_dir) / f"{safe}.png"
            fig.savefig(p, dpi=dpi)
            plt.close(fig)
            paths.append(str(p))
        else:
            figures.append(fig)

    return paths if output_dir else (figures[0] if len(figures) == 1 else figures)


def _plot_compare(df, output_dir, variable, figsize, dpi):
    import matplotlib.pyplot as plt

    v = variable or df["variable"].iloc[0]
    sub = df[df["variable"] == v].copy()
    if sub.empty:
        return []

    fig, ax = plt.subplots(figsize=figsize or (10, 4.5))
    unit = sub["unit"].dropna().iloc[0] if sub["unit"].notna().any() else ""

    for sid, g in sub.groupby("station_id", dropna=False):
        g = g.sort_values("time")
        name = g["station_name"].dropna().iloc[0] if g["station_name"].notna().any() else str(sid)
        t = pd.to_datetime(g["time"], errors="coerce")
        val = pd.to_numeric(g["value"], errors="coerce")
        ax.plot(t, val, lw=1.2, label=f"{name} ({sid})")

    ax.set_title(f"Multi-Station Comparison - {v.replace('_', ' ').title()}", fontsize=11, fontweight="bold")
    ax.set_ylabel(unit or "")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(loc="best", fontsize=8, framealpha=0.85)
    fig.tight_layout()

    if output_dir:
        p = Path(output_dir) / f"comparison_{v}.png"
        fig.savefig(p, dpi=dpi)
        plt.close(fig)
        return [str(p)]
    return fig


def _plot_fdc(df, output_dir, figsize, dpi):
    import matplotlib.pyplot as plt

    q_df = df[df["variable"] == "discharge"]
    if q_df.empty:
        return []

    paths, figures = [], []
    fig_size = figsize or (8, 4.5)

    for (src, sid), g in q_df.groupby(["source", "station_id"], dropna=False):
        vals = pd.to_numeric(g["value"], errors="coerce").dropna().sort_values(ascending=False).values
        if len(vals) < 5:
            continue

        n = len(vals)
        prob = (np.arange(1, n + 1) / (n + 1)) * 100.0

        fig, ax = plt.subplots(figsize=fig_size)
        ax.plot(prob, vals, color="#059669", lw=1.8, label="Flow Duration Curve")
        ax.set_yscale("log")

        # Mark percentiles Q10, Q50, Q90
        q10 = np.percentile(vals, 90)
        q50 = np.percentile(vals, 50)
        q90 = np.percentile(vals, 10)

        for q_val, p_pct, lbl in [(q10, 10, "Q10 (High Flow)"), (q50, 50, "Q50 (Median)"), (q90, 90, "Q90 (Low Flow)")]:
            ax.axvline(p_pct, color="#94a3b8", linestyle=":", lw=1)
            ax.scatter([p_pct], [q_val], color="#dc2626", s=25, zorder=5)
            ax.annotate(f"{lbl}: {q_val:.1f} m³/s", (p_pct + 1.5, q_val), fontsize=8, color="#1e293b")

        name = g["station_name"].dropna().iloc[0] if g["station_name"].notna().any() else sid
        ax.set_title(f"{name} ({sid}) - Flow Duration Curve (FDC)", fontsize=11, fontweight="bold")
        ax.set_xlabel("Exceedance Probability [%]")
        ax.set_ylabel("Discharge [m³/s] (log scale)")
        ax.grid(True, which="both", linestyle="--", alpha=0.35)

        fig.tight_layout()

        if output_dir:
            safe = "".join(c if c.isalnum() else "_" for c in f"{src}_{sid}_fdc")
            p = Path(output_dir) / f"{safe}.png"
            fig.savefig(p, dpi=dpi)
            plt.close(fig)
            paths.append(str(p))
        else:
            figures.append(fig)

    return paths if output_dir else (figures[0] if len(figures) == 1 else figures)


def _plot_interactive(df, output_dir, kind="timeseries", thresholds=True):
    try:
        import plotly.graph_objects as go
    except ImportError:
        warnings.warn("plotly is not installed; falling back to static matplotlib plots.")
        return plot(df, output_dir=output_dir, kind=kind, thresholds=thresholds, interactive=False)

    paths, figures = [], []
    cwc_meta = _get_cwc_threshold_lookup() if thresholds else {}

    for (src, sid, var), g in df.groupby(["source", "station_id", "variable"], dropna=False):
        g = g.sort_values("time")
        t = pd.to_datetime(g["time"], errors="coerce")
        v = pd.to_numeric(g["value"], errors="coerce")
        name = g["station_name"].dropna().iloc[0] if g["station_name"].notna().any() else sid
        unit = g["unit"].dropna().iloc[0] if g["unit"].notna().any() else ""

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=t, y=v,
            mode="lines",
            name=var.replace("_", " ").title(),
            line=dict(color="#1d4ed8" if var == "water_level" else "#059669", width=2),
            hovertemplate="Time: %{x}<br>Value: %{y:.2f} " + unit + "<extra></extra>",
        ))

        if thresholds and var == "water_level" and sid:
            meta = cwc_meta.get(str(sid).strip().lower(), {})
            if meta.get("warning_level"):
                fig.add_hline(y=float(meta["warning_level"]), line_dash="dash", line_color="#f59e0b", annotation_text="Warning")
            if meta.get("danger_level"):
                fig.add_hline(y=float(meta["danger_level"]), line_dash="dash", line_color="#ef4444", annotation_text="Danger")

        fig.update_layout(
            title=f"{name} ({sid}) - {var.replace('_', ' ').title()}",
            xaxis_title="Time",
            yaxis_title=unit,
            template="plotly_white",
            hovermode="x unified",
        )

        if output_dir:
            safe = "".join(c if c.isalnum() else "_" for c in f"{src}_{sid}_{var}")
            p = Path(output_dir) / f"{safe}.html"
            fig.write_html(str(p))
            paths.append(str(p))
        else:
            figures.append(fig)

    return paths if output_dir else (figures[0] if len(figures) == 1 else figures)


# Aliases
merge_run = merge
plot_run = plot
map = create_map
map_data = create_map
