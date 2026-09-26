import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wacc.fama_french import (
    FamaFrenchWaccInputs,
    compute_fama_french_wacc,
    fama_french_wacc_sensitivity,
)


def _base_inputs(**overrides):
    defaults = dict(
        risk_free_rate=0.04,
        market_risk_premium=0.05,
        smb_premium=0.02,
        hml_premium=0.03,
        beta_mkt=1.10,
        beta_smb=0.40,
        beta_hml=0.20,
        tax_rate_marginal=0.25,
        market_value_equity=800.0,
        market_value_debt=200.0,
        cost_of_debt_pretax=0.05,
    )
    defaults.update(overrides)
    return FamaFrenchWaccInputs(**defaults)


def test_cost_of_equity_is_three_factor_sum():
    inputs = _base_inputs()
    result = compute_fama_french_wacc(inputs)
    expected = 0.04 + 1.10 * 0.05 + 0.40 * 0.02 + 0.20 * 0.03
    assert math.isclose(result.cost_of_equity, expected, rel_tol=1e-9)


def test_factor_contributions_sum_to_excess_cost_of_equity():
    inputs = _base_inputs()
    result = compute_fama_french_wacc(inputs)
    total_excess = (
        result.market_factor_contribution
        + result.smb_factor_contribution
        + result.hml_factor_contribution
    )
    assert math.isclose(
        result.cost_of_equity - inputs.risk_free_rate, total_excess, rel_tol=1e-9
    )


def test_zero_smb_and_hml_beta_collapses_to_plain_capm():
    inputs = _base_inputs(beta_smb=0.0, beta_hml=0.0)
    result = compute_fama_french_wacc(inputs)
    expected_capm = 0.04 + 1.10 * 0.05
    assert math.isclose(result.cost_of_equity, expected_capm, rel_tol=1e-9)


def test_higher_smb_beta_increases_cost_of_equity_when_smb_premium_positive():
    low = compute_fama_french_wacc(_base_inputs(beta_smb=0.1))
    high = compute_fama_french_wacc(_base_inputs(beta_smb=0.8))
    assert high.cost_of_equity > low.cost_of_equity


def test_requires_positive_market_value_equity():
    try:
        _base_inputs(market_value_equity=0.0)
    except ValueError:
        return
    raise AssertionError("expected ValueError for non-positive market_value_equity")


def test_no_synthetic_rating_fallback_field_exists():
    # FamaFrenchWaccInputs has no interest_coverage_ratio parameter at all --
    # cost_of_debt_pretax is a required positional-or-keyword field.
    import inspect

    fields = inspect.signature(FamaFrenchWaccInputs).parameters
    assert "interest_coverage_ratio" not in fields
    assert "cost_of_debt_pretax" in fields


def test_uses_market_value_weights():
    inputs = _base_inputs()
    result = compute_fama_french_wacc(inputs)
    assert math.isclose(result.weight_equity, 800.0 / 1000.0, rel_tol=1e-9)
    assert math.isclose(result.weight_debt, 200.0 / 1000.0, rel_tol=1e-9)


def test_sensitivity_grid_shape_and_monotonic_smb():
    inputs = _base_inputs()
    grid = fama_french_wacc_sensitivity(
        inputs, smb_beta_deltas=(-0.2, 0.0, 0.2), hml_beta_deltas=(0.0,)
    )
    assert len(grid) == 3
    grid_sorted = sorted(grid, key=lambda r: r["beta_smb"])
    waccs = [row["wacc"] for row in grid_sorted]
    assert waccs[0] < waccs[1] < waccs[2]


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"OK: {t.__name__}")
    print(f"\n{len(tests)} tests passed.")
