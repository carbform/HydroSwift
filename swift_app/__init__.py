"""SWIFT app package metadata.

Internal implementation package for HydroSwift. Public entry points:
- import hydroswift
- hyswift ... / python -m hydroswift ...
"""

__version__ = "1.0.0"
__codename__ = "Arctic Amsterdam"

APP_NAME = "HydroSwift"
APP_TAGLINE = "Fast, unified workflows for hydrological data"
APP_ORG = "Carbform • carbform.github.io"

VERSION = f"{__version__}"
VERSION_FULL = f"{VERSION} — {__codename__}"

from .api import (  # noqa: E402
    search,
    estimate,
    fetch,
    load,
    merge,
    plot,
    save_catalog,
    load_catalog,
    refresh_cwc_stations,
    rsms,
    cwc_reservoirs,
    swot_reservoir_merge,
    help,
    cli_help,
    cite,
    coffee,
)
from .base_client import BaseHydrologyClient  # noqa: E402

from ._removed import make_getattr  # noqa: E402

__getattr__ = make_getattr(__name__)
