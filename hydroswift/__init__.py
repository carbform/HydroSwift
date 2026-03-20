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
from .base_client import BaseHydrologyClient  # noqa: E402


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
    raise AttributeError(f"module 'hydroswift' has no attribute {name!r}")
