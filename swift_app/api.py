"""
Public Python API for HydroSwift.

The workflow is Find -> Review -> Get -> Use:

    cat = hydroswift.search("rainfall", "Karnataka", period=("2020", "2022"))   # Find
    cat.attrs["source_status"]                                                 # Review: what each source said
    hydroswift.estimate(cat)                                                    # Review: how big is it?
    run = hydroswift.fetch(cat, output_dir="output", period=("2020", "2022"))  # Get
    data = hydroswift.load(run)                                                # Use: one tidy table

Also: hydroswift.merge(), hydroswift.plot(), hydroswift.rsms (reservoirs).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

PYTHON_HELP_TEXT = """HydroSwift Python API

Find -> Review -> Get -> Use

    import hydroswift as hs
    cat = hs.search("rainfall", "Karnataka", period=("2020", "2022"))
        # options: sources=["NWDP","CWC","CWC-RSMS"], ids=[...], basin=..., state=...
    cat.attrs["source_status"]      # per-source ok / error / complete / dropped rows
    cat.attrs["partial"]            # True if any source failed or was truncated
    hs.estimate(cat)                # adds EstRecords (exact for NWDP, unknown elsewhere)
    run = hs.fetch(cat, output_dir="output", period=("2020", "2022"))
    data = hs.load(run)             # tidy: time,value,variable,unit,station_id,...
    hs.merge(run, "all.parquet")    # csv | parquet | gpkg
    hs.plot(run, "plots/")          # one PNG per station and variable

