"""The single HydroSwift screen: Find -> Review -> Get -> Use.

Every action calls the same functions as Python and the CLI
(``search`` / ``estimate`` / ``fetch`` / ``load`` / ``plot`` / ``merge``), so
what the GUI shows is what a script would get.
"""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from typing import Optional

import pandas as pd
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QProgressBar, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from .. import api as _api
from . import model

SOURCES = [("NWDP", "NWDP (India-WRIS open data)"), ("CWC", "CWC flood forecasting"),
           ("CWC-RSMS", "CWC reservoir storage (latest day)")]
LEVEL_STYLE = {"ok": "color:#1b7f3b;", "partial": "color:#b36b00;font-weight:bold;",
               "failed": "color:#b00020;font-weight:bold;"}


class _Job(QThread):
    """Run one engine call off the UI thread. Progress events arrive as signals."""

    event = pyqtSignal(dict)
    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn, cancel: Optional[threading.Event] = None):
        super().__init__()
        self.fn, self.cancel = fn, cancel

    def run(self):
        try:
            self.done.emit(self.fn(self.event.emit, self.cancel))
        except Exception as e:  # shown to the user, never swallowed
            self.failed.emit(f"{type(e).__name__}: {e}")


def _table(headers, multi=True) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.ExtendedSelection if multi else QAbstractItemView.SingleSelection)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    t.setMinimumHeight(110)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    t.horizontalHeader().setStretchLastSection(True)
    return t


