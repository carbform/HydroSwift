"""Streamlit-free data selection behind the dashboard plots and export, so it can be tested."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd


def station_options(tidy: pd.DataFrame) -> Dict[str, pd.Series]:
    """Label -> row mask, one entry per (source, station), so sources are never mixed in a plot."""
    keys = tidy[["source", "station_id", "station_name"]].astype("string").fillna("")
    options = {}
    for src, sid, name in keys.drop_duplicates().sort_values(["station_name", "source", "station_id"]).values:
        label = f"{name or sid or 'unnamed station'} ({src}{' · ' + sid if sid else ''})"
        options[label] = (keys["source"] == src) & (keys["station_id"] == sid) & (keys["station_name"] == name)
    return options


def series(data: pd.DataFrame, *variables: str) -> pd.DataFrame:
    """Rows whose canonical variable is exactly one of *variables*, with values, in time order."""
    return data[data["variable"].isin(variables)].dropna(subset=["value"]).sort_values("time")


def is_estimated(data: pd.DataFrame) -> pd.Series:
    return data["method"].fillna("observed") != "observed"


def rating_pairs(data: pd.DataFrame) -> pd.DataFrame:
    """Simultaneous stage and *observed* discharge (columns value_stage, value_q).

    Discharge estimated from stage is left out: fitting it would be circular.
    """
    stage = series(data, "water_level")
    q = series(data, "discharge")
    q = q[~is_estimated(q)]
    return pd.merge(stage[["time", "value"]], q[["time", "value"]], on="time", suffixes=("_stage", "_q"))


def flood_thresholds(data: pd.DataFrame, lookup: Optional[dict] = None) -> Dict[str, float]:
    """CWC warning / danger levels for a single CWC station; {} when not published."""
    cwc = data[data["source"] == "CWC"]["station_id"].dropna().astype(str).str.strip().str.lower().unique()
    if len(cwc) != 1:
        return {}
    if lookup is None:
        from hydroswift.core.outputs import _get_cwc_threshold_lookup
        lookup = _get_cwc_threshold_lookup()
    meta = lookup.get(cwc[0], {})
    out = {}
    for key, label in (("warning_level", "Warning Level"), ("danger_level", "Danger Level")):
        value = pd.to_numeric(meta.get(key), errors="coerce")
        if pd.notna(value) and value > 0:
            out[label] = float(value)
    return out


def export_tidy(tidy: pd.DataFrame, output_dir, fmt: str) -> Path:
    """Write the combined tidy table in the format the user picked (parquet, gpkg or json)."""
    from hydroswift.core.outputs import merge
    path = Path(output_dir) / f"hydroswift_data_{datetime.now():%Y%m%dT%H%M%S}.{fmt}"
    merge(tidy, path)
    return path
