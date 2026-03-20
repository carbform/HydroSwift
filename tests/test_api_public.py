import sys
import pytest
import pandas as pd
from types import SimpleNamespace

from swift_app.api import _normalize_dataset_flags


def _get_cwc_engine_module():
    """Return the actual swift_app.cwc *module* (not the namespace object).

    ``swift_app.__init__`` exports ``cwc = _CwcNamespace()``, which shadows
    the ``swift_app.cwc`` submodule as a package attribute.  Tests that need
    to monkeypatch the engine module (e.g. ``PACKAGED_CSV``) must retrieve
    the module object from ``sys.modules`` instead.
    """
    import swift_app  # noqa: F401 – ensure __init__ has been loaded
    return sys.modules["swift_app.cwc"]


def test_dataset_aliases_cover_cli_style_and_python_style_names():
    flags = _normalize_dataset_flags(
        ["discharge", "atm_pressure", "solar_radiation", "groundwater_level"]
    )
    assert flags == ["q", "atm", "solar", "gwl"]


def test_unknown_dataset_error_is_actionable():
    with pytest.raises(ValueError, match="Supported values"):
        _normalize_dataset_flags(["bogus_dataset"])


def test_wris_stations_populates_river_from_discovery_fallback(monkeypatch):
    import swift_app.api as api_mod
    import swift_app.wris as wris_mod

    class DummyClient:
        def __init__(self, delay=0.25):
            self.delay = delay

        def get_basin_code(self, basin):
            return "5"

        def get_tributaries(self, basin_code, dataset_code):
            return [{"tributaryid": "t1", "tributary": "Trib-A"}]

        def get_rivers(self, tributary_id, dataset_code):
            return [{"localriverid": "r1", "riverName": "River-X"}]

        def get_agencies(self, tributary_id, localriver_id, dataset_code):
            return [{"agencyid": "a1"}]

        def get_stations(self, tributary_id, localriver_id, agency_id, dataset_code):
            return [{"stationcode": "S1"}]

        def get_metadata(self, station_code, dataset_code):
            return {
                "station_Name": "Demo Station",
                "latitude": 10.0,
                "longitude": 20.0,
                "riverName": None,
            }

    monkeypatch.setattr(api_mod, "WrisClient", DummyClient)
    monkeypatch.setattr(api_mod, "build_basin_structure", lambda client, basin_code: [("t1", "r1")])
    monkeypatch.setattr(api_mod, "discover_stations", lambda *args, **kwargs: ["S1"])

    out = api_mod.wris.stations("Godavari", "discharge")

    assert len(out) == 1
    assert out.loc[0, "river"] == "River-X"
    assert out.loc[0, "basin"] == "Godavari"
    assert out.loc[0, "variable"] == "discharge"
    assert out.attrs["basin"] == ["Godavari"]
    assert out.attrs["variable"] == ["discharge"]


