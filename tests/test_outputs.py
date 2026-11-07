"""merge() and plot() are built on load(); both must fail loudly when nothing maps."""
import json

import pandas as pd
import pytest

import swift_app.outputs as out
from swift_app.tidy import TIDY_COLUMNS


def run_frame(tmp_path, n=3, src="NWDP", lat=13.0):
    f = tmp_path / "r.csv"
    pd.DataFrame({"Station Code": ["A"] * n, "Location Name": ["Gandsi"] * n, "Latitude": [lat] * n,
                  "Longitude": [76.0] * n, "Monitoring Date": [f"{i + 1:02d}-06-2020" for i in range(n)],
                  "Rainfall (MM)": list(range(n))}).to_csv(f, index=False)
    return pd.DataFrame([{"source": src, "title": "Rainfall Manual Daily", "path": str(f), "status": "saved"}])


def test_merge_csv_and_parquet_roundtrip(tmp_path):
    run = run_frame(tmp_path)
    df = out.merge(run, tmp_path / "m.csv")
    assert list(df.columns) == TIDY_COLUMNS and len(pd.read_csv(tmp_path / "m.csv")) == 3
    try:
        out.merge(run, tmp_path / "m.parquet")
        assert len(pd.read_parquet(tmp_path / "m.parquet")) == 3
    except ImportError:
        pytest.skip("no parquet engine")


def test_merge_gpkg_writes_points_and_refuses_when_no_coordinates(tmp_path):
    gpd = pytest.importorskip("geopandas")
    run = run_frame(tmp_path)
    out.merge(run, tmp_path / "m.gpkg")
    assert len(gpd.read_file(tmp_path / "m.gpkg")) == 3
    with pytest.raises(ValueError, match="No rows have coordinates"):
        out.merge(run_frame(tmp_path, lat=float("nan")), tmp_path / "n.gpkg")
    assert not (tmp_path / "n.gpkg").exists()


def test_merge_gpkg_warns_on_partial_coordinates(tmp_path):
    pytest.importorskip("geopandas")
    a = run_frame(tmp_path)
    f2 = tmp_path / "r2.csv"
    pd.DataFrame({"Station Code": ["B"], "Monitoring Date": ["01-06-2020"], "Rainfall (MM)": [1.0]}).to_csv(f2, index=False)
    run = pd.concat([a, pd.DataFrame([{"source": "NWDP", "title": "Rainfall", "path": str(f2), "status": "saved"}])], ignore_index=True)
    with pytest.warns(UserWarning, match="1 of 4 rows have no coordinates"):
        out.merge(run, tmp_path / "p.gpkg")


def test_merge_refuses_empty_and_unknown_type(tmp_path):
    bad = pd.DataFrame([{"source": "NWDP", "title": "x", "path": str(tmp_path / "gone.csv"), "status": "saved"}])
    with pytest.raises(ValueError, match="Nothing to merge"):
        out.merge(bad, tmp_path / "m.csv")
    with pytest.raises(ValueError, match="Unsupported"):
        out.merge(run_frame(tmp_path), tmp_path / "m.txt")


def test_plot_writes_png_and_labels_estimated_series(tmp_path):
    f = tmp_path / "c.csv"
    pd.DataFrame({"station_code": ["S1"] * 4, "time": pd.date_range("2022-01-01", periods=4, freq="h").astype(str),
                  "wse": [1, 2, 3, 4], "discharge": [10, 20, 30, 40], "lat": 1.0, "lon": 2.0,
                  "discharge_source": ["rc_guardian_2024"] * 4}).to_csv(f, index=False)
    run = pd.DataFrame([{"source": "CWC", "title": "S", "path": str(f), "status": "saved"}])
    paths = out.plot(run, tmp_path / "p")
    assert len(paths) == 2 and all(p.endswith(".png") for p in paths)
    assert len(out.plot(run, tmp_path / "p2", variable="discharge")) == 1
    assert out.plot(run, tmp_path / "p3", variable="rainfall") == []


def test_plot_warns_when_capped(tmp_path):
    frames = []
    rows = []
    for i in range(3):
        f = tmp_path / f"f{i}.csv"
        pd.DataFrame({"Station Code": [f"S{i}"], "Monitoring Date": ["01-06-2020"], "Rainfall (MM)": [1.0]}).to_csv(f, index=False)
        rows.append({"source": "NWDP", "title": "Rainfall", "path": str(f), "status": "saved"})
    with pytest.warns(UserWarning, match="plotting the first 2"):
        paths = out.plot(pd.DataFrame(rows), tmp_path / "p", max_series=2)
    assert len(paths) == 2
