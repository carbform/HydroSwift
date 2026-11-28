"""Advanced mode: ``hyswift`` commands that act on the running dashboard session.

This is not a shell. A fixed set of commands is parsed and carried out on the
session state, so the page shows each result. Nothing here evaluates Python or
starts a process. No Streamlit calls: ``state`` is any mutable mapping.
"""

from __future__ import annotations

import argparse
import io
import shlex
from contextlib import redirect_stderr, redirect_stdout
from typing import Callable, MutableMapping

import pandas as pd

from hydroswift.core import analysis
from hydroswift.core.boundaries import INDIAN_BASINS, INDIAN_STATES, canonical_basin
from hydroswift.gui.model import pick_rows, row_keys
from hydroswift.gui.plotdata import station_options

HISTORY_LIMIT = 50
LOCAL_ADDRESSES = ("localhost", "127.0.0.1", "::1")
PLOT_KINDS = {"timeseries": "Time series", "hydrograph": "Time series", "hyetograph": "Rainfall",
              "rating_curve": "Rating curve", "compare": "Compare stations", "fdc": "Flow duration curve",
              "summary": "Summary & data quality", "monthly": "Monthly pattern",
              "exceedance": "Warning & danger exceedance", "groundwater": "Groundwater"}
VARIABLE_CHOICES = ["Water level", "Discharge", "Rainfall", "Groundwater level", "Water quality"]

HELP = """Commands (they update the page):
  search [variable] [--where TEXT | --basin NAME | --state NAME] [--source CWC ...] [--period 2023:2024]
  list [N]                      first N search results with their row numbers
  select 0,2-4 | all | none     tick rows
  get [--rows 0,2] [--period A:B] [--format csv|parquet|gpkg|json] [--out DIR] [--no-rc-discharge] [--overwrite]
  show                          what is loaded
  stats [--freq daily|monthly|annual] [--out FILE.csv]
  plot [station words] [--kind """ + "|".join(sorted(PLOT_KINDS)) + """]
  merge FILE.csv|.parquet|.gpkg|.json
  rsms daily                    reservoir status
  clear | help"""


class CommandError(Exception):
    """Message for the user; nothing was changed."""


