"""Calculator 5: Total Beta (Butler-Pinkerton) WACC.

Calculator 4's build-up method is one answer to "the subject company has no
market price and no return series to derive a beta from": replace beta*ERP
with a stack of separately-justified premia. Total beta is the other
camp's answer to the *same* use case (private company, closely-held
business, litigation/ESOP/small-business-sale valuation) -- it still
produces a single cost of equity from beta*ERP, but rescales a guideline
public comparable's beta to reflect *total* risk (systematic + unsystematic)
instead of only market risk, on the premise that the owner of a closely-held
business holds a concentrated, undiversified position and cannot diversify
away the unsystematic risk that CAPM assumes away.

Mechanically:

    total beta = comparable's levered beta / R

where R is the correlation coefficient (not R-squared) between the
guideline public comparable's returns and the market's, from the same
regression that produced the comparable's beta. A low R means the
comparable's returns are mostly driven by *something other than* the
market -- and dividing by a small R inflates the beta to compensate. R for
a single stock is typically 0.2-0.5, versus close to 1.0 for a diversified
portfolio, so total beta is routinely several times the plain levered beta.

This is a genuinely different mechanism from Calculator 4's method, not a
relabeling of it: build-up stacks independently-sourced additive premia;
total beta rescales a single multiplicative term. Don't stack them on the
same subject company -- total beta already folds unsystematic risk into
beta*ERP, so adding a separate company-specific risk premium on top (as
Calculator 4 does) double-counts it. `size_premium` and
`industry_risk_premium` are kept here, at default 0.0, only for structural
consistency with the other calculators; leave them at 0 unless you have a
specific reason the guideline comparable's own total beta doesn't already
capture (e.g. a genuine industry-wide premium the comparable itself doesn't
share in).

Like Calculator 4, this takes book value or a negotiated transaction value
for equity and debt -- the subject company has no market price to observe,
even though the comparable used to derive the beta does.

See finance/methods/wacc-methodology-reference.md's decision matrix, row
"Private company / closely-held business, concentrated undiversified
ownership" (Calculator 4's row covers the same population; pick by which
mechanism you trust more for the case at hand -- see README for the
tradeoff).
"""

from __future__ import annotations

from dataclasses import dataclass

from .beta import relever_beta
from .cost_of_debt import synthetic_rating_spread


@dataclass
class TotalBetaWaccInputs:
    risk_free_rate: float
    equity_risk_premium: float

    # Guideline public comparable's own unlevered beta and the correlation
    # coefficient (R, not R-squared) from the regression that produced it.
    unlevered_beta: float
    correlation_coefficient: float

    tax_rate_marginal: float

    # Book value or a negotiated transaction value -- there is no market
    # price to observe for the subject company, same as Calculator 4.
    equity_value: float
    debt_value: float

    # Cost of debt: supply either a directly observed pretax cost or an
    # interest coverage ratio to derive a synthetic rating, same rule as
    # Calculators 1 and 4. If both are given, cost_of_debt_pretax wins.
    cost_of_debt_pretax: float | None = None
    interest_coverage_ratio: float | None = None

    # Kept at 0.0 by default -- see module docstring on why stacking these
    # with total beta risks double-counting unsystematic risk it already
    # captures.
    industry_risk_premium: float = 0.0
    size_premium: float = 0.0

    preferred_value: float = 0.0
    preferred_dividend_yield: float = 0.0

    def __post_init__(self) -> None:
        if self.cost_of_debt_pretax is None and self.interest_coverage_ratio is None:
            raise ValueError(
                "Provide either cost_of_debt_pretax or interest_coverage_ratio"
            )
        if self.equity_value <= 0:
            raise ValueError("equity_value must be positive")
        if not (0.0 < self.correlation_coefficient <= 1.0):
            raise ValueError("correlation_coefficient must be in (0, 1]")


@dataclass
class TotalBetaWaccResult:
    wacc: float
    levered_beta: float
    total_beta: float
    cost_of_equity: float
    cost_of_debt_pretax: float
    cost_of_debt_aftertax: float
    synthetic_rating: str | None
    weight_equity: float
    weight_debt: float
    weight_preferred: float


