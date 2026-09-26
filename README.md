# WACC Toolkit

A small toolkit of WACC calculation methods that fix the shortcuts most free
WACC calculators take. Four calculators — the full set this toolkit was
scoped for — each solving a different problem; pick the one that matches
your situation, not just the first one you find. Runnable both as a plain
Python library and as a static browser page (via
[Pyodide](https://pyodide.org/)) with no server and no data leaving the page.

## Which calculator do I need?

| | Calculator 1: Bottom-Up Beta / Synthetic-Rating WACC | Calculator 2: Segment-Level (Sum-of-Parts) WACC | Calculator 3: Regression-Beta / Liquid Large-Cap WACC | Calculator 4: Private-Company Build-Up Method WACC |
|---|---|---|---|---|
| **Use when** | Valuing a whole company as a single unit; thinly-traded, recently-listed, or volatile names where a regression beta is noisy | The company has genuinely different-risk segments (a regulated utility arm vs. a merchant/growth arm) and one blended number would misprice at least one of them | A liquid large-cap with a stable capital structure and a long trading history, where a regression beta is reliable and traded-debt YTM is directly observable | A private company with no market price at all (litigation, ESOP, small-business sale) — no beta to estimate |
| **Function** | `compute_wacc(WaccInputs(...))` | `compute_segment_wacc(consolidated, [SegmentOverride(...), ...])` + `weighted_average_wacc(...)` | `compute_regression_wacc(RegressionWaccInputs(...))` | `compute_build_up_wacc(BuildUpWaccInputs(...))` |
| **Module** | `wacc/calculator.py` (+ `beta.py`, `cost_of_debt.py`) | `wacc/segment.py` (wraps calculator 1 — same core math, run once per segment) | `wacc/regression_beta.py` (independent — does not relever the beta, does not use `beta.py` or `cost_of_debt.py`) | `wacc/build_up.py` (independent — no beta at all; reuses only `cost_of_debt.py`'s synthetic rating) |
| **Output** | One WACC + a beta×ERP sensitivity grid | One WACC per segment + a capital-weighted sum-of-parts aggregate, for comparison against calculator 1's naive company-level number | One WACC + a regression-beta×ERP sensitivity grid | One WACC + a size-premium×company-specific-premium sensitivity grid |
| **Browser page** | `calculator-bottom-up-beta.html` | `calculator-segment-level.html` (typical case only — see Known limitations) | `calculator-regression-beta.html` | `calculator-build-up.html` |
| **Full docs** | § "Calculator 1" below | § "Calculator 2" below | § "Calculator 3" below | § "Calculator 4" below |

Not sure which applies? Read `finance/methods/wacc-methodology-reference.md`
(if you have access to the KB this toolkit was built for) — it has the full
decision matrix this table is a summary of. Calculators 1 and 2 share the
same underlying cost-of-equity/cost-of-debt method (calculator 2 only
changes *how many times* and *with what inputs* it runs); calculators 3 and
4 each use a genuinely different method (calculator 3: regression beta used
directly, no relevering, directly observed traded-debt YTM; calculator 4: a
build-up stack instead of CAPM, no beta at all, book/negotiated-value
weights instead of market value) — see their own sections for why.

## Layout

```
wacc/                 Core library (pure Python, no dependencies)
  beta.py             Relever/unlever (Hamada) -- shared by calculators 1 and 2
  cost_of_debt.py      Synthetic rating -> spread lookup -- shared by calculators 1, 2, and 4
  calculator.py        Calculator 1 (whole-company) -- WaccInputs / compute_wacc / wacc_sensitivity
  segment.py            Calculator 2 (segment-level) -- SegmentOverride /
                        compute_segment_wacc / weighted_average_wacc
  regression_beta.py    Calculator 3 (regression-beta) -- RegressionWaccInputs /
                        compute_regression_wacc / regression_wacc_sensitivity
                        (independent of beta.py / cost_of_debt.py -- see its own section)
  build_up.py            Calculator 4 (private-company build-up) -- BuildUpWaccInputs /
                        compute_build_up_wacc / build_up_wacc_sensitivity
                        (no beta at all; reuses only cost_of_debt.py -- see its own section)
data/
  synthetic_ratings.json   Interest-coverage-ratio -> rating -> spread table
  industry_betas.json      Sample industry unlevered betas (placeholder — see below)
scripts/
  update_data.py       Refreshes data/*.json from public sources (Damodaran, Treasury).
                        Not wired into CI yet; run manually and commit the diff.
                        `pip install -r scripts/requirements.txt` first.
web/
  index.html            Hub page — links to each calculator's own page,
                         mirrors the "Which calculator do I need?" table above
  calculator-bottom-up-beta.html
                        Calculator 1's static Pyodide page
  calculator-segment-level.html
                        Calculator 2's static Pyodide page (typical case only --
                        per-segment beta/weight; see Known limitations)
  calculator-regression-beta.html
                        Calculator 3's static Pyodide page
  calculator-build-up.html
                        Calculator 4's static Pyodide page
  shared/wacc-loader.js  Pyodide/manifest loading logic shared by every
                         calculator page (factored out 2026-09-27)
tests/
  test_calculator.py    Calculator 1 unit tests, no network required
  test_segment.py       Calculator 2 unit tests, no network required
  test_regression_beta.py  Calculator 3 unit tests, no network required
  test_build_up.py      Calculator 4 unit tests, no network required
  test_manifest.py      Guards web/'s generated file list against drift (§ below)
```

## Calculator 1: Bottom-Up Beta / Synthetic-Rating WACC (whole-company)

### What this does differently

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

### Running calculator 1

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

## Calculator 2: Segment-Level (Sum-of-Parts) WACC

A single company-level WACC (calculator 1) prices every segment at the same
business risk. That's wrong for a conglomerate with genuinely different-risk
segments — use `compute_segment_wacc` to get one WACC per segment instead,
reusing calculator 1's own math with a per-segment beta:

### Running calculator 2

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

## Calculator 3: Regression-Beta / Liquid Large-Cap WACC

### What this does differently

Calculators 1 and 2 exist because regression betas are *unreliable* for
thinly-traded, recently-listed, or volatile names — bottom-up industry beta
was built to fix that. A liquid large-cap with a long trading history is the
opposite case: its own trailing regression beta (typically 3-5yr monthly
returns vs. a broad index) *is* reliable, and using it is simpler and more
current than borrowing an industry proxy.

This isn't just "calculator 1 with a different beta source" — two real
mechanical differences follow from that:

- **No relevering.** A regression beta is already levered to the company's
  own current capital structure (it comes directly from the stock's own
  return series). Running it through `beta.py`'s Hamada relever step —
  built for an *unlevered* industry beta — would double-count leverage.
  `compute_regression_wacc` uses the regression beta directly in CAPM.
- **No synthetic-rating fallback.** Cost of debt requires a directly
  observed traded-debt YTM (`cost_of_debt_pretax` has no default and no
  interest-coverage-ratio alternative) — liquid large-caps generally have
  traded bonds, so the synthetic-rating proxy calculator 1 needs when no
  observed cost exists doesn't apply here.

### Running calculator 3

```python
from wacc import RegressionWaccInputs, compute_regression_wacc, regression_wacc_sensitivity

inputs = RegressionWaccInputs(
    risk_free_rate=0.04,
    equity_risk_premium=0.05,
    regression_beta=1.10,        # levered -- observed directly, not relevered
    tax_rate_marginal=0.25,
    market_value_equity=800.0,
    market_value_debt=200.0,
    cost_of_debt_pretax=0.05,    # traded-debt YTM -- required, no fallback
)

result = compute_regression_wacc(inputs)
print(result.wacc)

grid = regression_wacc_sensitivity(inputs)  # regression-beta x ERP grid, same shape as calculator 1's
```

`market_value_preferred`, `preferred_dividend_yield`, and `size_premium` are
all optional (default 0), same as calculator 1 — a size premium is usually
not applicable for a liquid large-cap, but the field is kept for consistency
across calculators.

## Calculator 4: Private-Company Build-Up Method WACC

### What this does differently

There is no beta here at all — not a bottom-up industry beta (calculator 1),
not a regression beta (calculator 3). A private company with no market
price has no return series to derive one from. The build-up method replaces
CAPM's single `beta x ERP` term with a stack of separately-justified premia:

```
cost of equity = risk-free rate
               + equity risk premium
               + industry risk premium (optional)
               + size premium
               + company-specific risk premium
```

Each premium is independently sourced (size premium typically from a
published size-premium study; company-specific risk from a qualitative
assessment of key-person dependence, customer concentration, etc.) rather
than one beta standing in for all of them. This is also the only calculator
in this toolkit that takes **book value or a negotiated transaction value**
instead of market value for equity and debt — there isn't a market price to
observe.

Cost of debt still supports the same two paths as calculator 1 (a directly
observed rate — here more likely a lender term sheet than a traded YTM — or
a synthetic rating from interest coverage), since interest coverage is
observable from financials even without a market price for equity or debt.

### Running calculator 4

```python
from wacc import BuildUpWaccInputs, compute_build_up_wacc, build_up_wacc_sensitivity

inputs = BuildUpWaccInputs(
    risk_free_rate=0.04,
    equity_risk_premium=0.05,
    size_premium=0.03,                    # e.g. from a Duff & Phelps / Kroll study
    company_specific_risk_premium=0.04,   # qualitative -- key-person risk, customer concentration, etc.
    tax_rate_marginal=0.25,
    equity_value=800_000.0,               # book value or negotiated transaction value, NOT market value
    debt_value=200_000.0,
    cost_of_debt_pretax=0.08,             # e.g. a lender term sheet rate -- or use interest_coverage_ratio instead
)

result = compute_build_up_wacc(inputs)
print(result.wacc)

grid = build_up_wacc_sensitivity(inputs)  # size-premium x company-specific-premium grid -- there's no beta to grid against
```

`industry_risk_premium`, `preferred_value`, and `preferred_dividend_yield`
are all optional (default 0). If `cost_of_debt_pretax` is omitted, pass
`interest_coverage_ratio` instead to derive a synthetic rating the same way
calculator 1 does.

## Running the tests

```
python -m pytest tests/
```

Or individually, without pytest (each file is plain-assert, runnable directly):

```
python tests/test_calculator.py
python tests/test_segment.py
python tests/test_regression_beta.py
python tests/test_build_up.py
python tests/test_manifest.py
```

## Running the browser page

`web/index.html` is the hub — it links to each calculator's own page.
Calculator pages fetch the `wacc/*.py` source files and `data/*.json` by
relative path via `web/shared/wacc-loader.js`, so they must be served (not
opened via `file://`):

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
- Sensitivity grids are two-axis only (beta × ERP for calculators 1 and 3,
  size premium × company-specific premium for calculator 4); leverage and
  cost-of-debt sensitivity are natural next axes for any of them.
- `calculator-segment-level.html` only exposes the *typical* case: per-segment
  unlevered beta and capital weight, everything else (tax rate, cost of debt,
  capital structure) defaulting to the consolidated company. `SegmentOverride`
  supports overriding any of those per segment (e.g. a ring-fenced
  project-finance subsidiary with its own disclosed structure) — that case is
  Python-library only, use `compute_segment_wacc` directly.
- No calculator fetches segment betas for you; you still have to pick a
  comparable pure-play beta per segment yourself (same manual step
  `industry_betas.json` automates at the whole-company level, not yet
  extended to segments).

## Adding a future calculator (5, ...)

Each calculator gets its own numbered `## Calculator N: <Descriptive Name>`
section (not a generic subsection folded into an existing one), following
the pattern above:

1. Add a row to the **"Which calculator do I need?"** table at the top —
   use case, function, module, output — *before* writing any code. If you
   can't fill in the "Use when" cell in one sentence, the calculator isn't
   scoped yet.
2. New logic goes in its own `wacc/<name>.py` module; reuse `beta.py` and
   `cost_of_debt.py` rather than re-deriving cost-of-equity/cost-of-debt
   math, the way `segment.py` reuses `calculator.py`.
3. **Run `python scripts/generate_manifest.py` and commit the regenerated
   `wacc/manifest.json`.** Every calculator page fetches its file list from
   this manifest instead of a hardcoded array — added 2026-09-26 specifically
   so this step can't be silently skipped the way it was on 2026-09-09 (see
   git history, commit `6ac4baf`), which broke the entire live browser page,
   not just the new calculator. `tests/test_manifest.py` fails loudly if you
   add a module or data file and forget this step.
4. **Give the new calculator its own page**, `web/calculator-<name>.html`,
   built on `web/shared/wacc-loader.js` the same way
   `calculator-bottom-up-beta.html` is (see that file for the pattern) — add
   a `<link rel="back">`-style link back to `index.html`, and add a card for
   it on the hub page (`web/index.html`) with a `LIVE` status badge. Don't
   add a form to an existing calculator's page; each method has different
   inputs.
5. Add `tests/test_<name>.py`, same plain-assert style as the existing test
   files (no pytest dependency required to read them, though the suite runs
   under pytest).
6. Check `finance/methods/wacc-methodology-reference.md` (if you have KB
   access) for whether the new calculator's decision-matrix row already
   exists there — update it if the new tool changes which method applies
   when.
