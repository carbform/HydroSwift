import pandas as pd
import pytest

from hydroswift.core import analysis
from hydroswift.core.tidy import GAUGE_ZERO_FLAG, TIDY_COLUMNS, tidy_cwc


def _tidy(values, times=None, variable="water_level", flag=None, sid="S1"):
    times = times or pd.date_range("2024-01-01", periods=len(values), freq="D")
    return pd.DataFrame({"time": times, "value": values, "variable": variable, "unit": "m", "station_id": sid,
                         "station_name": "A", "source": "CWC", "lat": 1.0, "lon": 2.0, "method": "observed",
                         "flag": flag, "file": "f"})[TIDY_COLUMNS]


def test_cwc_gauge_zero_readings_are_flagged_not_changed():
    raw = pd.DataFrame({"time": ["2024-01-01", "2024-01-02"], "wse": [433.0, 434.5], "water_depth": [0.0, 1.5],
                        "station_code": "S1"})
    out, why = tidy_cwc(raw, "f.csv", "A")
    assert why is None and out["value"].tolist() == [433.0, 434.5]
    assert out["flag"].astype("string").str.contains(GAUGE_ZERO_FLAG).fillna(False).tolist() == [True, False]
    assert analysis.screen(out).tolist() == [True, False]


def test_spike_screen_catches_isolated_jump_only():
    df = _tidy([435.0, 435.1, 1382.0, 435.2, 435.1, 435.3])
    assert analysis.screen(df, spike_limit=5).tolist() == [False, False, True, False, False, False]
    assert not analysis.screen(df).any()


def test_summary_reports_completeness_and_gaps():
    times = list(pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-10"]))
    row = analysis.summary(_tidy([1.0, 2.0, 3.0], times)).iloc[0]
    assert (row["readings"], row["days_with_data"], row["longest_gap_days"]) == (3, 3, 7)
    assert row["completeness_pct_of_record"] == 30.0
    assert pd.isna(row["total"])  # a level is never summed


def test_resample_sums_rain_and_averages_levels():
    times = list(pd.to_datetime(["2024-01-01 01:00", "2024-01-01 13:00", "2024-03-01 00:00"]))
    rain = analysis.resample(_tidy([2.0, 4.0, 1.0], times, "rainfall"), "monthly")
    level = analysis.resample(_tidy([2.0, 4.0, 1.0], times), "monthly")
    assert rain["value"].tolist() == [6.0, 1.0]  # February has no data and is left out
    assert level["value"].tolist() == [3.0, 1.0]
    assert rain["readings"].tolist() == [2, 1] and rain["days_with_data"].tolist() == [1, 1]
    with pytest.raises(ValueError):
        analysis.resample(_tidy([1.0]), "weekly")


def test_duration_curve_uses_daily_values():
    times = list(pd.to_datetime(["2024-01-01 00:00", "2024-01-01 06:00", "2024-01-01 12:00", "2024-01-02 00:00"]))
    curve = analysis.duration_curve(_tidy([10, 10, 10, 4], times, "discharge"))
    assert curve["value"].tolist() == [10, 4]


def test_threshold_events_are_timed_from_timestamps():
    times = list(pd.to_datetime(["2024-01-01 00:00", "2024-01-01 02:00", "2024-01-01 03:00", "2024-01-01 09:00",
                                 "2024-02-01 00:00", "2024-02-01 04:00"]))
    events = analysis.threshold_events(_tidy([1, 6, 8, 2, 7, 7], times), 5)
    assert events["hours"].tolist() == [7.0, 4.0]
    assert events["peak"].tolist() == [8, 7]


def test_a_long_silence_ends_an_event():
    times = list(pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-20"]))
    events = analysis.threshold_events(_tidy([6, 6, 6], times), 5)
    assert len(events) == 2


def test_requested_years_without_data_show_as_zero():
    out = analysis.yearly_completeness(_tidy([1.0, 2.0]), years=(2022, 2024))
    assert out["year"].tolist() == [2022, 2023, 2024]
    assert out["completeness_pct"].tolist() == [0.0, 0.0, 0.5]


def test_cli_explains_a_manifest_without_files(tmp_path, capsys):
    from hydroswift.cli import _which_manifest
    (tmp_path / "manifest.json").write_text('{"items": [{"status": "cancelled", "path": null}]}')
    _which_manifest(tmp_path)
    assert "saved no files" in capsys.readouterr().out