class Console:
    def __init__(self, state: MutableMapping, *, search: Callable, download: Callable):
        self.state, self._search, self._download = state, search, download

    # --- entry point ----------------------------------------------------------
    def run(self, line: str) -> str:
        line = (line or "").strip()
        if not line:
            return ""
        try:
            words = shlex.split(line)
            if words and words[0] == "hyswift":
                words = words[1:]
            if not words:
                return HELP
            command, rest = words[0], words[1:]
            handler = getattr(self, f"do_{command}", None)
            if handler is None:
                raise CommandError(f"Unknown command {command!r}. This console runs dashboard commands only; "
                                   "type help.")
            output = handler(rest)
        except CommandError as e:
            output = f"error: {e}"
        except Exception as e:  # a failing command must never take the page down
            output = f"error: {type(e).__name__}: {e}"
        if line.split()[-1:] != ["clear"]:
            record(self.state, line, output)
        return output

    # --- helpers ----------------------------------------------------------------
    @staticmethod
    def _parse(parser: argparse.ArgumentParser, args: list) -> argparse.Namespace:
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer), redirect_stderr(buffer):
                return parser.parse_args(args)
        except SystemExit:  # argparse exits on --help and on bad input
            raise CommandError(buffer.getvalue().strip() or "could not read the arguments") from None

    @staticmethod
    def _parser(name: str) -> argparse.ArgumentParser:
        return argparse.ArgumentParser(prog=name, allow_abbrev=False)

    def _catalog(self) -> pd.DataFrame:
        catalog = self.state.get("catalog")
        if catalog is None or catalog.empty:
            raise CommandError("no search results yet; run search first")
        return catalog

    def _tidy(self) -> pd.DataFrame:
        tidy = self.state.get("tidy")
        if tidy is None or tidy.empty:
            raise CommandError("no data loaded yet; run get first")
        return tidy

    def _idle(self) -> None:
        if self.state.get("job") is not None:
            raise CommandError("a download is running; wait for it or press Cancel download")

    def _rows(self, spec: str, count: int) -> list:
        from hydroswift.cli import _rows
        if spec == "all":
            return list(range(count))
        try:
            return _rows(spec, count)
        except (SystemExit, ValueError):
            raise CommandError(f"bad row list {spec!r}; rows are numbered 0 to {count - 1}, e.g. 0,2-4") from None

    def _select(self, keys: set) -> None:
        self.state["selected"], self.state["editor_base"] = keys, None

    # --- commands ---------------------------------------------------------------
    def do_help(self, args):
        return HELP

    def do_clear(self, args):
        self.state["console_history"] = []
        return ""

    def do_search(self, args):
        self._idle()
        from hydroswift.cli import build_parser, print_status
        parsed = self._parse(build_parser(), ["search", *args])
        ids = [x for x in (parsed.ids or "").split(",") if x.strip()] or None
        catalog = self._search(parsed.query, parsed.location, sources=parsed.sources, period=parsed.period,
                               ids=ids, basin=parsed.basin, state=parsed.state)
        self.state.update(catalog=catalog, selected=set(), editor_base=None, run=None, tidy=None,
                          last_download=None, estimate=None, active_view="Hydrology Data",
                          main_view="Select Stations")
        self._sync_sidebar(parsed)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            print_status(catalog)
            if parsed.save:
                from hydroswift.core.engine import save_catalog
                print("Saved:", save_catalog(catalog, parsed.save))
        return f"{len(catalog)} rows\n{buffer.getvalue().rstrip()}\n{self._table(catalog, min(parsed.limit, 10))}"

    def _sync_sidebar(self, parsed) -> None:
        """Make the sidebar describe the search that is on screen."""
        state = self.state
        basin = canonical_basin(parsed.basin) if parsed.basin else None
        region = next((s for s in INDIAN_STATES if parsed.state and s.lower() == parsed.state.lower()), None)
        state.update(active_basin=None, active_state=None)
        if basin in INDIAN_BASINS:
            state.update(boundary_mode="Hydrological (Basin)", sb_basin=basin, active_basin=basin)
        elif region:
            state.update(boundary_mode="Administrative (State)", sb_state=region, active_state=region)
        else:
            state.update(boundary_mode="All / Custom", sb_custom=parsed.location or "")
        if parsed.query:
            known = next((v for v in VARIABLE_CHOICES if v.lower() == parsed.query.lower()), None)
            state["sb_variable"] = known or "Custom..."
            if not known:
                state["sb_custom_var"] = parsed.query
        else:
            state["sb_variable"] = "All Variables"
        chosen = parsed.sources or ["CWC", "WRIS", "NWDP"]
        state.update(src_cwc="CWC" in chosen, src_wris="WRIS" in chosen, src_nwdp="NWDP" in chosen)
        if parsed.period:
            from hydroswift.core.engine import parse_period
            low, high = parse_period(parsed.period)
            if low:
                state["sb_start"] = int(low[:4])
            if high:
                state["sb_end"] = int(high[:4])

    def _table(self, catalog: pd.DataFrame, limit: int) -> str:
        columns = [c for c in ("Source", "Title", "Location", "Variable", "ID") if c in catalog.columns]
        text = catalog.reset_index(drop=True)[columns].head(limit).to_string(max_colwidth=34)
        more = len(catalog) - limit
        return text + (f"\n... {more} more rows (list N shows more)" if more > 0 else "")

    def do_list(self, args):
        parser = self._parser("list")
        parser.add_argument("n", nargs="?", type=int, default=20)
        return self._table(self._catalog(), max(1, self._parse(parser, args).n))

    def do_select(self, args):
        parser = self._parser("select")
        parser.add_argument("rows", help="0,2-4 | all | none")
        spec = self._parse(parser, args).rows
        catalog = self._catalog()
        if spec == "none":
            self._select(set())
            return "selection cleared"
        keys = row_keys(catalog)
        self._select({keys[i] for i in self._rows(spec, len(catalog))})
        self.state["main_view"] = "Select Stations"
        return f"{len(self.state['selected'])} selected"

    def do_get(self, args):
        self._idle()
        parser = self._parser("get")
        parser.add_argument("--from", dest="source_file", help="catalog JSON from search --save")
        parser.add_argument("--rows", help="row numbers; default: the ticked rows")
        parser.add_argument("--period", help="YYYY:YYYY; default: the sidebar years")
        parser.add_argument("--out", help="folder; default: the dashboard's download folder")
        parser.add_argument("--format", choices=["csv", "parquet", "gpkg", "json"])
        parser.add_argument("--no-rc-discharge", action="store_true")
        parser.add_argument("--overwrite", action="store_true")
        a = self._parse(parser, args)
        if a.source_file:
            from hydroswift.core.engine import load_catalog
            self.state.update(catalog=load_catalog(a.source_file), selected=set(), editor_base=None)
        catalog = self._catalog()
        if a.rows:
            keys = row_keys(catalog)
            self._select({keys[i] for i in self._rows(a.rows, len(catalog))})
        selected = self.state.get("selected") or set()
        if not selected:
            raise CommandError("nothing selected; use select, or get --rows 0,1")
        period = a.period or (f"{self.state.get('sb_start', 2020)}:{self.state.get('sb_end', 2024)}")
        folder = a.out or self.state.get("dest_input") or self.state.get("download_dir") or "output"
        table = pick_rows(catalog, selected)
        self._download(table, period=period, output_dir=folder,
                       export_format=a.format or self.state.get("export_format", "csv"),
                       rc_discharge=not a.no_rc_discharge, overwrite=a.overwrite)
        return f"downloading {len(table)} item(s) for {period} into {folder}; progress is shown on the page"

    def do_show(self, args):
        self._parse(self._parser("show"), args)
        grouped = self._tidy().groupby(["source", "variable", "unit", "method"], dropna=False)
        return grouped.agg(rows=("value", "size"), stations=("station_id", "nunique"),
                           start=("time", "min"), end=("time", "max")).to_string()

    def do_stats(self, args):
        parser = self._parser("stats")
        parser.add_argument("--freq", choices=list(analysis.FREQUENCIES))
        parser.add_argument("--out")
        a = self._parse(parser, args)
        tidy = self._tidy()
        table = analysis.resample(tidy, a.freq) if a.freq else analysis.summary(tidy)
        self.state["main_view"] = "Visualize"
        if not a.freq:
            self.state["viz_kind"] = "Summary & data quality"
        saved = ""
        if a.out:
            table.to_csv(a.out, index=False)
            saved = f"\nSaved: {a.out}"
        columns = (["station_id", "time", "variable", "value", "readings"] if a.freq else
                   ["station_id", "variable", "readings", "completeness_pct_of_record", "min", "mean", "max"])
        return table[columns].head(20).to_string(index=False) + (
            f"\n... {len(table) - 20} more rows (use --out)" if len(table) > 20 else "") + saved

    def do_plot(self, args):
        parser = self._parser("plot")
        parser.add_argument("station", nargs="*", help="words from the station name or ID")
        parser.add_argument("--kind", choices=sorted(PLOT_KINDS), default="timeseries")
        a = self._parse(parser, args)
        options = list(station_options(self._tidy()))
        words = [w.lower() for w in a.station]
        matches = [o for o in options if all(w in o.lower() for w in words)]
        if not matches:
            raise CommandError("no loaded station matches; loaded: " + "; ".join(options))
        self.state.update(main_view="Visualize", viz_kind=PLOT_KINDS[a.kind], active_view="Hydrology Data")
        if words:
            self.state["viz_station"] = matches[0]
        note = f" ({len(matches)} matched; showing the first)" if words and len(matches) > 1 else ""
        return f"showing {PLOT_KINDS[a.kind]}" + (f" for {matches[0]}" if words else "") + note

    def do_merge(self, args):
        parser = self._parser("merge")
        parser.add_argument("output")
        path = self._parse(parser, args).output
        from hydroswift.core.outputs import merge
        return f"wrote {len(merge(self._tidy(), path))} rows to {path}"

    def do_rsms(self, args):
        parser = self._parser("rsms")
        parser.add_argument("what", choices=["daily"])
        self._parse(parser, args)
        self.state.update(active_view="Reservoir Status", rsms_daily=None, rsms_fetch=True)
        return "fetching reservoir status; see the page"


def record(state: MutableMapping, command: str, output: str = "") -> None:
    """Append to the console history (also used to log what was done with the mouse)."""
    history = list(state.get("console_history") or [])
    history.append((command, output))
    state["console_history"] = history[-HISTORY_LIMIT:]


def row_spec(catalog: pd.DataFrame, keys: set) -> str:
    """Compact row list (``0,2-4``) for the ticked rows, as ``select`` reads it."""
    rows = [i for i, key in enumerate(row_keys(catalog)) if key in keys]
    parts, start = [], None
    for i, row in enumerate(rows):
        start = row if start is None else start
        if i + 1 == len(rows) or rows[i + 1] != row + 1:
            parts.append(str(start) if start == row else f"{start}-{row}")
            start = None
    return ",".join(parts)


def search_command(query, location, basin, state, sources, period) -> str:
    """The command that repeats a search made with the sidebar."""
    words = ["search"]
    if query:
        words.append(shlex.quote(query))
    if basin:
        words += ["--basin", shlex.quote(basin)]
    elif state:
        words += ["--state", shlex.quote(state)]
    elif location:
        words += ["--where", shlex.quote(location)]
    for source in sources:
        words += ["--source", source]
    if period:
        words += ["--period", ":".join(period)]
    return " ".join(words)
