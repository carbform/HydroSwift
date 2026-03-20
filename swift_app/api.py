"""
Public Python API for HydroSwift.

Namespaced access (preferred):
    hydroswift.wris.download(basin, variable, ...)
    hydroswift.wris.stations(basin, ...)
    hydroswift.cwc.download(station, ...)
    hydroswift.cwc.stations(...)

Top-level helpers:
    hydroswift.fetch(source, ...)
    hydroswift.merge_only(...)
    hydroswift.plot_only(...)
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import time

from .wris_client import WrisClient
from .cli import DATASETS, WRIS_BASINS
from .wris import run_wris_download, build_basin_structure, discover_stations
from .merge import run_merge_only
from .plot import run_plot_only
from .cwc import (
    run_cwc_download,
    get_cwc_station_metadata,
    repopulate_cwc_metadata_from_name_code,
)


# ---------------------------------------------------------
# Python help and CLI help bridge
# ---------------------------------------------------------

PYTHON_HELP_TEXT = """HydroSwift Python API help

Quick start:
    import hydroswift

Core namespaces:
    hydroswift.wris.variables()            # WRIS variable catalog
    hydroswift.wris.basins(variable=None)  # WRIS basins table
    hydroswift.wris.stations(basin, variable)   # WRIS station discovery table
    hydroswift.wris.download(...)               # WRIS download (explicit args)

    hydroswift.cwc.basins()                     # CWC basin summary
    hydroswift.cwc.stations(...)                # CWC station metadata table
    hydroswift.cwc.download(...)                # CWC download (explicit args)

Unified table workflow:
    hydroswift.fetch(table, ...)           # Download from WRIS/CWC station/basin tables

Post-processing helpers:
    hydroswift.merge_only(...)
    hydroswift.plot_only(...)

Utilities:
    hydroswift.help()                           # this Python API help menu
    hydroswift.cli_help()                       # CLI help (equivalent to `hyswift -h`)
    hydroswift.cite()
    hydroswift.coffee()
