"""Plot helpers for SWIFT."""

from __future__ import annotations

import os
from pathlib import Path

from .cli import DATASETS


def _collect_files(path: Path):
    """Collect CSV and XLSX station files recursively."""
    files = list(path.rglob("*.csv"))
    files.extend(path.rglob("*.xlsx"))
    return files


def run_plot_only(args) -> int:
    """Generate plots from existing SWIFT output folders without downloading."""

    import os
    from pathlib import Path
    from .cli import DATASETS, selected_datasets
    from .plot_station_timeseries import plot_station

    if not args.input_dir:
        raise SystemExit("--plot-only requires input_dir")

    root = Path(args.input_dir)

    if not root.exists():
        raise SystemExit("Input directory not found")

    # ---------------------------------------------------------
    # Dataset folder names
    # ---------------------------------------------------------

    dataset_names = {folder for _, folder in DATASETS.values()}

    # ---------------------------------------------------------
    # Detect WRIS root / basin directories
    # ---------------------------------------------------------

    wris_root = root / "wris"
    if wris_root.exists() and wris_root.is_dir():
        wris_input_root = wris_root
    else:
        wris_input_root = root

    if any((wris_input_root / d).is_dir() and d in dataset_names for d in os.listdir(wris_input_root)):
        basin_dirs = [wris_input_root]
    else:
        basin_dirs = [d for d in wris_input_root.iterdir() if d.is_dir()]

    selected = selected_datasets(args)

    print("\nPlot-only mode enabled.")

    total_plots = 0

    # ---------------------------------------------------------
    # CWC plotting
    # ---------------------------------------------------------

    if args.cwc:

        # CWC layout: <root>/cwc/<optional_basin>/stations/*.csv
        # Scan under the top-level cwc directory so that both the
        # legacy flat layout and the new basin-aware layout work.
        cwc_root = root / "cwc"

        if not cwc_root.exists():
            print("No CWC output found.")
            return 1

        files = _collect_files(cwc_root)

        if not files:
            print("No CWC station files found.")
            return 1

        print("\nScanning CWC stations:", len(files))

        image_root = str(args.output_dir) if getattr(args, "output_dir", None) else None

        for file in files:
            plot_station(
                file,
                image_root=image_root,
                include_images_subdir=False if image_root else True,
                export_png=not getattr(args, "plot_svg", False),
                export_svg=getattr(args, "plot_svg", False),
                moving_average_window=getattr(args, "plot_moving_average_window", None),
            )
            total_plots += 1

        print("\nPlots generated:", total_plots)
        return 0

    # ---------------------------------------------------------
    # WRIS plotting
    # ---------------------------------------------------------

    for basin_dir in basin_dirs:

        basin = basin_dir.name

        if not selected:

            files = _collect_files(basin_dir)

            if files:
                print(f"\nScanning WRIS basin folder: {basin_dir}")
                print("Stations found:", len(files))

                image_root = str(args.output_dir) if getattr(args, "output_dir", None) else None

                for file in files:
                    plot_station(
                        file,
                        image_root=image_root,
                        include_images_subdir=False if image_root else True,
                        export_png=not getattr(args, "plot_svg", False),
                        export_svg=getattr(args, "plot_svg", False),
                        moving_average_window=getattr(args, "plot_moving_average_window", None),
                    )
                    total_plots += 1

        else:

            for _, folder in selected.items():

                variable_dir = basin_dir / folder

                if not variable_dir.exists():
                    print(f"Dataset '{folder}' not found in basin: {basin}")
                    continue

                files = _collect_files(variable_dir)

                print(f"\nPlotting {basin} / {folder} ({len(files)} stations)")

                image_root = str(args.output_dir) if getattr(args, "output_dir", None) else None

                for file in files:
                    plot_station(
                        file,
                        image_root=image_root,
                        include_images_subdir=False if image_root else True,
                        export_png=not getattr(args, "plot_svg", False),
                        export_svg=getattr(args, "plot_svg", False),
                        moving_average_window=getattr(args, "plot_moving_average_window", None),
                    )
                    total_plots += 1

    if total_plots == 0:
        print("No station files found.")
        return 1

    print("\nPlots generated:", total_plots)

    return 0
