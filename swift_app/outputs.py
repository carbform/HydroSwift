"""Merge and plot, built on the tidy ``load()`` table (no folder conventions)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .tidy import load as _load


def merge(run, output="output/merged.parquet") -> pd.DataFrame:
    """Write the tidy table of *run* to .csv, .parquet or .gpkg and return it."""
    df = _load(run)
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
            import warnings
            warnings.warn(f"{dropped} of {len(df)} rows have no coordinates and were not written to the GeoPackage.")
    else:
        raise ValueError(f"Unsupported output type {ext!r}; use .csv, .parquet or .gpkg")
    return df


def plot(run, output_dir="output/plots", *, variable=None, max_series=60) -> list:
    """One PNG per (station, variable). Returns the written paths."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = _load(run)
    if variable:
        df = df[df["variable"] == variable]
    if df.empty:
        return []
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    keys = df.groupby(["source", "station_id", "variable"], dropna=False).size().index.tolist()
    if len(keys) > max_series:
        import warnings
        warnings.warn(f"{len(keys)} series; plotting the first {max_series}. Filter with variable= or load() and plot yourself.")
        keys = keys[:max_series]
    paths = []
    for src, sid, var in keys:
        g = df[(df["source"] == src) & (df["variable"] == var)]
        g = g[g["station_id"].isna()] if pd.isna(sid) else g[g["station_id"] == sid]
        g = g.sort_values("time")
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.plot(g["time"], g["value"], lw=0.8)
        unit = g["unit"].iloc[0]
        name = g["station_name"].dropna().iloc[0] if g["station_name"].notna().any() else sid
        ax.set_title(f"{name} - {var} ({src})")
        ax.set_ylabel(unit or "")
        methods = set(g["method"].dropna())
        if methods - {"observed"}:
            ax.text(0.01, 0.97, "estimated: " + ", ".join(sorted(methods - {"observed"})),
                    transform=ax.transAxes, va="top", fontsize=7)
        fig.tight_layout()
        safe = "".join(c if c.isalnum() else "_" for c in f"{src}_{sid}_{var}")
        p = Path(output_dir) / f"{safe}.png"
        fig.savefig(p, dpi=120)
        plt.close(fig)
        paths.append(str(p))
    return paths