"""

def cli_help():
    """Print the command-line help text (equivalent to ``hyswift -h``)."""
    from .cli import build_parser

    parser = build_parser()
    parser.print_help()
    return None


def help():
    """Print Python API help text.

    Use :func:`cli_help` when you want the CLI parser menu from Python.
    """
    print(PYTHON_HELP_TEXT)
    return None


# ---------------------------------------------------------
# Dataset aliases  (human-friendly → CLI flag)
# ---------------------------------------------------------

DATASET_ALIAS = {
    "discharge": "q",
    "water_level": "wl",
    "atm_pressure": "atm",
    "atmospheric_pressure": "atm",
    "rainfall": "rf",
    "temperature": "temp",
    "humidity": "rh",
    "solar": "solar",
    "solar_radiation": "solar",
    "sediment": "sed",
    "groundwater": "gwl",
    "groundwater_level": "gwl",
}

# Approximate WRIS variable → unit mapping for in-memory convenience.
# This is used only to populate gdf.attrs["units"] on concatenated
# GeoDataFrames returned by the high-level Python API; files on disk
# still carry the authoritative metadata in their headers.
WRIS_UNITS: dict[str, str] = {
    "discharge": "m3/s",
    "q": "m3/s",
    "water_level": "m",
    "wl": "m",
    "rainfall": "mm",
    "rf": "mm",
    "temperature": "degC",
    "temp": "degC",
    "solar": "W/m2",
    "solar_radiation": "W/m2",
    "sediment": "mg/l",
    "sed": "mg/l",
    "gwl": "m",
}


# ---------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------

def _normalize_datasets_input(datasets):
    if datasets is None:
        return []
    if isinstance(datasets, str):
        datasets = [datasets]
    return list(datasets)


def _normalize_cwc_station_input(cwc_station):
    if cwc_station is None:
        return None
    if isinstance(cwc_station, pd.DataFrame):
        if "code" in cwc_station.columns:
            vals = cwc_station["code"].tolist()
        elif "station_code" in cwc_station.columns:
            vals = cwc_station["station_code"].tolist()
        else:
            raise ValueError(
                "Table-like station input must include a 'code' column "
                "(or 'station_code')."
            )
        out = [str(v).strip() for v in vals if str(v).strip()]
        return out or None
    if isinstance(cwc_station, pd.Series):
        out = [str(v).strip() for v in cwc_station.tolist() if str(v).strip()]
        return out or None
    if isinstance(cwc_station, (str, int)):
        return [str(cwc_station)]
    return [str(x) for x in cwc_station]


def _normalize_wris_station_input(station):
    """Normalise WRIS station input to a list of codes or None."""
    if station is None:
        return None
    if isinstance(station, (str, int)):
        return [str(station)]
    return [str(x) for x in station]


def _normalize_cwc_basin_input(basin):
    """Normalise CWC basin filters from scalar/list/table-like inputs.

    Accepts:
    - str / scalar basin names
    - list/tuple/set of basin names
    - pandas Series of basin names
    - pandas DataFrame (or SwiftTable) containing a ``basin`` column
    """
    if basin is None:
        return []

    # Table-like input (e.g., hydroswift.cwc.basins()[0:3]).
    if isinstance(basin, pd.DataFrame):
        if "basin" not in basin.columns:
            raise ValueError(
                "Table-like basin input must include a 'basin' column. "
                "Use hydroswift.cwc.basins() or pass basin names directly."
            )
        vals = basin["basin"].tolist()
        return [str(b).strip() for b in vals if str(b).strip()]

    # Series input (e.g., df['basin']).
    if isinstance(basin, pd.Series):
        vals = basin.tolist()
        return [str(b).strip() for b in vals if str(b).strip()]

    if isinstance(basin, str):
        return [basin.strip()] if basin.strip() else []

    if isinstance(basin, (list, tuple, set)):
        return [str(b).strip() for b in basin if str(b).strip()]

    one = str(basin).strip()
    return [one] if one else []


def _normalize_dataset_flags(datasets):
    if not datasets:
        return []
    flags = []
    for d in datasets:
        if d in DATASET_ALIAS:
            flags.append(DATASET_ALIAS[d])
        elif d in DATASET_ALIAS.values():
            flags.append(d)
        else:
            valid = sorted(DATASET_ALIAS.keys()) + sorted(DATASET_ALIAS.values())
            raise ValueError(
                f"Unknown dataset: {d}. Supported values: {', '.join(valid)}"
            )
    return flags


def _unique_preserve_order(values):
    """Return de-duplicated non-empty string values preserving first-seen order."""
    seen = set()
    out = []
    for v in values:
        s = str(v).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _build_args(**kwargs):
    args = SimpleNamespace()
    args.basin = kwargs.get("basin")
    args.start_date = kwargs.get("start_date", "1950-01-01")
    args.end_date = kwargs.get("end_date") or time.strftime("%Y-%m-%d")
    args.merge = kwargs.get("merge", False)
    args.merge_only = kwargs.get("merge_only", False)
    args.plot_only = kwargs.get("plot_only", False)
    args.overwrite = kwargs.get("overwrite", False)
    args.output_dir = kwargs.get("output_dir")
    args.input_dir = kwargs.get("input_dir")
    args.delay = kwargs.get("delay", 0.25)
    args.format = kwargs.get("format", "csv")
    args.plot = kwargs.get("plot", False)
    args.plot_svg = kwargs.get("plot_svg", False)
    args.plot_moving_average_window = kwargs.get("plot_moving_average_window")
    args.metadata = kwargs.get("metadata", False)
    args.quiet = kwargs.get("quiet", False)
    args.cwc = kwargs.get("cwc", False)
    args.cwc_station = kwargs.get("cwc_station")
    args.cwc_basin_filter = kwargs.get("cwc_basin_filter")
    args.stations = kwargs.get("stations")
    args.cwc_refresh = kwargs.get("cwc_refresh", False)
    args.name_by = kwargs.get("name_by")
    args.gpkg_group = kwargs.get("gpkg_group")
    args.interface = kwargs.get("interface", "python")
    dataset_keys = ["q", "wl", "atm", "rf", "temp", "rh", "solar", "sed", "gwl"]
    for key in dataset_keys:
        setattr(args, key, False)
    for flag in kwargs.get("dataset_flags", []):
        setattr(args, flag, True)
    return args


def _resolve_basin(basin):
    """Normalise basin input (int / number-string / name) to a basin name."""
    if isinstance(basin, (list, tuple, set)):
        raise ValueError(
            "basin must be a single basin value here. "
            "For multiple basins, pass a list to hydroswift.wris.stations() or hydroswift.wris.download()."
        )
    if isinstance(basin, int):
        basin = str(basin)
    if basin in WRIS_BASINS:
        return WRIS_BASINS[basin]
    return basin


# ============================================================
# PRIMARY PUBLIC API
# ============================================================


def get_wris_data(
    var,
    basin,
    *,
    station=None,
    start_date="1950-01-01",
    end_date=None,
    output_dir="output",
    format="csv",
    overwrite=False,
    merge=False,
    plot=False,
    delay=0.25,
    quiet=False,
    name_by=None,
):
    """
    Download WRIS time-series data to files.

    Parameters
    ----------
    var : str or list[str]
        Variable(s) to download.  Accepts human-friendly names
        (``'discharge'``, ``'water_level'``, ``'rainfall'``, etc.)
        or short codes (``'q'``, ``'wl'``, ``'rf'``).
    basin : str or int
        Basin name or number (see ``hydroswift.wris.basins()``).
    station : str or list[str], optional
        Limit to specific station code(s).
    start_date, end_date : str
        ISO date strings (``'YYYY-MM-DD'``).
    output_dir : str
        Root output directory.
    format : ``'csv'`` | ``'xlsx'``
    overwrite : bool
        Re-download existing files.
    merge : bool
        Merge station files into a GeoPackage.
    plot : bool
        Generate hydrograph plots after download.
    delay : float
        Seconds between WRIS API requests.
    quiet : bool
        Suppress progress output.

    Examples
    --------
    >>> hydroswift.wris.download(basin='Krishna', variable='discharge')
    >>> hydroswift.wris.download(basin=6, variable=['discharge', 'rainfall'],
    ...                     start_date='2020-01-01', merge=True)
    """
    if isinstance(basin, (list, tuple, set)):
        basins = list(basin)
        if not basins:
            raise ValueError("basin must include at least one basin")
        # Multi-basin: concatenate all returned GeoDataFrames (when merge=True).
        try:
            import pandas as _pd  # type: ignore[import]
        except Exception:
            _pd = None
        frames = []
        for one_basin in basins:
            res = get_wris_data(
                var=var,
                basin=one_basin,
                station=station,
                start_date=start_date,
                end_date=end_date,
                output_dir=output_dir,
                format=format,
                overwrite=overwrite,
                merge=merge,
                plot=plot,
                delay=delay,
                quiet=quiet,
                name_by=name_by,
            )
            if res is None or _pd is None:
                continue
            # Normalise res to DataFrame
            if hasattr(res, "assign"):
                frames.append(res.assign(basin=str(one_basin)))
        if not frames or _pd is None:
            return None
        combined = _pd.concat(frames, ignore_index=True)
        # Attach units mapping for downstream analysis (same units across basins).
        vars_list = _normalize_datasets_input(var)
        units_map = {str(v): WRIS_UNITS.get(str(v), "") for v in vars_list}
        combined.attrs["units"] = units_map
        return combined

    datasets = _normalize_datasets_input(var)
    if not datasets:
        raise ValueError("var must specify at least one dataset")

    dataset_flags = _normalize_dataset_flags(datasets)
    if format not in {"csv", "xlsx"}:
        raise ValueError("format must be one of: csv, xlsx")

    basin_name = _resolve_basin(basin)
    stations = _normalize_wris_station_input(station)

    # Always enable on-disk GeoPackage merging; the *merge* flag controls
    # only whether a concatenated GeoDataFrame is returned from this
    # Python API, not whether files are merged on disk.
    args = _build_args(
        basin=basin_name,
        start_date=start_date,
        end_date=end_date,
        merge=True,
        overwrite=overwrite,
        output_dir=str(Path(output_dir)),
        delay=delay,
        format=format,
        plot=plot,
        quiet=quiet,
        dataset_flags=dataset_flags,
        stations=stations,
        name_by=name_by,
    )

    client = WrisClient(delay=delay)
    if not client.check_api():
        raise RuntimeError("WRIS API unavailable")

    basin_code = client.get_basin_code(args.basin)

    selected = {}
    for flag in dataset_flags:
        dataset_code, folder = DATASETS[flag]
        selected[dataset_code] = folder

    if not selected:
        raise ValueError("No datasets selected")

    # Early user feedback so notebooks show that work has started.
    try:
        var_desc = ", ".join(datasets)
        print(
            f"Searching WRIS database for basin={basin_name!r}, "
            f"Variables={var_desc} "
            f"from {start_date or '1950-01-01'} to {end_date or 'latest'}..."
            f"This might take a while..."
        )
    except Exception:
        # Best-effort only; never fail because of a progress message.
        pass

    summary = run_wris_download(args, selected, client, basin_code)

    # Optionally generate plots only for datasets that had data in the
    # requested time period, so we do not plot stale files from earlier runs.
    if plot and summary:
        _plot_func = globals().get("plot")
        if callable(_plot_func):
            folders_with_downloads = {
                item["dataset"] for item in summary
                if item.get("downloaded", 0) > 0
            }
            datasets_with_data = [
                d for d in datasets
                if DATASETS.get(_resolve_variable(d), (None, None))[1] in folders_with_downloads
            ]
            if datasets_with_data:
                basin_dir = Path(output_dir) / "wris" / str(basin_name).lower()
                _plot_func(
                    input_dir=str(basin_dir),
                    variable=datasets_with_data,
                    output_dir=None,
                    cwc=False,
                )

    # Optional in-memory result for WRIS when merge=True:
    # load GeoPackages produced by this run and concatenate.
    if not merge:
        return None

    try:
        import geopandas as gpd  # type: ignore[import]
    except Exception:
        return None

    vars_list = _normalize_datasets_input(var)
    start_slug = (start_date or "1950-01-01")[:10]
    end_slug = (end_date or time.strftime("%Y-%m-%d"))[:10]

    frames = []
    basin_label = str(basin_name)
    basin_dir_candidates = [
        Path(output_dir) / "wris" / basin_label.lower(),
        Path(output_dir) / "wris" / basin_label,
    ]
    # Preserve order while removing duplicates.
    basin_dir_candidates = list(dict.fromkeys(basin_dir_candidates))

    for v in vars_list:
        try:
            flag = _resolve_variable(v)
            folder = DATASETS[flag][1]
        except Exception:
            continue

        gpkg_candidates = []
        for basin_dir in basin_dir_candidates:
            gpkg_candidates.extend(
                [
                    basin_dir / f"{basin_label.lower()}_{folder}_{start_slug}_{end_slug}.gpkg",
                    basin_dir / f"{basin_label}_{folder}_{start_slug}_{end_slug}.gpkg",
                ]
            )

        # Preserve order while removing duplicate path candidates.
        gpkg_candidates = list(dict.fromkeys(gpkg_candidates))
        gpkg_path = next((p for p in gpkg_candidates if p.exists()), None)

        # Last-resort fallback: look for any matching dataset-period gpkg in
        # basin-scoped folders (covers legacy/custom naming).
        if gpkg_path is None:
            suffix = f"_{folder}_{start_slug}_{end_slug}.gpkg"
            for basin_dir in basin_dir_candidates:
                if not basin_dir.exists():
                    continue
                matches = sorted([p for p in basin_dir.glob(f"*{suffix}") if p.is_file()])
                if matches:
                    gpkg_path = matches[0]
                    break

        if gpkg_path is None:
            continue
        try:
            gdf = gpd.read_file(gpkg_path)
        except Exception:
            continue
        # Ensure basin / variable columns are present for downstream analysis.
        gdf = gdf.assign(basin=str(basin_name), variable=str(v))
        frames.append(gdf)

    if not frames:
        return None
    import pandas as _pd  # type: ignore[import]
    gdf_all = _pd.concat(frames, ignore_index=True)
    # Attach units mapping for downstream analysis.
    units_map = {str(v): WRIS_UNITS.get(str(v), "") for v in vars_list}
    gdf_all.attrs["units"] = units_map
    return gdf_all


def get_cwc_data(
    station=None,
    *,
    var=None,
    basin=None,
    start_date=None,
    end_date=None,
    output_dir="output",
    format="csv",
    overwrite=False,
    merge=False,
    plot=False,
    quiet=False,
    refresh=False,
    name_by=None,
    gpkg_group=None,
):
    """
    Download CWC water-level time-series data to files.

    The CWC flood-forecasting network only provides **water level**
    data.  If ``var`` is passed with any other value a warning is
    issued and the argument is ignored.

    Parameters
    ----------
    station : str or list[str], optional
        CWC station code(s).  Downloads all stations when omitted.
    basin : str or list[str], optional
        Basin name filter(s), case-insensitive substring match against
        CWC station metadata. When provided, download is restricted to
        matching stations (similar to ``fetch()`` behavior). Files are
        saved under basin-aware folders when a single basin is requested.
    var : ignored
        Accepted for API symmetry with :func:`get_wris_data` but CWC
        only provides water level.  A warning is raised if a non-water-
        level value is supplied.
    start_date, end_date : str, optional
        ISO date strings.
    output_dir : str
        Root output directory.
    format : ``'csv'`` | ``'xlsx'``
    overwrite : bool
        Re-download existing files.
    merge : bool
        Merge station files into a GeoPackage.
    plot : bool
        Generate hydrograph plots after download.
    quiet : bool
        Suppress progress output.
    refresh : bool
        Refresh CWC station metadata from the live API before
        downloading.

    Examples
    --------
    >>> hydroswift.cwc.download()
    >>> hydroswift.cwc.download(station='032-LGDHYD', start_date='2020-01-01')
    """
    # Early user feedback so notebooks show that work has started.
    try:
        print(
            f"Starting CWC download for station={station!r} "
            f"from {start_date or '1950-01-01'} to {end_date or 'latest'}..."
        )
    except Exception:
        pass

    if var is not None:
        allowed = {"water_level", "wl"}
        given = {var} if isinstance(var, str) else set(var)
        bad = given - allowed
        if bad:
            warnings.warn(
                f"CWC only provides water level data. "
                f"Ignoring unsupported variable(s): {', '.join(sorted(bad))}",
                stacklevel=2,
            )

    if format not in {"csv", "xlsx"}:
        raise ValueError("format must be one of: csv, xlsx")

    cwc_station = _normalize_cwc_station_input(station)

    # Resolve basin filters to station codes so direct namespace calls like
    # swift.cwc.download(basin=["Krishna", "Godavari"], ...) behave like
    # fetch() and WRIS downloads.
    basins = _normalize_cwc_basin_input(basin)

    if basins:
        basin_meta = cwc_stations(basin=basins, refresh=refresh)
        basin_codes = _unique_preserve_order(
            basin_meta["code"].dropna().tolist()
        )

        if not basin_codes:
            raise ValueError(
                "No matching CWC stations found for basin filter: "
                f"{', '.join(basins)}"
            )

        if cwc_station is None:
            cwc_station = basin_codes
        else:
            basin_set = set(basin_codes)
            cwc_station = [code for code in _unique_preserve_order(cwc_station) if code in basin_set]
            if not cwc_station:
                raise ValueError(
                    "No overlap between requested station code(s) and basin filter. "
                    f"Basin filter: {', '.join(basins)}"
                )

    # Preserve existing folder convention for single-basin inputs while still
    # supporting multi-basin filtering in one call.
    basin_arg = basins[0] if len(basins) == 1 else None

    # Always enable on-disk GeoPackage merging; the *merge* flag controls
    # only whether a concatenated GeoDataFrame is returned from this
    # Python API, not whether files are merged on disk.
    args = _build_args(
        cwc=True,
        cwc_station=cwc_station,
        cwc_refresh=refresh,
        basin=basin_arg,
        cwc_basin_filter=basins,
        start_date=start_date or "1950-01-01",
        end_date=end_date,
        overwrite=overwrite,
        merge=True,
        plot=plot,
        output_dir=str(Path(output_dir)),
        format=format,
        quiet=quiet,
        name_by=name_by,
        gpkg_group=gpkg_group,
    )

    run_cwc_download(args)

    # Optional in-memory result for CWC when merge=True:
    # load GeoPackages produced by this run and concatenate.
    if not merge:
        return None

    try:
        import geopandas as gpd  # type: ignore[import]
    except Exception:
        return None

    start_slug = (start_date or "1950-01-01")[:10]
    end_slug = (end_date or time.strftime("%Y-%m-%d"))[:10]
    cwc_root = Path(output_dir) / "cwc"
    if not cwc_root.exists():
        return None

    frames = []
    for gpkg_path in cwc_root.glob("cwc_waterlevel*.gpkg"):
        stem = gpkg_path.stem
        # Only include files matching the requested period.
        if start_slug not in stem or end_slug not in stem:
            continue
        try:
            gdf = gpd.read_file(gpkg_path)
        except Exception:
            continue
        # Infer basin from filename: cwc_waterlevel_<basin>_<start>_<end>
        parts = stem.split("_")
        basin_label = None
        if len(parts) > 3:
            basin_label = "_".join(parts[2:-2])
        gdf = gdf.assign(basin=basin_label)
        frames.append(gdf)

    if not frames:
        return None
    import pandas as _pd  # type: ignore[import]
    gdf_all = _pd.concat(frames, ignore_index=True)
    # Attach simple units metadata for CWC (water level).
    gdf_all.attrs["units"] = {"water_level": "m"}
    return gdf_all


# ---------------------------------------------------------
# Station discovery (internal; use hydroswift.wris.stations / hydroswift.cwc.stations)
# ---------------------------------------------------------

def _resolve_variable(var):
    """Normalise a single variable string to its dataset flag."""
    if var in DATASET_ALIAS:
        return DATASET_ALIAS[var]
    if var in DATASETS:
        return var
    valid = sorted(set(list(DATASET_ALIAS.keys()) + list(DATASETS.keys())))
    raise ValueError(
        f"Unknown variable: {var!r}. Supported values: {', '.join(valid)}"
    )


def _discover_station_codes(client, basin_code, basin_structure, dataset_code):
    """Discover station codes and river-name fallbacks for one (basin, variable).

    Returns ``(station_codes, river_fallback)`` where *station_codes* is a
    sorted list and *river_fallback* maps station_code → river name.
    """
    station_river_fallback: dict[str, str] = {}
    try:
        tributaries = client.get_tributaries(basin_code, dataset_code)
        for trib in tributaries:
            trib_id = trib.get("tributaryid")
            trib_name = (
                trib.get("tributary")
                or trib.get("tributaryName")
                or trib.get("tributaryname")
            )
            rivers = client.get_rivers(trib_id, dataset_code)
            for river in rivers:
                river_id = river.get("localriverid")
                river_name = (
                    river.get("riverName")
                    or river.get("localriver")
                    or river.get("localRiver")
                    or river.get("localrivername")
                    or river.get("river")
                )
                agencies = client.get_agencies(trib_id, river_id, dataset_code)
                for agency in agencies:
                    agency_id = agency.get("agencyid")
                    stations_items = client.get_stations(
                        trib_id, river_id, agency_id, dataset_code,
                    )
                    for s in stations_items:
                        code = s.get("stationcode")
                        if not code:
                            continue
                        label = (
                            river_name
                            or s.get("riverName")
                            or s.get("river")
                            or trib_name
                        )
                        if label and code not in station_river_fallback:
                            station_river_fallback[code] = label
    except Exception:
        pass

    agency_cache: dict = {}
    station_cache: dict = {}

    station_codes = discover_stations(
        client, basin_structure, dataset_code, agency_cache, station_cache,
    )
    return station_codes, station_river_fallback


def wris_stations(basin, var, delay=0.25):
    """
    List available WRIS stations for one or more basins and variables.

    Parameters
    ----------
    basin : str, int, or list
        Basin name(s) or number(s).  Pass a list for multiple basins.
    var : str or list[str]
        Dataset variable(s) (e.g. ``'discharge'``, ``'solar'``).
        Pass a list for multiple variables.
    delay : float
        Seconds between API requests.

    Returns
    -------
    SwiftTable
        DataFrame with columns ``station_code``, ``station_name``,
        ``latitude``, ``longitude``, ``river``, ``basin``, ``variable``.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    print("Searching the WRIS database... This might take a while...")

    # -- normalise inputs to lists --------------------------------
    if var is None:
        raise ValueError("var must be provided (for example: 'discharge' or 'solar').")
    if isinstance(var, str):
        var_list = [v.strip() for v in [var] if v.strip()]
    elif isinstance(var, (list, tuple, set)):
        var_list = [str(v).strip() for v in var if str(v).strip()]
    else:
        var_list = [str(var).strip()]
    if not var_list:
        raise ValueError("var must be provided (for example: 'discharge' or 'solar').")

    if isinstance(basin, (list, tuple, set)):
        basin_list = list(basin)
    else:
        basin_list = [basin]
    if not basin_list:
        raise ValueError("basin must include at least one basin.")

    # -- resolve each variable to its dataset flag and code -------
    var_specs = []
    for v in var_list:
        flag = _resolve_variable(v)
        dataset_code, _ = DATASETS[flag]
        var_specs.append((v, flag, dataset_code))

    # -- resolve each basin name ----------------------------------
    basin_names = [_resolve_basin(b) for b in basin_list]

    client = WrisClient(delay=delay)

    # ── Phase 1: pre-compute per-basin data (shared across variables) ──
    basin_cache: dict[str, tuple] = {}
    for bname in basin_names:
        if bname not in basin_cache:
            basin_code = client.get_basin_code(bname)
            basin_structure = build_basin_structure(client, basin_code)
            basin_cache[bname] = (basin_code, basin_structure)

    # ── Phase 2: discover station codes for each (basin, variable) ──
    combo_data: dict[tuple, tuple] = {}
    all_meta_keys: set[tuple[str, str]] = set()

    for bname in basin_names:
        basin_code, basin_structure = basin_cache[bname]
        for user_var, flag, dataset_code in var_specs:
            station_codes, river_fb = _discover_station_codes(
                client, basin_code, basin_structure, dataset_code,
            )
            combo_data[(bname, user_var)] = (station_codes, river_fb, dataset_code)
            for s in station_codes:
                all_meta_keys.add((s, dataset_code))

    # ── Phase 3: parallel metadata fetch ──
    meta_cache: dict[tuple[str, str], dict | None] = {}

    def _fetch_meta(key):
        s, dc = key
        return key, client.get_metadata(s, dc)

    n_workers = min(8, max(1, len(all_meta_keys)))
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = {pool.submit(_fetch_meta, k): k for k in all_meta_keys}
        for fut in as_completed(futures):
            key, meta = fut.result()
            meta_cache[key] = meta

    # ── Phase 4: assemble records ──
    all_records = []
    for bname in basin_names:
        for user_var, flag, dataset_code in var_specs:
            station_codes, river_fb, dc = combo_data[(bname, user_var)]
            for s in station_codes:
                meta = meta_cache.get((s, dc))
                if not meta:
                    continue
                all_records.append({
                    "station_code": s,
                    "station_name": meta.get("station_Name"),
                    "latitude": meta.get("latitude"),
                    "longitude": meta.get("longitude"),
                    "river": (
                        meta.get("riverName")
                        or meta.get("river")
                        or river_fb.get(s)
                    ),
                    "basin": bname,
                    "variable": user_var,
                })

    df = pd.DataFrame(all_records)
    if df.empty:
        df = pd.DataFrame(
            columns=["station_code", "station_name", "latitude",
                      "longitude", "river", "basin", "variable"]
        )
        var_str = ", ".join(var_list)
        basin_str = ", ".join(basin_names)
        print(f" No s tation found for {var_str} in the seletced {basin_str}")
    else:
        print(
            "The station list returned does not guarantee time series data "
            "availability for all time periods."
        )

    df = df.sort_values(["basin", "variable", "station_code"]).reset_index(drop=True)
    out = SwiftTable(df.copy())
    out.attrs["source"] = "wris"
    out.attrs["fetch_source"] = "wris"
    out.attrs["basin"] = basin_names
    out.attrs["variable"] = var_list

    return out


