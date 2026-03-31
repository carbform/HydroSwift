#!/usr/bin/env python3
"""Generate publication-ready hydrographs from SWIFT output."""

import sys
import importlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

matplotlib = importlib.import_module("matplotlib")
matplotlib.use("Agg")
plt = importlib.import_module("matplotlib.pyplot")
mdates = importlib.import_module("matplotlib.dates")


def load_swift_file(file_path):
    """Load SWIFT CSV/XLSX as a normalized dataframe with time/value columns."""
    file_path = str(file_path)
    if file_path.endswith(".csv"):
        df = pd.read_csv(file_path, comment="#")
    elif file_path.endswith(".xlsx"):
        df = pd.read_excel(file_path)
    else:
        return None

    df.columns = [str(c).strip().lower() for c in df.columns]

    known_vars = ["wse", "q", "wl", "atm", "rf", "temp", "rh", "solar", "sed", "gwl"]
    for var in known_vars:
        if var in df.columns and "value" not in df.columns:
            df["value"] = df[var]
            break

    if "time" not in df.columns or "value" not in df.columns:
        try:
            df = pd.read_excel(file_path, header=1)
            df.columns = [str(c).strip().lower() for c in df.columns]
        except Exception:
            return None
        if "time" not in df.columns or "value" not in df.columns:
            return None

    cols = [c for c in ["time", "value", "unit"] if c in df.columns]
    return df[cols]


def _resolve_plot_context(file_path, image_root=None, include_images_subdir=True):
    """Resolve output directory, title prefix, and labels from file path context."""
    parts = file_path.parts

    if "cwc" in parts:
        ylabel = "Water Level (m)"
        cwc_idx = parts.index("cwc")
        basin_name = None
        if len(parts) > cwc_idx + 2 and parts[cwc_idx + 2] == "stations":
            basin_name = parts[cwc_idx + 1]

        base_root = Path(image_root) if image_root else Path(*parts[:cwc_idx])
        cwc_root = base_root / "cwc"

        if basin_name:
            out_dir = cwc_root / basin_name / "images" if include_images_subdir else cwc_root / basin_name
        else:
            out_dir = cwc_root / "images" if include_images_subdir else cwc_root

        return out_dir, "CWC_", ylabel

    variable = file_path.parent.name
    basin = file_path.parent.parent.name

    if variable == "discharge":
        ylabel = "Discharge (m³/s)"
    elif variable == "water_level":
        ylabel = "Water Level (m)"
    else:
        ylabel = "Value"

    output_dir = Path(image_root) if image_root else file_path.parents[3]
    wris_root = output_dir / "wris"
    out_dir = wris_root / basin / "images" / variable if include_images_subdir else wris_root / basin / variable
    return out_dir, "", ylabel


def _apply_professional_style(ax):
    ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.35)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_facecolor("#fcfcfc")


def plot_station(
    file_path,
    image_root=None,
    include_images_subdir=True,
    export_png=None,
    export_svg=False,
    moving_average_window=None,
):
    """Plot one SWIFT station file to high-resolution PNG and/or SVG.

    The optional overlay is a moving average computed over the provided
    sample window, not a fitted trendline.
    """
    file_path = Path(file_path)
    try:
        if export_png is None:
            export_png = not export_svg

        df = load_swift_file(file_path)
        if df is None:
            print("Skipping (missing columns):", file_path.name)
            return

        df["time"] = pd.to_datetime(df["time"], errors="coerce")
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["time", "value"]).drop_duplicates(subset="time").sort_values("time")
        if df.empty:
            print("Skipping (no data):", file_path.name)
            return

        out_dir, prefix, ylabel = _resolve_plot_context(file_path, image_root, include_images_subdir)

        fig, ax = plt.subplots(figsize=(13, 5.2), constrained_layout=True)
        _apply_professional_style(ax)

        ax.plot(df["time"], df["value"], color="#1f4e79", linewidth=1.4, alpha=0.85, label="Observed")

        if moving_average_window and int(moving_average_window) > 1:
            rolling = df["value"].rolling(
                int(moving_average_window),
                min_periods=max(2, int(moving_average_window) // 3),
            ).mean()
            if rolling.notna().any():
                ax.plot(
                    df["time"],
                    rolling,
                    color="#c1121f",
                    linewidth=1.8,
                    alpha=0.9,
                    label=f"Moving Average - {int(moving_average_window)}",
                )

        ax.set_xlabel("Date", fontsize=10)
        ax.set_ylabel(ylabel, fontsize=10)
        title = file_path.stem.replace("_", " ")
        ax.set_title(title, fontsize=12, fontweight="bold", loc="left")

        # Smarter date ticks by span
        span_days = max(1, (df["time"].max() - df["time"].min()).days)
        if span_days > 3650:
            ax.xaxis.set_major_locator(mdates.YearLocator(2))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        elif span_days > 730:
            ax.xaxis.set_major_locator(mdates.YearLocator(1))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        else:
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        fig.autofmt_xdate()

        # Compact stat box for publication-readiness
        stats_txt = (
            f"n={len(df):,}\n"
            f"min={df['value'].min():.2f}\n"
            f"mean={df['value'].mean():.2f}\n"
            f"max={df['value'].max():.2f}"
        )
        ax.text(
            0.995,
            0.98,
            stats_txt,
            transform=ax.transAxes,
            va="top",
            ha="right",
            fontsize=8.5,
            bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "alpha": 0.8, "edgecolor": "#cccccc"},
        )

        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(frameon=False, loc="upper left")

        out_dir.mkdir(parents=True, exist_ok=True)
        saved_paths = []
        if export_png:
            png_path = out_dir / f"{prefix}{file_path.stem}.png"
            fig.savefig(png_path, dpi=300)
            saved_paths.append(str(png_path))
        if export_svg:
            svg_path = out_dir / f"{prefix}{file_path.stem}.svg"
            fig.savefig(svg_path)
            saved_paths.append(str(svg_path))
        plt.close(fig)
        if saved_paths:
            print("Saved:", ", ".join(saved_paths))
        else:
            print("Skipped (no export format enabled):", file_path.name)
    except Exception as e:
        print("Failed:", file_path.name, "|", str(e))

