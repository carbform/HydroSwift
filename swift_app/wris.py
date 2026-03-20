"""WRIS download pipeline for SWIFT."""

from __future__ import annotations

import glob
import importlib
import os
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pandas as pd

from .utils import Console, Logger, overwrite_tip, coffee_tip


try:
    tqdm = importlib.import_module("tqdm").tqdm
except Exception:
    def tqdm(iterable, **_kwargs):
        return iterable

# ---------------------------------------------------------
# Metadata builder (WRIS + CWC compatible)
# ---------------------------------------------------------
def build_metadata(meta, dataset, source):

    md = {
        "source": source,
        "dataset": dataset,
        "station_code": meta.get("station_code"),
        "station_name": meta.get("station_Name") or meta.get("station_name"),
        "latitude": meta.get("latitude") or meta.get("lat"),
        "longitude": meta.get("longitude") or meta.get("lon"),
        "river": meta.get("riverName") or meta.get("river"),
    }

    if source == "WRIS":
        md["agency"] = meta.get("agencyName")

    if source == "CWC":
        md["rl_zero"] = meta.get("rl_zero")
        md["warning_level"] = meta.get("warning_level")
        md["danger_level"] = meta.get("danger_level")
        md["hfl"] = meta.get("highestFlowLevel") or meta.get("hfl")
        md["hfl_date"] = meta.get("highestFlowLevelDate") or meta.get("hfl_date")

    return md




# ---------------------------------------------------------
# Save station timeseries
# ---------------------------------------------------------

def _save_timeseries(args, base_output, folder, meta, station, dataset, df, var_col):

    station_name = str(meta.get("station_Name", "unknown")).replace("/", "-")
    lat = meta.get("latitude", "")
    lon = meta.get("longitude", "")

    ext = args.format.lower()
    filename = f"{station}_{station_name}_{dataset}.{ext}"

    output_path = os.path.join(base_output, folder, filename)

    if os.path.exists(output_path) and not args.overwrite:
        return None

    df = df.copy()

    # ---------------------------------------------------------
    # Standardize dataframe
    # ---------------------------------------------------------

    df["station_code"] = station
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df = df.dropna(subset=["time"])

    if "value" in df.columns:
        df.rename(columns={"value": var_col}, inplace=True)

    df["lat"] = lat
    df["lon"] = lon

    # Cache unit value (if present) for metadata/header; do not keep as a column.
    unit_value = None
    if "unit" in df.columns:
        non_null_units = df["unit"].dropna().astype(str).unique()
        if len(non_null_units) > 0:
            unit_value = non_null_units[0]

    cols = ["station_code", "time", var_col, "lat", "lon"]
    cols = [c for c in cols if c in df.columns]
    df = df[cols]

    # ---------------------------------------------------------
    # Determine source and build metadata
    # ---------------------------------------------------------

    source = "CWC" if getattr(args, "cwc", False) else "WRIS"

    meta_dict = build_metadata(meta, dataset, source)

    meta_dict["station_code"] = station

    # ---------------------------------------------------------
    # CSV Output
    # ---------------------------------------------------------

    if args.format == "csv":

        header_lines = ["# HydroSwift Hydrological Timeseries"]

        for key, value in meta_dict.items():
            if value is not None and value != "":
                header_lines.append(f"# {key}: {value}")

        # Add variable-specific unit metadata if available, e.g. # unit_solar: W/m2
        if unit_value is not None and var_col:
            header_lines.append(f"# unit_{var_col}: {unit_value}")

        with open(output_path, "w") as f:
            for line in header_lines:
                f.write(line + "\n")

        df.to_csv(output_path, mode="a", index=False)

    # ---------------------------------------------------------
    # Excel Output
    # ---------------------------------------------------------

    else:

        # Include unit metadata in the Excel metadata sheet as well.
        meta_items = [{"field": k, "value": v} for k, v in meta_dict.items() if v is not None]
        if unit_value is not None and var_col:
            meta_items.append({"field": f"unit_{var_col}", "value": unit_value})

        meta_df = pd.DataFrame(meta_items)

        with pd.ExcelWriter(output_path) as writer:
            df.to_excel(writer, sheet_name="timeseries", index=False)
            meta_df.to_excel(writer, sheet_name="metadata", index=False)

    return output_path


