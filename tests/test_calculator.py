import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wacc.beta import relever_beta, unlever_beta
from wacc.cost_of_debt import synthetic_rating_spread
from wacc.calculator import WaccInputs, compute_wacc, wacc_sensitivity


def test_relever_unlever_roundtrip():
    unlevered = 1.10
    tax = 0.25
    de = 0.6
    levered = relever_beta(unlevered, tax, de)
    assert math.isclose(unlever_beta(levered, tax, de), unlevered, rel_tol=1e-9)


def test_relever_beta_zero_debt_is_noop():
    assert math.isclose(relever_beta(1.2, 0.25, 0.0), 1.2)


def test_synthetic_rating_buckets():
    rating, spread = synthetic_rating_spread(9.0)
    assert rating == "AAA"
    rating, spread = synthetic_rating_spread(0.5)
    assert rating == "C"
    rating, _ = synthetic_rating_spread(3.0)
    assert rating == "BBB"


def test_compute_wacc_basic_sanity():
    inputs = WaccInputs(
        risk_free_rate=0.04,
        equity_risk_premium=0.05,
        unlevered_beta=1.1,
        tax_rate_marginal=0.25,
        market_value_equity=800.0,
        market_value_debt=200.0,
        interest_coverage_ratio=6.0,
    )
    result = compute_wacc(inputs)
    # Cost of equity and after-tax cost of debt should each individually
    # bound the blended WACC.
    assert result.cost_of_debt_aftertax < result.wacc < result.cost_of_equity
    assert result.weight_equity + result.weight_debt == 1.0
    assert result.synthetic_rating == "A+"


def test_compute_wacc_requires_a_debt_cost_source():
    try:
        WaccInputs(
            risk_free_rate=0.04,
            equity_risk_premium=0.05,
            unlevered_beta=1.1,
            tax_rate_marginal=0.25,
            market_value_equity=800.0,
            market_value_debt=200.0,
        )
    except ValueError:
        return
    raise AssertionError("expected ValueError when no cost-of-debt source given")


def test_more_leverage_raises_component_costs_but_not_necessarily_wacc():
    low_leverage = WaccInputs(
        risk_free_rate=0.04,
        equity_risk_premium=0.05,
        unlevered_beta=1.1,
        tax_rate_marginal=0.25,
        market_value_equity=950.0,
        market_value_debt=50.0,
        interest_coverage_ratio=6.0,
    )
    high_leverage = WaccInputs(
        risk_free_rate=0.04,
        equity_risk_premium=0.05,
        unlevered_beta=1.1,
        tax_rate_marginal=0.25,
        market_value_equity=500.0,
        market_value_debt=500.0,
        interest_coverage_ratio=2.2,
    )
    low = compute_wacc(low_leverage)
    high = compute_wacc(high_leverage)
    # Relevered beta and both component costs must rise with leverage...
    assert high.levered_beta > low.levered_beta
    assert high.cost_of_equity > low.cost_of_equity
    assert high.cost_of_debt_pretax > low.cost_of_debt_pretax
    # ...but WACC itself is not guaranteed to: the tax shield can outweigh
    # the higher component costs (classic MM-with-taxes result), since this
    # model has no explicit bankruptcy-cost penalty term. Confirmed here
    # WACC actually dips slightly at higher leverage — that's a known
    # limitation of synthetic-rating-only WACC models, not a bug.
    assert high.wacc < low.wacc


def test_sensitivity_grid_shape_and_monotonic_beta():
    inputs = WaccInputs(
        risk_free_rate=0.04,
        equity_risk_premium=0.05,
        unlevered_beta=1.1,
        tax_rate_marginal=0.25,
        market_value_equity=800.0,
        market_value_debt=200.0,
        interest_coverage_ratio=6.0,
    )
    grid = wacc_sensitivity(inputs, beta_deltas=(-0.1, 0.0, 0.1), erp_deltas=(0.0,))
    assert len(grid) == 3
    waccs = [row["wacc"] for row in grid]
    assert waccs[0] < waccs[1] < waccs[2]


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"OK: {t.__name__}")
    print(f"\n{len(tests)} tests passed.")
