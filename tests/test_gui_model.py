import pandas as pd

from swift_app.gui import model


def _df():
    df = pd.DataFrame({"Source": ["NWDP", "CWC"], "Title": ["Rain A", "Gauge B"], "Location": ["Goa", "Krishna, Karnataka"],
                       "Variable": ["Rainfall", "Water level"], "ID": ["1", "2"],
                       "CoverageKnown": [True, False], "CoverageStart": ["2020-01-01", None], "CoverageEnd": ["2021-01-01", None],
                       "EstRecords": [120.0, None], "Inferred": [["Resolution"], []]})
    df.attrs["source_status"] = [
        dict(source="NWDP", ok=True, complete=True, rows=1, error=None, note="n", endpoint="e", dropped={"tiny": 3}),
        dict(source="CWC", ok=True, complete=False, rows=1, error="truncated", note=None, endpoint=None, dropped={})]
    return df


def test_cells_never_show_none():
    d = _df()
    assert model.review_value(d, 1, "EstRecords") == ""
    assert model.review_value(d, 0, "EstRecords") == "120"
    assert model.review_value(d, 1, "Coverage") == "unknown"
    assert model.review_value(d, 0, "Coverage") == "2020-01-01 to 2021-01-01"
    assert model.review_value(d, 0, "Inferred") == "Resolution"
    assert model.review_value(d, 1, "Inferred") == ""


def test_status_lines_flag_partial_and_dropped():
    lines = model.source_status_lines(_df())
    assert [x["level"] for x in lines] == ["ok", "partial"]
    assert "3 dropped: tiny" in lines[0]["detail"]
    assert "truncated" in lines[1]["detail"]
    lost = pd.DataFrame({"Source": []})
    assert model.source_status_lines(lost)[0]["text"] == "search provenance unavailable"


def test_text_filter_and_basket():
    d = _df()
    assert list(model.text_filter(d, "water")) == [False, True]
    assert list(model.text_filter(d, "karnataka level")) == [False, True]
    assert model.text_filter(d, "").all()
    b = model.add_to_basket(None, d, [0])
    b = model.add_to_basket(b, d, [0, 1])
    assert list(b["ID"]) == ["1", "2"] and b.attrs["source_status"] == d.attrs["source_status"]
    b = model.remove_from_basket(b, [0])
    assert list(b["ID"]) == ["2"] and "source_status" in b.attrs


def test_period_inputs():
    assert model.parse_period_inputs("", " ") is None
    assert model.parse_period_inputs("2020", "") == ("2020", None)


def test_summary():
    run = pd.DataFrame({"status": ["saved", "error", "saved"], "records": [10, None, 5]})
    assert model.summarise_fetch(run) == "3 items: 2 saved, 1 error; 15 records"
