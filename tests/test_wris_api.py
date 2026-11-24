"""Unit tests for the official India-WRIS REST API catalog adapter."""

import pytest
from unittest.mock import MagicMock
from hydroswift.sources.wris_api import WrisClient, normalize_wris_variable


def test_normalize_wris_variable():
    assert normalize_wris_variable("rainfall") == "RainFall"
    assert normalize_wris_variable("water_level") == "River Water Level"
    assert normalize_wris_variable("groundwater") == "Ground Water Level"
    assert normalize_wris_variable("temperature") == "Temperature"
    assert normalize_wris_variable("non_existent_var") is None


def test_wris_client_fetch_admin_mock(monkeypatch):
    client = WrisClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "statusCode": 200,
        "message": "Data fetched successfully",
        "data": [
            {
                "stationCode": "048-TEST",
                "stationName": "TEST_STATION",
                "dataValue": 5.4,
                "unit": "mm",
                "dataTime": "2024-12-01T08:30:00",
            }
        ]
    }
    monkeypatch.setattr(client.session, "post", lambda url, params, timeout: mock_resp)

    rows = client.fetch_admin("rainfall", "Andhra Pradesh", "Kadapa", "2024-12-01", "2024-12-02")
    assert len(rows) == 1
    assert rows[0]["stationCode"] == "048-TEST"
    assert rows[0]["dataValue"] == 5.4


def test_wris_client_fetch_basin_mock(monkeypatch):
    client = WrisClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "statusCode": 200,
        "data": [
            {
                "stationCode": "099-BASIN",
                "stationName": "BASIN_STATION",
                "dataValue": 10.2,
                "unit": "m",
            }
        ]
    }
    monkeypatch.setattr(client.session, "post", lambda url, params, timeout: mock_resp)

    rows = client.fetch_basin("water_level", "Krishna", "Tungabhadra", "2024-12-01", "2024-12-02")
    assert len(rows) == 1
    assert rows[0]["stationCode"] == "099-BASIN"


def test_wris_adapter_search():
    import hydroswift as hs
    from hydroswift.core.engine import WrisAdapter

    # Search with supported variable and location
    rows, st = WrisAdapter().search("rainfall", "Kadapa")
    assert st.ok is True
    assert len(rows) > 0
    assert any(r["ID"] == "048-HDCHENNAI" for r in rows)
    assert rows[0]["Variable"] == "RainFall"
    assert rows[0]["Source"] == "WRIS"

    # Search with unsupported variable
    rows_empty, st_empty = WrisAdapter().search("satellite radar altimetry", "Kadapa")
    assert len(rows_empty) == 0
    assert "does not serve" in st_empty.note

    # Exact basin search
    df = hs.search("rainfall", basin="Pennar", sources=["WRIS"])
    assert not df.empty
    assert (df["Source"] == "WRIS").all()
    assert all("Pennar" in loc for loc in df["Location"])


def test_wris_adapter_fetch_and_tidy(monkeypatch, tmp_path):
    import pandas as pd
    import hydroswift as hs
    from hydroswift.core.engine import WrisAdapter, FetchOptions
    from hydroswift.core.tidy import tidy_wris, TIDY_COLUMNS

    mock_client = MagicMock()
    mock_client.fetch_admin.return_value = [
        {
            "stationCode": "048-HDCHENNAI",
            "stationName": "RAYACHOTI",
            "stationType": "Surface Water",
            "latitude": 14.0667,
            "longitude": 78.7553,
            "agencyName": "CWC",
            "state": "Andhra Pradesh",
            "district": "Kadapa",
            "majorBasin": "Pennar",
            "tributary": "Cheyyeru",
            "dataAcquisitionMode": "Manual",
            "datatypeCode": "MPS",
            "description": "MANUAL-Rainfall - SRG(Standard Rain Gauge)",
            "dataValue": 2.4,
            "dataTime": "2024-12-01T08:30:00",
            "unit": "mm",
        }
    ]
    monkeypatch.setattr(WrisAdapter, "client_factory", staticmethod(lambda: mock_client))

    # Test adapter fetch
    row = {
        "ID": "048-HDCHENNAI",
        "Title": "RAYACHOTI",
        "Source": "WRIS",
        "Variable": "RainFall",
        "_var": "RainFall",
        "_state": "Andhra Pradesh",
        "_district": "Kadapa",
    }
    opts = FetchOptions(output_dir=str(tmp_path), start_date="2024-12-01", end_date="2024-12-02")
    rec = WrisAdapter().fetch(row, opts)
    assert rec.status == "saved"
    assert rec.records == 1
    assert rec.path is not None
    assert "048_HDCHENNAI_RainFall.csv" in rec.path

    # Test tidy loading
    df_raw = pd.read_csv(rec.path)
    tidy_df, err = tidy_wris(df_raw, rec.path)
    assert err is None
    assert list(tidy_df.columns) == TIDY_COLUMNS
    assert tidy_df.iloc[0]["variable"] == "rainfall"
    assert tidy_df.iloc[0]["unit"] == "mm"
    assert tidy_df.iloc[0]["value"] == 2.4
    assert tidy_df.iloc[0]["station_id"] == "048-HDCHENNAI"
    assert tidy_df.iloc[0]["source"] == "WRIS"


def test_wris_end_to_end_search_fetch_load(monkeypatch, tmp_path):
    import hydroswift as hs
    from hydroswift.core.engine import WrisAdapter

    mock_client = MagicMock()
    mock_client.fetch_admin.return_value = [
        {
            "stationCode": "048-HDCHENNAI",
            "stationName": "RAYACHOTI",
            "stationType": "Surface Water",
            "latitude": 14.0667,
            "longitude": 78.7553,
            "agencyName": "CWC",
            "state": "Andhra Pradesh",
            "district": "Kadapa",
            "majorBasin": "Pennar",
            "tributary": "Cheyyeru",
            "dataAcquisitionMode": "Manual",
            "datatypeCode": "MPS",
            "description": "MANUAL-Rainfall - SRG(Standard Rain Gauge)",
            "dataValue": 12.5,
            "dataTime": "2024-12-01T08:30:00",
            "unit": "mm",
        }
    ]
    monkeypatch.setattr(WrisAdapter, "client_factory", staticmethod(lambda: mock_client))

    # 1. Search
    cat = hs.search("rainfall", location="Kadapa", sources=["WRIS"])
    assert not cat.empty
    assert cat.iloc[0]["Source"] == "WRIS"

    # 2. Estimate
    est = hs.estimate(cat, network=False)
    assert "unknown" in est.iloc[0]["EstNote"]

    # 3. Fetch
    res = hs.fetch(cat.head(1), output_dir=str(tmp_path), period=("2024-12-01", "2024-12-02"))
    assert res.iloc[0]["status"] == "saved"

    # 4. Load
    tidy = hs.load(res)
    assert len(tidy) == 1
    assert tidy.iloc[0]["variable"] == "rainfall"
    assert tidy.iloc[0]["value"] == 12.5
    assert tidy.iloc[0]["source"] == "WRIS"

