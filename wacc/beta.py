"""Hamada relever/unlever for bottom-up beta.

Bottom-up beta (industry unlevered beta, relevered to the target company's
own capital structure) is used instead of a trailing regression beta because
regression betas are noisy for thinly-traded, recently-listed, or highly
volatile names.
"""


def relever_beta(unlevered_beta: float, tax_rate: float, debt_to_equity: float) -> float:
    """Relever an industry unlevered beta to a company's own D/E."""
    return unlevered_beta * (1 + (1 - tax_rate) * debt_to_equity)


def unlever_beta(levered_beta: float, tax_rate: float, debt_to_equity: float) -> float:
    """Strip a company's own leverage out of an observed levered beta."""
    return levered_beta / (1 + (1 - tax_rate) * debt_to_equity)
