"""The GUI must at least construct and show its tabs without touching removed APIs."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt5")


def test_main_window_constructs_offscreen(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # the window creates ./output
    from PyQt5.QtWidgets import QApplication
    from swift_app.gui.main_window import HydroSwiftGUI

    app = QApplication.instance() or QApplication([])
    w = HydroSwiftGUI()
    titles = [w.tab_widget.tabText(i) for i in range(w.tab_widget.count())]
    assert any("Search" in t for t in titles)
    assert not any("CWC" in t for t in titles)  # expert CWC tab used removed APIs
    w.deleteLater()  # close() would open the blocking exit-confirmation dialog
