"""
swot_merge.py — SWOT-ready GeoPackage builder for HydroSwift output.

After running a HydroSwift download (WRIS + CWC), call this module to merge
all station CSVs/GPKGs into a single GeoPackage conforming to the SWOT
validation pipeline schema:

    station_code, station_name, time, wse, discharge, lat, lon,
    rl, depth, basin, tributary, source_folder, data_type, geometry

Usage (CLI via HydroSwift):
    python -m hydroswift --swot-merge --output-dir output

Usage (standalone):
    python swift_app/swot_merge.py --output-dir output --output wris_merged.gpkg

Usage (importable):
    from swift_app.swot_merge import build_swot_gpkg
    gdf = build_swot_gpkg(output_dir="output", output_path="wris_merged.gpkg")
"""

from __future__ import annotations

import argparse
import logging
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

# ──────────────────────────────────────────────────────────────────────
# SCHEMA — must stay in sync with gauge_master.MASTER_COLUMNS
# ──────────────────────────────────────────────────────────────────────
SWOT_COLUMNS = [
    "station_code",
    "station_name",
    "time",
    "wse",
    "discharge",
    "lat",
    "lon",
    "rl",
    "depth",
    "basin",
    "tributary",
    "source_folder",
    "data_type",
]

DEFAULT_CRS = "EPSG:4326"

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────

def _to_float(val) -> float:
    if val is None:
        return np.nan
    try:
        return float(val)
    except (ValueError, TypeError):
        return np.nan


def _normalise_time(series: pd.Series) -> pd.Series:
    """Parse timestamps → tz-aware UTC (naive timestamps assumed IST)."""
    t = pd.to_datetime(series, errors="coerce")
    if t.dt.tz is None:
        t = t.dt.tz_localize("Asia/Kolkata", ambiguous="NaT", nonexistent="NaT")
    t = t.dt.tz_convert("UTC")
    t = t.dt.round("min")
    return t


def _compute_depth(df: pd.DataFrame) -> pd.Series:
    """depth = wse − rl (NaN when either is missing or depth < 0)."""
    wse = pd.to_numeric(df.get("wse", np.nan), errors="coerce")
    rl = pd.to_numeric(df.get("rl", np.nan), errors="coerce")
    depth = wse - rl
    depth[depth < 0] = np.nan
    return depth


def _load_cwc_station_meta(hydroswift_root: Path) -> pd.DataFrame:
    """
    Load CWC station metadata table from the packaged cwc_meta.csv.
    Returns DataFrame with columns: code, name, river, basin, lat, lon, rl_zero.
    """
    meta_path = hydroswift_root / "swift_app" / "cwc_meta.csv"
    if not meta_path.exists():
        logger.warning("cwc_meta.csv not found at %s", meta_path)
        return pd.DataFrame()
    try:
        df = pd.read_csv(meta_path)
        df.columns = [c.lower().strip() for c in df.columns]
        required = {"code", "name", "lat", "lon"}
        if not required.issubset(df.columns):
            logger.warning("cwc_meta.csv missing required columns")
            return pd.DataFrame()
        df["code"] = df["code"].astype(str).str.strip().str.upper()
        df["basin"] = df.get("basin", "").fillna("").str.strip()
        df["river"] = df.get("river", "").fillna("").str.strip()
        df["rl_zero"] = pd.to_numeric(df.get("rl_zero", np.nan), errors="coerce").fillna(0.0)
        return df
    except Exception as exc:
        logger.warning("Could not load cwc_meta.csv: %s", exc)
        return pd.DataFrame()


# ──────────────────────────────────────────────────────────────────────
# LOADERS — one per HydroSwift GPKG type
# ──────────────────────────────────────────────────────────────────────

