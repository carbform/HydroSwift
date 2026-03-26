import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock
from types import SimpleNamespace
import importlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
cwc_mod = importlib.import_module("swift_app.cwc")
fetch_station_data = cwc_mod.fetch_station_data
download_station = cwc_mod.download_station


def test_cwc_download_retry_logic(monkeypatch):
    """Test exponential backoff logic for CWC downloads."""
    # Isolate to the primary new-entry helper so retries stay deterministic.
    monkeypatch.setattr(cwc_mod, "_fetch_legacy_discharge", lambda *a, **k: None)
    monkeypatch.setattr(cwc_mod, "DISCHARGE_DATATYPES", ())

    # Mock sequence: failure, failure, success for water-level endpoint.
    mock_resp_fail = MagicMock()
    mock_resp_fail.status_code = 500

    mock_resp_succ = MagicMock()
    mock_resp_succ.status_code = 200
    mock_resp_succ.json.return_value = [
        {"stationCode": "TestStation", "id": {"dataTime": "2026-03-01"}, "dataValue": 10.5}
    ]

    mock_get = MagicMock(side_effect=[mock_resp_fail, mock_resp_fail, mock_resp_succ])
    monkeypatch.setattr(cwc_mod.session, "get", mock_get)

    from unittest.mock import patch
    with patch("time.sleep") as mock_sleep:
        # Ensure it works after failures
        result = fetch_station_data("TestStation")
    assert result is not None
    assert len(result) == 1
    assert result["water_level"].iloc[0] == 10.5
    
    # It should have called get 3 times
    assert mock_get.call_count == 3
    # It should have slept twice
    assert mock_sleep.call_count == 2


def test_fetch_station_data_returns_water_level_for_discharge_requests(monkeypatch):
    """Discharge requests still fetch stage; RC conversion happens later."""
    import pandas as pd

    wl = pd.DataFrame(
        {
            "station_code": ["040-CDJAPR"],
            "time": [pd.Timestamp("2024-01-01 00:00:00")],
            "water_level": [105.5],
        }
    )

    def fake_new_entry(code, start_date=None, end_date=None, datatype_code=None, value_col=None, retries=3):
        if value_col == "water_level":
            return wl
        return None

    monkeypatch.setattr(cwc_mod, "_fetch_new_entry_timeseries", fake_new_entry)
    monkeypatch.setattr(cwc_mod, "_fetch_legacy_discharge", lambda *a, **k: None)
    monkeypatch.setattr(cwc_mod, "DISCHARGE_DATATYPES", ("DISCHARG",))

    out = cwc_mod.fetch_station_data("040-CDJAPR", variables=["water_level", "discharge"])
    assert out is not None
    assert "water_level" in out.columns
    assert "discharge" not in out.columns


def test_fetch_station_data_does_not_use_legacy_discharge_endpoint(monkeypatch):
    """HydroSwift discharge is RC-based; legacy discharge endpoint is not used."""
    import pandas as pd

    wl = pd.DataFrame(
        {
            "station_code": ["040-CDJAPR"],
            "time": [pd.Timestamp("2024-01-01 00:00:00")],
            "water_level": [101.0],
        }
    )

    def fake_new_entry(code, start_date=None, end_date=None, datatype_code=None, value_col=None, retries=3):
        if value_col == "water_level":
            return wl
        return None

    legacy_called = {"yes": False}
    def fake_legacy(*args, **kwargs):
        legacy_called["yes"] = True
        return None

    monkeypatch.setattr(cwc_mod, "_fetch_new_entry_timeseries", fake_new_entry)
    monkeypatch.setattr(cwc_mod, "_fetch_legacy_discharge", fake_legacy)
    monkeypatch.setattr(cwc_mod, "DISCHARGE_DATATYPES", ("DISCHARG",))

    out = cwc_mod.fetch_station_data("040-CDJAPR", variables=["water_level", "discharge"])
    assert out is not None
    assert "discharge" not in out.columns
    assert legacy_called["yes"] is False


