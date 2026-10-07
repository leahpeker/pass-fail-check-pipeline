from pathlib import Path

import pandas as pd

from pipeline.checks import BREAK_COLUMNS
from pipeline.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_end_to_end_on_real_data(tmp_path: Path, capsys):
    out = tmp_path / "breaks.csv"
    code = main(["--config", str(ROOT / "config.yaml"), "--data", str(ROOT / "data"), "--out", str(out)])
    assert code == 0
    df = pd.read_csv(out)
    assert list(df.columns) == BREAK_COLUMNS
    assert len(df) > 0
    assert set(df["check"]) == {"day_over_day", "week_over_week"}
    assert set(df["ticker"]) == {"DJCA", "DJIA", "DJTA", "DJUA", "SP500"}
    assert df.loc[df["ticker"] == "SP500", "threshold_pct"].isin([1.5, 5.0]).all()
    assert (df["pct_change"].abs() > df["threshold_pct"]).all()
    assert "breaks" in capsys.readouterr().out


def test_config_error_exits_1(tmp_path: Path, capsys):
    bad = tmp_path / "c.yaml"
    bad.write_text("checks:\n  day_over_day:\n    threshold_pct: -1\n")
    code = main(["--config", str(bad), "--data", str(ROOT / "data"), "--out", str(tmp_path / "o.csv")])
    assert code == 1
    assert "error:" in capsys.readouterr().err


def test_unknown_override_ticker_exits_1(tmp_path: Path, capsys):
    bad = tmp_path / "c.yaml"
    bad.write_text("checks:\n  day_over_day:\n    threshold_pct: 1\n    overrides:\n      NASDAQ: 2\n")
    code = main(["--config", str(bad), "--data", str(ROOT / "data"), "--out", str(tmp_path / "o.csv")])
    assert code == 1
    assert "NASDAQ" in capsys.readouterr().err


def test_missing_data_dir_exits_1(tmp_path: Path, capsys):
    code = main(["--config", str(ROOT / "config.yaml"), "--data", str(tmp_path / "nope"), "--out", str(tmp_path / "o.csv")])
    assert code == 1
    assert "not a directory" in capsys.readouterr().err


def test_unwritable_out_path_exits_1(tmp_path: Path, capsys):
    code = main(["--config", str(ROOT / "config.yaml"), "--data", str(ROOT / "data"), "--out", str(tmp_path)])
    assert code == 1
    assert "error: could not write" in capsys.readouterr().err