# ---------------------------------------------------------
# Basin structure cache
# ---------------------------------------------------------

def build_basin_structure(client, basin_code):

    structure = []

    tributaries = client.get_tributaries(basin_code, "DISCHARG")

    for trib in tributaries:

        trib_id = trib.get("tributaryid")
        rivers = client.get_rivers(trib_id, "DISCHARG")

        for river in rivers:
            structure.append((trib_id, river.get("localriverid")))

    return structure


# ---------------------------------------------------------
# Station discovery
# ---------------------------------------------------------

def discover_stations(client, basin_structure, dataset_code, agency_cache, station_cache):

    stations = set()

    for tributary_id, river_id in basin_structure:

        key = (tributary_id, river_id, dataset_code)

        if key not in agency_cache:
            agency_cache[key] = client.get_agencies(
                tributary_id, river_id, dataset_code
            )

        for agency in agency_cache[key]:

            agency_id = agency.get("agencyid")

            key = (tributary_id, river_id, agency_id)

            if key in station_cache:
                items = station_cache[key]
            else:
                items = client.get_stations(
                    tributary_id,
                    river_id,
                    agency_id,
                    dataset_code
                )
                station_cache[key] = items

            for s in items:
                code = s.get("stationcode")
                if code:
                    stations.add(code)

    return sorted(stations)


# ---------------------------------------------------------
# Resume filter
# ---------------------------------------------------------

def filter_existing_stations(stations, dataset_dir, ext):

    remaining = []

    for s in stations:
        pattern = os.path.join(dataset_dir, f"{s}_*.{ext}")
        if not glob.glob(pattern):
            remaining.append(s)

    return remaining


# ---------------------------------------------------------
# Main download engine
# ---------------------------------------------------------

