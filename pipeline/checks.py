from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CheckConfig, Config

# Drafted with Claude Code (Anthropic); reviewed, edited, and tested by hand.

BREAK_COLUMNS = [
    "check",
    "ticker",
    "date",
    "comparison_date",
    "comparison_value",
    "value",
    "difference",
    "pct_change",
    "direction",
    "threshold_pct",
]


def run_checks(closes: pd.DataFrame, config: Config) -> pd.DataFrame:
    frames = [CHECKS[check.name](closes, check) for check in config.enabled_checks()]
    if not frames:
        return empty_breaks()
    return (
        pd.concat(frames, ignore_index=True)
        .sort_values(["date", "ticker", "check"])
        .reset_index(drop=True)
    )


def day_over_day(closes: pd.DataFrame, check: CheckConfig) -> pd.DataFrame:
    df = closes.sort_values(["ticker", "date"]).copy()
    by_ticker = df.groupby("ticker")
    df["comparison_date"] = by_ticker["date"].shift(1)
    df["comparison_value"] = by_ticker["close"].shift(1)
    return _flag_breaks(df, check)


def week_over_week(closes: pd.DataFrame, check: CheckConfig) -> pd.DataFrame:
    current = closes.sort_values("date").copy()
    current["target_date"] = current["date"] - pd.Timedelta(days=7)
    prior = closes.rename(columns={"date": "comparison_date", "close": "comparison_value"})
    prior = prior.sort_values("comparison_date")
    # Last close on or before exactly one week earlier, so a holiday-shortened
    # week still compares against the most recent trading day before it.
    merged = pd.merge_asof(
        current,
        prior,
        left_on="target_date",
        right_on="comparison_date",
        by="ticker",
        direction="backward",
    )
    return _flag_breaks(merged.drop(columns="target_date"), check)


def empty_breaks() -> pd.DataFrame:
    return pd.DataFrame(columns=BREAK_COLUMNS)


def _flag_breaks(df: pd.DataFrame, check: CheckConfig) -> pd.DataFrame:
    df = df.dropna(subset=["comparison_value"])
    df = df[df["comparison_value"] != 0].copy()
    df["threshold_pct"] = df["ticker"].map(check.threshold_for)
    df["difference"] = df["close"] - df["comparison_value"]
    df["pct_change"] = df["difference"] / df["comparison_value"] * 100
    breaks = df[df["pct_change"].abs() > df["threshold_pct"]].copy()
    breaks["check"] = check.name
    breaks["direction"] = np.where(breaks["pct_change"] > 0, "up", "down")
    breaks = breaks.rename(columns={"close": "value"})
    return breaks[BREAK_COLUMNS].reset_index(drop=True)


CHECKS = {"day_over_day": day_over_day, "week_over_week": week_over_week}