class Workbench(QWidget):
    status_changed = pyqtSignal(str)
    log_message = pyqtSignal(str, str)
    download_completed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.output_dir = Path("output")
        self.results: Optional[pd.DataFrame] = None   # last search (full, provenance in attrs)
        self.basket: Optional[pd.DataFrame] = None
        self.run: Optional[pd.DataFrame] = None       # last fetch
        self._shown: list = []                         # results index per table row
        self._job: Optional[_Job] = None
        self._cancel: Optional[threading.Event] = None
        self._build()
        self._refresh_buttons()

    # ------------------------------------------------------------------ layout
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        # 1 Find
        find = QGroupBox("1. Find")
        fl = QVBoxLayout(find)
        row = QHBoxLayout()
        self.location = QLineEdit(); self.location.setPlaceholderText("Location (organisation, basin, state, district or river)")
        self.query = QLineEdit(); self.query.setPlaceholderText("Variable or keyword, e.g. rainfall")
        self.start = QLineEdit(); self.start.setPlaceholderText("from (2020 or 2020-06-01)"); self.start.setMaximumWidth(170)
        self.end = QLineEdit(); self.end.setPlaceholderText("to (2022 or 2022-06-30)"); self.end.setMaximumWidth(170)
        for lab, w in (("Where", self.location), ("What", self.query), ("Period", self.start)):
            row.addWidget(QLabel(lab)); row.addWidget(w)
        row.addWidget(QLabel("to")); row.addWidget(self.end)
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.do_search)
        self.location.returnPressed.connect(self.do_search)
        self.query.returnPressed.connect(self.do_search)
        row.addWidget(self.search_btn)
        fl.addLayout(row)
        srow = QHBoxLayout()
        srow.addWidget(QLabel("Sources"))
        self.source_boxes = {}
        for key, label in SOURCES:
            cb = QCheckBox(label); cb.setChecked(True)
            self.source_boxes[key] = cb; srow.addWidget(cb)
        srow.addStretch()
        fl.addLayout(srow)
        self.status_row = QHBoxLayout()
        self.status_row.addWidget(QLabel("Source status: not searched yet"))
        fl.addLayout(self.status_row)
        self.banner = QLabel(""); self.banner.setWordWrap(True)
        self.banner.setStyleSheet("color:#b36b00;"); self.banner.hide()
        fl.addWidget(self.banner)

        # 2 Review
        review = QGroupBox("2. Review and choose")
        rl = QVBoxLayout(review)
        frow = QHBoxLayout()
        frow.addWidget(QLabel("Narrow these results"))
        self.narrow = QLineEdit(); self.narrow.setPlaceholderText("words that must appear in variable, title or location")
        self.narrow.textChanged.connect(self._apply_narrow)
        frow.addWidget(self.narrow)
        self.count_label = QLabel("")
        frow.addWidget(self.count_label)
        rl.addLayout(frow)
        self.table = _table([h for _, h in model.REVIEW_COLUMNS])
        self.table.itemSelectionChanged.connect(self._refresh_buttons)
        rl.addWidget(self.table)
        brow = QHBoxLayout()
        self.add_btn = QPushButton("Add selected to request"); self.add_btn.clicked.connect(self.add_selected)
        self.addall_btn = QPushButton("Add all shown"); self.addall_btn.clicked.connect(self.add_all_shown)
        brow.addWidget(self.add_btn); brow.addWidget(self.addall_btn); brow.addStretch()
        rl.addLayout(brow)

        # 3 Get
        get = QGroupBox("3. Get")
        gl = QVBoxLayout(get)
        self.basket_table = _table(["Source", "Title / station", "Variable", "Coverage", "Est. records", "ID"])
        self.basket_table.itemSelectionChanged.connect(self._refresh_buttons)
        self.basket_table.setMaximumHeight(170)
        gl.addWidget(QLabel("Your request"))
        gl.addWidget(self.basket_table)
        orow = QHBoxLayout()
        self.remove_btn = QPushButton("Remove selected"); self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_btn = QPushButton("Clear"); self.clear_btn.clicked.connect(self.clear_basket)
        self.est_btn = QPushButton("Estimate size"); self.est_btn.clicked.connect(self.do_estimate)
        for b in (self.remove_btn, self.clear_btn, self.est_btn):
            orow.addWidget(b)
        orow.addStretch()
        orow.addWidget(QLabel("Format"))
        self.format = QComboBox(); self.format.addItems(["csv", "xlsx", "json"]); orow.addWidget(self.format)
        self.rc = QCheckBox("CWC discharge (rating-curve estimate)"); self.rc.setChecked(True)
        self.overwrite = QCheckBox("Re-download existing")
        orow.addWidget(self.rc); orow.addWidget(self.overwrite)
        gl.addLayout(orow)
        drow = QHBoxLayout()
        drow.addWidget(QLabel("Save to"))
        self.out_edit = QLineEdit(str(self.output_dir)); drow.addWidget(self.out_edit)
        browse = QPushButton("Browse"); browse.clicked.connect(self._browse); drow.addWidget(browse)
        self.get_btn = QPushButton("Get data"); self.get_btn.setMinimumHeight(34)
        self.get_btn.clicked.connect(self.do_get)
        self.cancel_btn = QPushButton("Cancel"); self.cancel_btn.clicked.connect(self.do_cancel)
        drow.addWidget(self.get_btn); drow.addWidget(self.cancel_btn)
        gl.addLayout(drow)
        self.progress = QProgressBar(); self.progress.setTextVisible(True); self.progress.setFormat("%v / %m items")
        gl.addWidget(self.progress)
        self.progress_label = QLabel(""); gl.addWidget(self.progress_label)

        # 4 Use
        use = QGroupBox("4. Use")
        ul = QVBoxLayout(use)
        self.run_table = _table(["Status", "Source", "Title / station", "Records", "From", "To", "Note", "File"], multi=False)
        self.run_table.setMaximumHeight(170)
        ul.addWidget(self.run_table)
        self.run_summary = QLabel("Nothing fetched yet."); self.run_summary.setWordWrap(True)
        ul.addWidget(self.run_summary)
        urow = QHBoxLayout()
        self.plot_btn = QPushButton("Plot"); self.plot_btn.clicked.connect(self.do_plot)
        self.merge_btn = QPushButton("Merge to one file"); self.merge_btn.clicked.connect(self.do_merge)
        self.open_btn = QPushButton("Open folder"); self.open_btn.clicked.connect(self.open_folder)
        self.manifest_label = QLabel("")
        for b in (self.plot_btn, self.merge_btn, self.open_btn):
            urow.addWidget(b)
        urow.addWidget(self.manifest_label); urow.addStretch()
        ul.addLayout(urow)

        top = QSplitter(Qt.Vertical)
        for w in (find, review, get, use):
            top.addWidget(w)
        top.setStretchFactor(1, 4); top.setStretchFactor(2, 2); top.setStretchFactor(3, 2)
        top.setChildrenCollapsible(False)
        root.addWidget(top)

    # --------------------------------------------------------------- helpers
    def _log(self, msg, level="info"):
        self.log_message.emit(msg, level)

    def _busy(self) -> bool:
        return self._job is not None and self._job.isRunning()

    def _refresh_buttons(self):
        busy = self._busy()
        have_basket = self.basket is not None and len(self.basket) > 0
        have_run = self.run is not None and len(self.run) > 0
        self.search_btn.setEnabled(not busy)
        self.add_btn.setEnabled(not busy and bool(self.table.selectionModel().selectedRows()))
        self.addall_btn.setEnabled(not busy and bool(self._shown))
        self.remove_btn.setEnabled(not busy and bool(self.basket_table.selectionModel().selectedRows()))
        self.clear_btn.setEnabled(not busy and have_basket)
        self.est_btn.setEnabled(not busy and have_basket)
        self.get_btn.setEnabled(not busy and have_basket)
        self.cancel_btn.setEnabled(busy and self._cancel is not None)
        for b in (self.plot_btn, self.merge_btn):
            b.setEnabled(not busy and have_run)
        self.open_btn.setEnabled(True)

    def _sources(self):
        return [k for k, cb in self.source_boxes.items() if cb.isChecked()]

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Save data to", self.out_edit.text())
        if d:
            self.out_edit.setText(d)

    def set_output_dir(self, path):
        self.output_dir = Path(path)
        self.out_edit.setText(str(path))

    def _start(self, fn, on_done, label, cancellable=False):
        if self._busy():
            return
        self._cancel = threading.Event() if cancellable else None
        self._job = _Job(fn, self._cancel)
        self._job.done.connect(on_done)
        self._job.failed.connect(lambda m: self._on_failed(label, m))
        self._job.finished.connect(self._refresh_buttons)
        self._job.event.connect(self._on_event)
        self.status_changed.emit(label + "...")
        self._job.start()
        self._refresh_buttons()

    def _on_failed(self, label, msg):
        self._log(f"{label} failed: {msg}", "error")
        self.status_changed.emit(f"{label} failed")

    # ------------------------------------------------------------------ Find
    def do_search(self):
        sources = self._sources()
        if not sources:
            self._log("Tick at least one source.", "warning"); return
        loc, q = self.location.text().strip() or None, self.query.text().strip() or None
        period = model.parse_period_inputs(self.start.text(), self.end.text())
        if not (loc or q or period):
            self._log("Enter a place, a variable or a period first.", "warning"); return
        self._log(f"Searching {', '.join(sources)}: where={loc!r} what={q!r} period={period}")

        def job(emit, cancel):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # incomplete sources are shown in the status strip instead
                return _api.search(query=q, location=loc, sources=sources, period=period)

        self._start(job, self._on_results, "Searching")

    def _on_results(self, df):
        self.results = df
        self.narrow.blockSignals(True); self.narrow.clear(); self.narrow.blockSignals(False)
        self._show_status(df)
        self._fill_results()
        n = len(df)
        self._log(f"Found {n} item(s)." if n else "Nothing matched. Check the status strip for sources that failed.",
                  "success" if n else "warning")
        self.status_changed.emit("Search complete")

    def _show_status(self, df):
        while self.status_row.count():
            w = self.status_row.takeAt(0).widget()
            if w:
                w.setParent(None)  # leave the layout now; deleteLater alone leaves it painted
        self.status_row.addWidget(QLabel("Source status:"))
        lines = model.source_status_lines(df)
        for ln in lines:
            lab = QLabel(ln["text"]); lab.setStyleSheet(LEVEL_STYLE[ln["level"]])
            lab.setToolTip(ln["detail"] or "no further detail")
            self.status_row.addWidget(lab)
        self.status_row.addStretch()
        bad = [ln for ln in lines if ln["level"] != "ok"]
        if bad:
            self.banner.setText("Results may be incomplete: " + "; ".join(
                f"{b['source']} ({(b['detail'] or '').splitlines()[0] if b['detail'] else b['level']})" for b in bad))
            self.banner.show()
        else:
            self.banner.hide()

    def _fill_results(self):
        df = self.results
        mask = model.text_filter(df, self.narrow.text()) if df is not None and len(df) else None
        idx = list(df.index[mask]) if mask is not None else []
        self._shown = idx
        self.table.setRowCount(len(idx))
        for r, i in enumerate(idx):
            for c, (col, _) in enumerate(model.REVIEW_COLUMNS):
                it = QTableWidgetItem(model.review_value(df, i, col))
                it.setToolTip(it.text())
                self.table.setItem(r, c, it)
        self.table.resizeColumnsToContents()
        total = 0 if df is None else len(df)
        self.count_label.setText(f"{len(idx)} of {total} shown")
        self._refresh_buttons()

    def _apply_narrow(self, _):
        if self.results is not None:
            self._fill_results()

    # ---------------------------------------------------------------- Review
    def _add(self, idx):
        if not idx:
            return
        self.basket = model.add_to_basket(self.basket, self.results, idx)
        self._fill_basket()

    def add_selected(self):
        rows = sorted({m.row() for m in self.table.selectionModel().selectedRows()})
        self._add([self._shown[r] for r in rows])

    def add_all_shown(self):
        self._add(list(self._shown))

    def _fill_basket(self):
        b = self.basket
        n = 0 if b is None else len(b)
        self.basket_table.setRowCount(n)
        cols = ["Source", "Title", "Variable", "Coverage", "EstRecords", "ID"]
        for r in range(n):
            for c, col in enumerate(cols):
                self.basket_table.setItem(r, c, QTableWidgetItem(model.review_value(b, b.index[r], col)))
        self.basket_table.resizeColumnsToContents()
        self._refresh_buttons()

    def remove_selected(self):
        rows = [m.row() for m in self.basket_table.selectionModel().selectedRows()]
        if rows and self.basket is not None:
            self.basket = model.remove_from_basket(self.basket, rows)
            self._fill_basket()

    def clear_basket(self):
        self.basket = None
        self._fill_basket()

    def do_estimate(self):
        basket = self.basket
        self._log("Asking the sources for record counts (NWDP only; others do not report counts)...")

        def job(emit, cancel):
            return _api.estimate(basket)

        self._start(job, self._on_estimate, "Estimating")

    def _on_estimate(self, est):
        if self.basket is not None and len(est) == len(self.basket):
            self.basket["EstRecords"] = list(est["EstRecords"])
            self.basket["EstNote"] = list(est["EstNote"])
            self._fill_basket()
            known = int(pd.to_numeric(est["EstRecords"], errors="coerce").fillna(0).sum())
            unknown = int(est["EstRecords"].isna().sum())
            self._log(f"About {known:,} records in the whole NWDP resources; {unknown} item(s) with unknown size. "
                      "NWDP dates are applied after download, so the final file can be smaller.")
        self.status_changed.emit("Estimate ready")

    # ------------------------------------------------------------------- Get
    def do_get(self):
        basket = self.basket
        period = model.parse_period_inputs(self.start.text(), self.end.text())
        out, fmt = self.out_edit.text().strip() or "output", self.format.currentText()
        rc, ow = self.rc.isChecked(), self.overwrite.isChecked()
        self.progress.setRange(0, len(basket)); self.progress.setValue(0)
        self.progress_label.setText("")
        self._log(f"Getting {len(basket)} item(s) into {out} (period={period}, format={fmt}).")

        def job(emit, cancel):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return _api.fetch(basket, output_dir=out, period=period, format=fmt, overwrite=ow,
                                  rc_discharge=rc, progress=emit, cancel=cancel)

        self._start(job, self._on_fetched, "Downloading", cancellable=True)

    def do_cancel(self):
        if self._cancel is not None:
            self._cancel.set()
            self.progress_label.setText("Cancelling after the current page...")
            self._log("Cancel requested.", "warning")

    def _on_event(self, ev):
        text = model.progress_text(ev)
        self.progress_label.setText(text.strip())
        if ev.get("event") == "item_done":
            self.progress.setValue(int(ev.get("index") or 0))
            self._log(text, "error" if ev.get("status") == "error" else "info")

    def _on_fetched(self, run):
        self.run = run
        self._fill_run()
        self._cancel = None
        summary = model.summarise_fetch(run)
        self._log("Download finished: " + summary, "success")
        self.status_changed.emit("Download complete")
        self.download_completed.emit({"files_saved": int((run["status"] == "saved").sum()),
                                      "output_dir": self.out_edit.text()})

    # ------------------------------------------------------------------- Use
    def _fill_run(self):
        run = self.run
        self.run_table.setRowCount(len(run))
        for r, (_, x) in enumerate(run.iterrows()):
            vals = [x.get("status"), x.get("source"), x.get("title"), x.get("records"), x.get("start"),
                    x.get("end"), x.get("error") or x.get("method_note"), x.get("path")]
            for c, v in enumerate(vals):
                txt = "" if v is None or (not isinstance(v, str) and pd.isna(v)) else str(v)
                it = QTableWidgetItem(txt); it.setToolTip(txt)
                self.run_table.setItem(r, c, it)
        self.run_table.resizeColumnsToContents()
        self.run_summary.setText(model.summarise_fetch(run))
        mf = run.attrs.get("manifest")
        self.manifest_label.setText(f"Record of this run: {mf}" if mf else "")
        self._refresh_buttons()

    def do_plot(self):
        run, out = self.run, str(Path(self.out_edit.text()) / "plots")

        def job(emit, cancel):
            return _api.plot(run, out)

        self._start(job, lambda paths: self._on_plotted(paths, out), "Plotting")

    def _on_plotted(self, paths, out):
        self._log(f"Wrote {len(paths)} figure(s) to {out}", "success" if paths else "warning")
        if paths:
            self.open_path(out)

    def do_merge(self):
        run = self.run
        default = str(Path(self.out_edit.text()) / "merged.parquet")
        path, _ = QFileDialog.getSaveFileName(self, "Merge to one file", default,
                                              "Parquet (*.parquet);;CSV (*.csv);;GeoPackage (*.gpkg)")
        if not path:
            return

        def job(emit, cancel):
            return _api.merge(run, path)

        self._start(job, lambda t: self._log(f"Merged {len(t):,} rows into {path}", "success"), "Merging")

    def open_folder(self):
        self.open_path(self.out_edit.text())

    def open_path(self, path):
        Path(path).mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(["xdg-open", str(path)], check=False)
        except Exception as e:
            self._log(f"Could not open {path}: {e}", "warning")