def compute_total_beta_wacc(inputs: TotalBetaWaccInputs) -> TotalBetaWaccResult:
    debt_to_equity = inputs.debt_value / inputs.equity_value
    levered_beta = relever_beta(
        inputs.unlevered_beta, inputs.tax_rate_marginal, debt_to_equity
    )
    total_beta = levered_beta / inputs.correlation_coefficient

    cost_of_equity = (
        inputs.risk_free_rate
        + total_beta * inputs.equity_risk_premium
        + inputs.industry_risk_premium
        + inputs.size_premium
    )

    rating: str | None = None
    if inputs.cost_of_debt_pretax is not None:
        cost_of_debt_pretax = inputs.cost_of_debt_pretax
    else:
        rating, spread = synthetic_rating_spread(inputs.interest_coverage_ratio)
        cost_of_debt_pretax = inputs.risk_free_rate + spread
    cost_of_debt_aftertax = cost_of_debt_pretax * (1 - inputs.tax_rate_marginal)

    total_capital = inputs.equity_value + inputs.debt_value + inputs.preferred_value
    weight_equity = inputs.equity_value / total_capital
    weight_debt = inputs.debt_value / total_capital
    weight_preferred = inputs.preferred_value / total_capital

    wacc = (
        weight_equity * cost_of_equity
        + weight_debt * cost_of_debt_aftertax
        + weight_preferred * inputs.preferred_dividend_yield
    )

    return TotalBetaWaccResult(
        wacc=wacc,
        levered_beta=levered_beta,
        total_beta=total_beta,
        cost_of_equity=cost_of_equity,
        cost_of_debt_pretax=cost_of_debt_pretax,
        cost_of_debt_aftertax=cost_of_debt_aftertax,
        synthetic_rating=rating,
        weight_equity=weight_equity,
        weight_debt=weight_debt,
        weight_preferred=weight_preferred,
    )


def total_beta_wacc_sensitivity(
    inputs: TotalBetaWaccInputs,
    correlation_deltas: tuple[float, ...] = (-0.1, -0.05, 0.0, 0.05, 0.1),
    erp_deltas: tuple[float, ...] = (-0.005, 0.0, 0.005),
) -> list[dict]:
    """Grid of WACC outcomes as the correlation coefficient and ERP are
    perturbed.

    Correlation coefficient, not beta, is total beta's own most contestable
    and least standardized input: it comes from a single guideline
    comparable's regression, is typically low (0.2-0.5), and total beta is
    *divided* by it -- a small error in R swings total beta (and therefore
    WACC) far more than the same-sized error would swing a plain CAPM beta.
    That is why this grid perturbs correlation instead of beta x ERP the
    way Calculators 1 and 3 do.

    correlation_deltas that would push correlation_coefficient outside
    (0, 1] are silently skipped rather than raising, since the caller
    supplies a fixed delta tuple that may not suit every base correlation.
    """
    rows = []
    for c_delta in correlation_deltas:
        candidate_correlation = inputs.correlation_coefficient + c_delta
        if not (0.0 < candidate_correlation <= 1.0):
            continue
        for e_delta in erp_deltas:
            scenario = TotalBetaWaccInputs(
                risk_free_rate=inputs.risk_free_rate,
                equity_risk_premium=inputs.equity_risk_premium + e_delta,
                unlevered_beta=inputs.unlevered_beta,
                correlation_coefficient=candidate_correlation,
                tax_rate_marginal=inputs.tax_rate_marginal,
                equity_value=inputs.equity_value,
                debt_value=inputs.debt_value,
                cost_of_debt_pretax=inputs.cost_of_debt_pretax,
                interest_coverage_ratio=inputs.interest_coverage_ratio,
                industry_risk_premium=inputs.industry_risk_premium,
                size_premium=inputs.size_premium,
                preferred_value=inputs.preferred_value,
                preferred_dividend_yield=inputs.preferred_dividend_yield,
            )
            result = compute_total_beta_wacc(scenario)
            rows.append(
                {
                    "correlation_delta": c_delta,
                    "erp_delta": e_delta,
                    "correlation_coefficient": scenario.correlation_coefficient,
                    "equity_risk_premium": scenario.equity_risk_premium,
                    "total_beta": result.total_beta,
                    "wacc": result.wacc,
                }
            )
    return rows