def cwc_stations(station=None, basin=None, river=None, state=None, refresh=False):
    """
    Return CWC flood-forecast station metadata.

    By default reads the packaged metadata file shipped with HydroSwift
    (fast, no network).  Pass ``refresh=True`` to fetch live data from
    the CWC FFS portal.

    Parameters
    ----------
    station : str, optional
        Station code or partial name.
    basin : str or list[str], optional
        Basin name filter (substring, case-insensitive). Pass a list for multiple basins.
    river : str, optional
        River name filter (substring, case-insensitive).
    state : str or list[str], optional
        State name filter (substring, case-insensitive). Pass a list for multiple states.
    refresh : bool, default False
        If True, fetch fresh metadata from the CWC API (~2 min).
        Metadata is mostly static and only changes when a new HFL is
        recorded, so the packaged file is usually sufficient.

    Returns
    -------
    SwiftTable
        Has ``code``, ``name``, ``basin``, ``state``, ``river``, etc.
        Use with ``swift.fetch(table, ...)``; when the table has a ``basin``
        column, data is saved under ``output_dir/cwc/<basin>/stations/``.

    Examples
    --------
    >>> hydroswift.cwc.stations()
    >>> hydroswift.cwc.stations(station="032-LGDHYD")
    >>> hydroswift.cwc.stations(basin="godavari")
    >>> hydroswift.cwc.stations(basin=["Godavari", "Krishna"], state=["Telangana", "Andhra Pradesh"])
    """
    df = get_cwc_station_metadata(
        station=station,
        basin=basin,
        river=river,
        state=state,
        refresh=refresh,
    )
    out = SwiftTable(df.copy())
    out.attrs["source"] = "cwc"
    out.attrs["fetch_source"] = "cwc"
    if basin is not None:
        out.attrs["basin"] = [basin] if isinstance(basin, str) else list(basin)
    if state is not None:
        out.attrs["state"] = [state] if isinstance(state, str) else list(state)
    if river is not None:
        out.attrs["river"] = river
    return out


