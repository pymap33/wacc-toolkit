"""Calculator 4: Private-Company Build-Up Method WACC.

For a private company with no market price at all (litigation, ESOP,
small-business sale), there is no beta to estimate -- no traded shares, no
return series to regress or relever. The build-up method replaces CAPM's
single beta*ERP term with a stack of separately-justified premia:

    cost of equity = risk-free rate
                    + equity risk premium
                    + industry risk premium (optional)
                    + size premium
                    + company-specific risk premium

Each premium is its own defensible number (typically sourced from Duff &
Phelps / Kroll size-premium studies and a qualitative company-specific risk
assessment), rather than a single beta standing in for all of them. This is
also the only calculator in this toolkit that doesn't take a market value
for equity or debt -- there isn't one. It takes book value or a negotiated
transaction value instead, per the matrix row this implements.

Cost of debt still supports the same two paths as Calculator 1 (directly
observed -- here more likely a lender term sheet rate than a traded YTM --
or a synthetic rating derived from interest coverage), since interest
coverage is observable from a private company's financials even without a
market price for its equity or debt.

See finance/methods/wacc-methodology-reference.md's decision matrix, row
"Private company, no market price at all (litigation, ESOP, small-business
sale)."
"""

from __future__ import annotations

from dataclasses import dataclass

from .cost_of_debt import synthetic_rating_spread


@dataclass
class BuildUpWaccInputs:
    risk_free_rate: float
    equity_risk_premium: float
    size_premium: float
    company_specific_risk_premium: float
    tax_rate_marginal: float

    # Book value or a negotiated transaction value -- there is no market
    # price to observe, unlike every other calculator in this toolkit.
    equity_value: float
    debt_value: float

    # Cost of debt: supply either a directly observed pretax cost (e.g. a
    # lender term sheet rate) or an interest coverage ratio to derive a
    # synthetic rating. If both are given, cost_of_debt_pretax wins.
    cost_of_debt_pretax: float | None = None
    interest_coverage_ratio: float | None = None

    industry_risk_premium: float = 0.0
    preferred_value: float = 0.0
    preferred_dividend_yield: float = 0.0

    def __post_init__(self) -> None:
        if self.cost_of_debt_pretax is None and self.interest_coverage_ratio is None:
            raise ValueError(
                "Provide either cost_of_debt_pretax or interest_coverage_ratio"
            )
        if self.equity_value <= 0:
            raise ValueError("equity_value must be positive")


@dataclass
class BuildUpWaccResult:
    wacc: float
    cost_of_equity: float
    cost_of_debt_pretax: float
    cost_of_debt_aftertax: float
    synthetic_rating: str | None
    weight_equity: float
    weight_debt: float
    weight_preferred: float


def compute_build_up_wacc(inputs: BuildUpWaccInputs) -> BuildUpWaccResult:
    cost_of_equity = (
        inputs.risk_free_rate
        + inputs.equity_risk_premium
        + inputs.industry_risk_premium
        + inputs.size_premium
        + inputs.company_specific_risk_premium
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

    return BuildUpWaccResult(
        wacc=wacc,
        cost_of_equity=cost_of_equity,
        cost_of_debt_pretax=cost_of_debt_pretax,
        cost_of_debt_aftertax=cost_of_debt_aftertax,
        synthetic_rating=rating,
        weight_equity=weight_equity,
        weight_debt=weight_debt,
        weight_preferred=weight_preferred,
    )


def build_up_wacc_sensitivity(
    inputs: BuildUpWaccInputs,
    size_premium_deltas: tuple[float, ...] = (-0.01, -0.005, 0.0, 0.005, 0.01),
    company_specific_deltas: tuple[float, ...] = (-0.02, 0.0, 0.02),
) -> list[dict]:
    """Grid of WACC outcomes as size premium and company-specific risk
    premium are perturbed.

    There's no beta here, so beta x ERP (the other calculators' sensitivity
    axes) doesn't apply. Size premium and company-specific risk premium are
    the build-up method's own most contestable, least standardized inputs --
    unlike the equity risk premium, which is a broad-market number most
    practitioners agree on within a narrow range.
    """
    rows = []
    for sp_delta in size_premium_deltas:
        for cs_delta in company_specific_deltas:
            scenario = BuildUpWaccInputs(
                risk_free_rate=inputs.risk_free_rate,
                equity_risk_premium=inputs.equity_risk_premium,
                size_premium=inputs.size_premium + sp_delta,
                company_specific_risk_premium=inputs.company_specific_risk_premium + cs_delta,
                tax_rate_marginal=inputs.tax_rate_marginal,
                equity_value=inputs.equity_value,
                debt_value=inputs.debt_value,
                cost_of_debt_pretax=inputs.cost_of_debt_pretax,
                interest_coverage_ratio=inputs.interest_coverage_ratio,
                industry_risk_premium=inputs.industry_risk_premium,
                preferred_value=inputs.preferred_value,
                preferred_dividend_yield=inputs.preferred_dividend_yield,
            )
            result = compute_build_up_wacc(scenario)
            rows.append(
                {
                    "size_premium_delta": sp_delta,
                    "company_specific_delta": cs_delta,
                    "size_premium": scenario.size_premium,
                    "company_specific_risk_premium": scenario.company_specific_risk_premium,
                    "wacc": result.wacc,
                }
            )
    return rows
