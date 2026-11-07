"""Public HydroSwift package backed by the legacy ``swift_app`` source tree."""

from pathlib import Path as _Path

# Reuse the existing implementation modules from the legacy source directory
# so public imports can use ``hydroswift.*`` without a risky code move.
__path__ = [str(_Path(__file__).resolve().parent.parent / "swift_app")]

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
