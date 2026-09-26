import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wacc.build_up import (
    BuildUpWaccInputs,
    compute_build_up_wacc,
    build_up_wacc_sensitivity,
)


def test_cost_of_equity_is_a_simple_stack_no_beta():
    inputs = BuildUpWaccInputs(
        risk_free_rate=0.04,
        equity_risk_premium=0.05,
        size_premium=0.03,
        company_specific_risk_premium=0.04,
        tax_rate_marginal=0.25,
        equity_value=800.0,
        debt_value=200.0,
        cost_of_debt_pretax=0.08,
    )
    result = compute_build_up_wacc(inputs)
    expected_cost_of_equity = 0.04 + 0.05 + 0.0 + 0.03 + 0.04
    assert math.isclose(result.cost_of_equity, expected_cost_of_equity, rel_tol=1e-9)


def test_industry_risk_premium_is_optional_and_additive():
    base = BuildUpWaccInputs(
        risk_free_rate=0.04,
        equity_risk_premium=0.05,
        size_premium=0.03,
        company_specific_risk_premium=0.04,
        tax_rate_marginal=0.25,
        equity_value=800.0,
        debt_value=200.0,
        cost_of_debt_pretax=0.08,
    )
    with_industry = BuildUpWaccInputs(
        risk_free_rate=0.04,
        equity_risk_premium=0.05,
        size_premium=0.03,
        company_specific_risk_premium=0.04,
        tax_rate_marginal=0.25,
        equity_value=800.0,
        debt_value=200.0,
        cost_of_debt_pretax=0.08,
        industry_risk_premium=0.015,
    )
    r_base = compute_build_up_wacc(base)
    r_with = compute_build_up_wacc(with_industry)
    assert math.isclose(r_with.cost_of_equity - r_base.cost_of_equity, 0.015, rel_tol=1e-9)


def test_compute_build_up_wacc_basic_sanity():
    inputs = BuildUpWaccInputs(
        risk_free_rate=0.04,
        equity_risk_premium=0.05,
        size_premium=0.03,
        company_specific_risk_premium=0.04,
        tax_rate_marginal=0.25,
        equity_value=800.0,
        debt_value=200.0,
        interest_coverage_ratio=3.0,
    )
    result = compute_build_up_wacc(inputs)
    assert result.cost_of_debt_aftertax < result.wacc < result.cost_of_equity
    assert result.weight_equity + result.weight_debt == 1.0
    assert result.synthetic_rating == "BBB"


def test_requires_a_debt_cost_source():
    try:
        BuildUpWaccInputs(
            risk_free_rate=0.04,
            equity_risk_premium=0.05,
            size_premium=0.03,
            company_specific_risk_premium=0.04,
            tax_rate_marginal=0.25,
            equity_value=800.0,
            debt_value=200.0,
        )
    except ValueError:
        return
    raise AssertionError("expected ValueError when no cost-of-debt source given")


def test_requires_positive_equity_value():
    try:
        BuildUpWaccInputs(
            risk_free_rate=0.04,
            equity_risk_premium=0.05,
            size_premium=0.03,
            company_specific_risk_premium=0.04,
            tax_rate_marginal=0.25,
            equity_value=0.0,
            debt_value=200.0,
            cost_of_debt_pretax=0.08,
        )
    except ValueError:
        return
    raise AssertionError("expected ValueError for non-positive equity_value")


def test_lender_term_sheet_rate_overrides_synthetic_rating():
    # If both are given, the directly observed cost wins -- same rule as
    # Calculator 1 -- and no synthetic rating is computed.
    inputs = BuildUpWaccInputs(
        risk_free_rate=0.04,
        equity_risk_premium=0.05,
        size_premium=0.03,
        company_specific_risk_premium=0.04,
        tax_rate_marginal=0.25,
        equity_value=800.0,
        debt_value=200.0,
        cost_of_debt_pretax=0.09,
        interest_coverage_ratio=3.0,  # would imply BBB / a different spread if used
    )
    result = compute_build_up_wacc(inputs)
    assert result.cost_of_debt_pretax == 0.09
    assert result.synthetic_rating is None


def test_sensitivity_grid_shape_and_monotonic_company_specific_premium():
    inputs = BuildUpWaccInputs(
        risk_free_rate=0.04,
        equity_risk_premium=0.05,
        size_premium=0.03,
        company_specific_risk_premium=0.04,
        tax_rate_marginal=0.25,
        equity_value=800.0,
        debt_value=200.0,
        cost_of_debt_pretax=0.08,
    )
    grid = build_up_wacc_sensitivity(
        inputs, size_premium_deltas=(0.0,), company_specific_deltas=(-0.02, 0.0, 0.02)
    )
    assert len(grid) == 3
    waccs = [row["wacc"] for row in grid]
    assert waccs[0] < waccs[1] < waccs[2]


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"OK: {t.__name__}")
    print(f"\n{len(tests)} tests passed.")