def plot_rating_curve(
    file_path,
    image_root=None,
    include_images_subdir=True,
    export_png=None,
    export_svg=False,
):
    """Plot a rating curve (H vs Q) from a CWC station file.

    If the file contains both ``wse`` and ``discharge`` columns, this
    produces an H-Q line plot with the RC parameters annotated in a
    stat box.  Files without discharge data are silently skipped.
    """
    file_path = Path(file_path)
    try:
        if export_png is None:
            export_png = not export_svg

        df = load_swift_file(file_path)
        if df is None:
            return

        # Re-load full columns since load_swift_file may simplify.
        raw_file = str(file_path)
        if raw_file.endswith(".csv"):
            full = pd.read_csv(raw_file, comment="#")
        elif raw_file.endswith(".xlsx"):
            full = pd.read_excel(raw_file)
        else:
            return
        full.columns = [str(c).strip().lower() for c in full.columns]

        if "wse" not in full.columns or "discharge" not in full.columns:
            return  # no rating curve data

        full["wse"] = pd.to_numeric(full["wse"], errors="coerce")
        full["discharge"] = pd.to_numeric(full["discharge"], errors="coerce")
        rc = full.dropna(subset=["wse", "discharge"]).copy()
        rc = rc[rc["discharge"] > 0]
        if rc.empty or len(rc) < 2:
            return

        rc = rc.sort_values("wse").drop_duplicates(subset="wse")

        out_dir, prefix, _ = _resolve_plot_context(file_path, image_root, include_images_subdir)

        fig, ax = plt.subplots(figsize=(9, 7), constrained_layout=True)
        _apply_professional_style(ax)

        ax.plot(
            rc["wse"],
            rc["discharge"],
            color="#2a6f97",
            linewidth=1.6,
            alpha=0.9,
            label="Rating Curve",
        )

        ax.set_xlabel("Water Surface Elevation / Stage (m)", fontsize=10)
        ax.set_ylabel("Discharge (m³/s)", fontsize=10)
        title = file_path.stem.replace("_", " ") + " – Rating Curve"
        ax.set_title(title, fontsize=12, fontweight="bold", loc="left")

        # Attempt to annotate with RC source/method.
        rc_source = None
        rc_method = None
        if "discharge_source" in full.columns:
            rc_source = full["discharge_source"].dropna().iloc[0] if not full["discharge_source"].dropna().empty else None
        if "discharge_method" in full.columns:
            methods = full["discharge_method"].dropna().unique()
            rc_method = ", ".join(str(m) for m in methods) if len(methods) else None

        stat_lines = [
            f"n = {len(rc):,}",
            f"H range: {rc['wse'].min():.2f} – {rc['wse'].max():.2f} m",
            f"Q range: {rc['discharge'].min():.1f} – {rc['discharge'].max():.1f} m³/s",
        ]
        if rc_method:
            stat_lines.append(f"Method: {rc_method}")
        if rc_source:
            stat_lines.append(f"Source: {rc_source}")
        stats_txt = "\n".join(stat_lines)

        ax.text(
            0.03,
            0.97,
            stats_txt,
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=8.5,
            bbox={
                "boxstyle": "round,pad=0.35",
                "facecolor": "white",
                "alpha": 0.85,
                "edgecolor": "#cccccc",
            },
        )

        handles, labels = ax.get_legend_handles_labels()
        if handles:
            ax.legend(frameon=False, loc="lower right")

        out_dir.mkdir(parents=True, exist_ok=True)
        saved = []
        if export_png:
            png_path = out_dir / f"{prefix}{file_path.stem}_RC.png"
            fig.savefig(png_path, dpi=300)
            saved.append(str(png_path))
        if export_svg:
            svg_path = out_dir / f"{prefix}{file_path.stem}_RC.svg"
            fig.savefig(svg_path)
            saved.append(str(svg_path))
        plt.close(fig)
        if saved:
            print("Saved RC plot:", ", ".join(saved))
    except Exception as e:
        print("RC plot failed:", file_path.name, "|", str(e))


def collect_files(input_path):
    input_path = Path(input_path)
    if input_path.is_file():
        return [input_path]
    files = list(input_path.rglob("*.csv"))
    files.extend(input_path.rglob("*.xlsx"))
    return files


def main():
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("python plot_station_timeseries.py <file | folder>\n")
        sys.exit()

    files = collect_files(sys.argv[1])
    if not files:
        print("No station files found.")
        return

    print("Stations found:", len(files))
    with ThreadPoolExecutor(max_workers=min(8, len(files))) as ex:
        list(ex.map(plot_station, files))


if __name__ == "__main__":
    main()
