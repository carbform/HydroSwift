"""Engine tests: failures must be visible, paging must be complete, manifests must match files."""
import json
import warnings

import pandas as pd
import pytest

import swift_app.engine as eng
from swift_app.nwdp_client import NwdpClient


class FakeResp:
    def __init__(self, payload, status=200):
        self._p, self.status_code, self.text = payload, status, ""

    def json(self):
        return self._p


class FakeSession:
    """Serves CKAN package_search pages and datastore_search from canned data."""
    verify = False

    def __init__(self, packages=None, records=None, fail=None, total_override=None):
        self.packages, self.records = packages or [], records or []
        self.fail, self.total_override = fail, total_override
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        if self.fail:
            raise self.fail
        p = params or {}
        if url.endswith("package_search"):
            s, n = p.get("start", 0), p.get("rows", 1000)
            page = self.packages[s:s + n]
            return FakeResp({"success": True, "result": {"count": self.total_override or len(self.packages), "results": page}})
        if url.endswith("datastore_search"):
            s, n = p.get("offset", 0), p.get("limit", 10000)
            return FakeResp({"success": True, "result": {"total": len(self.records), "records": self.records[s:s + n]}})
        if url.endswith("organization_list"):
            return FakeResp({"success": True, "result": ["karnataka-gw"]})
        raise AssertionError(url)


def pkg(i, size=5000, rname="x"):
    return {"title": f"Rainfall Daily {i}", "name": f"ds{i}",
            "organization": {"title": "Karnataka GW", "name": "karnataka-gw"},
            "resources": [{"id": f"r{i}", "name": rname, "format": "CSV", "size": size}]}


@pytest.fixture
def nwdp(monkeypatch):
    def install(session):
        def factory():
            c = NwdpClient()
            c.session = session
            return c
        monkeypatch.setattr(eng.NwdpAdapter, "client_factory", staticmethod(factory))
    return install


def test_timeout_is_reported_not_silent(nwdp):
    nwdp(FakeSession(fail=TimeoutError("timed out")))
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        from swift_app import api
        df = api.search(query="rainfall", sources=["NWDP"])
    st = df.attrs["source_status"][0]
    assert df.empty and st["ok"] is False and "timed out" in st["error"]
    assert df.attrs["partial"] is True
    assert any("incomplete" in str(x.message) for x in w)


def test_paging_reads_all_packages(nwdp):
    s = FakeSession(packages=[pkg(i) for i in range(2500)])
    nwdp(s)
    df = eng.search_catalog("rainfall", sources=["NWDP"])
    assert len(df) == 2500 and not df.attrs["partial"]
    assert sum("package_search" in c[0] for c in s.calls) == 3  # 1000+1000+500


def test_truncated_listing_is_flagged(nwdp):
    nwdp(FakeSession(packages=[pkg(i) for i in range(10)], total_override=50))
    df = eng.search_catalog("rainfall", sources=["NWDP"])
    st = df.attrs["source_status"][0]
    assert st["complete"] is False and "10 of 50" in st["error"] and df.attrs["partial"]


def test_small_resources_are_counted(nwdp):
    nwdp(FakeSession(packages=[pkg(1), pkg(2, size=100)]))
    df = eng.search_catalog("rainfall", sources=["NWDP"])
    st = df.attrs["source_status"][0]
    assert len(df) == 1 and st["dropped"]["empty_resources(<=300 bytes)"] == 1


def test_schema_and_inferred_flags(nwdp):
    nwdp(FakeSession(packages=[pkg(1)]))
    df = eng.search_catalog("rainfall", sources=["NWDP"])
    assert list(df.columns[:len(eng.CATALOG_COLUMNS)]) == eng.CATALOG_COLUMNS
    assert df.loc[0, "Inferred"] == "Variable,Resolution"


def test_cwc_location_rule_and_matched_field():
    df = eng.search_catalog("discharge", "krishna", sources=["CWC"])
    assert len(df) > 0 and set(df["MatchedOn"]) <= {"basin", "state", "district", "river"}
    assert "basin" in set(df["MatchedOn"])
    assert (df["Inferred"].str.contains("Variable")).all()