# ============================================================
# NAMESPACED API  (preferred public interface)
# ============================================================

class _WrisNamespace:
    """``swift.wris`` namespace for India-WRIS operations."""

    @staticmethod
    def download(
        basin=None,
        variable=None,
        *,
        station=None,
        stations=None,
        start_date="1950-01-01",
        end_date=None,
        output_dir="output",
        format="csv",
        overwrite=False,
        merge=False,
        plot=False,
        delay=0.25,
        quiet=False,
    ):
        """Download WRIS time-series data.

        Parameters
        ----------
        basin : str, int, or list, required
            Basin name/number (or list of basin names/numbers).
        variable : str or list[str]
            Dataset variable(s) (``'discharge'``, ``'rainfall'``, etc.).
        station : str or list[str], optional
            Limit to specific station code(s).
        stations : str or list[str], optional
            Alias for ``station``.
        start_date, end_date : str
            ISO date strings.
        output_dir : str
            Root output directory.
        format : ``'csv'`` | ``'xlsx'``
        overwrite, merge, plot, quiet : bool
        delay : float
            Seconds between API requests.
        """
        if station is not None and stations is not None:
            raise ValueError("Provide only one of 'station' or 'stations', not both.")

        station_input = station if station is not None else stations

        if isinstance(basin, pd.DataFrame) or isinstance(station_input, pd.DataFrame):
            raise TypeError(
                "swift.wris.download() accepts explicit basin/variable/station values only. "
                "For WRIS station/basin tables, use swift.fetch(table, ...)."
            )

        if basin is None:
            raise ValueError(
                "basin is required for swift.wris.download()."
            )

        if variable is None:
            raise ValueError(
                "variable is required for swift.wris.download() when basin is "
                "provided as a name/id."
            )

        return get_wris_data(
            var=variable,
            basin=basin,
            station=station_input,
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir,
            format=format,
            overwrite=overwrite,
            merge=merge,
            plot=plot,
            delay=delay,
            quiet=quiet,
        )

    @staticmethod
    def stations(basin, variable, delay=0.25, state=None):
        """List available WRIS stations for one or more basins/variables.

        Parameters
        ----------
        basin : str, int, or list
            Basin name(s) or number(s).
        variable : str or list[str]
            Dataset variable(s) (e.g. ``'discharge'``, ``'solar'``).
        delay : float
            Seconds between API requests.

        Returns
        -------
        SwiftTable
            Columns: ``station_code``, ``station_name``, ``latitude``,
            ``longitude``, ``river``, ``basin``, ``variable``.
        """
        if state is not None and str(state).strip() != "":
            raise ValueError(
                "state filtering is currently only supported for hydroswift.cwc.stations(). "
                "WRIS station discovery supports basin-level filtering only."
            )
        if variable is None:
            raise ValueError(
                "variable is required for hydroswift.wris.stations() "
                "(for example: 'discharge' or 'solar')."
            )
        if isinstance(variable, str) and not variable.strip():
            raise ValueError(
                "variable is required for hydroswift.wris.stations() "
                "(for example: 'discharge' or 'solar')."
            )
        if isinstance(variable, (list, tuple, set)) and not variable:
            raise ValueError(
                "variable is required for hydroswift.wris.stations() "
                "(for example: 'discharge' or 'solar')."
            )
        return wris_stations(basin=basin, var=variable, delay=delay)

    @staticmethod
    def variables():
        """Return the supported WRIS variables as a table.

        Returns
        -------
        SwiftTable
            Columns: ``flag``, ``dataset_code``, ``folder``, ``canonical_name``,
            ``aliases``.
        """
        canonical_by_flag = {
            "q": "discharge",
            "wl": "water_level",
            "atm": "atm_pressure",
            "rf": "rainfall",
            "temp": "temperature",
            "rh": "humidity",
            "solar": "solar_radiation",
            "sed": "sediment",
            "gwl": "groundwater_level",
        }
        alias_map: dict[str, list[str]] = {}
        for alias, flag in DATASET_ALIAS.items():
            alias_map.setdefault(flag, []).append(alias)

        records = []
        for flag, (dataset_code, folder) in DATASETS.items():
            aliases = sorted(set(alias_map.get(flag, [])))
            records.append(
                {
                    "flag": flag,
                    "dataset_code": dataset_code,
                    "folder": folder,
                    "canonical_name": canonical_by_flag.get(flag, folder),
                    "aliases": aliases,
                }
            )

        out = SwiftTable(pd.DataFrame(records))
        out.attrs["source"] = "wris"
        out.attrs["type"] = "variables"
        return out

    @staticmethod
    def basins(variable=None):
        """Return WRIS basins as a table.

        Parameters
        ----------
        variable : str or list[str], optional
            When provided, expands the table to one row per
            ``(basin, variable)`` pair so it can be passed directly to
            ``hydroswift.fetch(...)`` for full-basin downloads.
        """
        base_records = [{"id": k, "basin": v} for k, v in WRIS_BASINS.items()]

        var_list: list[str] = []
        if variable is not None:
            if isinstance(variable, str):
                raw_vars = [variable]
            elif isinstance(variable, (list, tuple, set)):
                raw_vars = list(variable)
            else:
                raw_vars = [str(variable)]

            for v in raw_vars:
                vv = str(v).strip()
                if not vv:
                    continue
                # Validate variable names/flags early with the same resolver
                # used by download/stations.
                _resolve_variable(vv)
                var_list.append(vv)

            if not var_list:
                raise ValueError(
                    "variable must include at least one valid value "
                    "(for example: 'discharge' or ['solar', 'sediment'])."
                )

        if var_list:
            records = []
            for rec in base_records:
                for v in var_list:
                    records.append({"id": rec["id"], "basin": rec["basin"], "variable": v})
        else:
            records = base_records

        out = SwiftTable(pd.DataFrame(records))
        out.attrs["source"] = "wris"
        out.attrs["fetch_source"] = "wris"
        out.attrs["type"] = "basins"
        out.attrs["basin"] = [rec["basin"] for rec in base_records]
        if var_list:
            out.attrs["variable"] = var_list
        return out


