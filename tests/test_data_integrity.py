"""Regression tests: data must never be misattributed, silently lost or circular."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
import requests

from hydroswift.core import engine
from hydroswift.core.tidy import TIDY_COLUMNS, tidy_wris
from hydroswift.gui import plotdata
from hydroswift.sources.wris_api import WrisClient, WrisError

ROW = {"Source": "WRIS", "ID": "WANTED", "Title": "Wanted", "_state": "Kerala",
       "_district": "X", "_var": "River Water Level"}


def _reply(data, code=200, message="ok", http=200):
    r = MagicMock(status_code=http, text=message)
    r.json.return_value = {"statusCode": code, "message": message, "data": data}
    return r


def _fetch(monkeypatch, tmp_path, client):
    monkeypatch.setattr(engine.WrisAdapter, "client_factory", staticmethod(lambda: client))
    return engine.WrisAdapter().fetch(ROW, engine.FetchOptions(str(tmp_path), "2024-01-01", "2024-01-31"))


def _client(*replies):
    client = WrisClient()
    queue = list(replies)

    def post(url, params, timeout):
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
    client.session.post = post
    return client


def _rows(n, code="WANTED", start=0):
    return [{"stationCode": code, "dataTime": f"2024-01-01T00:00:00.{i}", "dataValue": i}
            for i in range(start, start + n)]


def test_wris_never_saves_other_stations_rows(monkeypatch, tmp_path):
    rec = _fetch(monkeypatch, tmp_path, _client(_reply(_rows(3, "OTHER"))))
    assert (rec.status, rec.records, rec.path) == ("empty", 0, None)
    assert "none for station WANTED" in rec.error


def test_wris_rows_without_station_code_are_rejected(monkeypatch, tmp_path):
    rec = _fetch(monkeypatch, tmp_path, _client(_reply([{"dataValue": 1}])))
    assert rec.status == "error" and rec.path is None


@pytest.mark.parametrize("reply", [
    requests.ConnectionError("down"),
    _reply([], http=503, message="unavailable"),
    _reply([], code=500, message="Internal failure"),
])
def test_wris_failures_are_errors_not_empty(monkeypatch, tmp_path, reply):
    rec = _fetch(monkeypatch, tmp_path, _client(*[reply] * WrisClient.ATTEMPTS))
    assert rec.status == "error" and rec.error


def test_wris_no_data_reply_is_empty(monkeypatch, tmp_path):
    reply = _reply([], code=500, message="No data found for the given criteria.")
    rec = _fetch(monkeypatch, tmp_path, _client(reply))
    assert rec.status == "empty" and rec.error is None


def test_wris_follows_every_page(monkeypatch, tmp_path):
    client = _client(_reply(_rows(1000)), _reply(_rows(5, start=1000)))
    rec = _fetch(monkeypatch, tmp_path, client)
    assert (rec.status, rec.records, rec.complete) == ("saved", 1005, True)


def test_wris_later_page_failure_is_flagged_incomplete(monkeypatch, tmp_path):
    rec = _fetch(monkeypatch, tmp_path, _client(_reply(_rows(1000)), *[requests.Timeout("slow")] * WrisClient.ATTEMPTS))
    assert (rec.status, rec.records, rec.complete) == ("saved", 1000, False)
    assert "truncated" in rec.error


@pytest.fixture(autouse=True)
def _no_retry_wait(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)


def test_wris_retries_a_page_that_times_out(monkeypatch, tmp_path):
    rec = _fetch(monkeypatch, tmp_path, _client(requests.Timeout("slow"), _reply(_rows(2))))
    assert (rec.status, rec.records, rec.complete) == ("saved", 2, True)


def test_wris_gauge_height_is_not_mixed_with_sea_level_elevation():
    raw = pd.DataFrame({"dataTime": ["2024-01-01"] * 2, "dataValue": [434.76, 1.76], "unit": "m",
                        "datatypeCode": ["HHS", "HZS"],
                        "description": ["MANUAL-WL by Staff Gauge (MSL)", "MANUAL-Water Level by Staff Gauge (0)"]})
    out, why = tidy_wris(raw, "f.csv", "River Water Level")
    assert why is None
    assert out.set_index("value")["variable"].to_dict() == {434.76: "water_level", 1.76: "gauge_height"}
    assert out["flag"].str.startswith("series: ").all()


def test_wris_client_raises_on_connection_error():
    client = _client(*[requests.ConnectionError("down")] * WrisClient.ATTEMPTS)
    with pytest.raises(WrisError):
        client.fetch_admin("rainfall", "a", "b", "2024-01-01", "2024-01-02")


def test_resume_ignores_wris_files_without_completeness_mark(tmp_path):
    data = tmp_path / "old.csv"
    data.write_text("x\n1\n")
    item = {"source": "WRIS", "id": "WANTED", "status": "saved", "path": str(data),
            "req_start": None, "req_end": None, "complete": None}
    (tmp_path / "manifest.json").write_text(json.dumps({"items": [item]}))
    assert engine._find_prior(tmp_path, ("WRIS", "WANTED"), None, None) is None


def test_wris_acquisition_mode_is_not_treated_as_estimated():
    raw = pd.DataFrame({"dataTime": ["2024-01-01"], "dataValue": [1.0], "unit": ["m"],
                        "dataAcquisitionMode": ["Manual"]})
    out, why = tidy_wris(raw, "f.csv", "t")
    assert why is None
    assert out["method"].iloc[0] == "observed"
    assert "acquisition mode: manual" in out["flag"].iloc[0]


def _tidy(variable, method="observed", source="CWC", sid="S1", n=4):
    df = pd.DataFrame({"time": pd.date_range("2024-01-01", periods=n), "value": range(1, n + 1),
                       "variable": variable, "unit": "m", "station_id": sid, "station_name": "Same name",
                       "source": source, "lat": 10.0, "lon": 76.0, "method": method, "flag": None, "file": "f"})
    return df[TIDY_COLUMNS]


def test_rating_pairs_exclude_estimated_discharge():
    stage = _tidy("water_level")
    assert plotdata.rating_pairs(pd.concat([stage, _tidy("discharge", "rc_guardian_2024")])).empty
    assert len(plotdata.rating_pairs(pd.concat([stage, _tidy("discharge")]))) == 4


def test_library_rating_curve_skips_estimated_discharge(tmp_path):
    from hydroswift.core.outputs import plot
    df = pd.concat([_tidy("water_level"), _tidy("discharge", "rc_guardian_2024")])
    with pytest.warns(UserWarning, match="excluded from the rating curve"):
        assert plot(df, tmp_path, kind="rating_curve", thresholds=False) == []


def test_series_matches_variables_exactly():
    df = pd.concat([_tidy("groundwater_level"), _tidy("rainfall")])
    assert plotdata.series(df, "water_level", "reservoir_level").empty
    assert set(plotdata.series(df, "groundwater_level")["variable"]) == {"groundwater_level"}


def test_stations_with_same_name_from_two_sources_stay_separate():
    df = pd.concat([_tidy("water_level"), _tidy("water_level", source="WRIS")], ignore_index=True)
    options = plotdata.station_options(df)
    assert len(options) == 2
    assert all(df[mask]["source"].nunique() == 1 for mask in options.values())


def test_flood_thresholds():
    lookup = {"s1": {"warning_level": 5.0, "danger_level": float("nan")}}
    assert plotdata.flood_thresholds(_tidy("water_level"), lookup) == {"Warning Level": 5.0}
    assert plotdata.flood_thresholds(_tidy("water_level", source="NWDP"), lookup) == {}


@pytest.mark.parametrize("fmt", ["parquet", "gpkg", "json"])
def test_export_writes_the_requested_format(tmp_path, fmt):
    pytest.importorskip({"parquet": "pyarrow", "gpkg": "geopandas", "json": "json"}[fmt])
    path = plotdata.export_tidy(_tidy("water_level"), tmp_path, fmt)
    assert path.suffix == f".{fmt}" and path.stat().st_size > 0


def test_cwc_json_download_writes_a_file(monkeypatch, tmp_path):
    from hydroswift.sources.cwc_ffs import client as cwc
    monkeypatch.setattr(cwc, "fetch_station_data", lambda *a, **k: pd.DataFrame(
        {"time": ["2024-01-01T00:00:00"], "wse": [1.5]}))
    args = MagicMock(format="json", overwrite=True, start_date=None, end_date=None,
                     cwc_var=None, cwc_rc_discharge=False)
    res = cwc.download_station_detail({"code": "S1", "name": "A", "basin": "B"}, str(tmp_path), args)
    assert res["status"] == "saved" and Path(res["path"]).exists()
    from hydroswift.core.tidy import load
    tidy = load(pd.DataFrame([{"source": "CWC", "status": "saved", "path": res["path"], "title": "A"}]))
    assert tidy["value"].tolist() == [1.5]
