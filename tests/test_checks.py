import pandas as pd
import pytest

from pipeline.checks import BREAK_COLUMNS, day_over_day, run_checks, week_over_week
from pipeline.config import CheckConfig, Config


def closes(rows):
    """rows: list of (date, ticker, close)."""
    df = pd.DataFrame(rows, columns=["date", "ticker", "close"])
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["ticker", "date"]).reset_index(drop=True)


DOD = CheckConfig(name="day_over_day", enabled=True, threshold_pct=1.0, overrides={})
WOW = CheckConfig(name="week_over_week", enabled=True, threshold_pct=5.0, overrides={})


def test_day_over_day_flags_both_directions_and_skips_first_row():
    df = closes([("2024-01-02", "X", 100), ("2024-01-03", "X", 101.5), ("2024-01-04", "X", 100.0)])
    out = day_over_day(df, DOD)
    assert list(out.columns) == BREAK_COLUMNS
    assert out["direction"].tolist() == ["up", "down"]
    assert out["date"].tolist() == [pd.Timestamp("2024-01-03"), pd.Timestamp("2024-01-04")]
    assert out["comparison_date"].tolist() == [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")]
    assert out["comparison_value"].tolist() == [100.0, 101.5]
    assert out["value"].tolist() == [101.5, 100.0]
    assert out["difference"].tolist() == pytest.approx([1.5, -1.5])
    assert out["pct_change"].tolist() == pytest.approx([1.5, -1.5 / 101.5 * 100])
    assert out["threshold_pct"].tolist() == [1.0, 1.0]
    assert out["check"].tolist() == ["day_over_day", "day_over_day"]


def test_exactly_at_threshold_is_not_a_break():
    df = closes([("2024-01-02", "X", 100), ("2024-01-03", "X", 101)])
    assert day_over_day(df, DOD).empty


def test_override_applies_to_one_ticker_only():
    check = CheckConfig(name="day_over_day", enabled=True, threshold_pct=1.0, overrides={"SP500": 1.5})
    df = closes([
        ("2024-01-02", "SP500", 100), ("2024-01-03", "SP500", 101.2),
        ("2024-01-02", "DJIA", 100), ("2024-01-03", "DJIA", 101.2),
    ])
    out = day_over_day(df, check)
    assert out["ticker"].tolist() == ["DJIA"]
    assert out["threshold_pct"].tolist() == [1.0]


def test_day_over_day_does_not_compare_across_tickers():
    df = closes([("2024-01-02", "A", 100), ("2024-01-03", "B", 200)])
    assert day_over_day(df, DOD).empty


def test_week_over_week_uses_close_on_or_before_seven_days_prior():
    df = closes([
        ("2024-01-02", "X", 100),
        ("2024-01-09", "X", 106),  # +6% vs 01-02 -> break
        ("2024-01-12", "X", 104),  # target 01-05 -> falls back to 01-02 (100): +4% -> no break
        # 2024-01-16 missing (holiday)
        ("2024-01-23", "X", 98),   # target 01-16 -> falls back to 01-12 (104): -5.77% -> break
    ])
    out = week_over_week(df, WOW)
    assert out["date"].tolist() == [pd.Timestamp("2024-01-09"), pd.Timestamp("2024-01-23")]
    assert out["comparison_date"].tolist() == [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-12")]
    assert out["direction"].tolist() == ["up", "down"]


def test_week_over_week_skips_rows_without_a_prior_week():
    df = closes([("2024-01-02", "X", 100), ("2024-01-05", "X", 150)])
    assert week_over_week(df, WOW).empty


def test_week_over_week_does_not_compare_across_tickers():
    df = closes([("2024-01-02", "A", 100), ("2024-01-09", "B", 200)])
    assert week_over_week(df, WOW).empty


def test_zero_comparison_value_is_dropped():
    df = closes([("2024-01-02", "X", 0.0), ("2024-01-03", "X", 5.0)])
    assert day_over_day(df, DOD).empty


def test_run_checks_respects_enabled_and_sorts():
    df = closes([("2024-01-02", "X", 100), ("2024-01-03", "X", 110), ("2024-01-10", "X", 120)])
    cfg = Config(checks={"day_over_day": DOD, "week_over_week": WOW})
    out = run_checks(df, cfg)
    assert out[["date", "check"]].values.tolist() == [
        [pd.Timestamp("2024-01-03"), "day_over_day"],
        [pd.Timestamp("2024-01-10"), "day_over_day"],
        [pd.Timestamp("2024-01-10"), "week_over_week"],
    ]
    disabled = Config(checks={"day_over_day": CheckConfig("day_over_day", False, 1.0, {})})
    empty = run_checks(df, disabled)
    assert empty.empty and list(empty.columns) == BREAK_COLUMNS