def test_cwc_skipped_for_rainfall_with_reason():
    df = eng.search_catalog("rainfall", sources=["CWC"])
    st = df.attrs["source_status"][0]
    assert df.empty and "does not match" in st["note"] and st["ok"]


def test_unknown_source_rejected():
    with pytest.raises(ValueError):
        eng.search_catalog("x", sources=["WRIS2"])


def test_fetch_manifest_matches_file_and_date_filter(nwdp, tmp_path):
    recs = [{"date": f"2020-01-{d:02d}", "v": d} for d in range(1, 31)]
    nwdp(FakeSession(packages=[pkg(1)], records=recs))
    table = eng.search_catalog("rainfall", sources=["NWDP"])
    out = eng.fetch_catalog(table, output_dir=tmp_path, start_date="2020-01-10", end_date="2020-01-20", quiet=True)
    row = out.iloc[0]
    assert row["status"] == "saved" and row["records"] == 11 and row["filtered_client_side"]
    assert len(pd.read_csv(row["path"])) == row["records"]
    assert row["start"].startswith("2020-01-10") and row["end"].startswith("2020-01-20")
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert m["items"][0]["records"] == 11 and "verification DISABLED" in m["security_notes"]["NWDP"]
    assert m["query"]["query"] == "rainfall"


def test_fetch_failure_recorded_and_second_manifest_kept(nwdp, tmp_path):
    nwdp(FakeSession(packages=[pkg(1)]))
    table = eng.search_catalog("rainfall", sources=["NWDP"])
    nwdp(FakeSession(fail=ConnectionError("down")))
    out = eng.fetch_catalog(table, output_dir=tmp_path, quiet=True)
    assert out.iloc[0]["status"] == "error" and "down" in out.iloc[0]["error"]
    eng.fetch_catalog(table, output_dir=tmp_path, quiet=True)
    assert len(list(tmp_path.glob("manifest*.json"))) == 2


def test_api_fetch_warns_on_failures(nwdp, tmp_path):
    from swift_app import api
    nwdp(FakeSession(packages=[pkg(1)]))
    table = api.search("rainfall", sources=["NWDP"])
    nwdp(FakeSession(fail=ConnectionError("down")))
    with pytest.warns(UserWarning, match="downloads failed"):
        api.fetch(table, output_dir=str(tmp_path), quiet=True)


def test_period_in_resource_name_becomes_coverage_and_skips_download(nwdp, tmp_path):
    s = FakeSession(packages=[pkg(1, rname="Rain 1900 To 1928"), pkg(2, rname="Rain 2015 To 2020")],
                    records=[{"Monitoring Date": "05-03-2016", "v": 1}])
    nwdp(s)
    table = eng.search_catalog("rainfall", sources=["NWDP"])
    assert list(table["CoverageStart"]) == ["1900-01-01", "2015-01-01"]
    assert "Coverage" in table.loc[0, "Inferred"] and table.loc[0, "Title"] == "Rain 1900 To 1928"
    out = eng.fetch_catalog(table, output_dir=tmp_path, start_date="2016-01-01", end_date="2016-12-31", quiet=True)
    assert list(out["status"]) == ["skipped", "saved"]
    assert "outside the requested range" in out.loc[0, "error"]
    # only the overlapping resource was requested from the datastore
    assert sum("datastore_search" in c[0] for c in s.calls) == 1


def test_nwdp_dates_are_day_first(nwdp, tmp_path):
    nwdp(FakeSession(packages=[pkg(1)], records=[{"Monitoring Date": "01-04-1927"}, {"Monitoring Date": "31-12-1928"}]))
    table = eng.search_catalog("rainfall", sources=["NWDP"])
    out = eng.fetch_catalog(table, output_dir=tmp_path, quiet=True)
    assert out.loc[0, "start"].startswith("1927-04-01") and out.loc[0, "end"].startswith("1928-12-31")
    assert "19270401_19281231" in out.loc[0, "path"]


# ---------------------------------------------------------------- new engine features
import threading


