"""Calculator 3: Regression-Beta / Liquid Large-Cap WACC.

For a liquid large-cap with a stable capital structure and a long trading
history, a trailing regression beta (typically 3-5yr monthly returns vs. a
broad index) is a reliable measure of levered equity risk. This is the
opposite case from Calculator 1's bottom-up industry beta, which exists
specifically because regression betas are *unreliable* for thinly-traded,
recently-listed, or highly volatile names.

Two things distinguish this from Calculator 1's math, not just its beta
source:

- A regression beta is already levered to the company's own current capital
  structure -- it comes directly from the stock's own observed return
  series. Running it through beta.py's Hamada relever step (built for an
  *unlevered* industry beta) would double-count leverage. This calculator
  uses the regression beta directly in CAPM.
- Cost of debt uses directly observed traded-debt YTM, not a synthetic
  rating from interest coverage -- liquid large-caps generally have traded
  bonds, so there's no need for the proxy Calculator 1 uses when no directly
  observed cost is available.

See finance/methods/wacc-methodology-reference.md's decision matrix, row
"Liquid large-cap, stable structure, long trading history."
"""

from __future__ import annotations

from dataclasses import dataclass

from .calculator import WaccResult


@dataclass
class RegressionWaccInputs:
    risk_free_rate: float
    equity_risk_premium: float
    regression_beta: float  # levered -- observed directly, do not relever
    tax_rate_marginal: float

    market_value_equity: float
    market_value_debt: float  # include capitalized operating leases
    cost_of_debt_pretax: float  # traded-debt YTM -- required, no synthetic-rating fallback for this row

    market_value_preferred: float = 0.0
    preferred_dividend_yield: float = 0.0
    size_premium: float = 0.0  # usually 0 for a liquid large-cap; kept for consistency with Calculator 1

    def __post_init__(self) -> None:
        if self.market_value_equity <= 0:
            raise ValueError("market_value_equity must be positive")


def compute_regression_wacc(inputs: RegressionWaccInputs) -> WaccResult:
    cost_of_equity = (
        inputs.risk_free_rate
        + inputs.regression_beta * inputs.equity_risk_premium
        + inputs.size_premium
    )

    cost_of_debt_pretax = inputs.cost_of_debt_pretax
    cost_of_debt_aftertax = cost_of_debt_pretax * (1 - inputs.tax_rate_marginal)

    total_capital = (
        inputs.market_value_equity
        + inputs.market_value_debt
        + inputs.market_value_preferred
    )
    weight_equity = inputs.market_value_equity / total_capital
    weight_debt = inputs.market_value_debt / total_capital
    weight_preferred = inputs.market_value_preferred / total_capital

    wacc = (
        weight_equity * cost_of_equity
        + weight_debt * cost_of_debt_aftertax
        + weight_preferred * inputs.preferred_dividend_yield
    )

    return WaccResult(
        wacc=wacc,
        levered_beta=inputs.regression_beta,
        cost_of_equity=cost_of_equity,
        cost_of_debt_pretax=cost_of_debt_pretax,
        cost_of_debt_aftertax=cost_of_debt_aftertax,
        synthetic_rating=None,
        weight_equity=weight_equity,
        weight_debt=weight_debt,
        weight_preferred=weight_preferred,
    )


def regression_wacc_sensitivity(
    inputs: RegressionWaccInputs,
    beta_deltas: tuple[float, ...] = (-0.2, -0.1, 0.0, 0.1, 0.2),
    erp_deltas: tuple[float, ...] = (-0.005, 0.0, 0.005),
) -> list[dict]:
    """Grid of WACC outcomes as the regression beta and ERP are perturbed.

    Same purpose as Calculator 1's wacc_sensitivity: a single WACC point
    estimate hides how sensitive a downstream DCF is to two of its noisiest
    inputs, even when the regression beta itself is a more reliable point
    estimate than a bottom-up industry beta would be for this kind of name.
    """
    rows = []
    for b_delta in beta_deltas:
        for e_delta in erp_deltas:
            scenario = RegressionWaccInputs(
                risk_free_rate=inputs.risk_free_rate,
                equity_risk_premium=inputs.equity_risk_premium + e_delta,
                regression_beta=inputs.regression_beta + b_delta,
                tax_rate_marginal=inputs.tax_rate_marginal,
                market_value_equity=inputs.market_value_equity,
                market_value_debt=inputs.market_value_debt,
                cost_of_debt_pretax=inputs.cost_of_debt_pretax,
                market_value_preferred=inputs.market_value_preferred,
                preferred_dividend_yield=inputs.preferred_dividend_yield,
                size_premium=inputs.size_premium,
            )
            result = compute_regression_wacc(scenario)
            rows.append(
                {
                    "beta_delta": b_delta,
                    "erp_delta": e_delta,
                    "regression_beta": scenario.regression_beta,
                    "equity_risk_premium": scenario.equity_risk_premium,
                    "wacc": result.wacc,
                }
            )
    return rows
