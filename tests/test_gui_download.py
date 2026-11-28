"""Selection, background download and retry behind the dashboard."""

import threading

import pandas as pd

from hydroswift.gui import model
from hydroswift.gui.jobs import DownloadJob


def _catalog():
    cat = pd.DataFrame({"Source": ["CWC", "WRIS", "NWDP"], "ID": ["1", "1", "2"], "Title": list("abc"),
                        "_state": ["x", "y", "z"]})
    cat.attrs["query"] = {"q": 1}
    return cat


def test_pick_rows_keeps_hidden_columns_and_provenance():
    cat = _catalog()
    picked = model.pick_rows(cat, {("WRIS", "1")})
    assert picked["Title"].tolist() == ["b"]
    assert picked["_state"].tolist() == ["y"]
    assert picked.attrs["query"] == {"q": 1}


def _run(*rows):
    return pd.DataFrame(rows, columns=["source", "id", "status", "path", "complete"])


def test_needs_retry():
    run = _run(("a", "1", "saved", "f", True), ("a", "2", "saved", "f", False), ("a", "3", "error", None, None),
               ("a", "4", "cancelled", None, None), ("a", "5", "empty", None, None))
    assert run[model.needs_retry(run)]["id"].tolist() == ["2", "3", "4"]


def test_retry_keeps_earlier_data():
    first = _run(("a", "1", "saved", "one", True), ("a", "2", "saved", "part", False),
                 ("a", "3", "error", None, None))
    again = _run(("a", "2", "error", None, None), ("a", "3", "saved", "three", True))
    out = model.combine_runs(first, again).set_index("id")
    assert out["path"].to_dict() == {"1": "one", "2": "part", "3": "three"}


def test_retry_keeps_earlier_data_when_missing_paths_are_nan():
    first = _run(("a", "2", "saved", "part", False))
    again = _run(("a", "2", "error", float("nan"), None))
    assert model.combine_runs(first, again)["path"].tolist() == ["part"]


def test_job_reports_progress_and_result():
    def fetch(table, progress, cancel, **kw):
        progress({"event": "page", "source": "WRIS", "id": "1", "title": "S", "read": 2000, "total": None})
        progress({"event": "item_done", "source": "WRIS", "id": "1", "title": "S", "status": "saved"})
        return table

    job = DownloadJob(_catalog(), fetch=fetch).start()
    job.join(5)
    snap = job.snapshot()
    assert (snap["done"], snap["total"], snap["pages"]) == (1, 3, [])
    assert not job.running and job.error is None and len(job.result) == 3


def test_job_can_be_cancelled():
    seen = threading.Event()

    def fetch(table, progress, cancel, **kw):
        seen.set()
        assert cancel.wait(5)
        return table.iloc[:0]

    job = DownloadJob(_catalog(), fetch=fetch).start()
    assert seen.wait(5) and job.running
    job.cancel()
    job.join(5)
    assert job.cancelling and not job.running and job.result.empty


def test_job_keeps_the_error():
    def fetch(table, **kw):
        raise OSError("disk full")

    job = DownloadJob(_catalog(), fetch=fetch).start()
    job.join(5)
    assert job.error == "disk full" and job.result is None


def test_after_retry_the_folder_loads_every_item(tmp_path):
    import json

    from hydroswift.core.tidy import load

    items = []
    for name in ("first", "second"):
        path = tmp_path / f"{name}.csv"
        path.write_text("time,wse,station_code\n2024-01-01,1.5," + name + "\n")
        items.append({"source": "CWC", "id": name, "title": name, "status": "saved", "path": str(path),
                      "records": 1, "error": None, "complete": float("nan")})
    manifest = tmp_path / "manifest_retry.json"
    manifest.write_text(json.dumps({"items": items[1:]}))
    model.update_manifest(manifest, pd.DataFrame(items))
    assert "NaN" not in manifest.read_text()
    assert sorted(load(tmp_path)["station_id"]) == ["first", "second"]
