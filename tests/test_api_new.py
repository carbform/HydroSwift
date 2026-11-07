"""Public API surface, removed-name guidance, CWC station table, and CLI."""
import json
import sys

import pandas as pd
import pytest

import hydroswift
import swift_app
from swift_app.cli import build_parser, main as cli_main

NEW = ["search", "estimate", "fetch", "load", "merge", "plot", "save_catalog", "load_catalog",
       "rsms", "swot_reservoir_merge", "help", "cite", "coffee"]
REMOVED = ["wris", "cwc", "nwdp", "get_wris_data", "get_cwc_data", "merge_only", "plot_only",
           "swot_merge", "datasets", "basins"]


@pytest.mark.parametrize("mod", [hydroswift, swift_app])
def test_new_surface_exposed(mod):
    for n in NEW:
        assert callable(getattr(mod, n)) or hasattr(mod, n), n


@pytest.mark.parametrize("mod", [hydroswift, swift_app])
@pytest.mark.parametrize("name", REMOVED)
def test_removed_names_raise_with_replacement(mod, name):
    if mod is swift_app and name == "cwc":
        pytest.skip("swift_app.cwc is the CWC submodule (still importable as a module)")
    with pytest.raises(AttributeError, match="has been removed") as e:
        getattr(mod, name)
    assert "hydroswift." in str(e.value)


def test_unknown_attribute_is_plain_error():
    with pytest.raises(AttributeError, match="no attribute"):
        hydroswift.definitely_not_here


def test_help_menu_names_the_four_steps(capsys):
    hydroswift.help()
    out = capsys.readouterr().out
    assert "Find -> Review -> Get -> Use" in out and "hs.load(run)" in out


def test_fetch_rejects_non_catalog_input():
    with pytest.raises(TypeError, match="search"):
        hydroswift.fetch("karnataka")
    with pytest.raises(TypeError, match="search"):
        hydroswift.fetch(pd.DataFrame({"code": ["x"]}))


# ---- CWC station table (ported from the removed cwc.stations tests)
def _cwc():
    return sys.modules["swift_app.cwc"]


