import pandas as pd
import pytest

from hydroswift.core.tidy import TIDY_COLUMNS
from hydroswift.gui import console


def _catalog():
    return pd.DataFrame({"Source": ["CWC"] * 4, "ID": list("abcd"), "Title": ["Alpha", "Beta", "Gamma", "Delta"],
                         "Location": "X", "Variable": "Water level"})


def _make(**state):
    calls = {}

    def search(query, location, **kw):
        calls["search"] = (query, location, kw)
        out = _catalog()
        out.attrs["source_status"] = []
        return out

    def download(table, **kw):
        calls["download"] = (table["ID"].tolist(), kw)

    return console.Console(state, search=search, download=download), state, calls


def _tidy():
    return pd.DataFrame({"time": pd.date_range("2024-01-01", periods=3), "value": [1.0, 2.0, 3.0],
                         "variable": "water_level", "unit": "m", "station_id": "s1", "station_name": "Kudlur",
                         "source": "CWC", "lat": 1.0, "lon": 2.0, "method": "observed", "flag": None,
                         "file": "f"})[TIDY_COLUMNS]


def test_search_updates_results_and_sidebar():
    term, state, calls = _make(selected={("CWC", "a")})
    out = term.run("hyswift search discharge --basin cauvery --source CWC --period 2023:2024")
    assert "4 rows" in out and calls["search"][2]["basin"] == "cauvery"
    assert state["main_view"] == "Select Stations" and state["selected"] == set()
    assert (state["sb_basin"], state["sb_variable"], state["boundary_mode"]) == (
        "Cauvery", "Discharge", "Hydrological (Basin)")
    assert (state["src_cwc"], state["src_wris"], state["sb_start"], state["sb_end"]) == (True, False, 2023, 2024)
    assert state["console_history"][-1][0].startswith("hyswift search")


def test_select_then_get_downloads_the_ticked_rows():
    term, state, calls = _make(catalog=_catalog(), sb_start=2022, sb_end=2023, dest_input="out")
    assert term.run("select 0,2-3") == "3 selected"
    term.run("get --no-rc-discharge")
    ids, kw = calls["download"]
    assert ids == ["a", "c", "d"]
    assert (kw["period"], kw["output_dir"], kw["export_format"], kw["rc_discharge"]) == (
        "2022:2023", "out", "csv", False)
    assert term.run("select none") == "selection cleared" and state["selected"] == set()


def test_get_needs_a_selection_and_no_running_job():
    term, _, calls = _make(catalog=_catalog())
    assert "nothing selected" in term.run("get")
    term, _, calls = _make(catalog=_catalog(), job=object())
    assert "download is running" in term.run("get --rows 0")
    assert "download is running" in term.run("search")
    assert calls == {}


@pytest.mark.parametrize("line", ["ls -la", "rm -rf /", "python -c 1", "gui", "__init__", "_select", "parse x"])
def test_only_listed_commands_run(line):
    term, state, calls = _make()
    assert term.run(line).startswith("error: Unknown command")
    assert calls == {}


def test_help_bad_arguments_and_bad_rows_are_messages():
    term, _, _ = _make(catalog=_catalog())
    assert "select 0,2-4" in term.run("help")
    assert "usage" in term.run("get --help")
    assert "usage" in term.run("search --bogus")
    assert "bad row list" in term.run("select 9")
    assert "bad row list" in term.run("select x")
    assert "No closing quotation" in term.run('search "x')
    assert "no data loaded" in term.run("plot")


def test_plot_and_stats_switch_the_view(tmp_path):
    term, state, _ = _make(tidy=_tidy())
    assert "Flow duration curve" in term.run("plot kudlur --kind fdc")
    assert state["main_view"] == "Visualize" and state["viz_station"].startswith("Kudlur")
    assert "no loaded station matches" in term.run("plot nowhere")
    out = term.run(f"stats --out {tmp_path / 's.csv'}")
    assert "completeness_pct_of_record" in out and (tmp_path / "s.csv").exists()
    assert state["viz_kind"] == "Summary & data quality"


def test_clear_and_history_limit():
    term, state, _ = _make()
    for _ in range(console.HISTORY_LIMIT + 5):
        term.run("help")
    assert len(state["console_history"]) == console.HISTORY_LIMIT
    term.run("clear")
    assert state["console_history"] == []


def test_row_spec_and_search_command():
    cat = _catalog()
    assert console.row_spec(cat, {("CWC", "a"), ("CWC", "b"), ("CWC", "d")}) == "0-1,3"
    assert console.search_command("Rainfall", None, "Cauvery", None, ["CWC"], ("2020", "2024")) == (
        "search Rainfall --basin Cauvery --source CWC --period 2020:2024")


def test_dock_html_escapes_output_and_shows_sources():
    from hydroswift.gui import dock

    html = dock.console_html([("search <b>", "line one\n<script>x</script>")])
    assert "<script>" not in html and "&lt;script&gt;" in html and "line one<br>" in html
    cat = _catalog()
    cat.attrs["source_status"] = [dict(source="CWC", ok=False, complete=False, rows=0, error="down",
                                       note=None, endpoint=None, dropped={})]
    assert "CWC: FAILED" in dock.sources_html(cat) and "Error: down" in dock.sources_html(cat)
    assert "No search yet" in dock.sources_html(None)
