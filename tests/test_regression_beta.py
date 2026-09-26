import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wacc.regression_beta import (
    RegressionWaccInputs,
    compute_regression_wacc,
    regression_wacc_sensitivity,
)


def test_regression_beta_used_directly_not_relevered():
    # A regression beta of 1.1 with zero debt should produce exactly the
    # same cost of equity CAPM would give directly -- no Hamada step.
    inputs = RegressionWaccInputs(
        risk_free_rate=0.04,
        equity_risk_premium=0.05,
        regression_beta=1.1,
        tax_rate_marginal=0.25,
        market_value_equity=1000.0,
        market_value_debt=0.0,
        cost_of_debt_pretax=0.045,
    )
    result = compute_regression_wacc(inputs)
    expected_cost_of_equity = 0.04 + 1.1 * 0.05
    assert math.isclose(result.cost_of_equity, expected_cost_of_equity, rel_tol=1e-9)
    assert result.levered_beta == 1.1


def test_compute_regression_wacc_basic_sanity():
    inputs = RegressionWaccInputs(
        risk_free_rate=0.04,
        equity_risk_premium=0.05,
        regression_beta=1.1,
        tax_rate_marginal=0.25,
        market_value_equity=800.0,
        market_value_debt=200.0,
        cost_of_debt_pretax=0.05,
    )
    result = compute_regression_wacc(inputs)
    assert result.cost_of_debt_aftertax < result.wacc < result.cost_of_equity
    assert result.weight_equity + result.weight_debt == 1.0
    assert result.synthetic_rating is None


def test_requires_positive_market_value_equity():
    try:
        RegressionWaccInputs(
            risk_free_rate=0.04,
            equity_risk_premium=0.05,
            regression_beta=1.1,
            tax_rate_marginal=0.25,
            market_value_equity=0.0,
            market_value_debt=200.0,
            cost_of_debt_pretax=0.05,
        )
    except ValueError:
        return
    raise AssertionError("expected ValueError for non-positive market_value_equity")


def test_cost_of_debt_pretax_is_required():
    try:
        RegressionWaccInputs(
            risk_free_rate=0.04,
            equity_risk_premium=0.05,
            regression_beta=1.1,
            tax_rate_marginal=0.25,
            market_value_equity=800.0,
            market_value_debt=200.0,
        )
    except TypeError:
        return
    raise AssertionError("expected TypeError -- cost_of_debt_pretax has no default, unlike Calculator 1")


def test_sensitivity_grid_shape_and_monotonic_beta():
    inputs = RegressionWaccInputs(
        risk_free_rate=0.04,
        equity_risk_premium=0.05,
        regression_beta=1.1,
        tax_rate_marginal=0.25,
        market_value_equity=800.0,
        market_value_debt=200.0,
        cost_of_debt_pretax=0.05,
    )
    grid = regression_wacc_sensitivity(inputs, beta_deltas=(-0.1, 0.0, 0.1), erp_deltas=(0.0,))
    assert len(grid) == 3
    waccs = [row["wacc"] for row in grid]
    assert waccs[0] < waccs[1] < waccs[2]


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"OK: {t.__name__}")
    print(f"\n{len(tests)} tests passed.")