def _load_cwc_gpkg(
    gpkg_path: Path,
    cwc_meta: pd.DataFrame,
) -> pd.DataFrame:
    """
    Load a CWC water-level GeoPackage produced by HydroSwift.

    HydroSwift CWC schema: station_code, time, wse, water_depth, unit, lat, lon
    Enrich with: station_name, basin, tributary (river), rl from cwc_meta.
    """
    import geopandas as gpd

    if not gpkg_path.exists():
        return pd.DataFrame(columns=SWOT_COLUMNS)

    try:
        gdf = gpd.read_file(gpkg_path)
    except Exception as exc:
        logger.warning("Failed reading %s: %s", gpkg_path.name, exc)
        return pd.DataFrame(columns=SWOT_COLUMNS)

    df = pd.DataFrame(gdf.drop(columns=["geometry"], errors="ignore"))

    # Normalise column aliases
    if "wse" not in df.columns and "water_level" in df.columns:
        df = df.rename(columns={"water_level": "wse"})
    if "wse" not in df.columns:
        df["wse"] = np.nan

    df["station_code"] = df["station_code"].astype(str).str.strip().str.upper()
    df["discharge"] = np.nan  # CWC GPKG is water-level only
    df["data_type"] = "HHS"
    df["source_folder"] = "cwc_waterlevel"

    # Enrich from CWC metadata
    if not cwc_meta.empty:
        meta = cwc_meta[["code", "name", "basin", "river", "lat", "lon", "rl_zero"]].copy()
        meta.columns = ["station_code", "station_name", "basin", "tributary", "lat_m", "lon_m", "rl"]
        df = df.merge(meta, on="station_code", how="left")
        # Prefer CSV coordinates over gpkg geometry coords where available
        df["lat"] = pd.to_numeric(df.get("lat"), errors="coerce").combine_first(
            pd.to_numeric(df.get("lat_m"), errors="coerce")
        )
        df["lon"] = pd.to_numeric(df.get("lon"), errors="coerce").combine_first(
            pd.to_numeric(df.get("lon_m"), errors="coerce")
        )
        df["rl"] = pd.to_numeric(df.get("rl"), errors="coerce").fillna(0.0)
    else:
        df["station_name"] = df["station_code"]
        df["basin"] = "Unknown"
        df["tributary"] = ""
        df["rl"] = 0.0
        df["lat"] = pd.to_numeric(df.get("lat"), errors="coerce")
        df["lon"] = pd.to_numeric(df.get("lon"), errors="coerce")

    df["station_name"] = df["station_name"].fillna(df["station_code"]).astype(str).str.strip()
    df["basin"] = df.get("basin", "Unknown").fillna("Unknown").astype(str)
    df["tributary"] = df.get("tributary", "").fillna("").astype(str)

    for col in SWOT_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan

    n = len(df)
    logger.info("  ✅ CWC water-level: %d records from %s", n, gpkg_path.name)
    print(f"  ✅ CWC water-level ({gpkg_path.name}): {n:,} records")
    return df[SWOT_COLUMNS]


def _load_wris_wl_gpkg(
    gpkg_path: Path,
    basin: str,
    source_label: str,
    cwc_meta: pd.DataFrame,
) -> pd.DataFrame:
    """
    Load a WRIS water-level GeoPackage produced by HydroSwift.

    HydroSwift WRIS water_level schema: station_code, time, wl, lat, lon
    """
    import geopandas as gpd

    if not gpkg_path.exists():
        return pd.DataFrame(columns=SWOT_COLUMNS)

    try:
        gdf = gpd.read_file(gpkg_path)
    except Exception as exc:
        logger.warning("Failed reading %s: %s", gpkg_path.name, exc)
        return pd.DataFrame(columns=SWOT_COLUMNS)

    df = pd.DataFrame(gdf.drop(columns=["geometry"], errors="ignore"))

    # wl → wse
    if "wl" in df.columns and "wse" not in df.columns:
        df = df.rename(columns={"wl": "wse"})
    if "wse" not in df.columns:
        df["wse"] = np.nan
    df["discharge"] = np.nan
    df["data_type"] = "HHS"
    df["source_folder"] = source_label

    df["station_code"] = df["station_code"].astype(str).str.strip().str.upper()
    df["lat"] = pd.to_numeric(df.get("lat"), errors="coerce")
    df["lon"] = pd.to_numeric(df.get("lon"), errors="coerce")

    # Enrich station_name / rl from CWC metadata where available
    if not cwc_meta.empty:
        meta = cwc_meta[["code", "name", "river", "rl_zero"]].rename(
            columns={"code": "station_code", "name": "station_name", "river": "tributary", "rl_zero": "rl"}
        )
        df = df.merge(meta, on="station_code", how="left")
        df["rl"] = pd.to_numeric(df.get("rl"), errors="coerce").fillna(0.0)
    else:
        df["station_name"] = df["station_code"]
        df["tributary"] = ""
        df["rl"] = 0.0

    df["station_name"] = df["station_name"].fillna(df["station_code"]).astype(str).str.strip()
    df["basin"] = basin
    df["tributary"] = df.get("tributary", "").fillna("").astype(str)

    for col in SWOT_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan

    n = len(df)
    logger.info("  ✅ WRIS water-level (%s): %d records", basin, n)
    print(f"  ✅ WRIS water-level ({basin}, {gpkg_path.name}): {n:,} records")
    return df[SWOT_COLUMNS]