def test_period_drops_known_outside_keeps_unknown_and_counts(nwdp):
    nwdp(FakeSession(packages=[pkg(1, rname="Rain 1900 To 1928"), pkg(2, rname="Rain 2015 To 2020"), pkg(3, rname="Rain no period")]))
    df = eng.search_catalog("rainfall", sources=["NWDP"], period=("2016", "2017"))
    assert list(df["Title"]) == ["Rain 2015 To 2020", "Rain no period"]
    st = df.attrs["source_status"][0]
    assert st["dropped"]["outside_period"] == 1 and "1 rows have unknown coverage" in st["note"]
    assert list(df["CoverageKnown"]) == [True, False]


def test_bad_period_rejected():
    with pytest.raises(ValueError):
        eng.parse_period(("2021", "2019"))
    assert eng.parse_period("2020:2022") == ("2020-01-01", "2022-12-31")


def test_ids_are_exact_not_substring(nwdp):
    nwdp(FakeSession(packages=[pkg(1), pkg(11)]))
    df = eng.search_catalog("rainfall", sources=["NWDP"], ids=["r1"])
    assert list(df["ID"]) == ["r1"]


def test_cwc_exact_basin_is_equality_and_nwdp_is_skipped_with_reason(nwdp):
    nwdp(FakeSession(packages=[pkg(1)]))
    exact = eng.search_catalog("discharge", basin="Krishna", sources=["CWC", "NWDP"])
    assert len(exact) > 0 and exact["Location"].str.split(",").str[0].str.strip().eq("Krishna").all()
    nw = [s for s in exact.attrs["source_status"] if s["source"] == "NWDP"][0]
    assert "skipped" in nw["note"] and not (exact["Source"] == "NWDP").any()
    partial = eng.search_catalog("discharge", location="rishn", sources=["CWC"])
    assert len(partial) >= len(exact)  # substring is broader than equality


def test_estimate_exact_for_nwdp_unknown_for_cwc(nwdp):
    nwdp(FakeSession(packages=[pkg(1)], records=[{"d": i} for i in range(7)]))
    t = pd.concat([eng.search_catalog("rainfall", sources=["NWDP"]),
                   eng.search_catalog("discharge", "krishna", sources=["CWC"]).head(1)], ignore_index=True)
    est = eng.estimate_catalog(t)
    assert est.loc[0, "EstRecords"] == 7
    assert pd.isna(est.loc[1, "EstRecords"]) and "unknown" in est.loc[1, "EstNote"]


def test_cancel_mid_download_marks_cancelled_and_writes_no_file(nwdp, tmp_path):
    nwdp(FakeSession(packages=[pkg(1)], records=[{"Monitoring Date": "01-01-2020", "v": i} for i in range(25000)]))
    table = eng.search_catalog("rainfall", sources=["NWDP"])
    ev = threading.Event()
    seen = []

    def cb(e):
        seen.append(e["event"])
        if e["event"] == "page":
            ev.set()

    out = eng.fetch_catalog(table, output_dir=tmp_path, progress=cb, cancel=ev)
    assert out.loc[0, "status"] == "cancelled"
    assert "page" in seen and "item_done" in seen
    assert not list((tmp_path / "nwdp").rglob("*.csv")) if (tmp_path / "nwdp").exists() else True


def test_faulty_progress_callback_does_not_break_download(nwdp, tmp_path):
    nwdp(FakeSession(packages=[pkg(1)], records=[{"Monitoring Date": "01-01-2020", "v": 1}]))
    table = eng.search_catalog("rainfall", sources=["NWDP"])
    out = eng.fetch_catalog(table, output_dir=tmp_path, progress=lambda e: 1 / 0)
    assert out.loc[0, "status"] == "saved"


def test_resume_same_request_reuses_but_different_period_redownloads(nwdp, tmp_path):
    s = FakeSession(packages=[pkg(1)], records=[{"Monitoring Date": "05-03-2016", "v": 1}])
    nwdp(s)
    table = eng.search_catalog("rainfall", sources=["NWDP"])
    a = eng.fetch_catalog(table, output_dir=tmp_path, period=("2016", "2016"))
    assert a.loc[0, "status"] == "saved"
    b = eng.fetch_catalog(table, output_dir=tmp_path, period=("2016", "2016"))
    assert b.loc[0, "status"] == "skipped" and b.loc[0, "reused"]
    c = eng.fetch_catalog(table, output_dir=tmp_path, period=("2016", "2016"))  # third run still reuses
    assert c.loc[0, "status"] == "skipped"
    d = eng.fetch_catalog(table, output_dir=tmp_path, period=("2015", "2017"))
    assert d.loc[0, "status"] == "saved"
    e = eng.fetch_catalog(table, output_dir=tmp_path, period=("2016", "2016"), overwrite=True)
    assert e.loc[0, "status"] == "saved"


