from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Drafted with Claude Code (Anthropic); reviewed, edited, and tested by hand.

CHECK_NAMES = ("day_over_day", "week_over_week")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class CheckConfig:
    name: str
    enabled: bool
    threshold_pct: float
    overrides: dict[str, float] = field(default_factory=dict)

    def threshold_for(self, ticker: str) -> float:
        return self.overrides.get(ticker, self.threshold_pct)


@dataclass(frozen=True)
class Config:
    checks: dict[str, CheckConfig]

    def enabled_checks(self) -> list[CheckConfig]:
        return [c for c in self.checks.values() if c.enabled]

    def validate_tickers(self, tickers: set[str]) -> None:
        for check in self.checks.values():
            unknown = sorted(set(check.overrides) - tickers)
            if unknown:
                raise ConfigError(
                    f"{check.name}.overrides: unknown tickers {unknown}; "
                    f"valid tickers are {sorted(tickers)}"
                )


def load_config(path: Path) -> Config:
    try:
        raw = yaml.safe_load(path.read_text())
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}") from None
    except yaml.YAMLError as exc:
        raise ConfigError(f"could not parse {path}: {exc}") from None
    return parse_config(raw)


def parse_config(raw: object) -> Config:
    if not isinstance(raw, dict) or not isinstance(raw.get("checks"), dict):
        raise ConfigError("config must have a top-level 'checks' mapping")
    checks: dict[str, CheckConfig] = {}
    for name, body in raw["checks"].items():
        if name not in CHECK_NAMES:
            raise ConfigError(f"unknown check '{name}'; expected one of {list(CHECK_NAMES)}")
        checks[name] = _parse_check(name, body)
    return Config(checks=checks)


def _parse_check(name: str, body: object) -> CheckConfig:
    if not isinstance(body, dict):
        raise ConfigError(f"{name}: expected a mapping")
    enabled = body.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ConfigError(f"{name}.enabled must be true or false, got {enabled!r}")
    threshold = _positive_number(f"{name}.threshold_pct", body.get("threshold_pct"))
    overrides_raw = body.get("overrides") or {}
    if not isinstance(overrides_raw, dict):
        raise ConfigError(f"{name}.overrides must be a mapping of ticker to threshold")
    overrides = {
        str(ticker): _positive_number(f"{name}.overrides.{ticker}", value)
        for ticker, value in overrides_raw.items()
    }
    return CheckConfig(name=name, enabled=enabled, threshold_pct=threshold, overrides=overrides)


def _positive_number(label: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ConfigError(f"{label} must be a positive number, got {value!r}")
    return float(value)