def test_download_station_writes_wse_and_discharge_columns(monkeypatch, tmp_path):
    """CWC station files should include `wse` and discharge-compatible fields."""

    station = {
        "code": "040-CDJAPR",
        "name": "Parwan",
        "lat": 24.0,
        "lon": 76.0,
        "rl_zero": 100.0,
    }

    def fake_fetch_station_data(code, start_date=None, end_date=None, retries=3, variables=None):
        import pandas as pd
        return pd.DataFrame(
            {
                "station_code": [code],
                "time": ["2024-01-01 08:00:00"],
                "water_level": [105.5],
                "discharge": [300.0],
            }
        )

    cwc_mod = importlib.import_module("swift_app.cwc")
    monkeypatch.setattr(cwc_mod, "fetch_station_data", fake_fetch_station_data)

    args = SimpleNamespace(
        format="csv",
        overwrite=True,
        start_date="2024-01-01",
        end_date="2024-01-02",
    )

    result = download_station(station, str(tmp_path), args)
    assert result is True

    out_files = list(tmp_path.glob("040-CDJAPR_*.csv"))
    assert out_files, "Expected station CSV file to be written"

    import pandas as pd
    df = pd.read_csv(out_files[0], comment="#")
    assert "wse" in df.columns
    assert df["wse"].iloc[0] == 105.5
    assert "discharge" in df.columns
    assert "q" in df.columns
    assert df["q"].iloc[0] == 300.0


def test_download_station_estimates_discharge_from_rc_when_api_missing(monkeypatch, tmp_path):
    """If API discharge is missing, RC fallback should populate q/discharge."""
    station = {
        "code": "040-CDJAPR",
        "name": "Parwan",
        "lat": 24.0,
        "lon": 76.0,
        "rl_zero": 100.0,
    }

    def fake_fetch_station_data(code, start_date=None, end_date=None, retries=3, variables=None):
        import pandas as pd
        return pd.DataFrame(
            {
                "station_code": [code],
                "time": ["2024-07-01 08:00:00"],  # monsoon
                "water_level": [10.0],
            }
        )

    # poly2: q = 2*x^2 + 3*x + 4 = 234
    rc_row = {
        "algo_m": 1,
        "m_poly_p1": 2.0,
        "m_poly_p2": 3.0,
        "m_poly_p3": 4.0,
        "algo_nm": 1,
        "nm_poly_p1": 1.0,
        "nm_poly_p2": 1.0,
        "nm_poly_p3": 1.0,
    }

    cwc_mod = importlib.import_module("swift_app.cwc")
    monkeypatch.setattr(cwc_mod, "fetch_station_data", fake_fetch_station_data)
    monkeypatch.setattr(cwc_mod, "_get_rc_row", lambda code, name=None: rc_row)

    args = SimpleNamespace(
        format="csv",
        overwrite=True,
        start_date="2024-07-01",
        end_date="2024-07-02",
    )

    result = download_station(station, str(tmp_path), args)
    assert result is True

    out_files = list(tmp_path.glob("040-CDJAPR_*.csv"))
    assert out_files

    import pandas as pd
    df = pd.read_csv(out_files[0], comment="#")
    assert "discharge" in df.columns
    assert "q" in df.columns
    assert abs(df["q"].iloc[0] - 234.0) < 1e-9
    assert df["discharge_source"].iloc[0] == "rc_guardian_2024"


