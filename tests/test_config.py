from pathlib import Path

import pytest

from pipeline.config import ConfigError, load_config, parse_config

VALID = {
    "checks": {
        "day_over_day": {"enabled": True, "threshold_pct": 1.0, "overrides": {"SP500": 1.5}},
        "week_over_week": {"enabled": False, "threshold_pct": 5},
    }
}


def test_parse_valid_config():
    cfg = parse_config(VALID)
    dod = cfg.checks["day_over_day"]
    assert dod.enabled is True
    assert dod.threshold_pct == 1.0
    assert dod.threshold_for("SP500") == 1.5
    assert dod.threshold_for("DJIA") == 1.0
    assert cfg.checks["week_over_week"].overrides == {}
    assert [c.name for c in cfg.enabled_checks()] == ["day_over_day"]


def test_load_config_from_yaml(tmp_path: Path):
    p = tmp_path / "c.yaml"
    p.write_text("checks:\n  day_over_day:\n    threshold_pct: 2\n")
    cfg = load_config(p)
    assert cfg.checks["day_over_day"].enabled is True
    assert cfg.checks["day_over_day"].threshold_pct == 2.0


def test_missing_file(tmp_path: Path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_malformed_yaml(tmp_path: Path):
    p = tmp_path / "c.yaml"
    p.write_text("checks: [unclosed")
    with pytest.raises(ConfigError, match="could not parse"):
        load_config(p)


@pytest.mark.parametrize(
    "raw, message",
    [
        ({}, "top-level 'checks'"),
        ({"checks": {"monthly": {"threshold_pct": 1}}}, "unknown check 'monthly'"),
        ({"checks": {"day_over_day": {"threshold_pct": 0}}}, "day_over_day.threshold_pct must be a positive number"),
        ({"checks": {"day_over_day": {"threshold_pct": "1.5"}}}, "day_over_day.threshold_pct must be a positive number"),
        ({"checks": {"day_over_day": {}}}, "day_over_day.threshold_pct must be a positive number"),
        ({"checks": {"day_over_day": {"threshold_pct": 1, "enabled": "yes"}}}, "day_over_day.enabled must be true or false"),
        ({"checks": {"day_over_day": {"threshold_pct": 1, "overrides": {"SP500": -1}}}}, "day_over_day.overrides.SP500 must be a positive number"),
        ({"checks": {"day_over_day": {"threshold_pct": 1, "overrides": ["SP500"]}}}, "day_over_day.overrides must be a mapping"),
    ],
)
def test_validation_errors(raw, message):
    with pytest.raises(ConfigError, match=message):
        parse_config(raw)


def test_validate_tickers_rejects_unknown_override():
    cfg = parse_config(VALID)
    with pytest.raises(ConfigError, match=r"unknown tickers \['SP500'\].*DJIA"):
        cfg.validate_tickers({"DJIA"})
    cfg.validate_tickers({"DJIA", "SP500"})
