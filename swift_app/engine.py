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
    "lat", "lon", "Unit", "CoverageStart", "CoverageEnd",
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


def parse_period(text) -> tuple:
    """Pull a 'YYYY To YYYY' span out of a resource name -> (start, end) ISO dates or (None, None)."""
    m = _PERIOD_RE.search(str(text or ""))
    if not m:
        return None, None
    a, b = int(m.group(1)), int(m.group(2))
    if a > b or not (1800 <= a <= 2100 and 1800 <= b <= 2100):
        return None, None
    return f"{a}-01-01", f"{b}-12-31"


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
    fetched_at: str = field(default_factory=_now)


@dataclass
class FetchOptions:
    output_dir: str = "output"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    format: str = "csv"
    overwrite: bool = False
    quiet: bool = False


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
            cov_s, cov_e = parse_period(rname)
            rows.append({
                "Source": self.name,
                "Title": title,
                "Location": str(r.get("organization", "")),
                "Variable": var, "Resolution": res,
                "ID": str(r.get("resource_id", "")),
                "lat": None, "lon": None, "Unit": None,
                "CoverageStart": cov_s, "CoverageEnd": cov_e,
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
            records = client.fetch_records(rec.id)
            info = getattr(client, "last_fetch", None) or {}
            rec.complete = info.get("complete", True)
            if not info.get("ok", True) or not rec.complete:
                rec.error = info.get("error")
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
                "Variable": "Water Level / Discharge", "Resolution": "Hourly",
                "ID": str(r.get("code", "")),
                "lat": r.get("lat"), "lon": r.get("lon"), "Unit": "m / m3/s",
                "CoverageStart": None, "CoverageEnd": None,
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
        args = Args(opts.format, opts.overwrite, opts.start_date, opts.end_date, None, False)
        station = {
            "code": row["ID"], "name": row["Title"],
            "basin": row.get("_basin") or str(row["Location"]).split(",")[0].strip(),
            "lat": row.get("lat"), "lon": row.get("lon"), "rl_zero": row.get("_rl_zero"),
        }
        try:
            os.makedirs(opts.output_dir, exist_ok=True)
            res = download_station_detail(station, opts.output_dir, args)
            rec.status = res["status"]
            rec.path, rec.records = res["path"], res["rows"]
            rec.start, rec.end = _iso(res["start"]), _iso(res["end"])
            rec.error = res["error"]
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
            "CoverageStart": None, "CoverageEnd": None,
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
            rec.error = "snapshot of the latest day only; start/end date not applied"
        except Exception as e:
            rec.status, rec.error = "error", str(e)
        return rec


ADAPTERS = {"NWDP": NwdpAdapter, "CWC": CwcAdapter, "CWC-RSMS": RsmsAdapter}


# ---------------------------------------------------------------------------
# Public engine functions
# ---------------------------------------------------------------------------

def search_catalog(query=None, location=None, sources=None) -> pd.DataFrame:
    """Search all (or the named) sources; return a CATALOG_COLUMNS table with status in ``attrs``."""
    names = [s.upper() for s in (sources or ADAPTERS)]
    unknown = [n for n in names if n not in ADAPTERS]
    if unknown:
        raise ValueError(f"Unknown source(s) {unknown}; choose from {list(ADAPTERS)}.")
    rows, statuses = [], []
    for n in names:
        try:
            r, st = ADAPTERS[n]().search(query, location)
        except Exception as e:
            r, st = [], SourceStatus(n, ok=False, complete=False, error=str(e))
        rows.extend(r)
        statuses.append(st)
    hidden = ["_org_id", "_basin", "_rl_zero"]
    df = pd.DataFrame(rows)
    for c in CATALOG_COLUMNS + hidden:
        if c not in df.columns:
            df[c] = None
    # hidden helper columns travel with the table so fetch() needs no second lookup
    df = df[CATALOG_COLUMNS + hidden].reset_index(drop=True)
    df.attrs["swift_type"] = "search_results"
    df.attrs["query"] = {"query": query, "location": location, "sources": names}
    df.attrs["source_status"] = [s.as_dict() for s in statuses]
    df.attrs["partial"] = any((not s.ok) or (not s.complete) for s in statuses)
    return df


def fetch_catalog(table: pd.DataFrame, *, output_dir="output", start_date=None, end_date=None,
                  format="csv", overwrite=False, quiet=False, manifest=True) -> pd.DataFrame:
    """Download every row of a catalog table; return one FetchRecord row per item."""
    opts = FetchOptions(str(output_dir), start_date, end_date, format, overwrite, quiet)
    os.makedirs(opts.output_dir, exist_ok=True)
    records = []
    for _, row in table.iterrows():
        src = row["Source"]
        if src not in ADAPTERS:
            records.append(FetchRecord(str(src), str(row.get("ID")), str(row.get("Title")),
                                       status="error", error=f"no adapter for source {src!r}"))
            continue
        rec = ADAPTERS[src]().fetch(row, opts)
        if not quiet:
            n = "?" if rec.records is None else rec.records
            print(f"[{rec.source}] {rec.title}: {rec.status} ({n} records)"
                  + (f" - {rec.error}" if rec.error else ""))
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
    doc = {
        "hydroswift": _version(),
        "created": _now(),
        "query": table.attrs.get("query"),
        "source_status": table.attrs.get("source_status"),
        "search_partial": table.attrs.get("partial"),
        "options": {k: v for k, v in asdict(opts).items()},
        "security_notes": verify,
        "items": [asdict(r) for r in records],
    }
    path = Path(opts.output_dir) / "manifest.json"
    # never overwrite earlier manifests: keep a history
    if path.exists():
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        path = Path(opts.output_dir) / f"manifest_{stamp}.json"
    path.write_text(json.dumps(doc, indent=2, default=str))
    return str(path)


def _version() -> str:
    try:
        from . import __version__  # type: ignore
        return __version__
    except Exception:
        return "unknown"
