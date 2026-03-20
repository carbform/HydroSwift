import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_plot_station_generates_svg_only_with_moving_average_when_requested(tmp_path):
    pytest.importorskip("matplotlib")
    import pandas as pd
    from swift_app.plot_station_timeseries import plot_station

    station_dir = tmp_path / "wris" / "krishna" / "discharge"
    station_dir.mkdir(parents=True)

    df = pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=10, freq="D"),
            "value": [1, 2, 3, 4, 3, 5, 4, 6, 5, 7],
            "unit": ["m3/s"] * 10,
        }
    )
    csv_path = station_dir / "station_001.csv"
    df.to_csv(csv_path, index=False)

    plot_station(
        csv_path,
        image_root=str(tmp_path),
        include_images_subdir=True,
        export_svg=True,
        moving_average_window=3,
    )

    out_png = tmp_path / "wris" / "krishna" / "images" / "discharge" / "station_001.png"
    out_svg = tmp_path / "wris" / "krishna" / "images" / "discharge" / "station_001.svg"

    assert not out_png.exists()
    assert out_svg.exists()