def _load_wris_discharge_gpkg(
    gpkg_path: Path,
    basin: str,
    source_label: str,
    cwc_meta: pd.DataFrame,
) -> pd.DataFrame:
    """
    Load a WRIS discharge GeoPackage produced by HydroSwift.

    HydroSwift WRIS discharge schema: station_code, time, q, lat, lon
    """
    import geopandas as gpd

    if not gpkg_path.exists():
        return pd.DataFrame(columns=SWOT_COLUMNS)

    try:
        gdf = gpd.read_file(gpkg_path)
    except Exception as exc:
        logger.warning("Failed reading %s: %s", gpkg_path.name, exc)
        return pd.DataFrame(columns=SWOT_COLUMNS)

    df = pd.DataFrame(gdf.drop(columns=["geometry"], errors="ignore"))

    # q → discharge
    if "q" in df.columns and "discharge" not in df.columns:
        df = df.rename(columns={"q": "discharge"})
    if "discharge" not in df.columns:
        df["discharge"] = np.nan
    df["wse"] = np.nan
    df["data_type"] = "QOB"
    df["source_folder"] = source_label

    df["station_code"] = df["station_code"].astype(str).str.strip().str.upper()
    df["lat"] = pd.to_numeric(df.get("lat"), errors="coerce")
    df["lon"] = pd.to_numeric(df.get("lon"), errors="coerce")

    # Enrich from CWC metadata
    if not cwc_meta.empty:
        meta = cwc_meta[["code", "name", "river", "rl_zero"]].rename(
            columns={"code": "station_code", "name": "station_name", "river": "tributary", "rl_zero": "rl"}
        )
        df = df.merge(meta, on="station_code", how="left")
        df["rl"] = pd.to_numeric(df.get("rl"), errors="coerce").fillna(0.0)
    else:
        df["station_name"] = df["station_code"]
        df["tributary"] = ""
        df["rl"] = 0.0

    df["station_name"] = df["station_name"].fillna(df["station_code"]).astype(str).str.strip()
    df["basin"] = basin
    df["tributary"] = df.get("tributary", "").fillna("").astype(str)

    for col in SWOT_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan

    n = len(df)
    logger.info("  ✅ WRIS discharge (%s): %d records", basin, n)
    print(f"  ✅ WRIS discharge ({basin}, {gpkg_path.name}): {n:,} records")
    return df[SWOT_COLUMNS]


# ──────────────────────────────────────────────────────────────────────
# GPKG DISCOVERY
# ──────────────────────────────────────────────────────────────────────

def _latest_cwc_gpkgs(cwc_root: Path) -> list[Path]:
    """
    Discover the most recent CWC water-level GPKGs under cwc_root.
    If basin-specific files exist, returns those and ignores 'all_stations'.
    """
    if not cwc_root.exists():
        return []
    import re
    candidates = sorted(cwc_root.glob("cwc_waterlevel*.gpkg"))
    groups = {}
    for p in candidates:
        m = re.match(r"(cwc_waterlevel_.*?)(?:_\d{4}-\d{2}-\d{2})", p.name)
        prefix = m.group(1) if m else p.stem
        groups.setdefault(prefix, []).append(p)
    
    latest_files = [sorted(fps)[-1] for fps in groups.values()]
    basin_files = [f for f in latest_files if "all_stations" not in f.name]
    return basin_files if basin_files else latest_files


def _latest_gpkg(folder: Path, prefix: str) -> Optional[Path]:
    """Return the most recently-named GPKG matching *prefix* in folder."""
    if not folder.exists():
        return None
    matches = sorted(folder.glob(f"{prefix}*.gpkg"))
    return matches[-1] if matches else None


# ──────────────────────────────────────────────────────────────────────
# MAIN BUILDER
# ──────────────────────────────────────────────────────────────────────