class _CwcNamespace:
    """``swift.cwc`` namespace for CWC flood-forecast operations."""

    @staticmethod
    def download(
        station=None,
        *,
        basin=None,
        start_date=None,
        end_date=None,
        output_dir="output",
        format="csv",
        overwrite=False,
        merge=False,
        plot=False,
        quiet=False,
        refresh=False,
        _name_by=None,
        _gpkg_group=None,
    ):
        """
        Download CWC water-level time-series data.

        Parameters
        ----------
        station : str or list[str], optional
            CWC station code(s). Downloads all when omitted. If both station and basin are provided, only stations in both sets are downloaded.
        basin : str or list[str], optional
            Basin filter(s) for station selection. Supports single or multiple basin names. If provided, only stations matching the basin(s) are downloaded (case-insensitive substring match).
        start_date, end_date : str, optional
            ISO date strings.
        output_dir : str
            Root output directory.
        format : ``'csv'`` | ``'xlsx'``
        overwrite, merge, plot, quiet : bool
        refresh : bool
            Refresh station metadata before downloading.

        Notes
        -----
        - Basin filtering is supported for CWC downloads and is applied before download.
        - If both station and basin are provided, only stations present in both are downloaded.
        - If no stations match the basin filter, a ValueError is raised.
        - Table-like inputs (for example from ``hydroswift.cwc.stations()`` or
          ``hydroswift.cwc.basins()``) should be passed to ``hydroswift.fetch(...)``.
        """
        if isinstance(station, pd.DataFrame) or isinstance(basin, pd.DataFrame):
            raise TypeError(
                "swift.cwc.download() accepts explicit station/basin values only. "
                "For CWC station/basin tables, use swift.fetch(table, ...)."
            )

        return get_cwc_data(
            station=station,
            basin=basin,
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir,
            format=format,
            overwrite=overwrite,
            merge=merge,
            plot=plot,
            quiet=quiet,
            refresh=refresh,
            name_by=_name_by,
            gpkg_group=_gpkg_group,
        )

    @staticmethod
    def stations(station=None, basin=None, river=None, state=None, refresh=False):
        """Return CWC flood-forecast station metadata.

        Returns
        -------
        SwiftTable
        """
        return cwc_stations(
            station=station,
            basin=basin,
            river=river,
            state=state,
            refresh=refresh,
        )

    @staticmethod
    def basins(refresh=False):
        """Return CWC basins with station counts from CWC station metadata.

        Parameters
        ----------
        refresh : bool, default False
            If True, refresh station metadata from the CWC API before
            summarising basins.
        """
        df = get_cwc_station_metadata(refresh=refresh)
        if "basin" not in df.columns:
            out = SwiftTable(pd.DataFrame(columns=["basin", "station_count"]))
            out.attrs["source"] = "cwc"
            out.attrs["fetch_source"] = "cwc"
            out.attrs["type"] = "basins"
            out.attrs["basin"] = []
            return out

        basin_series = (
            df["basin"]
            .fillna("")
            .astype(str)
            .str.strip()
        )
        basin_series = basin_series[basin_series != ""]
        if basin_series.empty:
            out = SwiftTable(pd.DataFrame(columns=["basin", "station_count"]))
            out.attrs["source"] = "cwc"
            out.attrs["fetch_source"] = "cwc"
            out.attrs["type"] = "basins"
            out.attrs["basin"] = []
            return out

        summary = (
            basin_series.value_counts()
            .rename_axis("basin")
            .reset_index(name="station_count")
            .sort_values("basin")
            .reset_index(drop=True)
        )
        out = SwiftTable(summary)
        out.attrs["source"] = "cwc"
        out.attrs["fetch_source"] = "cwc"
        out.attrs["type"] = "basins"
        out.attrs["basin"] = summary["basin"].tolist()
        return out

    @staticmethod
    def refresh_metadata(write=False):
        """Refresh packaged CWC metadata via live API lookups.

        Compares `name-code.csv` codes against the packaged metadata and
        fetches any missing entries from the live CWC API.

        Parameters
        ----------
        write : bool, default False
            If True, overwrite packaged `cwc_meta.csv` with refreshed output.

        Returns
        -------
        SwiftTable
            Refreshed metadata table. Also includes attrs:
            - ``appended_count``: number of rows discovered from name-code.csv
        """
        merged, appended = repopulate_cwc_metadata_from_name_code(write_packaged=write)
        out = SwiftTable(merged.copy())
        out.attrs["source"] = "cwc"
        out.attrs["fetch_source"] = "cwc"
        out.attrs["type"] = "metadata"
        out.attrs["appended_count"] = int(len(appended))
        return out


wris = _WrisNamespace()
cwc_ns = _CwcNamespace()


# ============================================================
# UNIFIED FETCH HELPER
# ============================================================

