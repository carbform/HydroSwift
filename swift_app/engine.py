"""HydroSwift core engine: one catalog schema, one search, one fetch.

Every data source is an *adapter* with two methods::

    adapter.search(query, location) -> (rows, SourceStatus)
    adapter.fetch(row, opts)        -> FetchRecord

Design rules (these exist so users can see where data came from):

* **Fixed schema.** Every search row has the columns in ``CATALOG_COLUMNS``.
* **Nothing fails silently.** Each source reports a ``SourceStatus`` (ok,
  error, rows, whether the listing is complete, rows dropped and why). It is
  stored on ``df.attrs['source_status']`` and ``df.attrs['partial']``.
* **Inferred is labelled.** Fields the source did not state (e.g. variable
  parsed from a dataset title) are listed in the row's ``Inferred`` column.
* **One location rule.** Case-insensitive substring match against the fields a
  source actually has (NWDP: organization; CWC: basin, state, district, river).
  The field that matched is recorded in ``MatchedOn``.
* **Manifest.** ``fetch`` writes ``<output_dir>/manifest.json`` with the query,
  endpoints, per-item record counts, actual date spans, and TLS verification.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

CATALOG_COLUMNS = [
    "Source", "Title", "Location", "Variable", "Resolution", "ID",
    "lat", "lon", "Unit", "CoverageStart", "CoverageEnd", "CoverageKnown",
    "Provider", "Endpoint", "MatchedOn", "Inferred",
]

_CWC_WL_WORDS = ("water level", "level", "stage", "discharge", "flow", "river", "gauge", "gage")
_RSMS_WORDS = ("reservoir", "storage", "live capacity", "dam")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def match_location(location: Optional[str], fields: dict) -> Optional[str]:
    """Return the name of the first field containing *location*, '' if no filter, None if no match."""
    if not location:
        return ""
    needle = str(location).strip().lower()
    for name, value in fields.items():
        if value is not None and needle in str(value).lower():
            return name
    return None


_PERIOD_RE = re.compile(r"(\d{4})\s*(?:to|-|–)\s*(\d{4})", re.I)


def parse_name_period(text) -> tuple:
    """Pull a 'YYYY To YYYY' span out of a resource name -> (start, end) ISO dates or (None, None)."""
    m = _PERIOD_RE.search(str(text or ""))
    if not m:
        return None, None
    a, b = int(m.group(1)), int(m.group(2))
    if a > b or not (1800 <= a <= 2100 and 1800 <= b <= 2100):
        return None, None
    return f"{a}-01-01", f"{b}-12-31"


def parse_period(period) -> tuple:
    """Normalise a period to (start_iso, end_iso) or (None, None).

    Accepts ("2020", "2022"), ("2020-03-01", None), "2020:2022" or "2020".
    A bare-year end means the end of that year.
    """
    if period is None:
        return None, None
    if isinstance(period, str):
        parts = period.split(":")
        period = (parts[0], parts[1] if len(parts) > 1 else parts[0])
    a, b = period
    def one(x, end):
        if x in (None, ""):
            return None
        x = str(x).strip()
        if re.fullmatch(r"\d{4}", x):
            return f"{x}-12-31" if end else f"{x}-01-01"
        return pd.Timestamp(x).date().isoformat()
    lo, hi = one(a, False), one(b, True)
    if lo and hi and lo > hi:
        raise ValueError(f"period start {lo} is after end {hi}")
    return lo, hi


def _overlaps(cs, ce, lo, hi) -> bool:
    if lo and ce and pd.Timestamp(ce) < pd.Timestamp(lo):
        return False
    if hi and cs and pd.Timestamp(cs) > pd.Timestamp(hi):
        return False
    return True


@dataclass
class SourceStatus:
    source: str
    ok: bool = True
    complete: bool = True
    rows: int = 0
    error: Optional[str] = None
    note: Optional[str] = None
    endpoint: Optional[str] = None
    dropped: dict = field(default_factory=dict)
    reported: Optional[int] = None

    def as_dict(self) -> dict:
        return asdict(self)

    def label(self) -> str:
        if not self.ok:
            return f"{self.source} FAILED ({self.error})"
        if not self.complete:
            return f"{self.source} PARTIAL ({self.error})"
        return f"{self.source} ok ({self.rows})"


@dataclass
class FetchRecord:
    source: str
    id: str
    title: str
    status: str = "pending"  # saved | skipped | empty | error
    path: Optional[str] = None
    records: Optional[int] = None
    start: Optional[str] = None
    end: Optional[str] = None
    endpoint: Optional[str] = None
    error: Optional[str] = None
    filtered_client_side: bool = False
    complete: Optional[bool] = None
    req_start: Optional[str] = None
    req_end: Optional[str] = None
    method_note: Optional[str] = None
    reused: bool = False
    fetched_at: str = field(default_factory=_now)


@dataclass
class FetchOptions:
    output_dir: str = "output"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    format: str = "csv"
    overwrite: bool = False
    quiet: bool = False
    rc_discharge: bool = True      # CWC discharge exists only as a rating-curve estimate
    resume: bool = True            # reuse files recorded in an earlier manifest for the same request
    progress: Any = None           # callable(event: dict); never prints
    cancel: Any = None             # threading.Event-like with is_set()


def _slug(x) -> str:
    return "".join(c if c.isalnum() else "_" for c in str(x or "unknown")).strip("_") or "unknown"


def _emit(opts, event, rec=None, **kw):
    if opts.progress is not None:
        try:
            opts.progress({"event": event, "source": getattr(rec, "source", None),
                           "id": getattr(rec, "id", None), "title": getattr(rec, "title", None), **kw})
        except Exception:
            pass  # a faulty UI callback must never break a download


def _iso(ts) -> Optional[str]:
    if ts is None or (not isinstance(ts, str) and pd.isna(ts)):
        return None
    try:
        return pd.Timestamp(ts).isoformat()
    except Exception:
        return str(ts)


# ---------------------------------------------------------------------------
# NWDP adapter
# ---------------------------------------------------------------------------

class NwdpAdapter:
    name = "NWDP"
    client_factory = None  # tests may inject

    def _client(self):
        if self.client_factory is not None:
            return self.client_factory()
        from .nwdp_client import NwdpClient
        return NwdpClient()

    def search(self, query, location):
        from .nwdp import _parse_nwdp_title
        client = self._client()
        st = SourceStatus(self.name, endpoint=getattr(client, "SEARCH_API", None))
        org = location
        matched_on = ""
        if location:
            try:
                orgs = client.get_organizations()
            except Exception as e:  # pragma: no cover - defensive
                orgs = []
                st.note = f"organization lookup failed: {e}"
            needle = location.lower()
            hits = [o["name"] for o in orgs
                    if needle in o.get("title", "").lower() or needle in o.get("name", "").lower()]
            org = hits if hits else location
            matched_on = "organization"
            if not hits:
                st.note = (st.note or "") + " no organization matched; NWDP location filter covers organizations only."
        raw = client.search_datasets(query=query, org=org)
        info = getattr(client, "last_search", None) or {}
        st.ok = info.get("ok", True)
        st.complete = info.get("complete", True)
        st.error = info.get("error")
        st.reported = info.get("packages_reported")
        if info.get("resources_dropped_small"):
            st.dropped["empty_resources(<=300 bytes)"] = info["resources_dropped_small"]
        rows = []
        for r in raw:
            var, res = _parse_nwdp_title(r.get("dataset_title"))
            # a dataset is often split into many resources whose NAME carries the period
            # ("... 1900 To 1928"); show it so rows are distinguishable, and use it as coverage
            rname = str(r.get("resource_name") or "").strip()
            title = rname or str(r.get("dataset_title", ""))
            cov_s, cov_e = parse_name_period(rname)
            rows.append({
                "Source": self.name,
                "Title": title,
                "Location": str(r.get("organization", "")),
                "Variable": var, "Resolution": res,
                "ID": str(r.get("resource_id", "")),
                "lat": None, "lon": None, "Unit": None,
                "CoverageStart": cov_s, "CoverageEnd": cov_e, "CoverageKnown": bool(cov_s),
                "Provider": str(r.get("organization", "")) or "NWDP",
                "Endpoint": r.get("dataset_url") or getattr(client, "BASE", ""),
                "MatchedOn": matched_on,
                # variable/resolution are parsed from the title text, not stated by the portal
                "Inferred": "Variable,Resolution" + (",Coverage" if cov_s else ""),
                "_org_id": r.get("org_id", "unknown"),
            })
        st.rows = len(rows)
        return rows, st

    def fetch(self, row, opts: FetchOptions) -> FetchRecord:
        from .nwdp import nwdp_save, _nwdp_time_span
        rec = FetchRecord(self.name, str(row["ID"]), str(row["Title"]))
        client = self._client()
        rec.endpoint = getattr(client, "DATASTORE_API", None)
        cs, ce = row.get("CoverageStart"), row.get("CoverageEnd")
        if cs and ce and (opts.start_date or opts.end_date):
            lo = pd.Timestamp(opts.start_date) if opts.start_date else pd.Timestamp.min
            hi = pd.Timestamp(opts.end_date) if opts.end_date else pd.Timestamp.max
            if pd.Timestamp(ce) < lo or pd.Timestamp(cs) > hi:
                rec.status, rec.records = "skipped", 0
                rec.error = f"not downloaded: resource period {cs[:4]}-{ce[:4]} (from its name) is outside the requested range"
                return rec
        try:
            def _page(read, total):
                _emit(opts, "page", rec, read=read, total=total)
            records = client.fetch_records(rec.id, progress=_page, cancel=opts.cancel)
            info = getattr(client, "last_fetch", None) or {}
            rec.complete = info.get("complete", True)
            if not info.get("ok", True) or not rec.complete:
                rec.error = info.get("error")
            if info.get("cancelled"):
                rec.status = "cancelled"
                rec.records = len(records)
                return rec
            if not records:
                rec.status = "error" if rec.error else "empty"
                rec.records = 0
                return rec
            df = pd.DataFrame(records)
            if opts.start_date or opts.end_date:
                date_cols = [c for c in df.columns if any(k in c.lower() for k in ("date", "time", "monitoring"))]
                if date_cols:
                    from .nwdp import parse_nwdp_dates
                    ts = parse_nwdp_dates(df[date_cols[0]])  # NWDP uses DD-MM-YYYY
                    keep = pd.Series(True, index=df.index)
                    if opts.start_date:
                        keep &= ts >= pd.Timestamp(opts.start_date)
                    if opts.end_date:
                        keep &= ts <= pd.Timestamp(opts.end_date)
                    df = df[keep.fillna(False)]
                    rec.filtered_client_side = True  # portal has no server-side date filter here
                else:
                    rec.error = (rec.error or "") + " no date column found; date range not applied"
            if df.empty:
                rec.status, rec.records = "empty", 0
                return rec
            org_id = row.get("_org_id") or row.get("Location") or "unknown"
            path = nwdp_save(df, opts.output_dir, org_id, row["Title"], opts.format)
            lo, hi = _nwdp_time_span(df)
            rec.status = "saved"  # rec.error/complete flag any truncation
            rec.path, rec.records = str(path), len(df)
            rec.start, rec.end = _iso(lo), _iso(hi)
        except Exception as e:
            rec.status, rec.error = "error", str(e)
        return rec


# ---------------------------------------------------------------------------
# CWC flood-forecasting stations adapter
# ---------------------------------------------------------------------------

class CwcAdapter:
    name = "CWC"
    endpoint = "https://ffs.india-water.gov.in/iam/api"

    def search(self, query, location):
        from .cwc import load_station_table
        st = SourceStatus(self.name, endpoint=self.endpoint)
        if query and not any(w in query.lower() for w in _CWC_WL_WORDS):
            st.note = f"CWC FFS serves only water level and discharge; '{query}' does not match, source skipped."
            return [], st
        df = load_station_table(refresh=False)
        st.note = "station list is the packaged/cached metadata table (not a live query)"
        try:
            from .cwc import _get_rc_row
        except Exception:  # pragma: no cover
            _get_rc_row = lambda *a, **k: None  # noqa: E731
        rows = []
        for _, r in df.iterrows():
            m = match_location(location, {
                "basin": r.get("basin"), "state": r.get("state"),
                "district": r.get("district"), "river": r.get("river"),
            })
            if m is None:
                continue
            rows.append({
                "Source": self.name,
                "Title": str(r.get("name", "")),
                "Location": f"{r.get('basin', '')}, {r.get('state', '')}",
                "Variable": ("Water level; discharge (rating-curve estimate)"
                             if _has_rc(_get_rc_row, r) else "Water level"),
                "Resolution": "Sub-daily (about 3 readings per day)",
                "ID": str(r.get("code", "")),
                "lat": r.get("lat"), "lon": r.get("lon"), "Unit": "m / m3/s",
                "CoverageStart": None, "CoverageEnd": None, "CoverageKnown": False,
                "Provider": "CWC", "Endpoint": self.endpoint,
                "MatchedOn": m,
                # catalogue does not state per-station variables, cadence or period of record
                "Inferred": "Variable,Resolution,Unit,Coverage",
                "_basin": str(r.get("basin", "")),
                "_rl_zero": r.get("rl_zero"),
            })
        st.rows = len(rows)
        return rows, st

    def fetch(self, row, opts: FetchOptions) -> FetchRecord:
        from collections import namedtuple
        from .cwc import download_station_detail
        rec = FetchRecord(self.name, str(row["ID"]), str(row["Title"]), endpoint=self.endpoint)
        Args = namedtuple("Args", ["format", "overwrite", "start_date", "end_date", "cwc_var", "cwc_rc_discharge"])
        # the engine owns skip/resume logic (manifest), so the legacy "any file exists" skip is off
        args = Args(opts.format, True, opts.start_date, opts.end_date, None, bool(opts.rc_discharge))
        station = {
            "code": row["ID"], "name": row["Title"],
            "basin": row.get("_basin") or str(row["Location"]).split(",")[0].strip(),
            "lat": row.get("lat"), "lon": row.get("lon"), "rl_zero": row.get("_rl_zero"),
        }
        try:
            outdir = os.path.join(opts.output_dir, "cwc", _slug(station["basin"]))
            os.makedirs(outdir, exist_ok=True)
            res = download_station_detail(station, outdir, args)
            rec.status = res["status"]
            rec.path, rec.records = res["path"], res["rows"]
            rec.start, rec.end = _iso(res["start"]), _iso(res["end"])
            rec.error = res["error"]
            if opts.rc_discharge:
                rec.method_note = "discharge, where present, is estimated from stage via rating curves (not observed)"
        except Exception as e:
            rec.status, rec.error = "error", str(e)
        return rec


# ---------------------------------------------------------------------------
# CWC RSMS (reservoir storage) adapter: a latest-day snapshot, not a history
# ---------------------------------------------------------------------------

class RsmsAdapter:
    name = "CWC-RSMS"
    endpoint = "https://rsms.india-water.gov.in"

    def search(self, query, location):
        st = SourceStatus(self.name, endpoint=self.endpoint)
        if not query or not any(w in query.lower() for w in _RSMS_WORDS):
            st.note = "only listed for reservoir/storage queries"
            return [], st
        if location:
            st.note = "RSMS snapshot covers all reservoirs; location filter not applied to this entry"
        row = {
            "Source": self.name, "Title": "CWC RSMS daily reservoir storage snapshot",
            "Location": "All India", "Variable": "Reservoir storage and level",
            "Resolution": "Daily (latest snapshot only)", "ID": "rsms-daily",
            "lat": None, "lon": None, "Unit": None,
            "CoverageStart": None, "CoverageEnd": None, "CoverageKnown": False,
            "Provider": "CWC", "Endpoint": self.endpoint,
            "MatchedOn": "", "Inferred": "Unit,Coverage",
        }
        st.rows = 1
        return [row], st

    def fetch(self, row, opts: FetchOptions) -> FetchRecord:
        from .cwc_rsms import CwcRsmsClient
        rec = FetchRecord(self.name, str(row["ID"]), str(row["Title"]), endpoint=self.endpoint)
        try:
            out = Path(opts.output_dir) / "cwc_rsms"
            out.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d")
            path = out / f"CWC_RSMS_daily_snapshot_{stamp}.csv"
            df = CwcRsmsClient().fetch_daily_snapshot()
            if df is None or df.empty:
                rec.status, rec.records = "empty", 0
                return rec
            df.to_csv(path, index=False)
            rec.status, rec.path, rec.records = "saved", str(path), len(df)
            rec.start = rec.end = _iso(pd.to_datetime(df.get("entry_date"), errors="coerce").max())
            rec.method_note = "snapshot of the latest day only; requested start/end not applied"
        except Exception as e:
            rec.status, rec.error = "error", str(e)
        return rec


def _has_rc(get_rc_row, r) -> bool:
    try:
        return get_rc_row(str(r.get("code", "")), str(r.get("name", ""))) is not None
    except Exception:
        return False


ADAPTERS = {"NWDP": NwdpAdapter, "CWC": CwcAdapter, "CWC-RSMS": RsmsAdapter}


# ---------------------------------------------------------------------------
# Public engine functions
# ---------------------------------------------------------------------------

def search_catalog(query=None, location=None, sources=None, *, period=None,
                   ids=None, basin=None, state=None) -> pd.DataFrame:
    """Search all (or the named) sources; return a CATALOG_COLUMNS table with status in ``attrs``.

    ``location`` is a case-insensitive substring. For exact selection use
    ``ids`` (catalog IDs), ``basin`` or ``state`` (case-insensitive equality).
    ``basin``/``state`` need source metadata, so only CWC can honour them;
    NWDP is then skipped and the status says so rather than ignoring the filter.
    ``period`` drops rows whose *known* coverage does not overlap it; rows with
    unknown coverage are kept, flagged ``CoverageKnown=False`` and counted.
    """
    names = [s.upper() for s in (sources or ADAPTERS)]
    unknown = [n for n in names if n not in ADAPTERS]
    if unknown:
        raise ValueError(f"Unknown source(s) {unknown}; choose from {list(ADAPTERS)}.")
    lo, hi = parse_period(period)
    id_set = {str(i).strip().lower() for i in ([ids] if isinstance(ids, str) else (ids or []))}
    exact = {"basin": basin, "state": state}
    rows, statuses = [], []
    for n in names:
        if (basin or state) and n != "CWC":
            statuses.append(SourceStatus(n, note=f"skipped: exact basin/state filters need source metadata that {n} does not provide"))
            continue
        try:
            r, st = ADAPTERS[n]().search(query, location)
        except Exception as e:
            r, st = [], SourceStatus(n, ok=False, complete=False, error=str(e))
        if n == "CWC":
            for key, want in exact.items():
                if want:
                    wl = str(want).strip().lower()
                    col = "Location"
                    keep = []
                    for row in r:
                        parts = [x.strip() for x in str(row["Location"]).split(",")]
                        base, st_ = parts[0], (parts[1] if len(parts) > 1 else "")
                        val = base if key == "basin" else st_
                        if val.lower() == wl:
                            keep.append(row)
                    st.dropped[f"not_{key}={want}"] = len(r) - len(keep)
                    r = keep
        if id_set:
            before = len(r)
            r = [x for x in r if str(x["ID"]).lower() in id_set]
            if before - len(r):
                st.dropped["not_in_ids"] = before - len(r)
        if lo or hi:
            keep = [x for x in r if _overlaps(x.get("CoverageStart"), x.get("CoverageEnd"), lo, hi)]
            if len(r) - len(keep):
                st.dropped["outside_period"] = len(r) - len(keep)
            unk = sum(1 for x in keep if not x.get("CoverageKnown"))
            if unk:
                st.note = ((st.note + "; ") if st.note else "") + f"{unk} rows have unknown coverage and were kept"
            r = keep
        st.rows = len(r)
        rows.extend(r)
        statuses.append(st)
    hidden = ["_org_id", "_basin", "_rl_zero"]
    df = pd.DataFrame(rows)
    for c in CATALOG_COLUMNS + hidden:
        if c not in df.columns:
            df[c] = None
    df = df[CATALOG_COLUMNS + hidden].reset_index(drop=True)
    df.attrs["swift_type"] = "search_results"
    df.attrs["query"] = {"query": query, "location": location, "sources": names, "period": [lo, hi],
                         "ids": sorted(id_set) or None, "basin": basin, "state": state}
    df.attrs["source_status"] = [s.as_dict() for s in statuses]
    df.attrs["partial"] = any((not s.ok) or (not s.complete) for s in statuses)
    return df


def estimate_catalog(table: pd.DataFrame, *, network: bool = True) -> pd.DataFrame:
    """Add ``EstRecords`` / ``EstNote``. NWDP: exact server count (one cheap request each);
    anything else: unknown (None), never a guess."""
    out = table.copy()
    est, note = [], []
    client = NwdpAdapter()._client() if network and (out["Source"] == "NWDP").any() else None
    for _, r in out.iterrows():
        if r["Source"] == "NWDP" and client is not None:
            n = client.count_records(str(r["ID"]))
            est.append(n)
            note.append("server-reported total for the whole resource (date range is applied after download)"
                        if n is not None else "count unavailable")
        elif r["Source"] == "NWDP":
            est.append(None); note.append("not requested")
        else:
            est.append(None); note.append("unknown: source does not report counts")
    out["EstRecords"], out["EstNote"] = est, note
    out.attrs.update(table.attrs)
    return out


def _find_prior(output_dir, rec_key, lo, hi):
    """Return a saved item from an earlier manifest with the same ID and requested range whose file still exists."""
    for mf in sorted(Path(output_dir).glob("manifest*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            items = json.loads(mf.read_text()).get("items", [])
        except Exception:
            continue
        for it in items:
            if (it.get("source"), it.get("id")) == rec_key and (it.get("status") == "saved" or (it.get("status") == "skipped" and it.get("reused"))) \
               and it.get("req_start") == lo and it.get("req_end") == hi \
               and it.get("complete") is not False and it.get("path") and Path(it["path"]).exists():
                return it
    return None


def fetch_catalog(table: pd.DataFrame, *, output_dir="output", period=None, start_date=None, end_date=None,
                  format="csv", overwrite=False, quiet=True, manifest=True, rc_discharge=True,
                  resume=True, progress=None, cancel=None) -> pd.DataFrame:
    """Download every row of a catalog table; return one FetchRecord row per item.

    Never prints. Pass ``progress(event_dict)`` to follow the run and a
    ``threading.Event`` as ``cancel`` to stop it between pages/items.
    """
    if period is not None:
        start_date, end_date = parse_period(period)
    opts = FetchOptions(str(output_dir), start_date, end_date, format, overwrite, quiet,
                        rc_discharge, resume, progress, cancel)
    os.makedirs(opts.output_dir, exist_ok=True)
    records = []
    n = len(table)
    for i, (_, row) in enumerate(table.iterrows(), 1):
        src = row["Source"]
        base = FetchRecord(str(src), str(row.get("ID")), str(row.get("Title")),
                           req_start=start_date, req_end=end_date)
        if cancel is not None and cancel.is_set():
            base.status, base.error = "cancelled", "cancelled before start"
            records.append(base)
            continue
        if src not in ADAPTERS:
            base.status, base.error = "error", f"no adapter for source {src!r}"
            records.append(base)
            continue
        _emit(opts, "item_start", base, index=i, total=n)
        prior = None if (overwrite or not resume) else _find_prior(opts.output_dir, (str(src), str(row.get("ID"))), start_date, end_date)
        if prior:
            base.status, base.path, base.records, base.reused = "skipped", prior["path"], prior.get("records"), True
            base.start, base.end = prior.get("start"), prior.get("end")
            base.error = "already downloaded for this exact request (see earlier manifest); use overwrite=True to redo"
            rec = base
        else:
            rec = ADAPTERS[src]().fetch(row, opts)
            rec.req_start, rec.req_end = start_date, end_date
        _emit(opts, "item_done", rec, index=i, total=n, status=rec.status, records=rec.records)
        records.append(rec)
    out = pd.DataFrame([asdict(r) for r in records])
    out.attrs["swift_type"] = "fetch_results"
    if manifest:
        out.attrs["manifest"] = write_manifest(opts, table, records)
    return out


def write_manifest(opts: FetchOptions, table: pd.DataFrame, records) -> str:
    verify = {}
    for r in records:
        if r.source == "NWDP":
            verify["NWDP"] = "TLS certificate verification DISABLED (verify=False)"
    prov = table.attrs.get("query")
    doc = {
        "hydroswift": _version(),
        "created": _now(),
        "query": prov if prov is not None else "search provenance unavailable (table was filtered or built by hand)",
        "source_status": table.attrs.get("source_status") or "search provenance unavailable",
        "search_partial": table.attrs.get("partial"),
        "options": {"output_dir": opts.output_dir, "start_date": opts.start_date, "end_date": opts.end_date,
                    "format": opts.format, "overwrite": opts.overwrite, "rc_discharge": opts.rc_discharge,
                    "resume": opts.resume},
        "security_notes": verify,
        "items": [asdict(r) for r in records],
    }
    path = Path(opts.output_dir) / "manifest.json"
    if path.exists():
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        path = Path(opts.output_dir) / f"manifest_{stamp}.json"
    path.write_text(json.dumps(doc, indent=2, default=str))
    return str(path)


def _version() -> str:
    try:
        from . import __version__  # type: ignore
        return __version__
    except Exception:
        return "unknown"


def save_catalog(table: pd.DataFrame, path) -> str:
    """Write a catalog and its provenance (query, per-source status) to JSON."""
    doc = {"hydroswift": _version(), "saved": _now(), "attrs": table.attrs,
           "rows": json.loads(table.to_json(orient="records", date_format="iso"))}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(doc, indent=2, default=str))
    return str(path)


def load_catalog(path) -> pd.DataFrame:
    """Read a catalog written by ``save_catalog``; provenance is restored in ``attrs``."""
    doc = json.loads(Path(path).read_text())
    df = pd.DataFrame(doc["rows"])
    for c in CATALOG_COLUMNS + ["_org_id", "_basin", "_rl_zero"]:
        if c not in df.columns:
            df[c] = None
    df.attrs.update(doc.get("attrs") or {})
    return df
