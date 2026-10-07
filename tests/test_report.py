from pathlib import Path

import pandas as pd

from pipeline.checks import BREAK_COLUMNS, empty_breaks
from pipeline.config import CheckConfig, Config
from pipeline.report import summarize, write_breaks

CFG = Config(
    checks={
        "day_over_day": CheckConfig("day_over_day", True, 1.0, {}),
        "week_over_week": CheckConfig("week_over_week", False, 5.0, {}),
    }
)


def sample():
    return pd.DataFrame(
        [
            {
                "check": "day_over_day",
                "ticker": "X",
                "date": pd.Timestamp("2024-01-03"),
                "comparison_date": pd.Timestamp("2024-01-02"),
                "comparison_value": 100.0,
                "value": 101.23456,
                "difference": 1.23456,
                "pct_change": 1.23456,
                "direction": "up",
                "threshold_pct": 1.0,
            }
        ]
    )[BREAK_COLUMNS]


def test_write_breaks_formats_dates_and_rounds(tmp_path: Path):
    out = tmp_path / "nested" / "breaks.csv"
    write_breaks(sample(), out)
    text = out.read_text().splitlines()
    assert text[0] == ",".join(BREAK_COLUMNS)
    assert text[1] == "day_over_day,X,2024-01-03,2024-01-02,100.0,101.23456,1.2346,1.2346,up,1.0"


def test_write_empty_breaks_has_header(tmp_path: Path):
    out = tmp_path / "breaks.csv"
    write_breaks(empty_breaks(), out)
    assert out.read_text().strip() == ",".join(BREAK_COLUMNS)


def test_summarize_counts_and_disabled(tmp_path: Path):
    text = summarize(sample(), CFG, tmp_path / "b.csv")
    assert "1 break" in text
    assert "day_over_day" in text and "X" in text
    assert "week_over_week: disabled" in text
    assert str(tmp_path / "b.csv") in text


def test_summarize_no_breaks(tmp_path: Path):
    assert "0 breaks" in summarize(empty_breaks(), CFG, tmp_path / "b.csv")