def fetch(
    stations,
    *,
    output_dir="output",
    start_date="1950-01-01",
    end_date=None,
    format="csv",
    overwrite=False,
    merge=False,
    plot=False,
    quiet=False,
    delay=0.25,
    refresh=False,
):
    """Download data for a HydroSwift table returned by stations/basins helpers.

    Parameters
    ----------
        stations : pandas.DataFrame
                HydroSwift table (typically from ``hydroswift.wris.stations()``,
                ``hydroswift.cwc.stations()``, ``hydroswift.wris.basins(variable=...)`` or
                ``hydroswift.cwc.basins()``).

                - WRIS station tables include ``station_code`` and optionally
                    per-row ``basin``/``variable`` columns.
                - WRIS basin tables are basin-level inputs and require variable
                    information either in a ``variable`` column or
                    ``stations.attrs['variable']``.
                - CWC station tables include ``code``.
                - CWC basin tables include basin information (column or attrs),
                    and fetch expands to all stations in each basin.
    output_dir : str
        Root output directory.
    start_date, end_date : str
        ISO date strings.
    format : ``'csv'`` | ``'xlsx'``
    overwrite, merge, plot, quiet : bool
    delay : float
        WRIS request delay in seconds.
    refresh : bool
        CWC metadata refresh flag before download.
    """
    # Early user feedback so notebooks show that work has started.
    try:
        n = getattr(stations, "shape", (len(stations),))[0] if hasattr(stations, "__len__") else "unknown"
        print(
            f"Starting fetch for stations table (rows={n}) "
            f"from {start_date or '1950-01-01'} to {end_date or 'latest'}..."
        )
    except Exception:
        pass

    if not isinstance(stations, pd.DataFrame):
        raise TypeError(
            "fetch() expects a pandas DataFrame/SwiftTable from "
            "hydroswift.wris.stations(...), hydroswift.cwc.stations(...), "
            "hydroswift.wris.basins(...), or hydroswift.cwc.basins(...)."
        )

    source = stations.attrs.get("source") or stations.attrs.get("fetch_source")
    table_type = str(stations.attrs.get("type", "")).lower().strip()
    if not source:
        if "station_code" in stations.columns:
            source = "wris"
        elif "variable" in stations.columns:
            source = "wris"
        elif table_type == "basins" and stations.attrs.get("variable") is not None:
            source = "wris"
        elif "code" in stations.columns:
            source = "cwc"
        elif "station_count" in stations.columns:
            source = "cwc"
        else:
            raise ValueError(
                "Unable to infer data source from stations table. "
                "Expected 'station_code' (WRIS) or 'code' (CWC) column."
            )

    source = str(source).lower().strip()
    if source == "wris":
        has_station_codes = "station_code" in stations.columns
        has_basin_col = "basin" in stations.columns
        has_variable_col = "variable" in stations.columns
        has_group_cols = (has_basin_col and has_variable_col)

        variable_attr = stations.attrs.get("variable")
        variable_attr_list = []
        if variable_attr is not None:
            if isinstance(variable_attr, str):
                variable_attr_list = [variable_attr]
            elif isinstance(variable_attr, (list, tuple, set)):
                variable_attr_list = [str(v) for v in variable_attr]
            else:
                variable_attr_list = [str(variable_attr)]
            variable_attr_list = [v.strip() for v in variable_attr_list if str(v).strip()]

        # Basin-level WRIS fetch from swift.wris.basins(variable=...):
        # table includes basin/variable but does not include station_code.
        if (has_group_cols or (has_basin_col and variable_attr_list)) and not has_station_codes:
            basin_values = []
            if has_basin_col:
                basin_values = sorted(
                    {
                        str(v).strip()
                        for v in stations["basin"].dropna().tolist()
                        if str(v).strip()
                    }
                )
            elif stations.attrs.get("basin") is not None:
                raw_basins = stations.attrs.get("basin")
                if isinstance(raw_basins, str):
                    basin_values = [raw_basins.strip()] if raw_basins.strip() else []
                elif isinstance(raw_basins, (list, tuple, set)):
                    basin_values = sorted({str(b).strip() for b in raw_basins if str(b).strip()})
                else:
                    one = str(raw_basins).strip()
                    basin_values = [one] if one else []

            if has_variable_col:
                variable_values = sorted(
                    {
                        str(v).strip()
                        for v in stations["variable"].dropna().tolist()
                        if str(v).strip()
                    }
                )
            else:
                variable_values = variable_attr_list

            if not basin_values or not variable_values:
                raise ValueError(
                    "WRIS basin table has no valid basin/variable pairs. "
                    "Use swift.wris.basins(variable=...) or provide non-empty "
                    "'basin' and 'variable' columns."
                )

            if has_group_cols:
                combo_df = stations[["basin", "variable"]].dropna().copy()
                combo_df["basin"] = combo_df["basin"].astype(str).str.strip()
                combo_df["variable"] = combo_df["variable"].astype(str).str.strip()
                combo_df = combo_df[
                    (combo_df["basin"] != "") & (combo_df["variable"] != "")
                ]
                unique_combos = sorted(
                    {
                        (row["basin"], row["variable"])
                        for _, row in combo_df.iterrows()
                    },
                    key=lambda x: (x[0], x[1]),
                )
            else:
                unique_combos = sorted(
                    {
                        (b, v)
                        for b in basin_values
                        for v in variable_values
                    },
                    key=lambda x: (x[0], x[1]),
                )

            # Explicit warning because this path downloads all stations per basin.
            warnings.warn(
                "Fetching WRIS data for basin-level input. "
                f"Dispatching {len(unique_combos)} basin-variable combinations; "
                "this may take a long time...",
                UserWarning,
                stacklevel=2,
            )

            try:
                import pandas as _pd  # type: ignore[import]
            except Exception:
                _pd = None

            frames = []
            for grp_basin, grp_variable in unique_combos:
                res = wris.download(
                    basin=grp_basin,
                    variable=grp_variable,
                    station=None,
                    start_date=start_date,
                    end_date=end_date,
                    output_dir=output_dir,
                    format=format,
                    overwrite=overwrite,
                    merge=merge,
                    plot=plot,
                    delay=delay,
                    quiet=quiet,
                )
                if res is not None and _pd is not None and hasattr(res, "assign"):
                    frames.append(res.assign(basin=str(grp_basin), variable=str(grp_variable)))

            if not frames or _pd is None:
                return None
            return _pd.concat(frames, ignore_index=True)

        if has_group_cols and has_station_codes:
            groups = stations.groupby(["basin", "variable"], sort=True)
            try:
                import pandas as _pd  # type: ignore[import]
            except Exception:
                _pd = None
            frames = []
            for (grp_basin, grp_variable), grp_df in groups:
                codes = sorted(
                    {
                        str(c).strip()
                        for c in grp_df["station_code"].dropna().tolist()
                        if str(c).strip()
                    }
                )
                if not codes:
                    continue
                res = get_wris_data(
                    var=grp_variable,
                    basin=grp_basin,
                    station=codes,
                    start_date=start_date,
                    end_date=end_date,
                    output_dir=output_dir,
                    format=format,
                    overwrite=overwrite,
                    merge=merge,
                    plot=plot,
                    delay=delay,
                    quiet=quiet,
                    name_by="station",
                )
                if res is not None and _pd is not None:
                    if hasattr(res, "assign"):
                        frames.append(res.assign(basin=str(grp_basin), variable=str(grp_variable)))
            if not frames or _pd is None:
                return None
            return _pd.concat(frames, ignore_index=True)

        if not has_station_codes:
            raise ValueError(
                "WRIS input table must include either 'station_code' (for station-level fetch) "
                "or both 'basin' and 'variable' columns (for basin-level fetch)."
            )

        basin = stations.attrs.get("basin")
        variable = stations.attrs.get("variable")
        if basin is None or variable is None:
            raise ValueError(
                "WRIS station table is missing 'basin'/'variable' columns or attrs. "
                "Build it using hydroswift.wris.stations(basin=..., variable=...)."
            )
        station_codes = sorted(
            {
                str(code).strip()
                for code in stations["station_code"].dropna().tolist()
                if str(code).strip()
            }
        )
        if not station_codes:
            raise ValueError("WRIS station table has no valid station_code entries.")
        return get_wris_data(
            var=variable,
            basin=basin,
            station=station_codes,
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir,
            format=format,
            overwrite=overwrite,
            merge=merge,
            plot=plot,
            delay=delay,
            quiet=quiet,
            name_by="station",
        )

    if source == "cwc":
        has_code_col = "code" in stations.columns
        has_basin_col = "basin" in stations.columns
        has_state_col = "state" in stations.columns

        # Basin-level CWC fetch from hydroswift.cwc.basins(): table includes
        # basin names and station counts, but no explicit station codes.
        if has_basin_col and not has_code_col:
            basin_df = stations[["basin"]].dropna().copy()
            basin_df["basin"] = basin_df["basin"].astype(str).str.strip()
            basin_df = basin_df[basin_df["basin"] != ""]
            if basin_df.empty:
                raise ValueError(
                    "CWC basin table has no valid basin values. "
                    "Use hydroswift.cwc.basins() or provide a non-empty 'basin' column."
                )

            unique_basins = _unique_preserve_order(basin_df["basin"].tolist())

            warnings.warn(
                "Fetching CWC data for basin-level input. "
                f"Dispatching {len(unique_basins)} basins; this might take a while...",
                UserWarning,
                stacklevel=2,
            )

            try:
                import pandas as _pd  # type: ignore[import]
            except Exception:
                _pd = None

            frames = []
            total_dispatched_stations = 0
            for grp_basin in unique_basins:
                basin_stations = cwc_ns.stations(
                    basin=grp_basin,
                    refresh=refresh,
                )
                if "code" not in basin_stations.columns:
                    continue
                codes = _unique_preserve_order(
                    basin_stations["code"].dropna().tolist()
                )
                if not codes:
                    continue
                total_dispatched_stations += len(codes)
                res = cwc_ns.download(
                    station=codes,
                    basin=grp_basin,
                    start_date=start_date,
                    end_date=end_date,
                    output_dir=output_dir,
                    format=format,
                    overwrite=overwrite,
                    merge=merge,
                    plot=plot,
                    quiet=quiet,
                    refresh=refresh,
                    _name_by="basin",
                )
                if res is not None and _pd is not None and hasattr(res, "assign"):
                    frames.append(res.assign(basin=str(grp_basin)))

            if not quiet and total_dispatched_stations > 0:
                print(
                    "CWC basin-dispatch summary: "
                    f"{len(unique_basins)} basins, "
                    f"{total_dispatched_stations} stations targeted in total."
                )
                print(
                    "Note: per-basin download tables report stations with data in the "
                    "requested period, so they can be lower than targeted station counts."
                )

            if not frames or _pd is None:
                return None
            return _pd.concat(frames, ignore_index=True)

        if not has_code_col:
            raise ValueError("CWC stations table must include 'code' column.")

        if has_basin_col:
            # Group by basin so each group is saved under output_dir/cwc/<basin>/stations/
            # Use "unknown" for missing basin so those stations still get a folder.
            def _basin_slug(val):
                if pd.isna(val) or val is None or str(val).strip() == "":
                    return "unknown"
                return str(val).strip()

            def _state_slug(val):
                if pd.isna(val) or val is None or str(val).strip() == "":
                    return "unknown"
                return str(val).strip()

            if has_state_col:
                groups = stations.groupby(
                    [
                        stations["basin"].map(_basin_slug),
                        stations["state"].map(_state_slug),
                    ],
                    sort=True,
                )
            else:
                groups = stations.groupby(
                    stations["basin"].map(_basin_slug),
                    sort=True,
                )
            try:
                import pandas as _pd  # type: ignore[import]
            except Exception:
                _pd = None
            frames = []
            for group_key, grp_df in groups:
                if has_state_col:
                    grp_basin, grp_state = group_key
                else:
                    grp_basin, grp_state = group_key, None
                codes = _unique_preserve_order(grp_df["code"].dropna().tolist())
                if not codes:
                    continue
                gpkg_group = str(grp_basin)
                if has_state_col and grp_state and str(grp_state).strip().lower() != "unknown":
                    gpkg_group = f"{grp_basin}_{grp_state}"
                res = cwc_ns.download(
                    station=codes,
                    basin=None,
                    start_date=start_date,
                    end_date=end_date,
                    output_dir=output_dir,
                    format=format,
                    overwrite=overwrite,
                    merge=merge,
                    plot=plot,
                    quiet=quiet,
                    refresh=refresh,
                    _name_by="basin",
                    _gpkg_group=gpkg_group,
                )
                if res is not None and _pd is not None and hasattr(res, "assign"):
                    if has_state_col:
                        frames.append(res.assign(basin=str(grp_basin), state=str(grp_state)))
                    else:
                        frames.append(res.assign(basin=str(grp_basin)))
            if not frames or _pd is None:
                return None
            return _pd.concat(frames, ignore_index=True)

        station_codes = _unique_preserve_order(stations["code"].dropna().tolist())
        if not station_codes:
            raise ValueError("CWC station table has no valid code entries.")
        return cwc_ns.download(
            station=station_codes,
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir,
            format=format,
            overwrite=overwrite,
            merge=merge,
            plot=plot,
            quiet=quiet,
            refresh=refresh,
            _name_by="basin",
        )

    raise ValueError(f"Unknown stations source: {source!r}.")


