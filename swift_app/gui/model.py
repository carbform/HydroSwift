"""Qt-free logic behind the GUI workbench, so it can be tested without a display."""

from __future__ import annotations

from typing import Iterable, List, Optional

import pandas as pd

# Columns shown in the Review table, in order: (catalog column, header)
REVIEW_COLUMNS = [
    ("Source", "Source"), ("Title", "Title / station"), ("Location", "Location"),
    ("Variable", "Variable"), ("Resolution", "Resolution"), ("Coverage", "Coverage"),
    ("Provider", "Provider"), ("MatchedOn", "Matched on"), ("Inferred", "Not stated by source"),
    ("EstRecords", "Est. records"), ("ID", "ID"),
]


def coverage_text(row) -> str:
    if not bool(row.get("CoverageKnown")):
        return "unknown"
    s, e = row.get("CoverageStart"), row.get("CoverageEnd")
    return f"{str(s)[:10]} to {str(e)[:10]}"


def review_value(df: pd.DataFrame, i, col: str) -> str:
    """Display text for one cell; missing values are blank, never the word 'None'."""
    if col == "Coverage":
        return coverage_text(df.loc[i])
    if col not in df.columns:
        return ""
    v = df.at[i, col]
    if v is None or (not isinstance(v, (list, tuple)) and pd.isna(v)):
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return ", ".join(map(str, v)) if isinstance(v, (list, tuple)) else str(v)


def source_status_lines(df: Optional[pd.DataFrame]) -> List[dict]:
    """One dict per source: text, level ('ok' | 'partial' | 'failed'), detail (tooltip)."""
    if df is None:
        return []
    out = []
    statuses = df.attrs.get("source_status")
    if not statuses:
        return [{"source": "?", "level": "partial", "text": "search provenance unavailable",
                 "detail": "This table has lost its search status (it was built or filtered by hand)."}]
    for st in statuses:
        level = "failed" if not st["ok"] else ("partial" if not st["complete"] else "ok")
        text = {"failed": f"{st['source']}: FAILED", "partial": f"{st['source']}: PARTIAL ({st['rows']})",
                "ok": f"{st['source']}: {st['rows']} found"}[level]
        bits = []
        if st.get("error"):
            bits.append(f"Error: {st['error']}")
        if st.get("note"):
            bits.append(st["note"])
        for reason, n in (st.get("dropped") or {}).items():
            bits.append(f"{n} dropped: {reason}")
        if st.get("endpoint"):
            bits.append(f"Endpoint: {st['endpoint']}")
        out.append({"source": st["source"], "level": level, "text": text, "detail": "\n".join(bits)})
    return out


def text_filter(df: pd.DataFrame, text: str) -> pd.Series:
    """Boolean mask: every whitespace-separated word must appear in Variable/Title/Location (case-insensitive)."""
    if df is None or df.empty:
        return pd.Series([], dtype=bool)
    words = [w for w in (text or "").lower().split() if w]
    blob = (df["Variable"].fillna("") + " " + df["Title"].fillna("") + " " + df["Location"].fillna("")).str.lower()
    mask = pd.Series(True, index=df.index)
    for w in words:
        mask &= blob.str.contains(w, regex=False)
    return mask


def add_to_basket(basket: Optional[pd.DataFrame], results: pd.DataFrame, idx: Iterable) -> pd.DataFrame:
    """Add rows (by index of *results*) to the basket, skipping duplicates. Provenance attrs are kept."""
    new = results.loc[list(idx)]
    if basket is None or basket.empty:
        merged = new.copy()
    else:
        merged = pd.concat([basket, new])
        merged = merged[~merged.duplicated(subset=["Source", "ID"], keep="first")]
    merged = merged.reset_index(drop=True)
    merged.attrs.update(results.attrs)
    return merged


def remove_from_basket(basket: pd.DataFrame, positions: Iterable[int]) -> pd.DataFrame:
    keep = basket.drop(basket.index[list(positions)]).reset_index(drop=True)
    keep.attrs.update(basket.attrs)
    return keep


def parse_period_inputs(start: str, end: str):
    """Blank means open-ended. Returns None or (start, end) for the engine."""
    s, e = (start or "").strip(), (end or "").strip()
    if not s and not e:
        return None
    return (s or None, e or None)


def summarise_fetch(run: pd.DataFrame) -> str:
    counts = run["status"].value_counts().to_dict() if len(run) else {}
    order = ["saved", "skipped", "empty", "cancelled", "error"]
    parts = [f"{counts[k]} {k}" for k in order if k in counts]
    rows = int(pd.to_numeric(run.get("records"), errors="coerce").fillna(0).sum()) if len(run) else 0
    return f"{len(run)} items: " + ", ".join(parts) + f"; {rows:,} records"


def progress_text(event: dict) -> str:
    kind = event.get("event")
    if kind == "item_start":
        return f"[{event.get('index')}/{event.get('total')}] {event.get('title') or event.get('id')}"
    if kind == "page":
        tot = event.get("total")
        return f"  {event.get('title') or event.get('id')}: {event.get('read')} of {tot if tot else '?'} records"
    if kind == "item_done":
        return f"[{event.get('index')}/{event.get('total')}] {event.get('status')}: {event.get('title') or event.get('id')}"
    return str(event)