def test_cwc_stations_refresh_uses_live_fetch(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    cwc_mod = _get_cwc_engine_module()

    fresh = pd.DataFrame(
        [
            {"code": "AAA001", "name": "Station A"},
            {"code": "BBB001", "name": "Station B"},
        ]
    )

    monkeypatch.setattr(cwc_mod, "fetch_cwc_station_metadata", lambda: fresh)
    monkeypatch.setattr(cwc_mod, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cwc_mod, "CACHE_FILE", tmp_path / "cwc_meta.csv")

    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = api_mod.cwc_ns.stations(refresh=True)

    assert list(out["code"]) == ["AAA001", "BBB001"]




def test_cwc_stations_refresh_applies_basin_filter_after_live_fetch(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    cwc_mod = _get_cwc_engine_module()

    fresh = pd.DataFrame(
        [
            {"code": "AAA001", "name": "A", "basin": "Krishna"},
            {"code": "BBB001", "name": "B", "basin": "Godavari"},
            {"code": "CCC001", "name": "C", "basin": "Mahanadi"},
        ]
    )

    monkeypatch.setattr(cwc_mod, "fetch_cwc_station_metadata", lambda: fresh)
    monkeypatch.setattr(cwc_mod, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cwc_mod, "CACHE_FILE", tmp_path / "cwc_meta.csv")

    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = api_mod.cwc_ns.stations(basin="Krishna", refresh=True)

    assert len(out) == 1
    assert out.iloc[0]["code"] == "AAA001"

def test_cwc_stations_refresh_falls_back_when_live_unavailable(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    cwc_mod = _get_cwc_engine_module()

    monkeypatch.setattr(cwc_mod, "fetch_cwc_station_metadata", lambda: pd.DataFrame())
    monkeypatch.setattr(cwc_mod, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cwc_mod, "CACHE_FILE", tmp_path / "nonexistent_cache.csv")

    fallback = tmp_path / "packaged.csv"
    fallback.write_text("code,name\n040-CDJAPR,Parwan pick-up Weir\n")
    monkeypatch.setattr(cwc_mod, "PACKAGED_CSV", fallback)

    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = api_mod.cwc_ns.stations(refresh=True)

    assert len(out) == 1
    assert out.iloc[0]["code"] == "040-CDJAPR"


def test_cwc_stations_default_uses_packaged_csv(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    cwc_mod = _get_cwc_engine_module()

    local_csv = tmp_path / "local.csv"
    local_csv.write_text("code,name\nLOC001,Local Station\n")
    monkeypatch.setattr(cwc_mod, "PACKAGED_CSV", local_csv)
    monkeypatch.setattr(cwc_mod, "CACHE_FILE", tmp_path / "nonexistent.csv")

    out = api_mod.cwc_ns.stations()

    assert len(out) == 1
    assert out.iloc[0]["code"] == "LOC001"


def test_cwc_stations_prefers_cache_over_packaged(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    cwc_mod = _get_cwc_engine_module()

    cache_csv = tmp_path / "cwc_meta.csv"
    cache_csv.write_text("code,name\nCACHE01,Cached Station\n")
    monkeypatch.setattr(cwc_mod, "CACHE_FILE", cache_csv)

    packaged = tmp_path / "packaged.csv"
    packaged.write_text("code,name\nPKG001,Packaged Station\n")
    monkeypatch.setattr(cwc_mod, "PACKAGED_CSV", packaged)

    out = api_mod.cwc_ns.stations()

    assert len(out) == 1
    assert out.iloc[0]["code"] == "CACHE01"


def test_cwc_stations_station_filter(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    cwc_mod = _get_cwc_engine_module()

    csv = tmp_path / "meta.csv"
    csv.write_text(
        "code,name\n001-AAA,Alpha\n002-BBB,Beta\n003-CCC,Gamma\n"
    )
    monkeypatch.setattr(cwc_mod, "PACKAGED_CSV", csv)
    monkeypatch.setattr(cwc_mod, "CACHE_FILE", tmp_path / "nonexistent.csv")

    out = api_mod.cwc_ns.stations(station="002-BBB")
    assert len(out) == 1
    assert out.iloc[0]["code"] == "002-BBB"


# ============================================================
# Namespace API tests
# ============================================================


def test_wris_namespace_download_dispatches(monkeypatch, tmp_path):
    """swift.wris.download() should delegate to the WRIS engine."""
    import swift_app.api as api_mod

    class DummyClient:
        def __init__(self, delay=0.25):
            self.delay = delay

        def check_api(self):
            return True

        def get_basin_code(self, basin):
            return "6"

    calls = {}

    def fake_run_wris_download(args, selected, client, basin_code):
        calls["selected"] = selected
        calls["basin_code"] = basin_code
        calls["stations"] = getattr(args, "stations", None)

    monkeypatch.setattr(api_mod, "WrisClient", DummyClient)
    monkeypatch.setattr(api_mod, "run_wris_download", fake_run_wris_download)

    api_mod.wris.download(
        basin="Krishna",
        variable=["discharge", "rainfall"],
        output_dir=tmp_path,
        quiet=True,
    )

    assert calls["basin_code"] == "6"
    assert calls["selected"] == {
        "DISCHARG": "discharge",
        "RAINF": "rainfall",
    }
    assert calls["stations"] is None


def test_wris_namespace_download_with_station_filter(monkeypatch, tmp_path):
    import swift_app.api as api_mod

    class DummyClient:
        def __init__(self, delay=0.25):
            self.delay = delay

        def check_api(self):
            return True

        def get_basin_code(self, basin):
            return "6"

    calls = {}

    def fake_run_wris_download(args, selected, client, basin_code):
        calls["stations"] = getattr(args, "stations", None)

    monkeypatch.setattr(api_mod, "WrisClient", DummyClient)
    monkeypatch.setattr(api_mod, "run_wris_download", fake_run_wris_download)

    api_mod.wris.download(
        basin="Krishna",
        variable="discharge",
        station=["ST001", "ST002"],
        output_dir=tmp_path,
        quiet=True,
    )

    assert calls["stations"] == ["ST001", "ST002"]


def test_wris_namespace_download_supports_multiple_basins(monkeypatch, tmp_path):
    import swift_app.api as api_mod

    class DummyClient:
        def __init__(self, delay=0.25):
            self.delay = delay

        def check_api(self):
            return True

        def get_basin_code(self, basin):
            return "6"

    calls = []

    def fake_run_wris_download(args, selected, client, basin_code):
        calls.append(args.basin)

    monkeypatch.setattr(api_mod, "WrisClient", DummyClient)
    monkeypatch.setattr(api_mod, "run_wris_download", fake_run_wris_download)

    api_mod.wris.download(
        basin=["Krishna", "Godavari"],
        variable="discharge",
        output_dir=tmp_path,
        quiet=True,
    )

    assert calls == ["Krishna", "Godavari"]


def test_wris_namespace_download_rejects_station_table(monkeypatch, tmp_path):
    import swift_app.api as api_mod

    stations = api_mod.SwiftTable(
        pd.DataFrame(
            {
                "station_code": ["ST001", "ST002"],
                "basin": ["Godavari", "Narmada"],
                "variable": ["solar", "sediment"],
            }
        )
    )
    stations.attrs["source"] = "wris"

    with pytest.raises(TypeError, match="use swift.fetch"):
        api_mod.wris.download(stations, output_dir=tmp_path, quiet=True)


def test_wris_namespace_download_rejects_station_table_via_station_kwarg(monkeypatch, tmp_path):
    import swift_app.api as api_mod

    stations = api_mod.SwiftTable(
        pd.DataFrame(
            {
                "station_code": ["ST001", "ST002"],
                "basin": ["Godavari", "Godavari"],
                "variable": ["discharge", "discharge"],
            }
        )
    )

    with pytest.raises(TypeError, match="use swift.fetch"):
        api_mod.wris.download(station=stations, basin="Krishna", variable="discharge", output_dir=tmp_path, quiet=True)


def test_wris_namespace_download_rejects_basin_table(monkeypatch, tmp_path):
    import swift_app.api as api_mod

    basins = api_mod.SwiftTable(
        pd.DataFrame(
            {
                "basin": ["Godavari", "Narmada"],
                "variable": ["solar", "sediment"],
            }
        )
    )

    with pytest.raises(TypeError, match="use swift.fetch"):
        api_mod.wris.download(basins, output_dir=tmp_path, quiet=True)


def test_cwc_namespace_download_rejects_station_table_input(monkeypatch):
    import swift_app.api as api_mod

    stations = api_mod.SwiftTable(
        pd.DataFrame(
            {
                "code": ["040-CDJAPR", "032-LGDHYD"],
                "name": ["A", "B"],
            }
        )
    )

    with pytest.raises(TypeError, match="use swift.fetch"):
        api_mod.cwc_ns.download(station=stations, quiet=True)


def test_cwc_namespace_download_dispatches(monkeypatch):
    """swift.cwc.download() should delegate to the CWC engine."""
    import swift_app.api as api_mod

    calls = {}

    def fake_run_cwc_download(args):
        calls["cwc"] = args.cwc
        calls["stations"] = args.cwc_station

    monkeypatch.setattr(api_mod, "run_cwc_download", fake_run_cwc_download)

    api_mod.cwc_ns.download(station=["040-CDJAPR"], quiet=True)
    assert calls["cwc"] is True
    assert calls["stations"] == ["040-CDJAPR"]

def test_cwc_namespace_download_basin_filter(monkeypatch):
    import swift_app.api as api_mod
    calls = {}
    def fake_run_cwc_download(args):
        calls["cwc"] = args.cwc
        calls["stations"] = args.cwc_station
        calls["basin_filter"] = args.cwc_basin_filter
    monkeypatch.setattr(api_mod, "run_cwc_download", fake_run_cwc_download)
    # Should filter by basin and pass correct args
    api_mod.cwc_ns.download(basin=["Krishna", "Godavari"], quiet=True)
    assert calls["cwc"] is True
    assert calls["basin_filter"] == ["Krishna", "Godavari"]


def test_cwc_namespace_download_rejects_basin_table_input(monkeypatch):
    import swift_app.api as api_mod

    basin_table = api_mod.SwiftTable(
        pd.DataFrame(
            {
                "basin": ["Krishna", "Godavari", "Mahanadi"],
                "station_count": [10, 20, 30],
            }
        )
    )

    with pytest.raises(TypeError, match="use swift.fetch"):
        api_mod.cwc_ns.download(basin=basin_table.iloc[0:2], quiet=True)


def test_cwc_namespace_refresh_metadata_exposes_appended_count(monkeypatch):
    import swift_app.api as api_mod

    merged = pd.DataFrame([{"code": "001-AAA", "name": "A"}])
    appended = pd.DataFrame([{"code": "001-AAA", "name": "A"}])

    monkeypatch.setattr(
        api_mod,
        "repopulate_cwc_metadata_from_name_code",
        lambda write_packaged=False: (merged, appended),
    )

    out = api_mod.cwc_ns.refresh_metadata(write=False)
    assert len(out) == 1
    assert out.attrs["appended_count"] == 1


def test_wris_namespace_stations(monkeypatch):
    import swift_app.api as api_mod

    class DummyClient:
        def __init__(self, delay=0.25):
            self.delay = delay

        def get_basin_code(self, basin):
            return "5"

        def get_tributaries(self, basin_code, dataset_code):
            return []

        def get_rivers(self, tributary_id, dataset_code):
            return []

        def get_agencies(self, tributary_id, localriver_id, dataset_code):
            return []

        def get_stations(self, tributary_id, localriver_id, agency_id, dataset_code):
            return []

        def get_metadata(self, station_code, dataset_code):
            return {"station_Name": "X", "latitude": 0, "longitude": 0}

    monkeypatch.setattr(api_mod, "WrisClient", DummyClient)
    monkeypatch.setattr(api_mod, "build_basin_structure", lambda c, bc: [("t1", "r1")])
    monkeypatch.setattr(api_mod, "discover_stations", lambda *a, **k: ["S1"])

    out = api_mod.wris.stations("Godavari", "discharge")
    assert len(out) == 1
    assert "basin" in out.columns
    assert "variable" in out.columns
    assert out.loc[0, "basin"] == "Godavari"
    assert out.loc[0, "variable"] == "discharge"


def test_wris_stations_multi_basin_multi_variable(monkeypatch):
    """wris.stations() with lists for basin and variable produces per-row columns."""
    import swift_app.api as api_mod

    call_log = []

    class DummyClient:
        def __init__(self, delay=0.25):
            self.delay = delay

        def get_basin_code(self, basin):
            return {"Godavari": "5", "Krishna": "6"}[basin]

        def get_tributaries(self, basin_code, dataset_code):
            return []

        def get_rivers(self, tributary_id, dataset_code):
            return []

        def get_agencies(self, tributary_id, localriver_id, dataset_code):
            return []

        def get_stations(self, tributary_id, localriver_id, agency_id, dataset_code):
            return []

        def get_metadata(self, station_code, dataset_code):
            return {
                "station_Name": f"Stn-{station_code}",
                "latitude": 10.0,
                "longitude": 20.0,
            }

    def fake_build_basin_structure(client, basin_code):
        return [("t1", "r1")]

    station_map = {
        ("5", "SOLAR_RD"): ["S1", "S2"],
        ("5", "DISCHARG"): ["S1", "S3"],
        ("6", "SOLAR_RD"): ["S4"],
        ("6", "DISCHARG"): ["S4", "S5"],
    }

    def fake_discover_stations(client, basin_structure, dataset_code, *a, **kw):
        basin_code = client.get_basin_code(
            "Godavari" if basin_structure == [("t1", "r1")] else "Krishna"
        )
        call_log.append((basin_code, dataset_code))
        return station_map.get((basin_code, dataset_code), [])

    monkeypatch.setattr(api_mod, "WrisClient", DummyClient)
    monkeypatch.setattr(api_mod, "build_basin_structure", fake_build_basin_structure)
    monkeypatch.setattr(api_mod, "discover_stations", fake_discover_stations)

    out = api_mod.wris.stations(
        basin=["Godavari", "Krishna"],
        variable=["solar", "discharge"],
    )

    assert "basin" in out.columns
    assert "variable" in out.columns
    assert set(out["basin"].unique()) == {"Godavari", "Krishna"}
    assert set(out["variable"].unique()) == {"solar", "discharge"}
    assert out.attrs["basin"] == ["Godavari", "Krishna"]
    assert out.attrs["variable"] == ["solar", "discharge"]
    assert out.attrs["source"] == "wris"
    assert len(out) > 0


def test_wris_namespace_stations_requires_variable():
    import swift_app.api as api_mod

    with pytest.raises(ValueError, match="variable is required"):
        api_mod.wris.stations("Godavari", None)


def test_wris_namespace_stations_empty_list_raises():
    import swift_app.api as api_mod

    with pytest.raises(ValueError, match="variable is required"):
        api_mod.wris.stations("Godavari", [])


def test_wris_namespace_stations_empty_string_raises():
    import swift_app.api as api_mod

    with pytest.raises(ValueError, match="variable is required"):
        api_mod.wris.stations("Godavari", "")


def test_cwc_namespace_stations(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    cwc_mod = _get_cwc_engine_module()

    csv = tmp_path / "meta.csv"
    csv.write_text("code,name\n040-CDJAPR,Parwan pick-up Weir\n")
    monkeypatch.setattr(cwc_mod, "PACKAGED_CSV", csv)
    monkeypatch.setattr(cwc_mod, "CACHE_FILE", tmp_path / "nonexistent.csv")

    out = api_mod.cwc_ns.stations(station="040-CDJAPR")
    assert len(out) == 1
    assert out.iloc[0]["code"] == "040-CDJAPR"


# ============================================================
# fetch() tests
# ============================================================


def test_fetch_dispatches_to_wris(monkeypatch, tmp_path):
    import swift_app.api as api_mod

    class DummyClient:
        def __init__(self, delay=0.25):
            self.delay = delay

        def check_api(self):
            return True

        def get_basin_code(self, basin):
            return "6"

    calls = {}

    def fake_run_wris_download(args, selected, client, basin_code):
        calls["selected"] = selected
        calls["basin_code"] = basin_code

    monkeypatch.setattr(api_mod, "WrisClient", DummyClient)
    monkeypatch.setattr(api_mod, "run_wris_download", fake_run_wris_download)

    stations = api_mod.SwiftTable(pd.DataFrame({
        "station_code": ["ST001", "ST002"],
        "basin": ["Krishna", "Krishna"],
        "variable": ["discharge", "discharge"],
    }))
    stations.attrs["source"] = "wris"
    stations.attrs["basin"] = ["Krishna"]
    stations.attrs["variable"] = ["discharge"]

    api_mod.fetch(stations, output_dir=tmp_path, quiet=True)

    assert calls["basin_code"] == "6"
    assert "DISCHARG" in calls["selected"]


def test_fetch_dispatches_to_cwc(monkeypatch):
    import swift_app.api as api_mod

    calls = {}

    def fake_run_cwc_download(args):
        calls["cwc"] = args.cwc
        calls["stations"] = args.cwc_station

    monkeypatch.setattr(api_mod, "run_cwc_download", fake_run_cwc_download)

    stations = api_mod.SwiftTable(pd.DataFrame({"code": ["040-CDJAPR"]}))
    stations.attrs["source"] = "cwc"
    api_mod.fetch(stations, quiet=True)

    assert calls["cwc"] is True
    assert calls["stations"] == ["040-CDJAPR"]


def test_fetch_invalid_input_type_raises():
    import swift_app.api as api_mod

    with pytest.raises(TypeError, match="expects a pandas DataFrame"):
        api_mod.fetch("invalid_source")


def test_fetch_dispatches_multi_basin_variable_groups(monkeypatch, tmp_path):
    """fetch() groups by (basin, variable) and dispatches each separately."""
    import swift_app.api as api_mod

    class DummyClient:
        def __init__(self, delay=0.25):
            self.delay = delay

        def check_api(self):
            return True

        def get_basin_code(self, basin):
            return {"Godavari": "5", "Krishna": "6"}[basin]

    calls = []

    def fake_run_wris_download(args, selected, client, basin_code):
        calls.append({
            "basin": args.basin,
            "basin_code": basin_code,
            "selected": selected,
            "stations": getattr(args, "stations", None),
        })

    monkeypatch.setattr(api_mod, "WrisClient", DummyClient)
    monkeypatch.setattr(api_mod, "run_wris_download", fake_run_wris_download)

    stations = api_mod.SwiftTable(pd.DataFrame({
        "station_code": ["S1", "S2", "S3", "S4"],
        "basin": ["Godavari", "Godavari", "Krishna", "Krishna"],
        "variable": ["solar", "solar", "discharge", "discharge"],
    }))
    stations.attrs["source"] = "wris"
    stations.attrs["basin"] = ["Godavari", "Krishna"]
    stations.attrs["variable"] = ["solar", "discharge"]

    api_mod.fetch(stations, output_dir=tmp_path, quiet=True)

    assert len(calls) == 2
    basins_dispatched = {c["basin"] for c in calls}
    assert basins_dispatched == {"Godavari", "Krishna"}
    for c in calls:
        if c["basin"] == "Godavari":
            assert c["basin_code"] == "5"
            assert "SOLAR_RD" in c["selected"]
            assert sorted(c["stations"]) == ["S1", "S2"]
        else:
            assert c["basin_code"] == "6"
            assert "DISCHARG" in c["selected"]
            assert sorted(c["stations"]) == ["S3", "S4"]


def test_get_wris_data_merge_reads_lowercase_basin_gpkg(monkeypatch, tmp_path):
    """merge=True should return data when downloader writes lowercase basin filenames."""
    import swift_app.api as api_mod

    class DummyClient:
        def __init__(self, delay=0.25):
            self.delay = delay

        def check_api(self):
            return True

        def get_basin_code(self, basin):
            return "5"

    def fake_run_wris_download(args, selected, client, basin_code):
        basin_dir = tmp_path / "wris" / "cauvery"
        basin_dir.mkdir(parents=True, exist_ok=True)
        gpkg_path = basin_dir / "cauvery_sediment_2024-04-01_2025-05-07.gpkg"
        gpkg_path.write_text("placeholder")
        return [{"dataset": "sediment", "downloaded": 1}]

    fake_gpd = SimpleNamespace(
        read_file=lambda _p: pd.DataFrame(
            {
                "station_code": ["S1"],
                "time": ["2024-04-02"],
                "sediment": [1.23],
            }
        )
    )

    monkeypatch.setattr(api_mod, "WrisClient", DummyClient)
    monkeypatch.setattr(api_mod, "run_wris_download", fake_run_wris_download)
    monkeypatch.setitem(sys.modules, "geopandas", fake_gpd)

    out = api_mod.get_wris_data(
        var="sediment",
        basin="Cauvery",
        start_date="2024-04-01",
        end_date="2025-05-07",
        output_dir=tmp_path,
        merge=True,
        quiet=True,
    )

    assert out is not None
    assert len(out) == 1
    assert out.loc[0, "basin"] == "Cauvery"
    assert out.loc[0, "variable"] == "sediment"


def test_fetch_wris_basin_table_dispatches_all_station_downloads(monkeypatch, tmp_path):
    """fetch() should accept wris.basins(variable=...) style tables."""
    import swift_app.api as api_mod

    class DummyClient:
        def __init__(self, delay=0.25):
            self.delay = delay

        def check_api(self):
            return True

        def get_basin_code(self, basin):
            return {"Godavari": "5", "Narmada": "4"}[basin]

    calls = []

    def fake_run_wris_download(args, selected, client, basin_code):
        calls.append(
            {
                "basin": args.basin,
                "variable_flags": sorted(selected.keys()),
                "stations": getattr(args, "stations", None),
                "basin_code": basin_code,
            }
        )

    monkeypatch.setattr(api_mod, "WrisClient", DummyClient)
    monkeypatch.setattr(api_mod, "run_wris_download", fake_run_wris_download)

    basins = api_mod.SwiftTable(
        pd.DataFrame(
            {
                "id": ["5", "4"],
                "basin": ["Godavari", "Narmada"],
                "variable": ["discharge", "discharge"],
            }
        )
    )
    basins.attrs["source"] = "wris"
    basins.attrs["type"] = "basins"

    with pytest.warns(UserWarning, match="may take a long time"):
        api_mod.fetch(basins, output_dir=tmp_path, quiet=True)

    assert len(calls) == 2
    by_basin = {c["basin"]: c for c in calls}
    assert by_basin["Godavari"]["stations"] is None
    assert by_basin["Godavari"]["basin_code"] == "5"
    assert by_basin["Narmada"]["stations"] is None
    assert by_basin["Narmada"]["basin_code"] == "4"
    assert by_basin["Godavari"]["variable_flags"] == ["DISCHARG"]
    assert by_basin["Narmada"]["variable_flags"] == ["DISCHARG"]


def test_fetch_wris_legacy_scalar_attrs(monkeypatch, tmp_path):
    """fetch() still works with old-style scalar attrs (backward compat)."""
    import swift_app.api as api_mod

    class DummyClient:
        def __init__(self, delay=0.25):
            self.delay = delay

        def check_api(self):
            return True

        def get_basin_code(self, basin):
            return "6"

    calls = {}

    def fake_run_wris_download(args, selected, client, basin_code):
        calls["basin"] = args.basin
        calls["selected"] = selected

    monkeypatch.setattr(api_mod, "WrisClient", DummyClient)
    monkeypatch.setattr(api_mod, "run_wris_download", fake_run_wris_download)

    stations = api_mod.SwiftTable(pd.DataFrame({"station_code": ["ST001"]}))
    stations.attrs["source"] = "wris"
    stations.attrs["basin"] = "Krishna"
    stations.attrs["variable"] = "discharge"

    api_mod.fetch(stations, output_dir=tmp_path, quiet=True)

    assert calls["basin"] == "Krishna"
    assert "DISCHARG" in calls["selected"]


def test_fetch_wris_missing_attrs_raises():
    import swift_app.api as api_mod

    stations = api_mod.SwiftTable(pd.DataFrame({"station_code": ["ST001"]}))
    stations.attrs["source"] = "wris"
    with pytest.raises(ValueError, match="missing"):
        api_mod.fetch(stations)


def test_fetch_cwc_missing_code_column_raises():
    import swift_app.api as api_mod

    stations = api_mod.SwiftTable(pd.DataFrame({"station_code": ["ST001"]}))
    stations.attrs["source"] = "cwc"
    with pytest.raises(ValueError, match="must include 'code' column"):
        api_mod.fetch(stations)


# ============================================================
# Merge/Plot with mode parameter
# ============================================================


def test_merge_only_with_mode_derives_input_dir(monkeypatch, tmp_path):
    import swift_app.api as api_mod

    (tmp_path / "wris" / "krishna").mkdir(parents=True)

    calls = {}

    def fake_run_merge_only(args):
        calls["input_dir"] = args.input_dir

    monkeypatch.setattr(api_mod, "run_merge_only", fake_run_merge_only)

    api_mod.merge_only(mode="wris", output_dir=str(tmp_path))

    assert calls["input_dir"] == str(tmp_path)


def test_merge_only_discovers_basins_from_input_dir(monkeypatch, tmp_path):
    import swift_app.api as api_mod

    (tmp_path / "wris" / "krishna").mkdir(parents=True)
    (tmp_path / "wris" / "godavari").mkdir(parents=True)

    calls = []

    def fake_run_merge_only(args):
        calls.append(args.input_dir)

    monkeypatch.setattr(api_mod, "run_merge_only", fake_run_merge_only)

    api_mod.merge_only(
        input_dir=str(tmp_path),
        variable=["solar"],
        output_dir=str(tmp_path / "merged"),
    )

    assert calls == [str(tmp_path)]


def test_merge_only_cwc_no_basin_warning(monkeypatch, tmp_path):
    """merge_only(mode='cwc') runs once with no basin/datasets warning."""
    import swift_app.api as api_mod

    (tmp_path / "cwc" / "godavari" / "stations").mkdir(parents=True)

    calls = []

    def fake_run_merge_only(args):
        calls.append((args.input_dir, getattr(args, "cwc", False)))

    monkeypatch.setattr(api_mod, "run_merge_only", fake_run_merge_only)

    api_mod.merge_only(mode="cwc", input_dir=str(tmp_path), output_dir=str(tmp_path))

    assert len(calls) == 1
    assert calls[0][0] == str(tmp_path)
    assert calls[0][1] is True


def test_plot_only_with_mode_derives_input_dir(monkeypatch, tmp_path):
    import swift_app.api as api_mod

    (tmp_path / "wris" / "krishna").mkdir(parents=True)

    calls = {}

    def fake_run_plot_only(args):
        calls["input_dir"] = args.input_dir
        calls["cwc"] = args.cwc

    monkeypatch.setattr(api_mod, "run_plot_only", fake_run_plot_only)

    api_mod.plot_only(mode="wris", output_dir=str(tmp_path))

    assert calls["input_dir"] == str(tmp_path)
    assert calls["cwc"] is False


def test_plot_only_discovers_basins_from_input_dir(monkeypatch, tmp_path):
    import swift_app.api as api_mod

    (tmp_path / "wris" / "krishna").mkdir(parents=True)
    (tmp_path / "wris" / "godavari").mkdir(parents=True)

    calls = []

    def fake_run_plot_only(args):
        calls.append(args.input_dir)

    monkeypatch.setattr(api_mod, "run_plot_only", fake_run_plot_only)

    api_mod.plot_only(
        input_dir=str(tmp_path),
        variable=["solar", "sediment"],
        output_dir=str(tmp_path / "plots"),
    )

    assert calls == [str(tmp_path)]


def test_plot_only_cwc_discovers_from_input_dir(monkeypatch, tmp_path):
    import swift_app.api as api_mod

    (tmp_path / "cwc" / "godavari" / "stations").mkdir(parents=True)

    calls = []

    def fake_run_plot_only(args):
        calls.append(args.input_dir)

    monkeypatch.setattr(api_mod, "run_plot_only", fake_run_plot_only)

    api_mod.plot_only(mode="cwc", input_dir=str(tmp_path), output_dir=str(tmp_path))

    assert calls == [str(tmp_path)]


def test_plot_only_cwc_mode_sets_cwc_flag(monkeypatch, tmp_path):
    import swift_app.api as api_mod

    calls = {}

    def fake_run_plot_only(args):
        calls["cwc"] = args.cwc

    monkeypatch.setattr(api_mod, "run_plot_only", fake_run_plot_only)

    api_mod.plot_only(mode="cwc", output_dir=str(tmp_path))

    assert calls["cwc"] is True


def test_plot_only_input_dir_must_exist(tmp_path):
    import swift_app.api as api_mod

    missing = tmp_path / "nonexistent"
    assert not missing.exists()

    with pytest.raises(ValueError, match="input_dir does not exist"):
        api_mod.plot_only(
            input_dir=str(missing),
            output_dir=str(tmp_path / "plots"),
        )


def test_plot_only_prefers_window_aliases(monkeypatch, tmp_path):
    import swift_app.api as api_mod

    (tmp_path / "wris" / "krishna").mkdir(parents=True)

    calls = {}

    def fake_run_plot_only(args):
        calls["plot_moving_average_window"] = getattr(args, "plot_moving_average_window", None)

    monkeypatch.setattr(api_mod, "run_plot_only", fake_run_plot_only)

    api_mod.plot_only(
        mode="wris",
        output_dir=str(tmp_path),
        moving_average=True,
        window=30,
    )

    assert calls["plot_moving_average_window"] == 30


def test_plot_only_bool_moving_average_defaults_to_30(monkeypatch, tmp_path):
    import swift_app.api as api_mod

    (tmp_path / "wris" / "krishna").mkdir(parents=True)

    calls = {}

    def fake_run_plot_only(args):
        calls["plot_moving_average_window"] = getattr(args, "plot_moving_average_window", None)

    monkeypatch.setattr(api_mod, "run_plot_only", fake_run_plot_only)

    api_mod.plot_only(
        mode="wris",
        output_dir=str(tmp_path),
        moving_average=True,
    )

    assert calls["plot_moving_average_window"] == 30


# ============================================================
# Package-level namespace access
# ============================================================


def test_package_exposes_wris_namespace():
    import swift_app

    assert hasattr(swift_app, "wris")
    assert hasattr(swift_app.wris, "download")
    assert hasattr(swift_app.wris, "stations")


def test_package_exposes_cwc_namespace():
    import swift_app

    assert hasattr(swift_app, "cwc")
    assert hasattr(swift_app.cwc, "download")
    assert hasattr(swift_app.cwc, "stations")


def test_package_exposes_fetch():
    import swift_app

    assert hasattr(swift_app, "fetch")
    assert callable(swift_app.fetch)


def test_package_exposes_merge_only_and_plot_only():
    import swift_app

    assert hasattr(swift_app, "merge_only")
    assert callable(swift_app.merge_only)
    assert hasattr(swift_app, "plot_only")
    assert callable(swift_app.plot_only)




def test_package_does_not_expose_removed_merge_plot_aliases():
    import swift_app

    merge_attr = getattr(swift_app, "merge", None)
    plot_attr = getattr(swift_app, "plot", None)

    # Submodule names may exist as module attributes; ensure the removed
    # public callable aliases are not exposed.
    assert not callable(merge_attr)
    assert not callable(plot_attr)

def test_package_does_not_expose_legacy_datasets_basins():
    import swift_app

    assert not hasattr(swift_app, "datasets")
    assert not hasattr(swift_app, "basins")


def test_wris_namespace_exposes_variables_and_basins():
    import swift_app.api as api_mod

    vars_df = api_mod.wris.variables()
    assert len(vars_df) > 0
    assert {"flag", "dataset_code", "folder", "canonical_name", "aliases"}.issubset(vars_df.columns)

    basins_df = api_mod.wris.basins()
    assert len(basins_df) > 0
    assert {"id", "basin"}.issubset(basins_df.columns)


def test_wris_basins_accepts_variable_and_expands_rows():
    import swift_app.api as api_mod

    out = api_mod.wris.basins(variable=["discharge", "solar"])

    assert {"id", "basin", "variable"}.issubset(out.columns)
    assert set(out["variable"].unique()) == {"discharge", "solar"}
    assert out.attrs["source"] == "wris"
    assert out.attrs["type"] == "basins"
    assert out.attrs["variable"] == ["discharge", "solar"]


def test_wris_basins_variable_validation_raises():
    import swift_app.api as api_mod

    with pytest.raises(ValueError, match="Unknown variable"):
        api_mod.wris.basins(variable="not_a_real_variable")


def test_cwc_namespace_exposes_basins(monkeypatch, tmp_path):
    import swift_app.api as api_mod
    cwc_mod = _get_cwc_engine_module()

    csv = tmp_path / "meta.csv"
    csv.write_text(
        "code,name,basin\n"
        "001-AAA,Alpha,Godavari\n"
        "002-BBB,Beta,Krishna\n"
        "003-CCC,Gamma,Godavari\n"
    )
    monkeypatch.setattr(cwc_mod, "PACKAGED_CSV", csv)
    monkeypatch.setattr(cwc_mod, "CACHE_FILE", tmp_path / "nonexistent.csv")

    out = api_mod.cwc_ns.basins()
    assert {"basin", "station_count"}.issubset(out.columns)
    counts = dict(zip(out["basin"], out["station_count"]))
    assert counts["Godavari"] == 2
    assert counts["Krishna"] == 1


def test_package_help_prints_python_api_menu(capsys):
    import swift_app

    swift_app.help()
    out = capsys.readouterr().out

    assert "HydroSwift Python API help" in out
    assert "swift.wris.download" in out
    assert "swift.fetch(table, ...)" in out
    assert "swift.cli_help()" in out

