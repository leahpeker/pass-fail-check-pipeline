from __future__ import annotations

from pathlib import Path

import pandas as pd

# Drafted with Claude Code (Anthropic); reviewed, edited, and tested by hand.

DATE_COLUMN = "observation_date"


class IngestError(ValueError):
    pass


def load_closes(data_dir: Path) -> pd.DataFrame:
    if not data_dir.is_dir():
        raise IngestError(f"not a directory: {data_dir}")
    files = sorted(data_dir.glob("*.csv"))
    if not files:
        raise IngestError(f"no csv files found in {data_dir}")
    frames = [_load_one(path) for path in files]
    return (
        pd.concat(frames, ignore_index=True)
        .sort_values(["ticker", "date"])
        .reset_index(drop=True)
    )


def _load_one(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    columns = [c.strip() for c in raw.columns]
    if len(columns) != 2 or columns[0] != DATE_COLUMN:
        raise IngestError(f"{path.name}: expected columns [{DATE_COLUMN}, <TICKER>], got {columns}")
    ticker = columns[1]
    raw.columns = ["date", "close"]

    # Validate dates on every row, before dropping blanks, so a date that
    # appears once empty and once with a value is still caught as a duplicate.
    date = pd.to_datetime(raw["date"], format="%Y-%m-%d", errors="coerce")
    if date.isna().any():
        example = raw.loc[date.isna(), "date"].iloc[0]
        raise IngestError(f"{path.name}: could not parse dates, e.g. {example!r}")
    if date.duplicated().any():
        example = date[date.duplicated()].iloc[0].date()
        raise IngestError(f"{path.name}: duplicate dates, e.g. {example}")

    # FRED writes market holidays as rows with an empty value.
    traded = raw["close"].str.strip() != ""
    raw, date = raw[traded], date[traded]

    close = pd.to_numeric(raw["close"], errors="coerce")
    if close.isna().any():
        bad = raw[close.isna()].iloc[0]
        raise IngestError(f"{path.name}: non-numeric close {bad['close']!r} on {bad['date']}")

    return pd.DataFrame({"date": date.values, "ticker": ticker, "close": close.astype(float).values})
