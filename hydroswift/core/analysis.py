"""Station statistics, quality screening and aggregation on the tidy table from ``load()``.

Used by the dashboard, ``hyswift stats`` and the Python API, so all three agree.
Nothing here changes values: screening only says which rows to look at.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from .tidy import GAUGE_ZERO_FLAG

SERIES_KEYS = ["source", "station_id", "station_name", "variable", "unit", "method"]
SUMMED_VARIABLES = {"rainfall", "evaporation"}  # totals; everything else is averaged
FREQUENCIES = {"daily": "D", "monthly": "MS", "annual": "YS"}


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["time"] = pd.to_datetime(out["time"], errors="coerce")
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    return out.dropna(subset=["time", "value"]).sort_values("time", kind="stable")


def screen(df: pd.DataFrame, *, gauge_zero: bool = True, spike_limit: Optional[float] = None) -> pd.Series:
    """Boolean mask (aligned with *df*) of rows that look unreliable.

    gauge_zero : rows ``load()`` flagged as equal to the station's gauge zero.
    spike_limit : rows further than this (in the variable's unit) from the median of
        the five readings around them, per series. A threshold you choose, not a fact.
    """
    mask = pd.Series(False, index=df.index)
    if gauge_zero:
        mask |= df["flag"].astype("string").str.contains(GAUGE_ZERO_FLAG, regex=False).fillna(False).astype(bool)
    if spike_limit and spike_limit > 0:
        for _, group in df.groupby(SERIES_KEYS, dropna=False):
            values = pd.to_numeric(group.sort_values("time", kind="stable")["value"], errors="coerce")
            median = values.rolling(5, center=True, min_periods=3).median()
            mask.loc[values.index[(values - median).abs() > spike_limit]] = True
    return mask


def summary(df: pd.DataFrame) -> pd.DataFrame:
    """One row per series: record period, completeness by day, longest gap and statistics."""
    rows = []
    for keys, group in _clean(df).groupby(SERIES_KEYS, dropna=False):
        values, times = group["value"], group["time"]
        days = pd.DatetimeIndex(times.dt.normalize().unique()).sort_values()
        span = (days[-1] - days[0]).days + 1
        gaps = pd.Series(days).diff().dt.days.dropna() - 1
        rows.append({
            **dict(zip(SERIES_KEYS, keys)),
            "readings": len(group), "start": times.iloc[0], "end": times.iloc[-1],
            "days_with_data": len(days), "completeness_pct_of_record": round(100 * len(days) / span, 1),
            "longest_gap_days": int(gaps.max()) if len(gaps) else 0,
            "min": values.min(), "p10": values.quantile(0.10), "median": values.median(),
            "mean": values.mean(), "p90": values.quantile(0.90), "max": values.max(),
            "total": values.sum() if keys[3] in SUMMED_VARIABLES else None,
            "gauge_zero_readings": int(screen(group).sum()),
        })
    return pd.DataFrame(rows)


def yearly_completeness(df: pd.DataFrame, years=None) -> pd.DataFrame:
    """Share of each calendar year's days that have at least one reading, per variable.

    years : (first, last) that were asked for; years among them without data show as 0 %.
    """
    data = _clean(df)
    rows = []
    for variable, series in data.groupby("variable"):
        counts = series.groupby(series["time"].dt.year)["time"].agg(lambda t: t.dt.normalize().nunique())
        wanted = set(counts.index)
        if years:
            wanted |= set(range(int(years[0]), int(years[1]) + 1))
        for year in sorted(wanted):
            days = int(counts.get(year, 0))
            total = 366 if pd.Timestamp(year=int(year), month=1, day=1).is_leap_year else 365
            rows.append({"variable": variable, "year": int(year), "days_with_data": days,
                         "completeness_pct": round(100 * days / total, 1)})
    return pd.DataFrame(rows)


def resample(df: pd.DataFrame, freq: str = "daily") -> pd.DataFrame:
    """Aggregate each series to daily, monthly or annual values.

    Rainfall and evaporation are summed; levels and discharge are averaged (never
    summed). ``readings`` and ``days_with_data`` show how much each value rests on.
    Periods without data are left out, not filled.
    """
    if freq not in FREQUENCIES:
        raise ValueError(f"freq must be one of {list(FREQUENCIES)}, not {freq!r}")
    frames = []
    for keys, group in _clean(df).groupby(SERIES_KEYS, dropna=False):
        how = "sum" if keys[3] in SUMMED_VARIABLES else "mean"
        indexed = group.set_index("time")["value"]
        buckets = indexed.resample(FREQUENCIES[freq])
        out = pd.DataFrame({"value": buckets.agg(how), "readings": buckets.count(),
                            "days_with_data": indexed.resample("D").count().gt(0)
                            .resample(FREQUENCIES[freq]).sum()})
        out = out[out["readings"] > 0].reset_index()
        for key, value in zip(SERIES_KEYS, keys):
            out[key] = value
        out["aggregation"] = how
        frames.append(out)
    columns = ["time", "value", "readings", "days_with_data", "aggregation", *SERIES_KEYS]
    return pd.concat(frames, ignore_index=True)[columns] if frames else pd.DataFrame(columns=columns)


def duration_curve(df: pd.DataFrame) -> pd.DataFrame:
    """Exceedance probability of *daily* values for one series.

    Daily first, so periods with many readings per day do not weigh more.
    """
    daily = resample(df, "daily")["value"].sort_values(ascending=False).reset_index(drop=True)
    return pd.DataFrame({"exceedance_pct": 100 * (daily.index + 1) / (len(daily) + 1), "value": daily})


def threshold_events(df: pd.DataFrame, level: float, *, max_gap: str = "48h") -> pd.DataFrame:
    """Periods of one series above *level*, timed from the readings' timestamps.

    An event ends at the first reading back at or below the level. A silence longer
    than *max_gap* also ends it, at the last reading seen above.
    """
    data = _clean(df)
    gap = pd.Timedelta(max_gap)
    events, current, previous = [], None, None
    for time, value in zip(data["time"], data["value"]):
        if current is not None and time - previous > gap:
            events.append((*current, previous))
            current = None
        if value > level:
            if current is None:
                current = [time, value, time]
            elif value > current[1]:
                current[1], current[2] = value, time
        elif current is not None:
            events.append((*current, time))
            current = None
        previous = time
    if current is not None:
        events.append((*current, previous))
    return pd.DataFrame(
        [{"start": s, "end": e, "hours": round((e - s).total_seconds() / 3600, 1), "peak": peak,
          "peak_time": when} for s, peak, when, e in events],
        columns=["start", "end", "hours", "peak", "peak_time"])


def monthly_pattern(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly value per year with its departure from that calendar month's average.

    The departure is only meaningful with several years of data (``years`` column).
    """
    monthly = resample(df, "monthly")
    monthly["year"], monthly["month"] = monthly["time"].dt.year, monthly["time"].dt.month
    by_month = monthly.groupby(["variable", "month"])["value"]
    monthly["normal"] = by_month.transform("mean")
    monthly["years"] = by_month.transform("size")
    monthly["departure"] = monthly["value"] - monthly["normal"]
    return monthly[["variable", "year", "month", "value", "normal", "departure", "years", "days_with_data"]]
