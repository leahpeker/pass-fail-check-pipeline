from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .checks import run_checks
from .config import ConfigError, load_config
from .ingest import IngestError, load_closes
from .report import summarize, write_breaks

# Drafted with Claude Code (Anthropic); reviewed, edited, and tested by hand.


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline",
        description="Flag day-over-day and week-over-week index moves that exceed configured thresholds.",
    )
    parser.add_argument("--config", type=Path, default=Path("config.yaml"), help="yaml check configuration")
    parser.add_argument("--data", type=Path, default=Path("data"), help="directory of FRED-format csv files")
    parser.add_argument("--out", type=Path, default=Path("results/breaks.csv"), help="where to write the breaks csv")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        closes = load_closes(args.data)
        config.validate_tickers(set(closes["ticker"]))
        breaks = run_checks(closes, config)
    except (ConfigError, IngestError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    try:
        write_breaks(breaks, args.out)
    except OSError as exc:
        print(f"error: could not write {args.out}: {exc.strerror or exc}", file=sys.stderr)
        return 1
    print(summarize(breaks, config, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
