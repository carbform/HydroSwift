"""The GUI is one Find -> Review -> Get -> Use screen on the shared engine."""
import os
import time

import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt5")

from swift_app.engine import CATALOG_COLUMNS  # noqa: E402


def _catalog():
    rows = [
        dict(Source="NWDP", Title="Rainfall Karnataka 2022", Location="KSNDMC", Variable="Rainfall",
             Resolution="Daily", ID="r1", CoverageKnown=True, CoverageStart="2022-01-01",
             CoverageEnd="2022-12-31", Provider="NWDP", Inferred=["Resolution"], MatchedOn="organization"),
        dict(Source="CWC", Title="Shimoga", Location="Krishna, Karnataka", Variable="Water level",
             Resolution="Sub-daily", ID="c1", CoverageKnown=False, Provider="CWC", Inferred=[], MatchedOn="state"),
    ]
    df = pd.DataFrame(rows)
    for c in CATALOG_COLUMNS + ["_org_id", "_basin", "_rl_zero"]:
        if c not in df.columns:
            df[c] = None
    df.attrs["source_status"] = [
        dict(source="NWDP", ok=True, complete=True, rows=1, error=None, note=None, endpoint="x", dropped={}, reported=1),
        dict(source="CWC", ok=False, complete=False, rows=1, error="timeout", note=None, endpoint="y", dropped={}, reported=None),
    ]
    df.attrs["partial"] = True
    return df


def _wait(app, w):
    while w._busy():
        app.processEvents()
        time.sleep(0.01)
    w._job.wait()
    app.processEvents()


def test_main_window_is_one_screen(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from PyQt5.QtWidgets import QApplication
    from swift_app.gui.main_window import HydroSwiftGUI
    app = QApplication.instance() or QApplication([])
    w = HydroSwiftGUI()
    assert not hasattr(w, "tab_widget")
    assert w.workbench.get_btn.text() == "Get data"
    assert not w.workbench.get_btn.isEnabled()  # nothing in the request yet
    w.deleteLater()  # close() would open the blocking exit-confirmation dialog


def test_find_review_get_use(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from PyQt5.QtWidgets import QApplication
    from swift_app import api
    from swift_app.gui.workbench import Workbench
    app = QApplication.instance() or QApplication([])
    seen = {}

    def fake_search(query=None, location=None, sources=None, *, period=None, **kw):
        seen["search"] = (query, location, sources, period)
        return _catalog()

    def fake_fetch(table, *, output_dir, period, format, overwrite, rc_discharge, progress, cancel, **kw):
        seen["fetch"] = (list(table["ID"]), period, format, rc_discharge, table.attrs.get("partial"))
        for i, (_, r) in enumerate(table.iterrows(), 1):
            progress({"event": "item_done", "index": i, "total": len(table), "title": r["Title"], "status": "saved"})
        out = pd.DataFrame({"status": ["saved"] * len(table), "source": table["Source"], "title": table["Title"],
                            "records": [5] * len(table), "path": ["f"] * len(table)})
        out.attrs["manifest"] = "m.json"
        return out

    monkeypatch.setattr(api, "search", fake_search)
    monkeypatch.setattr(api, "fetch", fake_fetch)
    w = Workbench()
    logs = []
    w.log_message.connect(lambda m, l: logs.append((m, l)))

    w.location.setText("Karnataka"); w.query.setText("rain"); w.start.setText("2022"); w.end.setText("2022")
    w.source_boxes["CWC-RSMS"].setChecked(False)
    w.do_search(); _wait(app, w)
    assert seen["search"] == ("rain", "Karnataka", ["NWDP", "CWC"], ("2022", "2022"))
    assert w.table.rowCount() == 2
    assert w.banner.isVisible() or not w.banner.isHidden()          # CWC failed -> warned
    assert "timeout" in w.banner.text()
    assert w.table.item(1, 5).text() == "unknown"                    # coverage shown honestly

    w.narrow.setText("water")                                        # narrow without re-searching
    assert w.table.rowCount() == 1 and w.count_label.text() == "1 of 2 shown"
    w.narrow.setText("")
    w.add_all_shown()
    assert len(w.basket) == 2 and w.basket.attrs["partial"] is True   # provenance travels
    w.add_all_shown()
    assert len(w.basket) == 2                                         # no duplicates

    w.format.setCurrentText("json"); w.rc.setChecked(False)
    w.do_get(); _wait(app, w)
    assert seen["fetch"] == (["r1", "c1"], ("2022", "2022"), "json", False, True)
    assert w.progress.value() == 2
    assert w.run_table.rowCount() == 2
    assert "2 saved" in w.run_summary.text()
    assert w.plot_btn.isEnabled() and w.merge_btn.isEnabled()
    assert any("Download finished" in m for m, _ in logs)


def test_failed_search_is_reported_not_swallowed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from PyQt5.QtWidgets import QApplication
    from swift_app import api
    from swift_app.gui.workbench import Workbench
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(api, "search", lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    w = Workbench()
    logs = []
    w.log_message.connect(lambda m, l: logs.append((m, l)))
    w.query.setText("rain")
    w.do_search(); _wait(app, w)
    assert any(l == "error" and "boom" in m for m, l in logs)
    assert w.search_btn.isEnabled()
