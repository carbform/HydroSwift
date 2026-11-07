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
