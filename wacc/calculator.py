"""WACC computation with bottom-up beta, synthetic-rating cost of debt,
market-value capital weights, and a sensitivity grid instead of a single
point estimate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .beta import relever_beta
from .cost_of_debt import synthetic_rating_spread


@dataclass
class WaccInputs:
    risk_free_rate: float
    equity_risk_premium: float
    unlevered_beta: float
    tax_rate_marginal: float

    market_value_equity: float
    market_value_debt: float  # include capitalized operating leases
    market_value_preferred: float = 0.0

    # Cost of debt: supply either a directly observed pretax cost (e.g. YTM
    # on outstanding bonds) or an interest coverage ratio to derive a
    # synthetic rating. If both are given, cost_of_debt_pretax wins.
    cost_of_debt_pretax: float | None = None
    interest_coverage_ratio: float | None = None

    preferred_dividend_yield: float = 0.0
    size_premium: float = 0.0

    def __post_init__(self) -> None:
        if self.cost_of_debt_pretax is None and self.interest_coverage_ratio is None:
            raise ValueError(
                "Provide either cost_of_debt_pretax or interest_coverage_ratio"
            )
        if self.market_value_equity <= 0:
            raise ValueError("market_value_equity must be positive")


@dataclass
class WaccResult:
    wacc: float
    levered_beta: float
    cost_of_equity: float
    cost_of_debt_pretax: float
    cost_of_debt_aftertax: float
    synthetic_rating: str | None
    weight_equity: float
    weight_debt: float
    weight_preferred: float


def compute_wacc(inputs: WaccInputs) -> WaccResult:
    debt_to_equity = inputs.market_value_debt / inputs.market_value_equity
    levered_beta = relever_beta(
        inputs.unlevered_beta, inputs.tax_rate_marginal, debt_to_equity
    )
    cost_of_equity = (
        inputs.risk_free_rate
        + levered_beta * inputs.equity_risk_premium
        + inputs.size_premium
    )

    rating: str | None = None
    if inputs.cost_of_debt_pretax is not None:
        cost_of_debt_pretax = inputs.cost_of_debt_pretax
    else:
        rating, spread = synthetic_rating_spread(inputs.interest_coverage_ratio)
        cost_of_debt_pretax = inputs.risk_free_rate + spread
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
        levered_beta=levered_beta,
        cost_of_equity=cost_of_equity,
        cost_of_debt_pretax=cost_of_debt_pretax,
        cost_of_debt_aftertax=cost_of_debt_aftertax,
        synthetic_rating=rating,
        weight_equity=weight_equity,
        weight_debt=weight_debt,
        weight_preferred=weight_preferred,
    )


def wacc_sensitivity(
    inputs: WaccInputs,
    beta_deltas: tuple[float, ...] = (-0.2, -0.1, 0.0, 0.1, 0.2),
    erp_deltas: tuple[float, ...] = (-0.005, 0.0, 0.005),
) -> list[dict]:
    """Grid of WACC outcomes as unlevered beta and ERP are perturbed.

    A single WACC point estimate hides how sensitive a downstream DCF is to
    two of its noisiest inputs. This returns every (beta_delta, erp_delta)
    combination so the caller can render a range rather than a point.
    """
    rows = []
    for b_delta in beta_deltas:
        for e_delta in erp_deltas:
            scenario = WaccInputs(
                risk_free_rate=inputs.risk_free_rate,
                equity_risk_premium=inputs.equity_risk_premium + e_delta,
                unlevered_beta=inputs.unlevered_beta + b_delta,
                tax_rate_marginal=inputs.tax_rate_marginal,
                market_value_equity=inputs.market_value_equity,
                market_value_debt=inputs.market_value_debt,
                market_value_preferred=inputs.market_value_preferred,
                cost_of_debt_pretax=inputs.cost_of_debt_pretax,
                interest_coverage_ratio=inputs.interest_coverage_ratio,
                preferred_dividend_yield=inputs.preferred_dividend_yield,
                size_premium=inputs.size_premium,
            )
            result = compute_wacc(scenario)
            rows.append(
                {
                    "beta_delta": b_delta,
                    "erp_delta": e_delta,
                    "unlevered_beta": scenario.unlevered_beta,
                    "equity_risk_premium": scenario.equity_risk_premium,
                    "wacc": result.wacc,
                }
            )
    return rows
