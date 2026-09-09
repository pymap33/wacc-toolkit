import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wacc.calculator import WaccInputs, compute_wacc
from wacc.segment import SegmentOverride, compute_segment_wacc, weighted_average_wacc


def _consolidated():
    return WaccInputs(
        risk_free_rate=0.04,
        equity_risk_premium=0.05,
        unlevered_beta=1.0,  # unused directly by segment WACCs, but required by WaccInputs
        tax_rate_marginal=0.25,
        market_value_equity=800.0,
        market_value_debt=200.0,
        interest_coverage_ratio=6.0,
    )


def test_segment_defaults_fall_back_to_consolidated():
    consolidated = _consolidated()
    same_beta_as_consolidated = SegmentOverride(
        name="X", unlevered_beta=consolidated.unlevered_beta, capital_weight=1.0
    )
    results = compute_segment_wacc(consolidated, [same_beta_as_consolidated])
    assert math.isclose(results[0].result.wacc, compute_wacc(consolidated).wacc)


def test_higher_beta_segment_gets_higher_wacc():
    consolidated = _consolidated()
    low_risk = SegmentOverride(name="Stable", unlevered_beta=0.6, capital_weight=0.7)
    high_risk = SegmentOverride(name="Growth", unlevered_beta=1.6, capital_weight=0.3)
    results = compute_segment_wacc(consolidated, [low_risk, high_risk])
    stable, growth = results
    assert stable.result.wacc < growth.result.wacc
    # Same capital-structure weights and cost of debt on both -- the entire
    # gap must come from the beta difference.
    assert stable.result.weight_equity == growth.result.weight_equity
    assert stable.result.cost_of_debt_pretax == growth.result.cost_of_debt_pretax


def test_segment_override_of_cost_of_debt_is_respected():
    consolidated = _consolidated()
    ring_fenced = SegmentOverride(
        name="ProjectCo",
        unlevered_beta=0.9,
        capital_weight=0.2,
        cost_of_debt_pretax=0.09,  # higher, riskier project-finance debt than the parent
    )
    result = compute_segment_wacc(consolidated, [ring_fenced])[0]
    assert result.result.cost_of_debt_pretax == 0.09
    assert result.result.synthetic_rating is None  # a directly supplied cost bypasses the rating lookup


def test_weighted_average_matches_naive_single_segment():
    consolidated = _consolidated()
    one_segment = SegmentOverride(
        name="Whole Company", unlevered_beta=1.2, capital_weight=1.0
    )
    results = compute_segment_wacc(consolidated, [one_segment])
    avg = weighted_average_wacc(results)
    assert math.isclose(avg, results[0].result.wacc)


def test_weighted_average_bounded_by_segment_extremes():
    consolidated = _consolidated()
    low_risk = SegmentOverride(name="Stable", unlevered_beta=0.6, capital_weight=60.0)
    high_risk = SegmentOverride(name="Growth", unlevered_beta=1.6, capital_weight=40.0)
    results = compute_segment_wacc(consolidated, [low_risk, high_risk])
    avg = weighted_average_wacc(results)
    waccs = [r.result.wacc for r in results]
    assert min(waccs) < avg < max(waccs)
    # capital_weight need not be pre-normalized to sum to 1.0
    assert not math.isclose(low_risk.capital_weight + high_risk.capital_weight, 1.0)


def test_weighted_average_rejects_zero_total_weight():
    consolidated = _consolidated()
    seg = SegmentOverride(name="Zero", unlevered_beta=1.0, capital_weight=0.0)
    results = compute_segment_wacc(consolidated, [seg])
    try:
        weighted_average_wacc(results)
    except ValueError:
        return
    raise AssertionError("expected ValueError for zero total capital_weight")


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"OK: {t.__name__}")
    print(f"\n{len(tests)} tests passed.")
