"""
HydroSwift — Main CLI Entrypoint (Modular Core)

Version: 1.0.0 — Arctic Amsterdam
 

------
Carbform (www.carbform.github.io)

Code structure, formatting and banner art assisted by GPT-5.3.
(Thanks GPT Go! I'm too poor to afford Claude.)

What this is
------------

This is the modular runtime entrypoint used by both:

    python -m hydroswift ...
    hyswift ...         (if installed)

The legacy top-level script is kept for habit-friendly usage,
while orchestration now lives in this package file.

If you are reading this while debugging at 2 AM:
- drink water
- then coffee
- then inspect `args.plot_only`
"""

from __future__ import annotations
from .banner import print_wish_banner

import time


def _print_coffee() -> None:
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


def main() -> int:
    """Main HydroSwift execution entry point."""

    import os
    import sys
    from pathlib import Path

    from .cli import build_parser, DATASETS, selected_datasets, WRIS_BASINS
    from .wris_client import WrisClient
    from .plot import run_plot_only
    from .wris import run_wris_download
    from .cwc import run_cwc_download
    from .merge import merge_dataset_folder

    raw_argv = sys.argv[1:]
    banner_already_printed = False

    # Ensure branding is visible for top-level informational CLI calls that
    # may exit inside argparse before runtime logic is reached.
    if len(raw_argv) == 0 or any(flag in raw_argv for flag in ("-h", "--help", "--version", "--cite")):
        print_wish_banner()
        banner_already_printed = True

    parser = build_parser()
    args = parser.parse_args()
    args.interface = "cli"

    def is_valid_basin_folder(folder: Path):

        dataset_names = {folder for _, folder in DATASETS.values()}

        try:
            for d in folder.iterdir():
                if d.is_dir() and d.name in dataset_names:
                    return True
        except Exception:
            pass

        return False

    # ---------------------------------------------------------
    # No arguments → show help
    # ---------------------------------------------------------

    if len(sys.argv) == 1:
        parser.print_help()
        return 0

    # ---------------------------------------------------------
    # Banner parsing & Quiet mode
    # ---------------------------------------------------------

    if args.coffee:
        args.quiet = True

    # Show banner for normal CLI runs unless quiet mode is enabled,
    # and avoid duplicate output if it was already shown for meta commands.
    if not args.quiet and not banner_already_printed:
        print_wish_banner()

    # ---------------------------------------------------------
    # Coffee ☕
    # ---------------------------------------------------------

    if args.coffee:
        _print_coffee()

        if not any([args.basin, args.cwc, args.cwc_station, getattr(args, "cwc_basin_filter", None), args.plot_only]):
            return 0

    # ---------------------------------------------------------
    # List mode
    # ---------------------------------------------------------

    if args.list:
        print("\nAvailable WRIS Basins:")
        for num, name in WRIS_BASINS.items():
            print(f"  [{num}] {name}")

        print("\nCWC Stations:")
        try:
            from .cwc import load_station_table

            stations = load_station_table(refresh=getattr(args, "cwc_refresh", False))
            count = 0 if stations is None else len(stations)
            print(f"  Total known stations: {count}")
            print("  Tip: use --cwc-station <CODE1 CODE2 ...> to download selected stations")
        except Exception:
            print("  Unable to load CWC station metadata right now.")
        return 0

    # ---------------------------------------------------------
    # Parse numbered basin input
    # ---------------------------------------------------------

    if args.basin and args.basin in WRIS_BASINS:
        args.basin = WRIS_BASINS[args.basin]

    # ---------------------------------------------------------
    # MERGE-ONLY MODE
    # ---------------------------------------------------------

    if args.merge_only:

        if not args.input_dir:
            raise SystemExit("--merge-only requires --input-dir")

        root = Path(args.input_dir)

        if not root.exists():
            raise SystemExit("Input directory not found")

        # -----------------------------------------------------
        # Detect WRIS root / basin folders
        # -----------------------------------------------------

        dataset_names = {folder for _, folder in DATASETS.values()}

        wris_root = root / "wris"
        if wris_root.exists() and wris_root.is_dir():
            input_root = wris_root
        else:
            input_root = root

        if any((input_root / d).is_dir() and d in dataset_names for d in os.listdir(input_root)):
            basin_dirs = [input_root]
        else:
            basin_dirs = [d for d in input_root.iterdir() if d.is_dir() and is_valid_basin_folder(d)]

        selected = selected_datasets(args)

        output_base = Path(args.output_dir) if args.output_dir else root
        output_base.mkdir(parents=True, exist_ok=True)

        for basin_dir in basin_dirs:

            basin = basin_dir.name

            if not selected:
                dataset_dirs = [
                    d for d in basin_dir.iterdir() if d.is_dir()
                ]
            else:
                dataset_dirs = [
                    basin_dir / folder for _, folder in selected.items()
                ]

            for d in dataset_dirs:

                gpkg_path = output_base / f"{basin}_{d.name}.gpkg"

                merge_dataset_folder(str(d), str(gpkg_path), d.name)

        return 0

    # ---------------------------------------------------------
    # PLOT-ONLY MODE
    # ---------------------------------------------------------

    if args.plot_only:

        if not args.input_dir:
            raise SystemExit("--plot-only requires --input-dir")

        root = Path(args.input_dir)

        if not root.exists():
            raise SystemExit("Input directory not found")

        return run_plot_only(args)

    # ---------------------------------------------------------
    # CWC compatibility check
    # ---------------------------------------------------------

    if args.cwc or getattr(args, "cwc_basin_filter", None):

        unsupported = []

        if args.q:
            unsupported.append("discharge")
        if args.rf:
            unsupported.append("rainfall")
        if args.temp:
            unsupported.append("temperature")
        if args.rh:
            unsupported.append("humidity")
        if args.solar:
            unsupported.append("solar radiation")
        if args.sed:
            unsupported.append("sediment")
        if args.gwl:
            unsupported.append("groundwater")
        if args.atm:
            unsupported.append("atmospheric pressure")

        if unsupported:
            from .utils import Console
            Console.warn("CWC API only supports water level data.")
            if not args.quiet:
                print(f"  Ignoring unsupported datasets: {', '.join(unsupported)}\n")

    # ---------------------------------------------------------
    # CWC download
    # ---------------------------------------------------------

    if args.cwc or args.cwc_station or getattr(args, "cwc_basin_filter", None):
        return run_cwc_download(args)

    # ---------------------------------------------------------
    # Citation
    # ---------------------------------------------------------

    if args.cite:
        print("""
        If you use HydroSwift in your research, please consider citing:

        Sarat, C., Dash, D., & Kumar, A. (2026).
        HydroSwift: Automated Retrieval of Hydrological Station Data
        from India-WRIS and CWC Portals.
        Journal of Open Source Software.

        Repository:
        https://github.com/carbform/HydroSwift
        """)
        return 0

    # ---------------------------------------------------------
    # DEFAULT WRIS DOWNLOAD
    # ---------------------------------------------------------

    if not args.basin:
        raise SystemExit("Error: basin required unless using --cwc")

    client = WrisClient(delay=args.delay)

    if not client.check_api():
        raise SystemExit(1)

    basin_code = client.get_basin_code(args.basin)

    selected = selected_datasets(args)

    if not selected:
        raise SystemExit("No dataset selected")

    run_wris_download(args, selected, client, basin_code)

    if args.plot:
        args.input_dir = str(Path(args.output_dir) / "wris" / args.basin.lower())
        run_plot_only(args)

    return 0