def test_manifest_says_provenance_unavailable_when_attrs_lost(nwdp, tmp_path):
    nwdp(FakeSession(packages=[pkg(1), pkg(2)], records=[{"Monitoring Date": "05-03-2016", "v": 1}]))
    table = eng.search_catalog("rainfall", sources=["NWDP"])
    filtered = pd.DataFrame(table.to_dict("records"))  # rebuilt by hand: attrs are gone
    assert not filtered.attrs
    out = eng.fetch_catalog(filtered, output_dir=tmp_path)
    doc = json.loads(open(out.attrs["manifest"]).read())
    assert "unavailable" in doc["query"] and "unavailable" in doc["source_status"]


# ---------------------------------------------------------------- tidy / load
import swift_app.tidy as tidy


def _write(path, df, header=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + df.to_csv(index=False))
    return str(path)


def item(src, title, path, status="saved"):
    return {"source": src, "title": title, "path": path, "status": status}


def test_tidy_nwdp_rainfall_units_and_columns(tmp_path):
    p = _write(tmp_path / "r.csv", pd.DataFrame({
        "Station Code": ["A", "A"], "Location Name": ["Gandsi", "Gandsi"], "Latitude": [13.1, 13.1],
        "Longitude": [76.2, 76.2], "Monitoring Date": ["01-04-1927", "02-04-1927"], "Rainfall (MM)": [1.5, 0.0]}))
    out = tidy.load(pd.DataFrame([item("NWDP", "Rainfall Manual Daily Karnataka", p)]))
    assert list(out.columns) == tidy.TIDY_COLUMNS and len(out) == 2
    assert set(out["variable"]) == {"rainfall"} and set(out["unit"]) == {"mm"}
    assert out["time"].min() == pd.Timestamp("1927-04-01")  # day-first, not Jan 4
    assert out.loc[0, "station_name"] == "Gandsi" and out.loc[0, "lat"] == 13.1


def test_tidy_unit_normalisation_and_flags(tmp_path):
    base = {"Station": ["S"], "Latitude": [1.0], "Longitude": [2.0], "Data Acquisition Time": ["05-03-2016 14:00:00"]}
    cases = {
        "Air Temperature Telemetry Hourly (AoC)": ("temperature", "degC"),
        "Telemetry Hourly Wind Speed (Km/Hr)": ("wind_speed", "km/h"),
        "Telemetry_Hourly_Atmospheric Pressure (mb)": ("atm_pressure", "hPa"),
        "Solar Radiation (Watt/m2)": ("solar_radiation", "W/m2"),
    }
    for col, (var, unit) in cases.items():
        p = _write(tmp_path / f"{var}.csv", pd.DataFrame({**base, col: [3.0]}))
        out = tidy.load(pd.DataFrame([item("NWDP", col, p)]))
        assert (out.loc[0, "variable"], out.loc[0, "unit"]) == (var, unit), col
        assert out.loc[0, "time"] == pd.Timestamp("2016-03-05 14:00")


def test_tidy_groundwater_and_reservoir_use_title_and_flag(tmp_path):
    gw = _write(tmp_path / "g.csv", pd.DataFrame({"Station": ["S"], "RL_MSL": [100.0], "Data Acquisition Time": ["05-03-2016 14:00:00"],
                                                   "Groundwater Level Telemetry Quadridaily (meter)": [4.2]}))
    rs = _write(tmp_path / "rs.csv", pd.DataFrame({"Station": ["Pench"], "Data Acquisition Time": ["05-03-2016 14:00:00"], "Water Level (M)": [450.0]}))
    out = tidy.load(pd.DataFrame([item("NWDP", "Ground Water Level Kerala", gw),
                                  item("NWDP", "Reservoir Water Level, Pench Reservoir", rs)]))
    g = out[out.variable == "groundwater_level"].iloc[0]
    assert "depth vs elevation" in g["flag"] and g["value"] == 4.2   # RL_MSL not mistaken for the value
    assert (out.variable == "reservoir_level").sum() == 1