def test_station_table_refresh_uses_live_fetch(monkeypatch, tmp_path):
    m = _cwc()
    fresh = pd.DataFrame([{"code": "AAA001", "name": "A"}, {"code": "BBB001", "name": "B"}])
    monkeypatch.setattr(m, "fetch_cwc_station_metadata", lambda: fresh)
    monkeypatch.setattr(m, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(m, "CACHE_FILE", tmp_path / "cwc_meta.csv")
    with pytest.warns(UserWarning):
        out = swift_app.refresh_cwc_stations()
    assert list(out["code"]) == ["AAA001", "BBB001"]
    assert (tmp_path / "cwc_meta.csv").exists()


def test_station_table_refresh_falls_back_when_live_unavailable(monkeypatch, tmp_path):
    m = _cwc()
    monkeypatch.setattr(m, "fetch_cwc_station_metadata", lambda: pd.DataFrame())
    monkeypatch.setattr(m, "CACHE_FILE", tmp_path / "none.csv")
    pk = tmp_path / "packaged.csv"
    pk.write_text("code,name\n040-CDJAPR,Parwan\n")
    monkeypatch.setattr(m, "PACKAGED_CSV", pk)
    with pytest.warns(UserWarning):
        out = swift_app.refresh_cwc_stations()
    assert list(out["code"]) == ["040-CDJAPR"]


def test_station_table_prefers_cache_over_packaged(monkeypatch, tmp_path):
    m = _cwc()
    cache, pk = tmp_path / "cache.csv", tmp_path / "pk.csv"
    cache.write_text("code,name,basin,state,district,river,lat,lon\nCACHE01,C,Krishna,Karnataka,x,y,1,2\n")
    pk.write_text("code,name\nPKG001,P\n")
    monkeypatch.setattr(m, "CACHE_FILE", cache)
    monkeypatch.setattr(m, "PACKAGED_CSV", pk)
    df = swift_app.search("discharge", sources=["CWC"])
    assert list(df["ID"]) == ["CACHE01"]
    assert list(swift_app.search("discharge", sources=["CWC"], ids=["nope"])["ID"]) == []


# ---- catalog round-trip keeps provenance
def test_catalog_json_roundtrip_keeps_provenance(tmp_path):
    df = hydroswift.search("discharge", basin="Krishna", sources=["CWC"])
    p = hydroswift.save_catalog(df, tmp_path / "c.json")
    back = hydroswift.load_catalog(p)
    assert len(back) == len(df) and back.attrs["query"]["basin"] == "Krishna"
    assert back.attrs["source_status"][0]["source"] == "CWC"
    assert list(back["ID"]) == list(df["ID"])


# ---- CLI
def test_parser_has_workflow_subcommands_and_branding():
    p = build_parser()
    text = p.format_help()
    assert p.prog == "hyswift" and "HydroSwift - Fast, unified workflows for hydrological data" in text
    a = p.parse_args(["search", "rainfall", "--where", "Karnataka", "--period", "2020:2022", "--source", "NWDP"])
    assert (a.command, a.query, a.location, a.period, a.sources) == ("search", "rainfall", "Karnataka", "2020:2022", ["NWDP"])
    with pytest.raises(SystemExit):
        p.parse_args(["search", "--source", "WRIS"])  # not a source any more
    with pytest.raises(SystemExit):
        p.parse_args(["-b", "krishna", "-q"])  # old flat flags are gone


def test_cli_search_prints_source_status_and_saves(tmp_path, capsys):
    out = tmp_path / "cat.json"
    rc = cli_main(["search", "discharge", "--basin", "Krishna", "--source", "CWC", "--save", str(out), "--limit", "3"])
    text = capsys.readouterr().out
    assert rc == 0 and "Sources:" in text and "CWC" in text and out.exists()
    assert json.loads(out.read_text())["attrs"]["query"]["basin"] == "Krishna"


def test_cli_get_rejects_out_of_range_rows(tmp_path):
    cat = hydroswift.search("discharge", basin="Krishna", sources=["CWC"])
    p = hydroswift.save_catalog(cat, tmp_path / "c.json")
    with pytest.raises(SystemExit, match="out of range"):
        cli_main(["get", "--from", p, "--rows", "9999", "--out", str(tmp_path / "o")])


def test_cli_version_shows_banner(capsys):
    with pytest.raises(SystemExit) as e:
        cli_main(["--version"])
    out = capsys.readouterr().out
    assert e.value.code == 0 and "HYDROSWIFT" in out and "HydroSwift" in out


def test_cli_no_args_non_tty_prints_help(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", type("S", (), {"isatty": lambda self: False})())
    assert cli_main([]) == 0
    assert "usage:" in capsys.readouterr().out


def test_cli_show_merge_plot_on_a_fetched_folder(tmp_path, capsys):
    f = tmp_path / "nwdp" / "x.csv"
    f.parent.mkdir(parents=True)
    pd.DataFrame({"Station Code": ["A"] * 3, "Location Name": ["Gandsi"] * 3, "Latitude": [13.0] * 3,
                  "Longitude": [76.0] * 3, "Monitoring Date": ["01-06-2020", "02-06-2020", "03-06-2020"],
                  "Rainfall (MM)": [1.0, 2.0, 0.5]}).to_csv(f, index=False)
    (tmp_path / "manifest.json").write_text(json.dumps({"items": [
        {"source": "NWDP", "title": "Rainfall Manual Daily", "path": str(f), "status": "saved"}]}))
    assert cli_main(["show", str(tmp_path)]) == 0
    assert "rainfall" in capsys.readouterr().out
    assert cli_main(["merge", str(tmp_path), str(tmp_path / "all.csv")]) == 0
    assert len(pd.read_csv(tmp_path / "all.csv")) == 3
    assert cli_main(["plot", str(tmp_path), str(tmp_path / "plots")]) == 0
    assert len(list((tmp_path / "plots").glob("*.png"))) == 1
