from pathlib import Path

import pandas as pd
import pytest

from pipeline.ingest import IngestError, load_closes


def write(dir_: Path, name: str, body: str) -> None:
    (dir_ / name).write_text(body)


def test_ticker_from_header_and_blank_rows_dropped(tmp_path: Path):
    write(tmp_path, "SP500.csv", "observation_date,SP500\n2024-01-02,100.5\n2024-01-03,\n2024-01-04,101\n")
    df = load_closes(tmp_path)
    assert list(df.columns) == ["date", "ticker", "close"]
    assert df["ticker"].tolist() == ["SP500", "SP500"]
    assert df["close"].tolist() == [100.5, 101.0]
    assert df["date"].tolist() == [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-04")]


def test_multiple_files_combine_sorted(tmp_path: Path):
    write(tmp_path, "b.csv", "observation_date,ZZZ\n2024-01-03,3\n2024-01-02,2\n")
    write(tmp_path, "a.csv", "observation_date,AAA\n2024-01-02,1\n")
    df = load_closes(tmp_path)
    assert df["ticker"].tolist() == ["AAA", "ZZZ", "ZZZ"]
    assert df["close"].tolist() == [1.0, 2.0, 3.0]


def test_non_numeric_close(tmp_path: Path):
    write(tmp_path, "X.csv", "observation_date,X\n2024-01-02,abc\n")
    with pytest.raises(IngestError, match=r"X\.csv: non-numeric close 'abc' on 2024-01-02"):
        load_closes(tmp_path)


def test_bad_columns(tmp_path: Path):
    write(tmp_path, "X.csv", "date,X\n2024-01-02,1\n")
    with pytest.raises(IngestError, match=r"X\.csv: expected columns"):
        load_closes(tmp_path)


def test_bad_date(tmp_path: Path):
    write(tmp_path, "X.csv", "observation_date,X\nnot-a-date,1\n")
    with pytest.raises(IngestError, match=r"X\.csv: could not parse dates"):
        load_closes(tmp_path)


def test_duplicate_dates(tmp_path: Path):
    write(tmp_path, "X.csv", "observation_date,X\n2024-01-02,1\n2024-01-02,2\n")
    with pytest.raises(IngestError, match=r"X\.csv: duplicate dates"):
        load_closes(tmp_path)


def test_missing_or_empty_dir(tmp_path: Path):
    with pytest.raises(IngestError, match="no csv files"):
        load_closes(tmp_path)
    with pytest.raises(IngestError, match="not a directory"):
        load_closes(tmp_path / "nope")
