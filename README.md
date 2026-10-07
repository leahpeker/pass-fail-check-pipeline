# Pass/Fail Check Pipeline

A command-line pipeline that reads daily closes for five US market indexes,
flags day-over-day and week-over-week moves that exceed configurable
thresholds, and writes every break to a CSV.

## Quickstart

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pipeline
```

That reads `config.yaml` and `data/*.csv`, writes `results/breaks.csv`, and
prints a summary:

```
3663 breaks written to results/breaks.csv
  day_over_day (> 1.0%): 3081
    DJCA: 543  (threshold 1.0%)
    DJIA: 559  (threshold 1.0%)
    DJTA: 962  (threshold 1.0%)
    DJUA: 718  (threshold 1.0%)
    SP500: 299  (threshold 1.5%)
  week_over_week (> 5.0%): 582
    ...
```

Run the tests with `uv run pytest`.

Without uv, a plain virtualenv works too:

```bash
python3 -m venv .venv
.venv/bin/pip install . pytest
.venv/bin/pipeline
.venv/bin/python -m pytest
```

## Command line

```
uv run pipeline [--config PATH] [--data DIR] [--out PATH]
```

| flag | default | meaning |
|------|---------|---------|
| `--config` | `config.yaml` | check configuration |
| `--data` | `data/` | directory of FRED-format CSVs |
| `--out` | `results/breaks.csv` | where to write the breaks |

Exit code is 0 on success (even with zero breaks) and 1 on a configuration
or data error, with one line on stderr saying what was wrong.

## Configuration

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

- `enabled` switches a check on or off. Defaults to `true`.
- `threshold_pct` is the global threshold in percent. A move is a break when
  its absolute percent change is strictly greater than this.
- `overrides` maps a ticker to its own threshold. Every other ticker keeps the
  global value. In the example above, SP500 only flags daily moves over 1.5%
  while the other four indexes flag over 1%.
- A check that is not listed is not run.

Validation fails fast with a named key: unknown check names, missing or
non-positive thresholds, non-boolean `enabled`, and override tickers that do
not appear in the data all stop the run. A typo in an override should not
silently do nothing.

## Input data

One CSV per index in `data/`, in the format FRED exports:

```
observation_date,SP500
2016-01-11,1923.67
2016-01-18,
```

The ticker is taken from the header of the second column, so adding an index
means adding a file. Rows with an empty value (market holidays) are dropped.
Non-numeric values, unparseable dates, and duplicate dates are errors.

Included: `DJIA`, `DJTA`, `DJUA`, `DJCA`, `SP500`, daily from 2016-01-11 to
2026-01-09.

## Checks

**Day-over-day** compares each close to the previous trading day for the same
ticker. The first row per ticker has nothing to compare against and is
skipped.

**Week-over-week** compares each close to the last close on or before the date
exactly seven days earlier. A Tuesday compares to the previous Tuesday, or to
the Monday before it if that Tuesday was a holiday. This gives every trading
day a weekly comparison and keeps the window at exactly seven calendar days
whenever that day traded, falling back to the most recent earlier close when
it did not; `comparison_date` in the output shows which. Rows in the first
week are skipped.

Both directions count. `pct_change` is
`(value - comparison_value) / comparison_value * 100`.

## Output

`results/breaks.csv`, sorted by date, ticker, check. The committed file is the
output of running the default configuration against the included data.

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
| `threshold_pct` | the threshold that applied to this ticker |

For example, the first trading day after the March 2020 circuit breakers:

```
check,ticker,date,comparison_date,comparison_value,value,difference,pct_change,direction,threshold_pct
day_over_day,DJIA,2020-03-16,2020-03-13,23185.62,20188.52,-2997.1,-12.9265,down,1.0
week_over_week,DJIA,2020-03-16,2020-03-09,23851.02,20188.52,-3662.5,-15.3557,down,5.0
day_over_day,SP500,2020-03-16,2020-03-13,2711.02,2386.13,-324.89,-11.9841,down,1.5
```

`comparison_date` and `threshold_pct` are included so a downstream consumer
can audit any row without opening the config or the source data.

## Design

```
config.yaml ──► config.py ──► Config
                                  │
data/*.csv  ──► ingest.py ──► (date, ticker, close)
                                  │
                           checks.py ──► breaks
                                  │
                           report.py ──► csv + summary
                                  ▲
                            cli.py
```

Each module does one thing and hands the next a plain pandas DataFrame or a
frozen dataclass, so each is tested on its own with small hand-built inputs.
Both checks return the same schema, so the report layer does not care which
rule produced a row and adding a third check is one function plus one entry
in the `CHECKS` map.

`docs/design.md` has the full design, including error handling and the test
plan.

### Libraries

- **pandas**: `shift` within a ticker group and `merge_asof` make the two
  checks a few lines each, and it is the standard tool for this kind of
  tabular work.
- **PyYAML**: YAML allows comments, which matters for a config file people
  edit by hand.
- **pytest**: tests.
- **uv**: dependency management and the `uv run pipeline` entrypoint.

No orchestrator (Airflow, Prefect, Dagster). Five CSVs and two rules do not
need a scheduler, a DAG, or a server, and adding one would mean defending a
dependency the problem does not require.

## File-based vs. database configuration

This pipeline reads its configuration from a static YAML file. Both choices
have a place.

**A static file fits configuration that changes with the code.** The rule
definitions, default thresholds, and the shape of the config itself belong
next to the code that interprets them. A file is reviewed in a pull request,
versioned with the pipeline, diffable, and reproducible: checking out a commit
gives you exactly the config that ran. It needs no infrastructure to read, so
the pipeline runs anywhere the repo does.

**Database records fit configuration that changes at run time or per
tenant.** If an analyst tunes the SP500 threshold weekly, if each client
needs its own thresholds, or if an operator wants to switch a check off
without a deploy, that configuration should live in the pipeline's storage
with an audit trail of who changed what and when. Other systems can read it
too, and the pipeline can pick up changes without a release.

**Results and run history belong in the pipeline's storage regardless.** A
CSV is the right deliverable for this exercise, but a `breaks` table keyed by
run would let downstream systems query by date or ticker, let the pipeline
run incrementally, and let a run record which configuration it used.

Moving this pipeline to database configuration would mean a `check_config`
table with the same columns as the YAML (`check`, `enabled`,
`threshold_pct`) plus a `check_override` table (`check`, `ticker`,
`threshold_pct`), read by a second loader in `config.py` that returns the
same `Config` dataclass. Nothing downstream of `config.py` would change.

## AI assistance

Code, tests, and docs were drafted with Claude Code (Anthropic) using a
design-first flow: the design in `docs/design.md` was agreed before any code
was written, then each module was built test-first and committed separately.
Every module in `pipeline/` carries a one-line comment to that effect. All
code was reviewed, run, and edited by hand, and the commit history shows the
stages.

## Layout

```
config.yaml          default check configuration
data/                five FRED-format index csvs
docs/design.md       design document
pipeline/
  cli.py             argparse entrypoint, exit codes
  config.py          yaml -> Config, validation
  ingest.py          csvs -> one long frame
  checks.py          day_over_day, week_over_week
  report.py          csv writer, stdout summary
results/breaks.csv   output of the default run
tests/               one file per module plus an end-to-end run
```