def test_download_station_skips_rc_when_disabled(monkeypatch, tmp_path):
    station = {
        "code": "040-CDJAPR",
        "name": "Parwan",
        "lat": 24.0,
        "lon": 76.0,
        "rl_zero": 100.0,
    }

    def fake_fetch_station_data(code, start_date=None, end_date=None, retries=3, variables=None):
        import pandas as pd
        return pd.DataFrame(
            {
                "station_code": [code],
                "time": ["2024-07-01 08:00:00"],
                "water_level": [10.0],
            }
        )

    rc_row = {
        "algo_m": 1,
        "m_poly_p1": 2.0,
        "m_poly_p2": 3.0,
        "m_poly_p3": 4.0,
    }

    cwc_mod = importlib.import_module("swift_app.cwc")
    monkeypatch.setattr(cwc_mod, "fetch_station_data", fake_fetch_station_data)
    monkeypatch.setattr(cwc_mod, "_get_rc_row", lambda code, name=None: rc_row)

    args = SimpleNamespace(
        format="csv",
        overwrite=True,
        start_date="2024-07-01",
        end_date="2024-07-02",
        cwc_rc_discharge=False,
    )

    result = download_station(station, str(tmp_path), args)
    assert result is True
    out_files = list(tmp_path.glob("040-CDJAPR_*.csv"))
    assert out_files

    import pandas as pd
    df = pd.read_csv(out_files[0], comment="#")
    assert "q" not in df.columns
    assert "discharge" not in df.columns


def test_run_cwc_download_applies_basin_filter_before_download(monkeypatch, tmp_path):
    import pandas as pd
    cwc_mod = importlib.import_module("swift_app.cwc")

    stations_df = pd.DataFrame(
        [
            {"code": "001-AAA", "name": "A", "basin": "Krishna"},
            {"code": "002-BBB", "name": "B", "basin": "Godavari"},
            {"code": "003-CCC", "name": "C", "basin": "Mahanadi"},
        ]
    )

    basin_df = pd.DataFrame(
        [
            {"code": "001-AAA", "name": "A", "basin": "Krishna"},
            {"code": "002-BBB", "name": "B", "basin": "Godavari"},
        ]
    )

    monkeypatch.setattr(cwc_mod, "load_station_table", lambda refresh=False: stations_df)
    monkeypatch.setattr(
        cwc_mod,
        "get_cwc_station_metadata",
        lambda station=None, basin=None, river=None, state=None, refresh=False: basin_df,
    )

    seen = []

    def fake_download_station(station, output_dir, args):
        seen.append(str(station["code"]))
        return True

    monkeypatch.setattr(cwc_mod, "download_station", fake_download_station)

    args = SimpleNamespace(
        output_dir=str(tmp_path),
        quiet=True,
        cwc_refresh=False,
        cwc_station=None,
        cwc_basin_filter=["Krishna", "Godavari"],
        start_date="2024-01-01",
        end_date="2024-01-07",
        format="csv",
        overwrite=True,
        plot=False,
        merge=False,
        basin=None,
    )

    cwc_mod.run_cwc_download(args)

    assert set(seen) == {"001-AAA", "002-BBB"}


def test_run_cwc_download_intersects_station_and_basin_filters(monkeypatch, tmp_path):
    import pandas as pd
    cwc_mod = importlib.import_module("swift_app.cwc")

    stations_df = pd.DataFrame(
        [
            {"code": "001-AAA", "name": "A", "basin": "Krishna"},
            {"code": "002-BBB", "name": "B", "basin": "Godavari"},
            {"code": "003-CCC", "name": "C", "basin": "Mahanadi"},
        ]
    )

    basin_df = pd.DataFrame(
        [
            {"code": "001-AAA", "name": "A", "basin": "Krishna"},
            {"code": "002-BBB", "name": "B", "basin": "Godavari"},
        ]
    )

    monkeypatch.setattr(cwc_mod, "load_station_table", lambda refresh=False: stations_df)
    monkeypatch.setattr(
        cwc_mod,
        "get_cwc_station_metadata",
        lambda station=None, basin=None, river=None, state=None, refresh=False: basin_df,
    )

    seen = []

    def fake_download_station(station, output_dir, args):
        seen.append(str(station["code"]))
        return True

    monkeypatch.setattr(cwc_mod, "download_station", fake_download_station)

    args = SimpleNamespace(
        output_dir=str(tmp_path),
        quiet=True,
        cwc_refresh=False,
        cwc_station=["002-BBB", "003-CCC"],
        cwc_basin_filter=["Krishna", "Godavari"],
        start_date="2024-01-01",
        end_date="2024-01-07",
        format="csv",
        overwrite=True,
        plot=False,
        merge=False,
        basin=None,
    )

    cwc_mod.run_cwc_download(args)

    assert seen == ["002-BBB"]