# ---------------------------------------------------------
# Merge / Plot
# ---------------------------------------------------------

def _resolve_mode_input_dir(mode, output_dir):
    """Derive ``input_dir`` from *mode* using HydroSwift conventions (root containing wris/ and cwc/)."""
    base = Path(output_dir or "output")
    if mode in ("wris", "cwc"):
        return str(base)
    raise ValueError(f"Unknown mode: {mode!r}. Use 'wris' or 'cwc'.")


def merge_only(
    input_dir=None,
    output_dir=None,
    *,
    mode=None,
    variable=None,
):
    """
    Merge existing HydroSwift station files into GeoPackages.

    Basins and (for CWC) agencies are auto-discovered from the directory
    layout under *input_dir*; no basin argument is needed.

    Parameters
    ----------
    input_dir : str or Path, optional
        Root directory containing ``wris/`` and/or ``cwc/`` subfolders.
        When *mode* is set and this is omitted, defaults to *output_dir*.
    output_dir : str or Path, optional
        Destination for merged GeoPackages (defaults to *input_dir*).
        WRIS outputs go to ``output_dir/wris/``, CWC to ``output_dir/cwc/``.
    mode : ``'wris'`` | ``'cwc'``, optional
        Data source mode.  When provided and *input_dir* is omitted,
        *input_dir* is taken from *output_dir*.
    variable : str or list[str], optional
        Subset of variables to merge (WRIS only; e.g. ``["solar", "discharge"]``).
    """
    _var_list = (
        [] if variable is None
        else [variable] if isinstance(variable, str)
        else list(variable)
    )
    if mode == "cwc" and _var_list:
        warnings.warn(
            "hydroswift.merge_only(mode='cwc', ...) ignores variable; CWC data only has water levels.",
            UserWarning,
            stacklevel=2,
        )
        _var_list = []
    dataset_flags = _normalize_dataset_flags(_var_list)

    if mode is not None and input_dir is None:
        input_dir = _resolve_mode_input_dir(mode, output_dir)

    if input_dir is None:
        raise ValueError(
            "input_dir must be specified (or provide mode= and output_dir= to derive it)"
        )
    p = Path(input_dir)
    if not p.exists():
        raise ValueError("input_dir does not exist")

    # When output_dir is provided, preserve existing behavior: merge to disk
    # and also return a concatenated GeoDataFrame for convenience.
    if output_dir is not None:
        args = _build_args(
            input_dir=str(p),
            output_dir=str(output_dir),
            merge_only=True,
            dataset_flags=dataset_flags,
            cwc=(mode == "cwc") if mode else False,
        )
        try:
            run_merge_only(args)
        except PermissionError as exc:
            raise ValueError(
                f"output_dir is not writable: {output_dir!r}. "
                "Choose a writable directory (for example, a path inside your workspace)."
            ) from exc
        except OSError as exc:
            raise ValueError(
                f"Unable to use output_dir={output_dir!r}: {exc}"
            ) from exc
        # After on-disk merge, load the resulting GeoPackages and concatenate.
        try:
            import geopandas as gpd  # type: ignore[import]
        except Exception:
            return None

        frames = []
        root = Path(output_dir)
        if mode == "cwc":
            cwc_root = root / "cwc"
            for gpkg_path in cwc_root.glob("cwc_waterlevel*.gpkg"):
                try:
                    gdf = gpd.read_file(gpkg_path)
                except Exception:
                    continue
                stem = gpkg_path.stem
                parts = stem.split("_")
                basin_label = None
                if len(parts) > 3:
                    basin_label = "_".join(parts[2:])
                gdf = gdf.assign(basin=basin_label)
                frames.append(gdf)
        else:
            wris_root = root / "wris"
            if wris_root.exists() and wris_root.is_dir():
                for gpkg_path in wris_root.glob("*.gpkg"):
                    try:
                        gdf = gpd.read_file(gpkg_path)
                    except Exception:
                        continue
                    # Infer basin / variable from filename: <basin>_<dataset>.gpkg
                    stem = gpkg_path.stem
                    parts = stem.split("_", 1)
                    basin_label = parts[0] if parts else None
                    var_label = parts[1] if len(parts) > 1 else None
                    gdf = gdf.assign(basin=basin_label, variable=var_label)
                    frames.append(gdf)

        if not frames:
            return None
        import pandas as _pd  # type: ignore[import]
        return _pd.concat(frames, ignore_index=True)

    # When output_dir is omitted, operate in-memory only: read station files
    # under input_dir and return a concatenated GeoDataFrame without writing
    # any GeoPackages.
    try:
        import pandas as _pd  # type: ignore[import]
    except Exception:
        return None
    from .merge import merge_dataset_folder

    # Reuse merge_dataset_folder's CSV/XLSX reading logic by writing to a
    # temporary GeoPackage and reading it back, then deleting it.
    import tempfile
    import os as _os

    tmp_dir = tempfile.mkdtemp()
    try:
        if mode == "cwc":
            # CWC station dirs under input_dir/cwc/...
            from pathlib import Path as _P
            root_cwc = _P(input_dir) / "cwc"
            station_dirs = []
            legacy = root_cwc / "stations"
            if legacy.exists() and legacy.is_dir():
                station_dirs.append(str(legacy))
            for sub in root_cwc.iterdir() if root_cwc.exists() else []:
                if sub.is_dir() and sub.name != "stations":
                    sdir = sub / "stations"
                    if sdir.exists() and sdir.is_dir():
                        station_dirs.append(str(sdir))
            frames = []
            for d in station_dirs:
                tmp_gpkg = _os.path.join(tmp_dir, "tmp_cwc.gpkg")
                merge_dataset_folder(d, tmp_gpkg, "cwc_waterlevel")
                try:
                    import geopandas as gpd  # type: ignore[import]
                    gdf = gpd.read_file(tmp_gpkg)
                    frames.append(gdf)
                except Exception:
                    continue
            if not frames:
                return None
            return _pd.concat(frames, ignore_index=True)
        else:
            # WRIS: detect basin directories and dataset dirs as in run_merge_only
            from pathlib import Path as _P
            from .cli import DATASETS, selected_datasets
            root = _P(input_dir)
            dataset_names = {folder for _, folder in DATASETS.values()}
            wris_root = root / "wris"
            wris_input_root = wris_root if wris_root.exists() and wris_root.is_dir() else root
            if any((wris_input_root / d).is_dir() and d in dataset_names for d in _os.listdir(wris_input_root)):
                basin_dirs = [wris_input_root]
            else:
                basin_dirs = [d for d in wris_input_root.iterdir() if d.is_dir()]
            # Build args-like object for selected_datasets
            class _Args:
                pass
            a = _Args()
            for key in ["q", "wl", "atm", "rf", "temp", "rh", "solar", "sed", "gwl"]:
                setattr(a, key, False)
            for flag in dataset_flags:
                setattr(a, flag, True)
            selected = selected_datasets(a)
            frames = []
            import geopandas as gpd  # type: ignore[import]
            for basin_dir in basin_dirs:
                basin = basin_dir.name
                if not selected:
                    dataset_dirs = [d for d in basin_dir.iterdir() if d.is_dir()]
                else:
                    dataset_dirs = [basin_dir / folder for _, folder in selected.items()]
                for d in dataset_dirs:
                    if not d.exists():
                        continue
                    tmp_gpkg = _os.path.join(tmp_dir, "tmp_wris.gpkg")
                    merge_dataset_folder(str(d), tmp_gpkg, d.name)
                    try:
                        gdf = gpd.read_file(tmp_gpkg)
                    except Exception:
                        continue
                    gdf = gdf.assign(basin=str(basin), variable=str(d.name))
                    frames.append(gdf)
            if not frames:
                return None
            return _pd.concat(frames, ignore_index=True)
    finally:
        import shutil as _shutil
        _shutil.rmtree(tmp_dir, ignore_errors=True)


