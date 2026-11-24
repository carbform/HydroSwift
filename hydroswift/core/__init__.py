"""HydroSwift core engine, schemas, and tidy transformation."""

from .engine import (
    CATALOG_COLUMNS,
    SourceStatus,
    FetchRecord,
    FetchOptions,
    search_catalog,
    estimate_catalog,
    fetch_catalog,
    write_manifest,
    ADAPTERS,
    parse_period,
    NwdpAdapter,
    CwcAdapter,
    RsmsAdapter,
    WrisAdapter,
)
from .tidy import (
    load,
    TIDY_COLUMNS,
    VARIABLES,
    normalise_unit,
    infer_variable,
    tidy_wris,
)
from .outputs import (
    merge_run,
    plot_run,
)

__all__ = [
    "CATALOG_COLUMNS",
    "SourceStatus",
    "FetchRecord",
    "FetchOptions",
    "search_catalog",
    "estimate_catalog",
    "fetch_catalog",
    "write_manifest",
    "ADAPTERS",
    "parse_period",
    "NwdpAdapter",
    "CwcAdapter",
    "RsmsAdapter",
    "WrisAdapter",
    "load",
    "TIDY_COLUMNS",
    "VARIABLES",
    "normalise_unit",
    "infer_variable",
    "tidy_wris",
    "merge_run",
    "plot_run",
]