def run_wris_download(args, selected: dict[str, str], client, basin_code: str):

    import json

    base_output = os.path.join(args.output_dir, "wris", args.basin.lower())
    os.makedirs(base_output, exist_ok=True)
    
    Console.is_quiet = getattr(args, "quiet", False)
    logger = Logger(base_output)
    
    logger.log("INFO", f"Starting WRIS download for basin: {args.basin}")

    metadata_records = {}
    metadata_cache = {}
    summary = []
    lock = Lock()

    # ---------------------------------------------------------
    # Basin structure cache (in-memory)
    # ---------------------------------------------------------

    if not hasattr(client, "_basin_structure_cache"):
        client._basin_structure_cache = {}

    if basin_code not in client._basin_structure_cache:
        client._basin_structure_cache[basin_code] = build_basin_structure(client, basin_code)

    basin_structure = client._basin_structure_cache[basin_code]

    agency_cache = {}
    station_cache = {}

    # ---------------------------------------------------------
    # Basin station cache (disk)
    # ---------------------------------------------------------

    cache_file = os.path.join(base_output, "_station_tree.json")

    if os.path.exists(cache_file):
        try:
            with open(cache_file) as f:
                basin_station_cache = json.load(f)
        except Exception:
            basin_station_cache = {}
    else:
        basin_station_cache = {}

    cache_updated = False

    def _station_slug(codes):
        clean = []
        seen = set()
        for code in codes or []:
            norm = str(code).strip().lower()
            if not norm or norm in seen:
                continue
            seen.add(norm)
            clean.append(norm)
        if not clean:
            return ""
        if len(clean) == 1:
            return clean[0]
        head = "_".join(clean[:3])
        if len(clean) > 3:
            return f"stations_{head}_plus{len(clean) - 3}"
        return f"stations_{head}"

    # ---------------------------------------------------------
    # Estimate total runtime across all datasets
    # ---------------------------------------------------------

    total_stations = 0
    station_filter = getattr(args, "stations", None)
    # Normalise to set for O(1) lookup; use lowercased for case-insensitive match
    # so DataFrame codes (e.g. "007-ugdhyd") match API/cache codes (e.g. "007-UGDHYD").
    station_filter_norm = None
    if station_filter:
        station_filter_norm = {str(s).strip().lower() for s in station_filter}

    def _station_in_filter(code):
        if not station_filter_norm:
            return True
        return (str(code).strip().lower() if code else "") in station_filter_norm

    for dataset_code in selected.keys():

        if dataset_code in basin_station_cache:
            stations = list(basin_station_cache[dataset_code])
        else:
            stations = discover_stations(
                client,
                basin_structure,
                dataset_code,
                agency_cache,
                station_cache
            )
            basin_station_cache[dataset_code] = stations
            cache_updated = True

        stations_for_run = stations
        if station_filter_norm:
            stations_for_run = [s for s in stations if _station_in_filter(s)]

        total_stations += len(stations_for_run)

    workers = min(8, (os.cpu_count() or 1) * 2)
    est_runtime = int(total_stations * args.delay / max(workers, 1))

    if est_runtime > 600 and not Console.is_quiet:
        mins = est_runtime // 60
        Console.info(f"Estimated total runtime: ~{mins} minutes ({total_stations} stations)")
        print(f"{Console.ITALIC}{coffee_tip(args)}{Console.RESET}")

    for dataset_code, folder in selected.items():

        from .cli import DATASET_COLUMNS
        from .merge import merge_dataset_folder, merge_dataset_files

        var_col = DATASET_COLUMNS.get(dataset_code, "value")

        Console.section(f"Dataset: {folder}")
        logger.log("INFO", f"Processing dataset: {folder}")

        dataset_start = time.time()

        # ---------------------------------------------------------
        # Station discovery with disk cache
        # ---------------------------------------------------------

        if dataset_code in basin_station_cache:

            stations = list(basin_station_cache[dataset_code])
            Console.info("Using cached station discovery")

        else:

            stations = discover_stations(
                client,
                basin_structure,
                dataset_code,
                agency_cache, station_cache
            )

            basin_station_cache[dataset_code] = stations
            cache_updated = True
            logger.log("INFO", f"Discovered {len(stations)} stations from WRIS API")

        stations_for_run = stations
        if station_filter_norm:
            stations_for_run = [s for s in stations if _station_in_filter(s)]

        dataset_dir = os.path.join(base_output, folder)
        os.makedirs(dataset_dir, exist_ok=True)

        ext = args.format.lower()

        if args.overwrite:
            station_list = stations_for_run
        else:
            station_list = filter_existing_stations(stations_for_run, dataset_dir, ext)

        remaining = len(station_list)
        skipped = 0 if args.overwrite else len(stations_for_run) - remaining


        if skipped > 0:
            Console.warn(f"Stations skipped (already downloaded): {skipped}")
            if not Console.is_quiet:
                print(f"{Console.ITALIC}{overwrite_tip(args)}{Console.RESET}")
            logger.log("INFO", f"Skipped {skipped} existing stations")

        counter = {"downloaded": 0, "failed_or_empty": 0}
        downloaded_files = []

        # ---------------------------------------------------------
        # Worker
        # ---------------------------------------------------------

        def worker(station_code):

            if station_code in metadata_cache:
                meta = metadata_cache[station_code]
            else:
                meta = client.get_metadata(station_code, dataset_code)
                if not meta:
                    with lock:
                        counter["failed_or_empty"] += 1
                    logger.log("WARN", f"No metadata found for station: {station_code}")
                    return
                metadata_cache[station_code] = meta

            frame = client.get_timeseries(
                station_code,
                dataset_code,
                start_date=args.start_date,
                end_date=args.end_date,
            )

            if frame is None or frame.empty:
                with lock:
                    counter["failed_or_empty"] += 1
                logger.log("WARN", f"No data returned for station: {station_code}")
                return

            outfile = _save_timeseries(
                args,
                base_output,
                folder,
                meta,
                station_code,
                dataset_code,
                frame,
                var_col,
            )

            if outfile:
                with lock:
                    metadata_records[station_code] = meta
                    counter["downloaded"] += 1
                    downloaded_files.append(outfile)
                logger.log("SUCCESS", f"Downloaded {station_code} -> {os.path.basename(outfile)}")
            else:
                with lock:
                    counter["failed_or_empty"] += 1
                logger.log("WARN", f"Failed to save output for station: {station_code}")

        # ---------------------------------------------------------
        # Parallel download
        # ---------------------------------------------------------

        if remaining > 0:

            max_workers = min(8, (os.cpu_count() or 1) * 2)

            with ThreadPoolExecutor(max_workers=max_workers) as executor:

                futures = [executor.submit(worker, s) for s in station_list]

                for f in tqdm(
                    futures,
                    total=len(futures),
                    desc=f"{folder}",
                    unit="station",
                    leave=True,
                    dynamic_ncols=True,
                    disable=Console.is_quiet
                ):
                    f.result()

        else:
            Console.info("All stations already downloaded — skipping download step.")

        # ---------------------------------------------------------
        # Merge (only newly downloaded files; gpkg name includes time period)
        # ---------------------------------------------------------

        if args.merge:

            start_slug = (args.start_date or "1950-01-01")[:10]
            end_slug = (args.end_date or "").strip()[:10] or time.strftime("%Y-%m-%d")

            name_by = str(getattr(args, "name_by", "") or "").strip().lower()
            station_name_slug = _station_slug(station_filter)
            basin_name_slug = str(args.basin).strip().lower()

            if name_by == "station":
                gpkg_basename = station_name_slug or basin_name_slug
            elif name_by == "basin":
                gpkg_basename = basin_name_slug or station_name_slug
            elif station_filter and len(station_filter) == 1:
                gpkg_basename = station_name_slug
            else:
                gpkg_basename = basin_name_slug

            gpkg_path = os.path.join(
                base_output,
                f"{gpkg_basename}_{folder}_{start_slug}_{end_slug}.gpkg",
            )

            if counter["downloaded"] == 0 and len(stations_for_run) > 0:
                # Only warn when user provided a station list (e.g. from fetch(stations));
                # direct wris.download() discovers stations itself, so no time-period warning.
                if station_filter_norm and not Console.is_quiet:
                    Console.warn(
                        "No stations found with data in the requested time period; "
                        "skipping merge for this dataset."
                    )
                logger.log("WARN", "No data in requested time period; skipping merge")
            elif counter["downloaded"] == 0 and os.path.exists(gpkg_path):
                Console.info(
                    f"Using cached GeoPackage for {folder} ({start_slug} to {end_slug})"
                )
            elif counter["downloaded"] > 0:
                logger.log(
                    "INFO",
                    f"Merging {len(downloaded_files)} file(s) to GeoPackage ({start_slug} to {end_slug})",
                )
                merge_dataset_files(downloaded_files, gpkg_path, folder)

        runtime = round(time.time() - dataset_start, 1)

        if counter["downloaded"] > 0:
            if not Console.is_quiet:
                print()
            Console.success(f"{folder} downloaded in {runtime} seconds")

        selected = len(stations_for_run)
        attempted = remaining

        summary.append({
            "dataset": folder,
            "selected": selected,
            "attempted": attempted,
            "downloaded": counter["downloaded"],
            "skipped": skipped,
            "failed_or_empty": counter["failed_or_empty"],
            "time": runtime
        })
        
        logger.log(
            "INFO",
            (
                f"Finished {folder}: "
                f"Selected {selected}, Attempted {attempted}, "
                f"Downloaded {counter['downloaded']}, Skipped {skipped}, "
                f"NoData/Failed {counter['failed_or_empty']} in {runtime}s"
            ),
        )

    # ---------------------------------------------------------
    # Save updated station cache
    # ---------------------------------------------------------

    if cache_updated:
        try:
            with open(cache_file, "w") as f:
                json.dump(basin_station_cache, f)
        except Exception:
            pass

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    if not Console.is_quiet:
        print("\n-------------------------------------------------------------")
        print("Download Summary")
        print("-------------------------------------------------------------")
        print(
            f"{'Dataset':<18}"
            f"{'Selected':<10}"
            f"{'Attempted':<11}"
            f"{'Downloaded':<12}"
            f"{'Skipped':<9}"
            f"{'NoData/Fail':<13}"
            f"{'Time(s)'}"
        )
        print("-------------------------------------------------------------")

        for item in summary:
            print(
                f"{item['dataset']:<18}"
                f"{item['selected']:<10}"
                f"{item['attempted']:<11}"
                f"{item['downloaded']:<12}"
                f"{item['skipped']:<9}"
                f"{item['failed_or_empty']:<13}"
                f"{item['time']}"
            )

        print("-------------------------------------------------------------")
        print(f"Output directory: {base_output}")
        print("-------------------------------------------------------------")

    return summary