def test_run_cwc_download_uses_basin_arg_as_filter_fallback(monkeypatch, tmp_path):
    import pandas as pd
    cwc_mod = importlib.import_module("swift_app.cwc")

    stations_df = pd.DataFrame(
        [
            {"code": "001-AAA", "name": "A", "basin": "Krishna"},
            {"code": "002-BBB", "name": "B", "basin": "Godavari"},
            {"code": "003-CCC", "name": "C", "basin": "Mahanadi"},
        ]
    )

    basin_df = pd.DataFrame(
        [
            {"code": "001-AAA", "name": "A", "basin": "Krishna"},
            {"code": "002-BBB", "name": "B", "basin": "Godavari"},
        ]
    )

    monkeypatch.setattr(cwc_mod, "load_station_table", lambda refresh=False: stations_df)
    monkeypatch.setattr(
        cwc_mod,
        "get_cwc_station_metadata",
        lambda station=None, basin=None, river=None, state=None, refresh=False: basin_df,
    )

    seen = []

    def fake_download_station(station, output_dir, args):
        seen.append(str(station["code"]))
        return True

    monkeypatch.setattr(cwc_mod, "download_station", fake_download_station)

    args = SimpleNamespace(
        output_dir=str(tmp_path),
        quiet=True,
        cwc_refresh=False,
        cwc_station=None,
        cwc_basin_filter=None,
        basin=["Krishna", "Godavari"],
        start_date="2024-01-01",
        end_date="2024-01-07",
        format="csv",
        overwrite=True,
        plot=False,
        merge=False,
    )

    cwc_mod.run_cwc_download(args)

    assert set(seen) == {"001-AAA", "002-BBB"}


def test_repopulate_cwc_metadata_from_name_code_appends_discovered_rows(monkeypatch, tmp_path):
    import pandas as pd
    cwc_mod = importlib.import_module("swift_app.cwc")

    current = pd.DataFrame(
        [
            {"code": "001-AAA", "name": "A", "basin": "Krishna"},
        ]
    )
    monkeypatch.setattr(cwc_mod, "load_station_table", lambda refresh=False: current)

    name_code = tmp_path / "name-code.csv"
    name_code.write_text("code,name\n001-AAA,A\n002-BBB,B\n")
    monkeypatch.setattr(cwc_mod, "NAME_CODE_CSV", name_code)

    ff_map = {"002-BBB": {"warningLevel": 1.0, "dangerLevel": 2.0}}

    monkeypatch.setattr(
        cwc_mod,
        "_fetch_all_lookups",
        lambda: (
            {10: "Godavari River"},
            lambda lr_id: "Godavari",
            lambda tahsil_id: "Telangana",
            lambda tahsil_id: "Nizamabad",
            lambda subdiv_id: "UGD",
            ff_map,
        ),
    )

    monkeypatch.setattr(
        cwc_mod,
        "_fetch_station_detail",
        lambda code, retries=3: {
            "name": "B",
            "streamLocalriverId": 10,
            "tahsilId": 20,
            "subdivisionalOfficeId": 30,
            "lat": 18.0,
            "lon": 79.0,
            "reducedLevelOfZeroGauge": 123.4,
        }
        if code == "002-BBB"
        else None,
    )

    merged, appended = cwc_mod.repopulate_cwc_metadata_from_name_code(write_packaged=False)

    assert set(merged["code"].tolist()) == {"001-AAA", "002-BBB"}
    assert appended["code"].tolist() == ["002-BBB"]
    row = merged[merged["code"] == "002-BBB"].iloc[0]
    assert row["basin"] == "Godavari"
    assert row["warning_level"] == 1.0