def build_swot_gpkg(
    output_dir: str | Path = "output",
    output_path: Optional[str | Path] = None,
    hydroswift_root: Optional[str | Path] = None,
    overwrite: bool = False,
    layer: str = "wris_merged",
) -> "gpd.GeoDataFrame":  # type: ignore[name-defined]
    """
    Build a SWOT-ready merged GeoPackage from HydroSwift output folders.

    Reads from the standard HydroSwift output layout::

        <output_dir>/
          cwc/
            cwc_waterlevel_all_stations_<dates>.gpkg
          wris/
            godavari/
              godavari_water_level_<dates>.gpkg
              godavari_discharge_<dates>.gpkg
            krishna/
              krishna_water_level_<dates>.gpkg
              krishna_discharge_<dates>.gpkg

    Parameters
    ----------
    output_dir : str | Path
        Root of the HydroSwift output tree (same as ``--output-dir`` CLI arg).
    output_path : str | Path, optional
        Destination GeoPackage. Defaults to ``<output_dir>/wris_merged.gpkg``.
    hydroswift_root : str | Path, optional
        Root of the HydroSwift repo (for cwc_meta.csv lookup).
        Defaults to the parent of this file's package directory.
    overwrite : bool
        Overwrite output_path if it already exists.
    layer : str
        GeoPackage layer name for the output.

    Returns
    -------
    geopandas.GeoDataFrame
        Merged GeoDataFrame with SWOT_COLUMNS + geometry (EPSG:4326).
    """
    import geopandas as gpd
    from shapely.geometry import Point

    output_dir = Path(output_dir)
    if output_path is None:
        output_path = output_dir / "wris_merged.gpkg"
    output_path = Path(output_path)

    if output_path.exists():
        if not overwrite:
            raise FileExistsError(
                f"{output_path} already exists. Pass overwrite=True to replace."
            )
        output_path.unlink()

    # Locate HydroSwift root for cwc_meta.csv
    if hydroswift_root is None:
        hydroswift_root = Path(__file__).resolve().parent.parent  # swift_app/../
    hydroswift_root = Path(hydroswift_root)

    print("\n" + "=" * 65)
    print("SWOT MERGE — Building unified gauge GeoPackage")
    print(f"  Output dir  : {output_dir.resolve()}")
    print(f"  Output file : {output_path.resolve()}")
    print("=" * 65)

    # ── Load station metadata ──
    cwc_meta = _load_cwc_station_meta(hydroswift_root)
    if not cwc_meta.empty:
        print(f"  ℹ️  CWC metadata loaded: {len(cwc_meta):,} stations")
    else:
        print("  ⚠️  CWC metadata unavailable — station names will fall back to station_code")

    cwc_root = output_dir / "cwc"
    wris_god_dir = output_dir / "wris" / "godavari"
    wris_kri_dir = output_dir / "wris" / "krishna"

    # ── Discover source GPKGs ──
    cwc_gpkgs = _latest_cwc_gpkgs(cwc_root)
    god_wl_gpkg = _latest_gpkg(wris_god_dir, "godavari_water_level_")
    god_q_gpkg = _latest_gpkg(wris_god_dir, "godavari_discharge_")
    kri_wl_gpkg = _latest_gpkg(wris_kri_dir, "krishna_water_level_")
    kri_q_gpkg = _latest_gpkg(wris_kri_dir, "krishna_discharge_")

    print("\n📂 Discovered GPKGs:")
    for p in cwc_gpkgs:
        print(f"  {'CWC water-level':<28}: {p}")
    for label, p in [
        ("Godavari water-level", god_wl_gpkg),
        ("Godavari discharge", god_q_gpkg),
        ("Krishna water-level", kri_wl_gpkg),
        ("Krishna discharge", kri_q_gpkg),
    ]:
        status = str(p) if p else "⚠️  not found"
        print(f"  {label:<28}: {status}")

    # ── Load each source ──
    print("\n📥 Loading sources …")
    frames = []

    for p in cwc_gpkgs:
        frames.append(_load_cwc_gpkg(p, cwc_meta))
    if god_wl_gpkg:
        frames.append(_load_wris_wl_gpkg(god_wl_gpkg, "Godavari", "wris_godavari_water_level", cwc_meta))
    if god_q_gpkg:
        frames.append(_load_wris_discharge_gpkg(god_q_gpkg, "Godavari", "wris_godavari_discharge", cwc_meta))
    if kri_wl_gpkg:
        frames.append(_load_wris_wl_gpkg(kri_wl_gpkg, "Krishna", "wris_krishna_water_level", cwc_meta))
    if kri_q_gpkg:
        frames.append(_load_wris_discharge_gpkg(kri_q_gpkg, "Krishna", "wris_krishna_discharge", cwc_meta))

    frames = [f for f in frames if f is not None and not f.empty]
    if not frames:
        raise RuntimeError(
            "No source GPKGs found under output_dir. "
            "Run HydroSwift download with --merge first."
        )

    # ── Concatenate ──
    master = pd.concat(frames, ignore_index=True)
    print(f"\n  Combined raw rows: {len(master):,}")

    # ── Normalise numerics ──
    for col in ("wse", "discharge", "lat", "lon", "rl"):
        master[col] = pd.to_numeric(master[col], errors="coerce")

    # ── Normalise time ──
    master["time"] = _normalise_time(master["time"])

    # Drop rows without valid time
    n_before = len(master)
    master = master.dropna(subset=["time"])
    n_dropped = n_before - len(master)
    if n_dropped > 0:
        print(f"  Dropped {n_dropped:,} rows with invalid timestamps")

    # ── Compute depth ──
    master["depth"] = _compute_depth(master)

    # ── Deduplicate (station_code, time) keeping WSE-richer source ──
    master["_has_wse"] = master["wse"].notna().astype(int)
    master["_has_q"] = master["discharge"].notna().astype(int)
    master = master.sort_values(
        ["station_code", "time", "_has_wse", "_has_q"], ascending=[True, True, False, False]
    )
    n_before = len(master)
    master = master.drop_duplicates(subset=["station_code", "time"], keep="first")
    n_dedup = n_before - len(master)
    if n_dedup > 0:
        print(f"  Deduplicated {n_dedup:,} duplicate (station_code, time) rows")
    master = master.drop(columns=["_has_wse", "_has_q"], errors="ignore")

    # ── Enforce SWOT column order ──
    for col in SWOT_COLUMNS:
        if col not in master.columns:
            master[col] = np.nan
    master = master[SWOT_COLUMNS]

    # ── Build GeoDataFrame ──
    geom = [
        Point(lon, lat) if pd.notna(lon) and pd.notna(lat) else None
        for lon, lat in zip(master["lon"], master["lat"])
    ]
    gdf = gpd.GeoDataFrame(master, geometry=geom, crs=DEFAULT_CRS)
    gdf = gdf[gdf.geometry.notna()].copy()

    # ── Sort ──
    gdf = gdf.sort_values(["basin", "station_name", "time"]).reset_index(drop=True)

    # ── Summary ──
    print("\n" + "-" * 65)
    print("SWOT MERGE SUMMARY")
    print("-" * 65)
    print(f"  Total records    : {len(gdf):,}")
    print(f"  Basins           : {sorted(gdf['basin'].dropna().unique())}")
    print(f"  Stations         : {gdf['station_code'].nunique()}")
    if len(gdf):
        print(f"  Date range       : {gdf['time'].min()} → {gdf['time'].max()}")
    print(f"  Records with WSE : {gdf['wse'].notna().sum():,}")
    print(f"  Records with Q   : {gdf['discharge'].notna().sum():,}")
    print(f"  Sources          : {sorted(gdf['source_folder'].unique())}")
    print("-" * 65)

    # ── Write output ──
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(output_path, layer=layer, driver="GPKG")
    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"\n✅ Saved: {output_path}  ({size_mb:.1f} MB, layer='{layer}')")

    return gdf


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build SWOT-ready merged GeoPackage from HydroSwift output."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="HydroSwift output root (default: ./output)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Destination GeoPackage path (default: <output-dir>/wris_merged.gpkg)",
    )
    parser.add_argument(
        "--layer",
        type=str,
        default="wris_merged",
        help="GeoPackage layer name (default: wris_merged)",
    )
    parser.add_argument(
        "--hydroswift-root",
        type=Path,
        default=None,
        help="HydroSwift repo root (for cwc_meta.csv lookup; auto-detected if omitted)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the output file if it already exists",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    build_swot_gpkg(
        output_dir=args.output_dir,
        output_path=args.output,
        hydroswift_root=args.hydroswift_root,
        overwrite=args.overwrite,
        layer=args.layer,
    )


if __name__ == "__main__":
    main()
