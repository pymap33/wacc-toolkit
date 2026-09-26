import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wacc.beta import relever_beta
from wacc.total_beta import (
    TotalBetaWaccInputs,
    compute_total_beta_wacc,
    total_beta_wacc_sensitivity,
)


def _base_inputs(**overrides):
    defaults = dict(
        risk_free_rate=0.04,
        equity_risk_premium=0.05,
        unlevered_beta=0.90,
        correlation_coefficient=0.35,
        tax_rate_marginal=0.25,
        equity_value=800.0,
        debt_value=200.0,
        cost_of_debt_pretax=0.08,
    )
    defaults.update(overrides)
    return TotalBetaWaccInputs(**defaults)


def test_total_beta_is_levered_beta_divided_by_correlation():
    inputs = _base_inputs()
    result = compute_total_beta_wacc(inputs)
    expected_levered_beta = relever_beta(0.90, 0.25, 200.0 / 800.0)
    assert math.isclose(result.levered_beta, expected_levered_beta, rel_tol=1e-9)
    assert math.isclose(
        result.total_beta, expected_levered_beta / 0.35, rel_tol=1e-9
    )


def test_total_beta_exceeds_levered_beta_for_correlation_below_one():
    inputs = _base_inputs()
    result = compute_total_beta_wacc(inputs)
    assert result.total_beta > result.levered_beta


def test_total_beta_equals_levered_beta_at_correlation_one():
    inputs = _base_inputs(correlation_coefficient=1.0)
    result = compute_total_beta_wacc(inputs)
    assert math.isclose(result.total_beta, result.levered_beta, rel_tol=1e-9)


def test_lower_correlation_produces_higher_cost_of_equity():
    high_r = compute_total_beta_wacc(_base_inputs(correlation_coefficient=0.6))
    low_r = compute_total_beta_wacc(_base_inputs(correlation_coefficient=0.3))
    assert low_r.cost_of_equity > high_r.cost_of_equity


def test_requires_correlation_in_zero_one_range():
    for bad_value in (0.0, -0.2, 1.5):
        try:
            _base_inputs(correlation_coefficient=bad_value)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for correlation_coefficient={bad_value}")


def test_requires_a_debt_cost_source():
    try:
        TotalBetaWaccInputs(
            risk_free_rate=0.04,
            equity_risk_premium=0.05,
            unlevered_beta=0.90,
            correlation_coefficient=0.35,
            tax_rate_marginal=0.25,
            equity_value=800.0,
            debt_value=200.0,
        )
    except ValueError:
        return
    raise AssertionError("expected ValueError when no cost-of-debt source given")


def test_requires_positive_equity_value():
    try:
        _base_inputs(equity_value=0.0)
    except ValueError:
        return
    raise AssertionError("expected ValueError for non-positive equity_value")


def test_uses_book_or_negotiated_value_not_market_value():
    inputs = _base_inputs()
    result = compute_total_beta_wacc(inputs)
    assert math.isclose(result.weight_equity, 800.0 / 1000.0, rel_tol=1e-9)
    assert math.isclose(result.weight_debt, 200.0 / 1000.0, rel_tol=1e-9)


def test_lender_term_sheet_rate_overrides_synthetic_rating():
    inputs = _base_inputs(cost_of_debt_pretax=0.09, interest_coverage_ratio=3.0)
    result = compute_total_beta_wacc(inputs)
    assert result.cost_of_debt_pretax == 0.09
    assert result.synthetic_rating is None


def test_sensitivity_grid_skips_out_of_range_correlation():
    # base correlation 0.35, a -0.4 delta would go to -0.05 -- must be skipped
    inputs = _base_inputs()
    grid = total_beta_wacc_sensitivity(
        inputs, correlation_deltas=(-0.4, 0.0, 0.4), erp_deltas=(0.0,)
    )
    deltas_present = {row["correlation_delta"] for row in grid}
    assert -0.4 not in deltas_present
    assert 0.0 in deltas_present
    assert 0.4 in deltas_present


def test_sensitivity_grid_monotonic_in_correlation():
    inputs = _base_inputs()
    grid = total_beta_wacc_sensitivity(
        inputs, correlation_deltas=(-0.1, 0.0, 0.1), erp_deltas=(0.0,)
    )
    grid_sorted = sorted(grid, key=lambda r: r["correlation_coefficient"])
    waccs = [row["wacc"] for row in grid_sorted]
    # higher correlation -> lower total beta -> lower WACC
    assert waccs[0] > waccs[1] > waccs[2]


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"OK: {t.__name__}")
    print(f"\n{len(tests)} tests passed.")