Reservoirs (CWC RSMS):  hs.rsms.daily() / bulletins() / backfill() / build_database()
Utilities:  hs.help()  hs.cite()  hs.coffee()  hs.save_catalog(cat, path)  hs.load_catalog(path)
"""


def help():
    """Print Python API help text."""
    print(PYTHON_HELP_TEXT)
    return None


def cli_help():
    """Print the command-line help text (equivalent to ``hyswift -h``)."""
    from .cli import build_parser
    build_parser().print_help()
    return None


def fetch(table, *, output_dir="output", period=None, start_date=None, end_date=None,
          format="csv", overwrite=False, rc_discharge=True, resume=True,
          progress=None, cancel=None, quiet=True):
    """Download every row of a catalog table returned by :func:`search`.

    Parameters
    ----------
    table : DataFrame
        A (possibly filtered) catalog from :func:`search`. Keep the original
        object's ``attrs`` if you want search provenance in the manifest.
    period : (start, end) or "YYYY:YYYY", optional
        Applied to every source (NWDP: filtered after download, since the
        portal cannot filter by date; CWC: requested from the portal).
    format : "csv" | "xlsx" | "json"
        NWDP supports csv/json, CWC csv/xlsx.
    rc_discharge : bool
        CWC discharge exists only as a rating-curve estimate from stage; it is
        labelled ``rc_guardian_2024`` in the data. Set False for stage only.
    resume : bool
        Reuse files recorded in an earlier manifest for the same ID and requested range.
    progress : callable(event: dict), optional
    cancel : threading.Event, optional

    Returns
    -------
    DataFrame
        One row per item: status (saved/skipped/empty/error/cancelled), path,
        records, actual start/end, error. ``.attrs['manifest']`` is the manifest path.
    """
    from .engine import fetch_catalog
    if not isinstance(table, pd.DataFrame) or not {"Source", "ID", "Title"} <= set(table.columns):
        raise TypeError(
            "fetch() expects a table returned by hydroswift.search(...) "
            "(columns Source, Title, ID, ...)."
        )
    result = fetch_catalog(table, output_dir=output_dir, period=period, start_date=start_date,
                           end_date=end_date, format=format, overwrite=overwrite, quiet=quiet,
                           rc_discharge=rc_discharge, resume=resume, progress=progress, cancel=cancel)
    failed = result[result["status"] == "error"]
    if len(failed):
        warnings.warn(
            f"{len(failed)} of {len(result)} downloads failed; see the 'error' column "
            f"or {result.attrs.get('manifest')}.",
            stacklevel=2,
        )
    return result


def estimate(table, *, network=True):
    """Add ``EstRecords`` / ``EstNote`` to a catalog (exact for NWDP, unknown elsewhere)."""
    from .engine import estimate_catalog
    return estimate_catalog(table, network=network)


def load(run):
    """Load fetched data as one tidy table (see :mod:`swift_app.tidy`)."""
    from .tidy import load as _load
    return _load(run)


def merge(run, output="output/merged.parquet"):
    """Merge fetched data into one file (.csv, .parquet or .gpkg). Returns the tidy table."""
    from .outputs import merge as _merge
    return _merge(run, output)


def plot(run, output_dir="output/plots", **kw):
    """Plot one time series figure per station and variable. Returns the list of PNG paths."""
    from .outputs import plot as _plot
    return _plot(run, output_dir, **kw)


def save_catalog(table, path):
    """Save a catalog (including its provenance) to JSON so it can be re-used later."""
    from .engine import save_catalog as _s
    return _s(table, path)


def load_catalog(path):
    """Load a catalog written by :func:`save_catalog`, with its provenance."""
    from .engine import load_catalog as _l
    return _l(path)


def refresh_cwc_stations():
    """Re-download the CWC station table from the portal (slow, ~2 minutes)."""
    from .cwc import load_station_table
    return load_station_table(refresh=True)


def search(query: str = None, location: str = None, sources=None, *, period=None,
           ids=None, basin: str = None, state: str = None) -> pd.DataFrame:
    """
    Unified discovery across NWDP, CWC flood-forecasting stations and CWC RSMS.

    Parameters
    ----------
    query : str, optional
        Variable or keyword (e.g. "Rainfall", "Discharge").
    location : str, optional
        Case-insensitive substring matched against the fields each source has
        (NWDP: organization; CWC: basin, state, district, river). The field
        that matched is in the ``MatchedOn`` column.
    sources : list of str, optional
        Subset of ``["NWDP", "CWC", "CWC-RSMS"]``. Default: all.
    period : (start, end) or "YYYY:YYYY", optional
        Drops rows whose known coverage does not overlap; unknown coverage is kept and flagged.
    ids, basin, state : optional
        Exact (not substring) selection by catalog ID, basin or state. basin/state are CWC-only.

    Returns
    -------
    pd.DataFrame
        One row per dataset or station. ``df.attrs['source_status']`` lists
        per-source ok/error/complete flags and ``df.attrs['partial']`` is True
        if any source failed or returned a truncated listing. The ``Inferred``
        column names fields that were assumed rather than stated by the source.
    """
    import warnings
    from .engine import search_catalog
    df = search_catalog(query=query, location=location, sources=sources, period=period,
                        ids=ids, basin=basin, state=state)
    for st in df.attrs["source_status"]:
        if not st["ok"] or not st["complete"]:
            warnings.warn(f"{st['source']} search incomplete: {st['error']}", stacklevel=2)
    return df


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




class _CwcReservoirsNamespace:
    """Namespace for CWC Reservoir Storage Monitoring System (RSMS) workflows."""

    @staticmethod
    def daily(output_path=None, timeout=15, max_reservoirs=None):
        """Fetch latest real-time daily reservoir storage & level snapshot.

        Parameters
        ----------
        output_path : str or Path, optional
            Destination CSV to append or save the snapshot.
        timeout : int, default 15
            Request timeout in seconds.
        max_reservoirs : int, optional
            Limit reservoir count (useful for testing).

        Returns
        -------
        SwiftTable
            Table of daily reservoir observations.
        """
        from .cwc_rsms import CwcRsmsClient
        client = CwcRsmsClient()
        df = client.fetch_daily_snapshot(output_path=output_path, timeout=timeout, max_reservoirs=max_reservoirs)
        out = SwiftTable(df)
        out.attrs["source"] = "cwc_rsms"
        out.attrs["type"] = "daily_snapshot"
        return out

    @staticmethod
    def bulletins(from_date="", to_date="", cache_file=None):
        """Discover published CWC weekly bulletin reports from the RSMS portal.

        Parameters
        ----------
        from_date : str, default ""
            Optional start date filter (YYYY-MM-DD).
        to_date : str, default ""
            Optional end date filter (YYYY-MM-DD).
        cache_file : str or Path, optional
            Cache JSON path.

        Returns
        -------
        SwiftTable
            Table of published bulletin reports.
        """
        from .cwc_rsms import CwcRsmsClient
        client = CwcRsmsClient()
        items = client.fetch_bulletin_catalog(from_date=from_date, to_date=to_date, cache_file=cache_file)
        out = SwiftTable(pd.DataFrame(items))
        out.attrs["source"] = "cwc_rsms"
        out.attrs["type"] = "bulletin_catalog"
        return out

    @staticmethod
    def backfill(start_date="2025-05-15", end_date=None, output_csv=None, bulletin_dir="output/cwc/bulletins"):
        """Download and parse historical CWC bulletins into a consolidated time series.

        Parameters
        ----------
        start_date : str, default '2025-05-15'
            Start date for backfill (YYYY-MM-DD).
        end_date : str, optional
            End date for backfill.
        output_csv : str or Path, optional
            CSV file to store parsed observations.
        bulletin_dir : str or Path, default 'output/cwc/bulletins'
            Folder where bulletin PDFs are downloaded.

        Returns
        -------
        SwiftTable
            Consolidated reservoir time series table.
        """
        from .cwc_rsms import CwcRsmsClient
        client = CwcRsmsClient()
        df = client.backfill_bulletins(start_date=start_date, end_date=end_date, output_csv=output_csv, bulletin_dir=bulletin_dir)
        out = SwiftTable(df)
        out.attrs["source"] = "cwc_rsms"
        out.attrs["type"] = "bulletin_timeseries"
        return out

    @staticmethod
    def build_database(
        reservoir_shp,
        swot_observations,
        gauge_source,
        output_gpkg=None,
        output_sqlite=None,
        output_parquet=None,
        cwc_metadata=None,
        tolerance_days=3.5,
        fix_anomalies=True,
    ):
        """Build unified SWOT & in-situ reservoir database (GPKG, SQLite, Parquet).

        Parameters
        ----------
        reservoir_shp : str or Path
            Path to reservoir polygon shapefile or GeoPackage.
        swot_observations : str, Path, or DataFrame
            Path to SQLite database containing `observations` table, or DataFrame.
        gauge_source : str, Path, or DataFrame
            Directory of gauge CSVs (`<reservoir_id>.csv`), single CSV file, or DataFrame.
        output_gpkg : str or Path, optional
            Path for destination GeoPackage.
        output_sqlite : str or Path, optional
            Path for destination SQLite database.
        output_parquet : str or Path, optional
            Path for destination Parquet unified time series file.
        cwc_metadata : str, Path, or DataFrame, optional
            Metadata table containing FRL, DSL, capacities.
        tolerance_days : float, default 3.5
            Temporal matching tolerance in days.
        fix_anomalies : bool, default True
            Fix known transcription outliers (Manikdoh, Rihand).

        Returns
        -------
        dict
            Summary metrics including row counts and output paths.
        """
        from .cwc_rsms import UnifiedReservoirBuilder
        return UnifiedReservoirBuilder.build_database(
            reservoir_shp=reservoir_shp,
            swot_observations=swot_observations,
            gauge_source=gauge_source,
            output_gpkg=output_gpkg,
            output_sqlite=output_sqlite,
            output_parquet=output_parquet,
            cwc_metadata=cwc_metadata,
            tolerance_days=tolerance_days,
            fix_anomalies=fix_anomalies,
        )


def swot_reservoir_merge(
    reservoir_shp,
    swot_observations,
    gauge_source,
    output_gpkg=None,
    output_sqlite=None,
    output_parquet=None,
    cwc_metadata=None,
    tolerance_days=3.5,
    fix_anomalies=True,
):
    """Build SWOT-ready unified reservoir database combining satellite observations and in-situ gauges."""
    from .cwc_rsms import UnifiedReservoirBuilder
    return UnifiedReservoirBuilder.build_database(
        reservoir_shp=reservoir_shp,
        swot_observations=swot_observations,
        gauge_source=gauge_source,
        output_gpkg=output_gpkg,
        output_sqlite=output_sqlite,
        output_parquet=output_parquet,
        cwc_metadata=cwc_metadata,
        tolerance_days=tolerance_days,
        fix_anomalies=fix_anomalies,
    )




rsms = _CwcReservoirsNamespace()
cwc_reservoirs = rsms


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


