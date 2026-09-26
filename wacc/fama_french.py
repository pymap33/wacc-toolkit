"""Calculator 6: Fama-French 3-Factor WACC.

Calculator 3 exists for a liquid large-cap where a trailing regression beta
against a broad market index is reliable. That single market beta is
exactly what Fama-French adds two more factors to: empirical evidence that
small-cap and value-tilted stocks earn returns CAPM's single beta
systematically under-predicts. For a mega-cap blend name with negligible
size or value tilt, CAPM and FF3 converge to nearly the same number and
Calculator 3 is simpler. For anything with a real size or value/growth
tilt -- a mid-cap, a deep-value name, a high-growth name -- FF3 will differ
from Calculator 3's output because it is pricing risk factors a single beta
cannot see, not merely re-deriving the same number a different way.

    cost of equity = risk-free rate
                    + beta_mkt * market risk premium
                    + beta_smb * SMB premium   (size: small-minus-big)
                    + beta_hml * HML premium   (value: high-minus-low book/market)

All three betas are the company's own factor loadings from a time-series
regression of its excess returns against the three Fama-French factors
(e.g. Ken French's published factor data). Like Calculator 3's regression
beta, that regression happens outside this toolkit -- this calculator
consumes the already-estimated loadings, it does not run the regression
itself. `beta_mkt` is levered (it comes directly from the company's own
observed return series) and is used directly, the same no-relevering rule
Calculator 3 uses and for the same reason.

There is deliberately no separate `size_premium` field here, unlike
Calculators 1, 3, and 4. SMB *is* the size adjustment in this model --
`beta_smb * smb_premium` already prices it from the company's own measured
sensitivity to the size factor. Stacking an additional manual size premium
on top would double-count it, the same double-counting risk Calculator 5's
docstring flags for combining total beta with a separate company-specific
premium.

Cost of debt follows Calculator 3's rule, not Calculator 1's: a directly
observed traded-debt YTM is required, with no synthetic-rating fallback,
because this calculator targets the same liquid, exchange-listed population
Calculator 3 does.

See finance/methods/wacc-methodology-reference.md's decision matrix, row
"Liquid public company with a real size or value/growth tilt" (if you have
KB access) -- and this module's own docstring for why that's a genuinely
different population from Calculator 3's "mega-cap blend" sweet spot, not
just an alternate way to arrive at the same number.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FamaFrenchWaccInputs:
    risk_free_rate: float

    # Factor premiums (annualized, decimal).
    market_risk_premium: float  # Rm - Rf
    smb_premium: float          # small-minus-big
    hml_premium: float          # high-minus-low book-to-market

    # The company's own factor loadings from a time-series regression
    # against the three factors above. beta_mkt is levered -- observed
    # directly, do not relever (same rule as Calculator 3's regression_beta).
    beta_mkt: float
    beta_smb: float
    beta_hml: float

    tax_rate_marginal: float

    market_value_equity: float
    market_value_debt: float  # include capitalized operating leases
    cost_of_debt_pretax: float  # traded-debt YTM -- required, no synthetic-rating fallback

    market_value_preferred: float = 0.0
    preferred_dividend_yield: float = 0.0

    def __post_init__(self) -> None:
        if self.market_value_equity <= 0:
            raise ValueError("market_value_equity must be positive")


@dataclass
class FamaFrenchWaccResult:
    wacc: float
    cost_of_equity: float
    market_factor_contribution: float
    smb_factor_contribution: float
    hml_factor_contribution: float
    cost_of_debt_pretax: float
    cost_of_debt_aftertax: float
    weight_equity: float
    weight_debt: float
    weight_preferred: float


def compute_fama_french_wacc(inputs: FamaFrenchWaccInputs) -> FamaFrenchWaccResult:
    market_factor_contribution = inputs.beta_mkt * inputs.market_risk_premium
    smb_factor_contribution = inputs.beta_smb * inputs.smb_premium
    hml_factor_contribution = inputs.beta_hml * inputs.hml_premium

    cost_of_equity = (
        inputs.risk_free_rate
        + market_factor_contribution
        + smb_factor_contribution
        + hml_factor_contribution
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

    return FamaFrenchWaccResult(
        wacc=wacc,
        cost_of_equity=cost_of_equity,
        market_factor_contribution=market_factor_contribution,
        smb_factor_contribution=smb_factor_contribution,
        hml_factor_contribution=hml_factor_contribution,
        cost_of_debt_pretax=cost_of_debt_pretax,
        cost_of_debt_aftertax=cost_of_debt_aftertax,
        weight_equity=weight_equity,
        weight_debt=weight_debt,
        weight_preferred=weight_preferred,
    )


def fama_french_wacc_sensitivity(
    inputs: FamaFrenchWaccInputs,
    smb_beta_deltas: tuple[float, ...] = (-0.3, -0.15, 0.0, 0.15, 0.3),
    hml_beta_deltas: tuple[float, ...] = (-0.3, -0.15, 0.0, 0.15, 0.3),
) -> list[dict]:
    """Grid of WACC outcomes as the size and value factor loadings are
    perturbed.

    beta_smb and beta_hml are this model's own distinguishing inputs -- the
    two loadings CAPM and Calculator 3 don't have at all -- so, following
    Calculator 4's and Calculator 5's pattern of gridding each calculator's
    own most novel/contestable inputs rather than always reusing beta x ERP,
    this grids the two factor loadings against each other instead of
    against market risk premium.
    """
    rows = []
    for smb_delta in smb_beta_deltas:
        for hml_delta in hml_beta_deltas:
            scenario = FamaFrenchWaccInputs(
                risk_free_rate=inputs.risk_free_rate,
                market_risk_premium=inputs.market_risk_premium,
                smb_premium=inputs.smb_premium,
                hml_premium=inputs.hml_premium,
                beta_mkt=inputs.beta_mkt,
                beta_smb=inputs.beta_smb + smb_delta,
                beta_hml=inputs.beta_hml + hml_delta,
                tax_rate_marginal=inputs.tax_rate_marginal,
                market_value_equity=inputs.market_value_equity,
                market_value_debt=inputs.market_value_debt,
                cost_of_debt_pretax=inputs.cost_of_debt_pretax,
                market_value_preferred=inputs.market_value_preferred,
                preferred_dividend_yield=inputs.preferred_dividend_yield,
            )
            result = compute_fama_french_wacc(scenario)
            rows.append(
                {
                    "smb_beta_delta": smb_delta,
                    "hml_beta_delta": hml_delta,
                    "beta_smb": scenario.beta_smb,
                    "beta_hml": scenario.beta_hml,
                    "wacc": result.wacc,
                }
            )
    return rows
