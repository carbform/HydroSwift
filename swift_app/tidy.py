"""Standard variable vocabulary and the tidy long-format loader.

``load(run)`` returns one long table for every source:

    time, value, variable, unit, station_id, station_name, source,
    lat, lon, method, flag, file

* ``variable`` is always one of ``VARIABLES`` (the same names the catalog
  offers), ``unit`` is normalised (mm, m, m3/s, degC, %, km/h, W/m2, hPa, BCM).
* ``method`` is "observed" unless the value is derived (e.g. rating-curve
  discharge). ``flag`` carries caveats such as "unit not stated".
* Groundwater levels are returned **as the provider reports them**; providers
  differ on depth-below-ground vs. elevation, so the flag says so.
* A file that does not fit the schema is *not guessed at*: it is reported in
  ``tidy.attrs['unmapped']`` with the reason.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pandas as pd

TIDY_COLUMNS = ["time", "value", "variable", "unit", "station_id", "station_name",
                "source", "lat", "lon", "method", "flag", "file"]

# canonical name -> (default unit, human label)
VARIABLES = {
    "rainfall": ("mm", "Rainfall"),
    "water_level": ("m", "River / surface water level"),
    "discharge": ("m3/s", "River discharge"),
    "groundwater_level": ("m", "Groundwater level"),
    "reservoir_level": ("m", "Reservoir water level"),
    "reservoir_storage": ("BCM", "Reservoir live storage"),
    "temperature": ("degC", "Air temperature"),
    "humidity": ("%", "Relative humidity"),
    "wind_speed": ("km/h", "Wind speed"),
    "solar_radiation": ("W/m2", "Solar radiation"),
    "atm_pressure": ("hPa", "Atmospheric pressure"),
    "evaporation": ("mm", "Pan evaporation"),
}

# Ordered: first hit wins. Matched against "<title> | <value column name>".
_VAR_PATTERNS = [
    ("groundwater_level", r"ground\s*water"),
    ("reservoir_level", r"reservoir"),
    ("discharge", r"discharge"),
    ("water_level", r"water\s*level|stage|gauge"),
    ("rainfall", r"rain"),
    ("evaporation", r"evaporation"),
    ("humidity", r"humidity"),
    ("wind_speed", r"wind"),
    ("solar_radiation", r"solar|radiation|rediation"),
    ("atm_pressure", r"pressure"),
    ("temperature", r"temp"),
]

_UNIT_MAP = {
    "mm": "mm", "meter": "m", "metre": "m", "m": "m", "cdeg": "degC", "aoc": "degC",
    "degc": "degC", "c": "degC", "%": "%", "km/hr": "km/h", "km/h": "km/h",
    "watt/m2": "W/m2", "w/m2": "W/m2", "mb": "hPa", "hpa": "hPa",
    "m3/sec": "m3/s", "m3/s": "m3/s", "cumec": "m3/s", "bcm": "BCM",
}

_TIME_NAMES = ("data acquisition time", "monitoring date", "date", "datetime", "time")
_STATION_ID = ("station code", "station_code", "location code", "station")
_STATION_NAME = ("station name", "location name", "locationname", "station", "name of station")
_NOT_VALUE = re.compile(r"normal|departure|departue|category|cumulative|weekly|monthly|code|"
                        r"lgd|slno|_id|latitude|longitude|rl_|meansea|available|area|velocity", re.I)


def _lower_map(cols):
    return {str(c).strip().lower(): c for c in cols}


def _find(cols_lower: dict, names) -> Optional[str]:
    for n in names:
        if n in cols_lower:
            return cols_lower[n]
    return None


def normalise_unit(raw: Optional[str]) -> tuple:
    """Return (unit, known). Unknown units are kept verbatim and flagged."""
    if raw is None:
        return None, False
    key = str(raw).strip().lower().replace(" ", "")
    if key in _UNIT_MAP:
        return _UNIT_MAP[key], True
    return str(raw).strip(), False


def infer_variable(*texts) -> Optional[str]:
    blob = " | ".join(str(t) for t in texts if t).lower()
    for name, pat in _VAR_PATTERNS:
        if re.search(pat, blob):
            return name
    return None


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=TIDY_COLUMNS)


def _parse_time(series: pd.Series) -> pd.Series:
    from .nwdp import parse_nwdp_dates
    ts = parse_nwdp_dates(series)
    bad = ts.isna()
    if bad.any():  # e.g. '05-03-2016 14:00:00' with a clock part
        s = series.astype(str).str.strip()
        ts[bad] = pd.to_datetime(s[bad], errors="coerce", format="%d-%m-%Y %H:%M:%S")
    bad = ts.isna()
    if bad.any():
        ts[bad] = pd.to_datetime(series[bad], errors="coerce", dayfirst=False)
    return ts


def tidy_nwdp(df: pd.DataFrame, title: str, file: str):
    """Map one NWDP resource to tidy rows, or return (None, reason)."""
    cl = _lower_map(df.columns)
    tcol = _find(cl, _TIME_NAMES)
    if tcol is None:
        return None, "no recognisable time column"
    cands = []
    tv = infer_variable(title)
    for c in df.columns:
        if c == tcol or _NOT_VALUE.search(str(c)):
            continue
        if pd.api.types.is_numeric_dtype(df[c]) or pd.to_numeric(df[c].head(50), errors="coerce").notna().any():
            if infer_variable(str(c)) or tv:
                cands.append(c)
    named = [c for c in cands if infer_variable(str(c))]
    cands = named or cands
    with_unit = [c for c in cands if re.search(r"\(([^)]+)\)", str(c))]
    cands = with_unit or cands
    if not cands:
        return None, "no value column recognised"
    if len(cands) > 1 and not all(infer_variable(str(c)) for c in cands):
        return None, f"cannot pick value columns (candidates: {[str(c) for c in cands]})"
    cands_vars = {}
    for c in cands:
        cv = infer_variable(str(c))
        # the dataset title is more specific about *where* (reservoir, groundwater)
        var = tv if tv in ("reservoir_level", "groundwater_level") and cv in (None, "water_level", "groundwater_level") else (cv or tv)
        if var is None:
            return None, "variable not recognised from title or column name"
        if var in cands_vars.values() and len(cands) > 1:
            return None, f"two columns map to {var}: {[str(c) for c in cands]}"
        cands_vars[c] = var
    sid = _find(cl, _STATION_ID)
    sname = _find(cl, _STATION_NAME)
    lat = _find(cl, ("latitude",))
    lon = _find(cl, ("longitude",))
    time = _parse_time(df[tcol])
    frames = []
    for vcol, var in cands_vars.items():
        m = re.search(r"\(([^)]+)\)", str(vcol))
        unit, known = normalise_unit(m.group(1) if m else None)
        flag = []
        if not m:
            unit = VARIABLES[var][0]
            flag.append("unit not stated by provider; default assumed")
        elif not known:
            flag.append(f"unit '{unit}' not recognised; kept as reported")
        if var == "groundwater_level":
            flag.append("as reported by provider (depth vs elevation convention varies)")
        frames.append(pd.DataFrame({
            "time": time,
            "value": pd.to_numeric(df[vcol], errors="coerce"),
            "variable": var,
            "unit": unit,
            "station_id": df[sid].astype(str) if sid else None,
            "station_name": df[sname].astype(str) if sname else None,
            "source": "NWDP",
            "lat": pd.to_numeric(df[lat], errors="coerce") if lat else None,
            "lon": pd.to_numeric(df[lon], errors="coerce") if lon else None,
            "method": "observed",
            "flag": "; ".join(flag) or None,
            "file": file,
        }))
    out = pd.concat(frames, ignore_index=True).dropna(subset=["time"])
    return out[TIDY_COLUMNS], None


def tidy_cwc(df: pd.DataFrame, file: str, name=None):
    """CWC FFS files: wse (m) and discharge (m3/s)."""
    if "time" not in df.columns:
        return None, "no time column"
    t = pd.to_datetime(df["time"], errors="coerce")
    parts = []
    base = {"station_id": df.get("station_code"), "station_name": name, "source": "CWC",
            "lat": df.get("lat"), "lon": df.get("lon"), "file": file}
    if "wse" in df.columns:
        parts.append(pd.DataFrame({**base, "time": t, "value": pd.to_numeric(df["wse"], errors="coerce"),
                                   "variable": "water_level", "unit": "m", "method": "observed", "flag": None}))
    if "discharge" in df.columns:
        src = df.get("discharge_source")
        derived = src.notna() if src is not None else pd.Series(False, index=df.index)
        meth = pd.Series("observed", index=df.index).where(~derived, src.astype(str) if src is not None else "observed")
        parts.append(pd.DataFrame({**base, "time": t, "value": pd.to_numeric(df["discharge"], errors="coerce"),
                                   "variable": "discharge", "unit": "m3/s", "method": meth,
                                   "flag": pd.Series(None, index=df.index).where(~derived, "estimated from stage via rating curve")}))
    if not parts:
        return None, "no water level or discharge columns"
    out = pd.concat(parts, ignore_index=True).dropna(subset=["time", "value"])
    return out[TIDY_COLUMNS], None


def tidy_rsms(df: pd.DataFrame, file: str):
    if "storage_bcm" not in df.columns or "entry_date" not in df.columns:
        return None, "RSMS columns not as expected"
    out = pd.DataFrame({
        "time": pd.to_datetime(df["entry_date"], errors="coerce"),
        "value": pd.to_numeric(df["storage_bcm"], errors="coerce"),
        "variable": "reservoir_storage", "unit": "BCM",
        "station_id": df.get("reservoir_unique_id"), "station_name": df.get("reservoir_name"),
        "source": "CWC-RSMS", "lat": pd.to_numeric(df.get("latitude"), errors="coerce"),
        "lon": pd.to_numeric(df.get("longitude"), errors="coerce"),
        "method": "observed", "flag": None, "file": file,
    })
    return out.dropna(subset=["time"])[TIDY_COLUMNS], None


def _read_with_header(path: Path) -> pd.DataFrame:
    ext = path.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(path, comment="#", low_memory=False)
    if ext == ".xlsx":
        return pd.read_excel(path, sheet_name="timeseries")
    if ext == ".json":
        return pd.read_json(path, orient="records", convert_dates=False)
    raise ValueError(f"{ext} not supported by load(); use csv, xlsx or json")


def load(run) -> pd.DataFrame:
    """Load fetched data as one tidy table.

    *run* is the DataFrame returned by ``fetch`` (uses its ``path``/``source``/
    ``title`` columns), a path to a ``manifest*.json``, or an output directory
    (all items of its newest manifest).
    """
    import json

    if isinstance(run, (str, Path)):
        p = Path(run)
        if p.is_dir():
            ms = sorted(p.glob("manifest*.json"), key=lambda x: x.stat().st_mtime)
            if not ms:
                raise FileNotFoundError(f"No manifest*.json in {p}; nothing to load.")
            p = ms[-1]
        items = pd.DataFrame(json.loads(p.read_text())["items"])
    else:
        items = run
    frames, unmapped = [], []
    for _, it in items.iterrows():
        path = it.get("path")
        if not path or str(it.get("status")) not in ("saved", "skipped") or pd.isna(path):
            continue
        path = Path(path)
        if not path.exists():
            unmapped.append({"file": str(path), "reason": "file missing"})
            continue
        try:
            raw = _read_with_header(path)
            src = it.get("source")
            if src == "NWDP":
                out, why = tidy_nwdp(raw, str(it.get("title", "")), str(path))
            elif src == "CWC":
                out, why = tidy_cwc(raw, str(path), str(it.get("title")) if it.get("title") else None)
            elif src == "CWC-RSMS":
                out, why = tidy_rsms(raw, str(path))
            else:
                out, why = None, f"unknown source {src!r}"
        except Exception as e:
            out, why = None, str(e)
        if out is None:
            unmapped.append({"file": str(path), "reason": why})
        else:
            frames.append(out)
    res = pd.concat(frames, ignore_index=True) if frames else _empty()
    res.attrs["unmapped"] = unmapped
    res.attrs["swift_type"] = "tidy"
    return res
