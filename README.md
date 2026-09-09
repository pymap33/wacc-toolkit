# WACC Toolkit

A WACC calculator that fixes the shortcuts most free WACC calculators take,
runnable both as a plain Python library and as a static browser page (via
[Pyodide](https://pyodide.org/)) with no server and no data leaving the page.

## What this does differently

Most WACC calculators (free web tools, most spreadsheet templates):

- use a **trailing regression beta**, which is noisy for thinly-traded,
  recently-listed, or volatile names
- use the **embedded** cost of debt (`interest expense / total debt`)
  instead of the **marginal** cost of new borrowing
- use the **current** capital structure with no way to express a target
  structure
- drop lease liabilities, preferred stock, and minority interest from the
  capital base
- use **effective** tax rate instead of **marginal**
- output a single point estimate with no sense of how sensitive it is to
  the two noisiest inputs (beta, equity risk premium)

This tool instead:

- relevers a **bottom-up (industry) unlevered beta** to the company's own
  D/E and marginal tax rate (Hamada equation)
- derives a **marginal, synthetic-rating-based** cost of debt from interest
  coverage ratio when no directly observed cost (YTM on traded bonds) is
  available
- takes market-value equity, debt (including capitalized operating
  leases), and preferred stock as explicit separate inputs
- returns a **sensitivity grid** across beta and ERP perturbations instead
  of only a point estimate

It does **not** model bankruptcy/distress costs, so — as the classic
Modigliani-Miller-with-taxes result predicts — WACC can *decrease* as
leverage increases if the tax shield outweighs higher component costs. That
is expected model behavior, not a bug; see `tests/test_calculator.py`.

## Layout

```
wacc/                 Core library (pure Python, no dependencies)
  beta.py             Relever/unlever (Hamada)
  cost_of_debt.py      Synthetic rating -> spread lookup
  calculator.py        WaccInputs / compute_wacc / wacc_sensitivity
  segment.py            Segment-level (sum-of-parts) WACC -- SegmentOverride /
                        compute_segment_wacc / weighted_average_wacc
data/
  synthetic_ratings.json   Interest-coverage-ratio -> rating -> spread table
  industry_betas.json      Sample industry unlevered betas (placeholder — see below)
scripts/
  update_data.py       Refreshes data/*.json from public sources (Damodaran, Treasury).
                        Not wired into CI yet; run manually and commit the diff.
                        `pip install -r scripts/requirements.txt` first.
web/
  index.html            Static Pyodide page — loads the wacc/ package into
                         the browser's virtual filesystem and runs it client-side
tests/
  test_calculator.py    Pure-Python unit tests, no network required
```

## Running the library

```python
from wacc import WaccInputs, compute_wacc, wacc_sensitivity

inputs = WaccInputs(
    risk_free_rate=0.04,
    equity_risk_premium=0.05,
    unlevered_beta=1.10,          # industry bottom-up beta
    tax_rate_marginal=0.25,
    market_value_equity=800.0,
    market_value_debt=200.0,       # include capitalized operating leases
    interest_coverage_ratio=6.0,   # or pass cost_of_debt_pretax directly
)
result = compute_wacc(inputs)
print(result.wacc)

grid = wacc_sensitivity(inputs)   # list of {beta_delta, erp_delta, wacc, ...}
```

## Segment-level (sum-of-parts) WACC

A single company-level WACC prices every segment at the same business risk.
That's wrong for a conglomerate with genuinely different-risk segments — use
`compute_segment_wacc` to get one WACC per segment instead, reusing the same
core calculator with a per-segment beta:

```python
from wacc import WaccInputs, SegmentOverride, compute_segment_wacc, weighted_average_wacc

consolidated = WaccInputs(
    risk_free_rate=0.04,
    equity_risk_premium=0.05,
    unlevered_beta=1.0,          # only used if a segment doesn't override it
    tax_rate_marginal=0.25,
    market_value_equity=800.0,
    market_value_debt=200.0,
    interest_coverage_ratio=6.0,
)

segments = [
    SegmentOverride(name="Regulated Grid", unlevered_beta=0.5, capital_weight=0.7),
    SegmentOverride(name="Merchant Renewables", unlevered_beta=1.4, capital_weight=0.3),
]

results = compute_segment_wacc(consolidated, segments)
for r in results:
    print(r.name, r.result.wacc)

sum_of_parts_wacc = weighted_average_wacc(results)  # capital-weighted average, for comparison against compute_wacc(consolidated).wacc
```

Only `unlevered_beta` needs to differ per segment in the typical case —
capital-structure weights and cost of debt default to the consolidated
company (debt is almost never actually allocated to a segment on the balance
sheet), but every field on `SegmentOverride` can be overridden individually
for the rare case where a segment has its own disclosed structure (e.g. a
ring-fenced project-finance subsidiary).

## Running the tests

```
python tests/test_calculator.py
python tests/test_segment.py
```

## Running the browser page

`web/index.html` fetches the `wacc/*.py` source files and `data/*.json` by
relative path, so it must be served (not opened via `file://`):

```
python -m http.server 8000
# then open http://localhost:8000/web/
```

## Data freshness

`data/industry_betas.json` and `data/risk_free_rate.json` are refreshed by
running `scripts/update_data.py` — **validated against a live network pull
2026-09-06** (see Known limitations). `data/synthetic_ratings.json` is a
static approximation of Damodaran's published interest-coverage-ratio bucket
structure and should be refreshed periodically the same way, though no script
does that yet.

## Known limitations / next steps

- No distress-cost term, so WACC-vs-leverage is not bounded below in
  extreme scenarios (see note above).
- `scripts/update_data.py` was validated end-to-end against live sources
  2026-09-06. Two bugs were found and fixed in that pass: the Treasury CSV
  is sorted **newest-first**, so the risk-free-rate reader must take row 0,
  not row -1 (it silently pulled an 8-month-stale rate before the fix); and
  the Treasury URL needs `home.treasury.gov` (not `www.`) plus a browser
  `User-Agent` header, or the connection is reset. The year in that URL is
  now derived from the current date rather than hardcoded. Damodaran's
  workbook layout still shifts occasionally between updates — re-check the
  parsed output after any run that logs an unexpected column set before
  trusting it unattended (e.g., in a scheduled CI job).
- Not yet wired into a scheduled job — still a manual run + commit.
- No multi-currency / cross-border WACC handling for multinationals.
- Sensitivity grid is beta × ERP only; leverage and cost-of-debt sensitivity
  are natural next axes.
- Segment-level WACC (`wacc/segment.py`) is Python-library only — not yet
  wired into `web/index.html`'s browser UI, and it does not fetch segment
  betas for you; you still have to pick a comparable pure-play beta per
  segment (same manual step `industry_betas.json` automates at the
  whole-company level, not yet extended to segments).
