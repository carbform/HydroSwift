from __future__ import annotations

import glob
import os
import pandas as pd
import importlib


def merge_dataset_files(file_paths: list[str], gpkg_path: str, layer: str) -> int:
    """Merge a list of station CSV/XLSX files into a single GeoPackage.

    Use this when only the files from the current run should be merged
    (e.g. time-period-specific gpkg). File paths must point to existing files.
    """
    if not file_paths:
        return 0

    frames = []
    for f in file_paths:
        if not os.path.isfile(f):
            continue
        try:
            if f.endswith(".csv"):
                df = pd.read_csv(f, comment="#")
            else:
                df = pd.read_excel(f)

            if {"lat", "lon"}.issubset(df.columns):
                frames.append(df)

        except Exception:
            continue

    if not frames:
        return 0

    merged = pd.concat(frames, ignore_index=True)
    merged["lat"] = pd.to_numeric(merged["lat"], errors="coerce")
    merged["lon"] = pd.to_numeric(merged["lon"], errors="coerce")
    mask = merged["lat"].notna() & merged["lon"].notna()

    gpd = importlib.import_module("geopandas")
    gdf = gpd.GeoDataFrame(
        merged[mask],
        geometry=gpd.points_from_xy(
            merged.loc[mask, "lon"],
            merged.loc[mask, "lat"]
        ),
        crs="EPSG:4326"
    )
    rows = len(gdf)
    gdf.to_file(gpkg_path, layer=layer, driver="GPKG")
    print(f"Saved GeoPackage: {gpkg_path} ({rows} rows)")
    return rows


def merge_dataset_folder(dataset_dir: str, gpkg_path: str, layer: str) -> int:

    files = glob.glob(os.path.join(dataset_dir, "*.csv"))
    files += glob.glob(os.path.join(dataset_dir, "*.xlsx"))

    if not files:
        print("No station files found:", dataset_dir)
        return 0

    frames = []

    for f in files:
        try:
            if f.endswith(".csv"):
                # New SWIFT CSV format has \"#\" metadata lines before the
                # actual header. Treat them as comments so pandas skips them.
                df = pd.read_csv(f, comment="#")
            else:
                df = pd.read_excel(f)

            if {"lat", "lon"}.issubset(df.columns):
                frames.append(df)

        except Exception:
            continue

    if not frames:
        print("No valid station files with coordinates.")
        return 0

    merged = pd.concat(frames, ignore_index=True)

    merged["lat"] = pd.to_numeric(merged["lat"], errors="coerce")
    merged["lon"] = pd.to_numeric(merged["lon"], errors="coerce")

    mask = merged["lat"].notna() & merged["lon"].notna()

    gpd = importlib.import_module("geopandas")

    gdf = gpd.GeoDataFrame(
        merged[mask],
        geometry=gpd.points_from_xy(
            merged.loc[mask, "lon"],
            merged.loc[mask, "lat"]
        ),
        crs="EPSG:4326"
    )

    rows = len(gdf)

    gdf.to_file(gpkg_path, layer=layer, driver="GPKG")

    print(f"Saved GeoPackage: {gpkg_path} ({rows} rows)")

    return rows

   
def run_merge_only(args):

    import os
    from pathlib import Path
    from .cli import DATASETS, selected_datasets
    from .merge import merge_dataset_folder

    if not args.input_dir:
        raise SystemExit("--merge-only requires input_dir")

    root = Path(args.input_dir)

    if not root.exists():
        raise SystemExit("Input directory not found")

    dataset_names = {folder for _, folder in DATASETS.values()}

    output_base = Path(args.output_dir) if args.output_dir else root
    try:
        output_base.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        raise PermissionError(
            f"Cannot create output directory: {output_base}. "
            "Check that the path exists and you have write permissions."
        ) from exc
    except OSError as exc:
        raise OSError(
            f"Failed to prepare output directory: {output_base}. "
            f"Original error: {exc}"
        ) from exc

    # ---------------------------------------------------------
    # CWC mode: merge from cwc/stations and cwc/<basin>/stations
    # ---------------------------------------------------------
    if getattr(args, "cwc", False):
        cwc_root = root / "cwc"
        if not cwc_root.exists() or not cwc_root.is_dir():
            print("No CWC output found:", cwc_root)
            return 0

        # Collect all dirs that contain station CSVs/XLSX (flat or basin-aware)
        station_dirs = []
        legacy_stations = cwc_root / "stations"
        if legacy_stations.exists() and legacy_stations.is_dir():
            station_dirs.append((str(legacy_stations), "cwc_waterlevel", "cwc_waterlevel"))
        for sub in cwc_root.iterdir():
            if sub.is_dir() and sub.name != "stations":
                stations_sub = sub / "stations"
                if stations_sub.exists() and stations_sub.is_dir():
                    basin_slug = sub.name
                    layer = "cwc_waterlevel"
                    gpkg_name = f"cwc_waterlevel_{basin_slug}.gpkg"
                    station_dirs.append((str(stations_sub), gpkg_name, layer))

        cwc_out = output_base / "cwc"
        cwc_out.mkdir(parents=True, exist_ok=True)
        for dataset_dir, gpkg_name, layer in station_dirs:
            gpkg_path = cwc_out / gpkg_name
            merge_dataset_folder(dataset_dir, str(gpkg_path), layer)
        return 0

    # ---------------------------------------------------------
    # WRIS: detect basin directories
    # ---------------------------------------------------------

    wris_root = root / "wris"
    if wris_root.exists() and wris_root.is_dir():
        wris_input_root = wris_root
    else:
        wris_input_root = root

    if any((wris_input_root / d).is_dir() and d in dataset_names for d in os.listdir(wris_input_root)):
        basin_dirs = [wris_input_root]
    else:
        basin_dirs = [d for d in wris_input_root.iterdir() if d.is_dir()]

    selected = selected_datasets(args)

    # ---------------------------------------------------------
    # Merge WRIS datasets (save under output_base/wris/, like plot)
    # ---------------------------------------------------------

    wris_out = output_base / "wris"
    wris_out.mkdir(parents=True, exist_ok=True)

    for basin_dir in basin_dirs:

        basin = basin_dir.name

        if not selected:
            dataset_dirs = [
                d for d in basin_dir.iterdir()
                if d.is_dir()
            ]
        else:
            dataset_dirs = [
                basin_dir / folder
                for _, folder in selected.items()
            ]

        for d in dataset_dirs:

            if not d.exists():
                if selected:
                    print(f"Dataset '{d.name}' not found in basin: {basin}")
                continue

            gpkg_path = wris_out / f"{basin}_{d.name}.gpkg"

            merge_dataset_folder(str(d), str(gpkg_path), d.name)

    return 0