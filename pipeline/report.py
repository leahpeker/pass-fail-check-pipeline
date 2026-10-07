from __future__ import annotations

from pathlib import Path

import pandas as pd

from .checks import BREAK_COLUMNS
from .config import Config

# Drafted with Claude Code (Anthropic); reviewed, edited, and tested by hand.


def write_breaks(breaks: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    formatted = breaks[BREAK_COLUMNS].copy()
    for column in ("date", "comparison_date"):
        formatted[column] = pd.to_datetime(formatted[column]).dt.strftime("%Y-%m-%d")
    for column in ("difference", "pct_change"):
        formatted[column] = formatted[column].astype(float).round(4)
    formatted.to_csv(out_path, index=False)


def summarize(breaks: pd.DataFrame, config: Config, out_path: Path) -> str:
    plural = "" if len(breaks) == 1 else "s"
    lines = [f"{len(breaks)} break{plural} written to {out_path}"]
    for name, check in config.checks.items():
        if not check.enabled:
            lines.append(f"  {name}: disabled")
            continue
        subset = breaks[breaks["check"] == name]
        lines.append(f"  {name} (> {check.threshold_pct}%): {len(subset)}")
        for ticker, count in subset.groupby("ticker").size().sort_index().items():
            lines.append(f"    {ticker}: {count}  (threshold {check.threshold_for(ticker)}%)")
    return "\n".join(lines)
