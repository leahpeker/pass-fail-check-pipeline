# Design: Pass/Fail Check Pipeline

A command-line pipeline that reads daily closes for US market indexes, flags
day-over-day and week-over-week moves that exceed configurable thresholds, and
writes the breaks to a CSV.

## Goals

- Run end to end with one command and produce a results CSV.
- Thresholds and on/off switches live in a static YAML file, with per-index
  overrides (e.g. SP500 daily at 1.5% while everything else stays at 1%).
- Every row in the output carries enough context for a downstream system to
  understand which rule fired, on what values, and why.
- Small enough to read, explain, and change live.

## Non-goals

- Database-backed configuration or results storage (discussed in the README).
- Incremental or scheduled runs, alerting, a UI.

## Inputs

Five CSVs in FRED export format, one per index: `DJIA`, `DJTA`, `DJUA`,
`DJCA`, `SP500`. Each has two columns, `observation_date` and a value column
named after the ticker. Rows cover 2016-01-11 to 2026-01-09. Market holidays
appear as rows with an empty value.

## Architecture

```
config.yaml ──► config.py ──► Config (dataclasses)
                                     │
data/*.csv  ──► ingest.py ──► long frame (date, ticker, close)
                                     │
                              checks.py ──► breaks frame
                                     │
                              report.py ──► results CSV + stdout summary
                                     ▲
                               cli.py (argparse, exit codes)
```

Each module has one job and a plain pandas DataFrame or dataclass as its
interface, so each can be tested in isolation.

### `config.py`

Loads YAML into frozen dataclasses and validates it.

```yaml
checks:
  day_over_day:
    enabled: true
    threshold_pct: 1.0
    overrides:
      SP500: 1.5
  week_over_week:
    enabled: true
    threshold_pct: 5.0
```

Validation fails fast with a clear message on: unknown check names,
missing or non-positive thresholds, non-boolean `enabled`, and override
tickers that do not match any ingested ticker. A silent no-op from a typo is
worse than a loud failure.

`threshold_for(ticker)` on a check returns the override if present, else the
global threshold.

### `ingest.py`

Reads every `*.csv` in the data directory. The ticker is taken from the value
column header, so adding an index means dropping a file in the directory.
Blank values (holidays) are dropped. Non-numeric values raise with the file and
row named. Output is one long frame sorted by ticker then date:

| date | ticker | close |
|------|--------|-------|

### `checks.py`

Both checks return the same schema so the report layer does not care which
rule produced a row.

**Day-over-day.** For each ticker, compare each close to the previous trading
row. The first row per ticker has no comparison and is skipped.

**Week-over-week.** For each row, look up the last close on or before
`date - 7 days` for the same ticker (`merge_asof`, direction `backward`).
This handles holiday-shortened weeks: a Tuesday compares to the prior
Tuesday, or to the Monday before it if that Tuesday was a holiday. Rows in the
first week have no comparison and are skipped.

A break is `abs(pct_change) > threshold_pct`. Both directions count.
`pct_change = (value - comparison_value) / comparison_value * 100`.

### `report.py`

Writes the breaks CSV and prints a per-check, per-ticker count table to
stdout.

Output columns, in order:

| column | meaning |
|--------|---------|
| `check` | `day_over_day` or `week_over_week` |
| `ticker` | index symbol |
| `date` | observation date that broke the threshold |
| `comparison_date` | the earlier date it was compared against |
| `comparison_value` | close on `comparison_date` |
| `value` | close on `date` |
| `difference` | `value - comparison_value` |
| `pct_change` | signed percent change, 4 decimals |
| `direction` | `up` or `down` |
| `threshold_pct` | the threshold that was applied to this ticker |

Rows are sorted by `date`, `ticker`, `check`. `comparison_date` and
`threshold_pct` are included so a consumer can audit a row without reading
the config or the source data.

### `cli.py`

```
uv run pipeline [--config config.yaml] [--data data/] [--out results/breaks.csv]
```

All flags have defaults. Config and data errors print one line to stderr and
exit 1. A successful run exits 0 even when there are zero breaks.

## Error handling

| condition | behaviour |
|-----------|-----------|
| config file missing or malformed YAML | exit 1, message names the file |
| unknown check name, bad threshold, bad `enabled` | exit 1, message names the key |
| override ticker not in data | exit 1, message lists valid tickers |
| CSV with unexpected columns | exit 1, message names the file |
| non-numeric close | exit 1, message names file and row |
| holiday / blank row | dropped silently |
| all checks disabled | exit 0, empty CSV with headers, summary says so |

## Testing

pytest, one file per module plus an end-to-end test.

- **config**: valid file round-trips; each validation error is raised with the
  expected message; `threshold_for` prefers the override.
- **ingest**: ticker comes from the header; blank rows dropped; non-numeric
  value raises; two files combine into one long frame.
- **checks**: hand-built series with known percentages. Exactly-at-threshold
  is not a break. Up and down both flagged. Weekly lookup skips a holiday.
  Override applies to one ticker only. Disabled check returns no rows.
- **end to end**: run the CLI against the real data directory into a temp
  file; assert exit 0, expected columns, non-empty.

## Libraries

- **pandas**: vectorised shift and `merge_asof` make both checks a few lines
  and are the standard tool for this kind of tabular work.
- **PyYAML**: YAML is friendlier than JSON for a hand-edited config with
  comments.
- **pytest**: tests.
- **uv**: dependency management and the `uv run pipeline` entrypoint.

## File vs. database configuration

Covered in the README. Short version: static files suit configuration that
changes with code (rule definitions, defaults) and should be reviewed and
versioned. Database records suit configuration that changes at run time or per
tenant (thresholds tuned by an analyst, enable flags toggled operationally) and
that other systems need to read. The pipeline's own storage is the right home
for results and run history regardless.

## AI assistance

Drafted with Claude Code and reviewed, edited, and tested by hand. Each module
notes this in a comment. Commits are made at each stage so the history shows
what was generated and what changed afterwards.
