# WACC Toolkit

A small toolkit of WACC calculation methods that fix the shortcuts most free
WACC calculators take. Six calculators — each solving a different
problem; pick the one that matches your situation, not just the first one
you find. Runnable both as a plain Python library and as a static browser
page (via [Pyodide](https://pyodide.org/)) with no server and no data
leaving the page.

## Which calculator do I need?

| | Calculator 1: Bottom-Up Beta / Synthetic-Rating WACC | Calculator 2: Segment-Level (Sum-of-Parts) WACC | Calculator 3: Regression-Beta / Liquid Large-Cap WACC | Calculator 4: Private-Company Build-Up Method WACC | Calculator 5: Total Beta (Butler-Pinkerton) WACC | Calculator 6: Fama-French 3-Factor WACC |
|---|---|---|---|---|---|---|
| **Use when** | Valuing a whole company as a single unit; thinly-traded, recently-listed, or volatile names where a regression beta is noisy | The company has genuinely different-risk segments (a regulated utility arm vs. a merchant/growth arm) and one blended number would misprice at least one of them | A liquid large-cap with a stable capital structure and a long trading history, where a regression beta is reliable and traded-debt YTM is directly observable | A private company with no market price at all (litigation, ESOP, small-business sale) — no beta to estimate | Same private/closely-held population as Calculator 4, but you want total (systematic + unsystematic) risk priced via a rescaled guideline-comparable beta instead of a stack of additive premia | A liquid public company with a real size or value/growth tilt, where a single market beta (Calculator 3) misprices the size and value risk a two-factor addition captures directly |
| **Function** | `compute_wacc(WaccInputs(...))` | `compute_segment_wacc(consolidated, [SegmentOverride(...), ...])` + `weighted_average_wacc(...)` | `compute_regression_wacc(RegressionWaccInputs(...))` | `compute_build_up_wacc(BuildUpWaccInputs(...))` | `compute_total_beta_wacc(TotalBetaWaccInputs(...))` | `compute_fama_french_wacc(FamaFrenchWaccInputs(...))` |
| **Module** | `wacc/calculator.py` (+ `beta.py`, `cost_of_debt.py`) | `wacc/segment.py` (wraps calculator 1 — same core math, run once per segment) | `wacc/regression_beta.py` (independent — does not relever the beta, does not use `beta.py` or `cost_of_debt.py`) | `wacc/build_up.py` (independent — no beta at all; reuses only `cost_of_debt.py`'s synthetic rating) | `wacc/total_beta.py` (reuses `beta.py`'s relever step and `cost_of_debt.py`'s synthetic rating, like calculator 1) | `wacc/fama_french.py` (independent — no relevering, no synthetic-rating fallback, same rules as calculator 3) |
| **Output** | One WACC + a beta×ERP sensitivity grid | One WACC per segment + a capital-weighted sum-of-parts aggregate, for comparison against calculator 1's naive company-level number | One WACC + a regression-beta×ERP sensitivity grid | One WACC + a size-premium×company-specific-premium sensitivity grid | One WACC + a correlation-coefficient×ERP sensitivity grid | One WACC + a size-beta×value-beta sensitivity grid, plus each factor's own contribution to cost of equity |
| **Browser page** | `calculator-bottom-up-beta.html` | `calculator-segment-level.html` (typical case only — see Known limitations) | `calculator-regression-beta.html` | `calculator-build-up.html` | `calculator-total-beta.html` | `calculator-fama-french.html` |
| **Full docs** | § "Calculator 1" below | § "Calculator 2" below | § "Calculator 3" below | § "Calculator 4" below | § "Calculator 5" below | § "Calculator 6" below |

Not sure which applies? Read `finance/methods/wacc-methodology-reference.md`
(if you have access to the KB this toolkit was built for) — it has the full
decision matrix this table is a summary of. Calculators 1 and 2 share the
same underlying cost-of-equity/cost-of-debt method (calculator 2 only
changes *how many times* and *with what inputs* it runs); calculators 3, 4,
5, and 6 each use a genuinely different method (calculator 3: regression
beta used directly, no relevering, directly observed traded-debt YTM;
calculator 4: a build-up stack instead of CAPM, no beta at all,
book/negotiated-value weights instead of market value; calculator 5: a
guideline comparable's beta rescaled by its own correlation coefficient
instead of stacked additive premia, for the same no-market-price population
as calculator 4; calculator 6: two additional priced factors — size and
value — on top of the market factor, instead of a single beta) — see their
own sections for why. Calculators 4 and 5 solve the *same* use case with
different mechanisms — pick one, don't run both and average them.

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
  total_beta.py          Calculator 5 (total beta) -- TotalBetaWaccInputs /
                        compute_total_beta_wacc / total_beta_wacc_sensitivity
                        (reuses beta.py's relever step and cost_of_debt.py, like calculator 1 --
                        see its own section for how it differs from calculator 4)
  fama_french.py         Calculator 6 (Fama-French 3-factor) -- FamaFrenchWaccInputs /
                        compute_fama_french_wacc / fama_french_wacc_sensitivity
                        (independent of beta.py / cost_of_debt.py, same rules as calculator 3 --
                        see its own section)
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
  calculator-total-beta.html
                        Calculator 5's static Pyodide page
  calculator-fama-french.html
                        Calculator 6's static Pyodide page
  shared/wacc-loader.js  Pyodide/manifest loading logic shared by every
                         calculator page (factored out 2026-09-27)
tests/
  test_calculator.py    Calculator 1 unit tests, no network required
  test_segment.py       Calculator 2 unit tests, no network required
  test_regression_beta.py  Calculator 3 unit tests, no network required
  test_build_up.py      Calculator 4 unit tests, no network required
  test_total_beta.py    Calculator 5 unit tests, no network required
  test_fama_french.py   Calculator 6 unit tests, no network required
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

## Calculator 5: Total Beta (Butler-Pinkerton) WACC

### What this does differently

Calculator 4 is one answer to "the subject company has no market price and
no return series to derive a beta from": replace `beta x ERP` with a stack
of separately-justified premia. Total beta is the other camp's answer to
the *same* population (private company, closely-held business,
litigation/ESOP/small-business-sale valuation) — it keeps `beta x ERP` as a
single term, but rescales a guideline public comparable's beta for *total*
risk (systematic + unsystematic) instead of only market risk, on the
premise that the owner of a closely-held business holds a concentrated,
undiversified position and cannot diversify away the unsystematic risk CAPM
assumes away:

```
total beta = comparable's levered beta / R
```

where `R` is the correlation coefficient (**not** R²) between the
guideline public comparable's returns and the market's, from the same
regression that produced the comparable's beta. A low `R` means the
comparable's own returns are driven mostly by something other than the
market — dividing by a small `R` inflates the beta to compensate. `R` for a
single stock is typically 0.2–0.5, so total beta routinely runs several
times the plain levered beta.

This is a genuinely different *mechanism* from calculator 4, not a
relabeling of it — build-up stacks independently-sourced additive premia;
total beta rescales a single multiplicative term. **Don't run both on the
same subject company and average them:** total beta already folds
unsystematic risk into `beta x ERP`, so adding calculator 4's
company-specific risk premium on top double-counts it. `industry_risk_premium`
and `size_premium` exist here only for structural consistency with the
other calculators and default to `0.0` — leave them there unless you have a
specific reason the guideline comparable's own total beta doesn't already
capture.

Like calculator 4, this takes **book value or a negotiated transaction
value** for equity and debt — the subject company has no market price,
even though the comparable used to derive the beta does. Cost of debt
supports the same two paths as calculators 1 and 4.

### Running calculator 5

```python
from wacc import TotalBetaWaccInputs, compute_total_beta_wacc, total_beta_wacc_sensitivity

inputs = TotalBetaWaccInputs(
    risk_free_rate=0.04,
    equity_risk_premium=0.05,
    unlevered_beta=0.90,           # guideline public comparable's own unlevered beta
    correlation_coefficient=0.35,  # R, not R-squared, from the same regression
    tax_rate_marginal=0.25,
    equity_value=800_000.0,        # book value or negotiated transaction value, NOT market value
    debt_value=200_000.0,
    cost_of_debt_pretax=0.08,      # e.g. a lender term sheet rate -- or use interest_coverage_ratio instead
)

result = compute_total_beta_wacc(inputs)
print(result.wacc, result.total_beta)

grid = total_beta_wacc_sensitivity(inputs)  # correlation-coefficient x ERP grid
```

`industry_risk_premium`, `size_premium`, `preferred_value`, and
`preferred_dividend_yield` are all optional (default 0). If
`cost_of_debt_pretax` is omitted, pass `interest_coverage_ratio` instead,
same as calculators 1 and 4.

## Calculator 6: Fama-French 3-Factor WACC

### What this does differently

Calculator 3 exists for a liquid large-cap where a trailing regression beta
against a broad market index is reliable. That single market beta is
exactly what Fama-French adds two more priced factors to — empirical
evidence that small-cap and value-tilted stocks earn returns a single beta
systematically under-predicts:

```
cost of equity = risk-free rate
               + beta_mkt * market risk premium
               + beta_smb * SMB premium   (size: small-minus-big)
               + beta_hml * HML premium   (value: high-minus-low book/market)
```

All three betas are the company's own factor loadings from a time-series
regression of its excess returns against the three published Fama-French
factors (e.g. Ken French's data library) — run externally, the same way
calculator 3's regression beta is; this calculator consumes the
already-estimated loadings rather than running the regression itself.
`beta_mkt` is levered and used directly, no relevering, same rule and same
reason as calculator 3.

For a mega-cap blend name with negligible size or value tilt, this
converges to nearly the same number as calculator 3 — plain CAPM is a fine
approximation there. For a mid-cap, a deep-value name, or a high-growth
name, expect a genuinely different cost of equity, not just a different
route to the same one. There is deliberately no separate `size_premium`
field here: `beta_smb * smb_premium` **is** the size adjustment in this
model, and stacking a manual size premium on top of it would double-count
size the same way combining calculator 5's total beta with calculator 4's
company-specific premium would double-count unsystematic risk. Cost of
debt follows calculator 3's rule — a directly observed traded-debt YTM is
required, with no synthetic-rating fallback.

### Running calculator 6

```python
from wacc import FamaFrenchWaccInputs, compute_fama_french_wacc, fama_french_wacc_sensitivity

inputs = FamaFrenchWaccInputs(
    risk_free_rate=0.04,
    market_risk_premium=0.05,
    smb_premium=0.02,
    hml_premium=0.03,
    beta_mkt=1.10,   # levered -- observed directly, do not relever
    beta_smb=0.40,
    beta_hml=0.20,
    tax_rate_marginal=0.25,
    market_value_equity=800.0,
    market_value_debt=200.0,
    cost_of_debt_pretax=0.05,  # traded-debt YTM -- required, no synthetic-rating fallback
)

result = compute_fama_french_wacc(inputs)
print(result.wacc, result.cost_of_equity)

grid = fama_french_wacc_sensitivity(inputs)  # beta_smb x beta_hml grid
```

`market_value_preferred` and `preferred_dividend_yield` are optional
(default 0), same as calculator 3.

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
python tests/test_total_beta.py
python tests/test_fama_french.py
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
  size premium × company-specific premium for calculator 4, correlation
  coefficient × ERP for calculator 5, size-beta × value-beta for calculator
  6); leverage and cost-of-debt sensitivity are natural next axes for any of
  them.
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

## Adding a future calculator (7, ...)

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
