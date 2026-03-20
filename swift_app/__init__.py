"""SWIFT app package metadata.

Internal implementation package for SWIFT.
Public commands are exposed through:
- python -m hydroswift ...
- hyswift ... (if installed)
- python -m swift_app ... (legacy internal entrypoint)
"""

__version__ = "1.0.0"
__codename__ = "Arctic Amsterdam"

APP_NAME = "HydroSwift"
APP_TAGLINE = "Fast, unified workflows for hydrological data"
APP_ORG = "Carbform • carbform.github.io"

VERSION = f"{__version__}"
VERSION_FULL = f"{VERSION} — {__codename__}"

from .api import (
    wris,
    cwc_ns as cwc,
    help,
    cli_help,
    merge_only,
    plot_only,
    fetch,
    cite,
    coffee,
)
from .base_client import BaseHydrologyClient


_LEGACY_API_REDIRECTS = {
    "datasets": (
        "`hydroswift.datasets` has been removed. "
        "Use `hydroswift.wris.variables()` for WRIS variable definitions."
    ),
    "basins": (
        "`hydroswift.basins()` has been removed. "
        "Use `hydroswift.wris.basins()` for WRIS basins or `hydroswift.cwc.basins()` for CWC basins."
    ),
    "merge": (
        "`hydroswift.merge()` has been removed. Use `hydroswift.merge_only()` instead."
    ),
    "plot": (
        "`hydroswift.plot()` has been removed. Use `hydroswift.plot_only()` instead."
    ),
}


def __getattr__(name: str):
    """Provide clear migration guidance for removed legacy API symbols."""
    if name in _LEGACY_API_REDIRECTS:
        raise AttributeError(_LEGACY_API_REDIRECTS[name])
    raise AttributeError(f"module 'swift_app' has no attribute {name!r}")