def plot_only(
    input_dir=None,
    output_dir=None,
    cwc=False,
    *,
    mode=None,
    variable=None,
    plot_svg=False,
    moving_average=None,
    window=None,
):
    """
    Generate hydrograph plots from existing HydroSwift output.

    Basins and (for CWC) agencies are auto-discovered from the directory
    layout under *input_dir*; no basin argument is needed.

    Parameters
    ----------
    input_dir : str or Path, optional
        Root directory containing ``wris/`` and/or ``cwc/`` subfolders.
        When *mode* is set and this is omitted, defaults to *output_dir*.
    output_dir : str or Path, optional
        Destination for plot images (defaults to *input_dir*).
        WRIS images go to ``output_dir/wris/<basin>/images/<variable>/``, CWC to ``output_dir/cwc/...``.
    cwc : bool, default False
        Legacy flag -- prefer ``mode='cwc'``.
    mode : ``'wris'`` | ``'cwc'``, optional
        Data source mode.
    variable : str or list[str], optional
        Subset of variables to plot (WRIS only; e.g. ``["solar", "discharge"]``).
    moving_average : bool | int, optional
        Enable moving-average overlay. Pass ``True`` to use the default
        30-sample window or pass an integer window size directly.
    window : int, optional
        Moving-average window size in samples. Preferred companion to
        ``moving_average=True``.
    """
    _var_list = (
        [] if variable is None
        else [variable] if isinstance(variable, str)
        else list(variable)
    )
    if (mode == "cwc" or cwc) and _var_list:
        warnings.warn(
            "hydroswift.plot_only(mode='cwc', ...) ignores variable; CWC data only has water levels.",
            UserWarning,
            stacklevel=2,
        )
        _var_list = []
    dataset_flags = _normalize_dataset_flags(_var_list)

    if mode is not None:
        if mode == "cwc":
            cwc = True
        if input_dir is None:
            input_dir = _resolve_mode_input_dir(mode, output_dir)

    if input_dir is None:
        raise ValueError(
            "input_dir must be specified (or provide mode= and output_dir= to derive it)"
        )
    p = Path(input_dir)
    if not p.exists():
        raise ValueError("input_dir does not exist")

    resolved_moving_average_window = None
    if window is not None:
        resolved_moving_average_window = window
    elif isinstance(moving_average, bool):
        resolved_moving_average_window = 30 if moving_average else None
    elif moving_average is not None:
        resolved_moving_average_window = moving_average

    args = _build_args(
        input_dir=str(p),
        output_dir=str(output_dir) if output_dir else None,
        plot_only=True,
        dataset_flags=dataset_flags,
        cwc=cwc,
        plot_svg=plot_svg,
        plot_moving_average_window=resolved_moving_average_window,
    )
    run_plot_only(args)
    return None



# ---------------------------------------------------------
# SwiftTable (DataFrame wrapper for nicer notebook display)
# ---------------------------------------------------------

class SwiftTable(pd.DataFrame):
    """DataFrame subclass with a HydroSwift header in ``repr``."""

    @property
    def _constructor(self):
        return SwiftTable

    def __repr__(self):
        rows, cols = self.shape
        header = (
            f"HydroSwift Table\n"
            f"Rows: {rows:,} | Columns: {cols}\n"
            f"{'-' * 40}\n"
        )
        return header + super().__repr__()


# ---------------------------------------------------------
# Notebook helpers  (tab-completion namespaces)
# ---------------------------------------------------------

# ---------------------------------------------------------
# Citation / Easter eggs
# ---------------------------------------------------------

from .banner import print_wish_banner


def cite():
    """Print the banner and citation information."""
    print_wish_banner()
    print(
        """
    If you use HydroSwift in your research, please cite:

    Sarat, C., Dash, D., & Kumar, A. (2026).
    HydroSwift: Automated Retrieval of Hydrological Station Data
    from India-WRIS and CWC Portals.
    Journal of Open Source Software.

    Repository:
    https://github.com/carbform/swift
    """
    )


def coffee():
    """HydroSwift coffee break easter egg for notebooks."""
    print(
        r"""
        ( (
        ) )
        ........
        |      |]
        \      /
        `----'
        TIME FOR A COFFEE BREAK
    """
    )
    print(
        "Many kinds of monkeys have a strong taste for tea, "
        "coffee and spirituous liqueurs. - Charles Darwin"
    )
    return None
