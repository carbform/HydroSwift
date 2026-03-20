"""Command-line parsing for HydroSwift."""

from __future__ import annotations

import argparse
import time
from collections import OrderedDict

DATASETS = OrderedDict(
    {
        "q": ("DISCHARG", "discharge"),
        "wl": ("WATERLVL", "water_level"),
        "atm": ("PRESS", "atm_pressure"),
        "rf": ("RAINF", "rainfall"),
        "temp": ("MT_TEMP", "temperature"),
        "rh": ("HUMID", "humidity"),
        "solar": ("SOLAR_RD", "solar_radiation"),
        "sed": ("SEDIM", "sediment"),
        "gwl": ("GWATERLVL", "groundwater_level"),
    }
)

WRIS_BASINS = OrderedDict(
    {
        "1": "Brahmani and Baitarni",
        "2": "Cauvery",
        "3": "East flowing rivers between Mahanadi and Pennar",
        "4": "East flowing rivers between Pennar and Kanyakumari",
        "5": "Godavari",
        "6": "Krishna",
        "7": "Mahanadi",
        "8": "Mahi",
        "9": "Minor rivers draining into Myanmar and Bangladesh",
        "10": "Narmada",
        "11": "Pennar",
        "12": "Sabarmati",
        "13": "Subernarekha",
        "14": "Tapi",
        "15": "West flowing rivers from Tadri to Kanyakumari",
        "16": "West flowing rivers from Tapi to Tadri",
        "17": "West flowing rivers of Kutch and Saurashtra including Luni",
    }
)

# Map dataset codes to short column names for the value column
DATASET_COLUMNS = {
    "DISCHARG": "q",
    "WATERLVL": "wl",
    "PRESS": "atm",
    "RAINF": "rf",
    "MT_TEMP": "temp",
    "HUMID": "rh",
    "SOLAR_RD": "solar",
    "SEDIM": "sed",
    "GWATERLVL": "gwl",
}


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for the HydroSwift CLI."""
    parser = argparse.ArgumentParser(
        prog="hyswift",
        description=(
            "HydroSwift - Fast, unified workflows for hydrological data\n\n"
            "Download hydrological datasets from India-WRIS and CWC."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    from . import VERSION

    parser.add_argument("--version", action="version", version=f"HydroSwift {VERSION}")

    basin_help = "WRIS basin name or number:\n"
    for num, name in WRIS_BASINS.items():
        basin_help += f"  [{num}] {name}\n"

    source = parser.add_argument_group("Source selection")
    source.add_argument("-b", "--basin", help=basin_help)
    source.add_argument(
        "--cwc",
        action="store_true",
        help="Use CWC source (Python equivalent: hydroswift.cwc.download(...))",
    )
    source.add_argument(
        "--cwc-station",
        "--station",
        dest="cwc_station",
        nargs="+",
        help="CWC station code(s) (Python equivalent: station=[...])",
    )
    source.add_argument(
        "--cwc-basin",
        dest="cwc_basin_filter",
        nargs="+",
        help="CWC basin filter(s) (Python equivalent: basin=[...])",
    )
    source.add_argument(
        "--cwc-refresh",
        action="store_true",
        default=False,
        help="Refresh CWC station metadata from the live API before download.",
    )

    datasets = parser.add_argument_group("WRIS variables")
    datasets.add_argument("-q", "--discharge", dest="q", action="store_true", help="Discharge")
    datasets.add_argument("-wl", "--water-level", dest="wl", action="store_true", help="Water level")
    datasets.add_argument("-atm", "--atm-pressure", dest="atm", action="store_true", help="Atmospheric pressure")
    datasets.add_argument("-rf", "--rainfall", dest="rf", action="store_true", help="Rainfall")
    datasets.add_argument("-temp", "--temperature", dest="temp", action="store_true", help="Temperature")
    datasets.add_argument("-rh", "--humidity", dest="rh", action="store_true", help="Relative humidity")
    datasets.add_argument("-solar", "--solar-radiation", dest="solar", action="store_true", help="Solar radiation")
    datasets.add_argument("-sed", "--sediment", dest="sed", action="store_true", help="Suspended sediment")
    datasets.add_argument("-gwl", "--groundwater-level", dest="gwl", action="store_true", help="Groundwater level")

    download = parser.add_argument_group("Download behavior")
    download.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    download.add_argument("--merge", action="store_true", help="Merge station files into GeoPackages")
    download.add_argument(
        "--merge-only",
        action="store_true",
        help="Only merge existing output (Python equivalent: hydroswift.merge_only(...))",
    )
    download.add_argument("--delay", type=float, default=0.25, help="Delay between WRIS API requests (seconds)")
    download.add_argument("--start-date", default="1950-01-01", help="Start date (YYYY-MM-DD)")
    download.add_argument("--end-date", default=time.strftime("%Y-%m-%d"), help="End date (YYYY-MM-DD)")

    output = parser.add_argument_group("Output options")
    output.add_argument("--metadata", action="store_true", help="Save station metadata as CSV")
    output.add_argument("--input-dir", help="Input directory for --merge-only / --plot-only")
    output.add_argument("--plot", action="store_true", help="Generate plots after download")
    output.add_argument(
        "--plot-svg",
        action="store_true",
        help="Also export publication-ready SVG files when plotting",
    )
    output.add_argument(
        "--plot-moving-average-window",
        type=int,
        default=None,
        help="Optional moving-average window (number of samples) overlay for plots",
    )
    output.add_argument("--plot-only", action="store_true", help="Generate plots from existing output")
    output.add_argument("--output-dir", default="output", help="Output directory (default: output)")
    output.add_argument("--format", choices=["csv", "xlsx"], default="csv", help="Output file format")

    misc = parser.add_argument_group("Misc")
    misc.add_argument("--quiet", action="store_true", help="Suppress console output")
    misc.add_argument("--list", action="store_true", help="List available WRIS basins and CWC station count")
    misc.add_argument("--cite", action="store_true", help="Show citation information")
    misc.add_argument("--coffee", action="store_true", help="Take a virtual coffee break ☕")

    return parser


def selected_datasets(args: argparse.Namespace) -> dict[str, str]:
    """Map selected CLI flags to WRIS dataset code => output folder."""
    selected: dict[str, str] = {}
    for key, (dataset_code, folder_name) in DATASETS.items():
        if getattr(args, key):
            selected[dataset_code] = folder_name
    return selected