def test_tidy_multiple_named_columns_become_separate_variables(tmp_path):
    p = _write(tmp_path / "d.csv", pd.DataFrame({
        "Station": ["S"], "Data Acquisition Time": ["05-03-2016 14:00:00"], "River Water Level (m)": [2.0],
        "Area (m2)": [10.0], "Velocity (m/sec)": [0.5], "Total_discharge (m3/sec)": [5.0]}))
    out = tidy.load(pd.DataFrame([item("NWDP", "River Velocity and Discharge Rajasthan", p)]))
    assert sorted(out["variable"]) == ["discharge", "water_level"]
    assert out[out.variable == "discharge"].iloc[0]["unit"] == "m3/s"


def test_tidy_unstated_unit_is_flagged(tmp_path):
    p = _write(tmp_path / "q.csv", pd.DataFrame({"Station Code": ["S"], "Monitoring Date": ["05-03-2016"], "Water Discharge": [9.0]}))
    out = tidy.load(pd.DataFrame([item("NWDP", "Discharge Gauge Daily Karnataka", p)]))
    assert out.loc[0, "variable"] == "discharge" and "unit not stated" in out.loc[0, "flag"]


def test_unmappable_resource_is_reported_not_guessed(tmp_path):
    p = _write(tmp_path / "wq.csv", pd.DataFrame({"NAME OF STATION": ["S"], "MONTH": ["Jan"], "PARAMETER": ["pH"], "READING": [7.1]}))
    missing = str(tmp_path / "gone.csv")
    out = tidy.load(pd.DataFrame([item("NWDP", "Surface Water Quality Manual Sikkim", p),
                                  item("NWDP", "Rainfall x", missing)]))
    assert out.empty
    reasons = {u["file"]: u["reason"] for u in out.attrs["unmapped"]}
    assert "no recognisable time column" in reasons[p] and reasons[missing] == "file missing"


def test_tidy_cwc_marks_rating_curve_discharge_as_estimated(tmp_path):
    p = _write(tmp_path / "c.csv", pd.DataFrame({
        "station_code": ["001-X"] * 2, "time": ["2022-01-01 08:00", "2022-01-01 09:00"], "wse": [10.0, 10.5],
        "discharge": [100.0, 110.0], "lat": [1.0] * 2, "lon": [2.0] * 2,
        "discharge_source": ["rc_guardian_2024"] * 2}), header="# HydroSwift\n# a: b\n")
    out = tidy.load(pd.DataFrame([item("CWC", "Shimoga", p)]))
    assert set(out["station_name"]) == {"Shimoga"}  # the CWC file has no name column; the catalog title is used
    q = out[out.variable == "discharge"]
    assert set(q["method"]) == {"rc_guardian_2024"} and "rating curve" in q.iloc[0]["flag"]
    assert set(out[out.variable == "water_level"]["method"]) == {"observed"}


def test_tidy_rsms_and_load_from_directory(tmp_path):
    p = _write(tmp_path / "cwc_rsms" / "s.csv", pd.DataFrame({
        "reservoir_unique_id": ["R1"], "reservoir_name": ["Dam"], "entry_date": ["2026-11-06"],
        "storage_bcm": [1.25], "latitude": [10.0], "longitude": [20.0]}))
    (tmp_path / "manifest.json").write_text(json.dumps({"items": [item("CWC-RSMS", "snap", p)]}))
    out = tidy.load(tmp_path)
    assert out.loc[0, "variable"] == "reservoir_storage" and out.loc[0, "unit"] == "BCM"
    with pytest.raises(FileNotFoundError):
        tidy.load(tmp_path / "cwc_rsms")


def test_load_skips_failed_and_cancelled_items(tmp_path):
    out = tidy.load(pd.DataFrame([item("NWDP", "x", None, status="error"), item("NWDP", "y", None, status="cancelled")]))
    assert out.empty and out.attrs["unmapped"] == []
