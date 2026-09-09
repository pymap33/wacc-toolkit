"""Segment-level (sum-of-parts) WACC.

A single company-level WACC assumes every dollar of invested capital faces
the same business risk. That assumption breaks down for a conglomerate with
genuinely different-risk segments (a regulated grid business bolted onto a
merchant renewables business, a stable device franchise bolted onto a
newly-acquired high-growth one) -- one blended number misprices whichever
segment is furthest from the company-level average.

This module runs the existing `compute_wacc` once per segment, swapping in
that segment's own bottom-up beta (the thing that actually differs by
business), while defaulting every other input -- capital-structure weights,
cost of debt, tax rate -- to the consolidated company. That default matters:
debt is almost always issued at the whole-company level, not allocated to a
segment on the balance sheet, so there is usually no segment-specific weight
or cost-of-debt figure to use even in principle. Override a field only when
the segment genuinely has its own disclosed capital structure (e.g. a
ring-fenced project-finance subsidiary).
"""

from __future__ import annotations

from dataclasses import dataclass

from .calculator import WaccInputs, WaccResult, compute_wacc


@dataclass
class SegmentOverride:
    """Per-segment inputs. Only `unlevered_beta` is required to differ from
    the consolidated company in the typical case -- every other field left
    as None falls back to the `consolidated` WaccInputs passed to
    `compute_segment_wacc`.
    """

    name: str
    unlevered_beta: float
    capital_weight: float  # this segment's share of total invested capital (or revenue/EBIT, caller's choice) -- used only by weighted_average_wacc, not by the segment's own WACC
    tax_rate_marginal: float | None = None
    cost_of_debt_pretax: float | None = None
    interest_coverage_ratio: float | None = None
    market_value_equity: float | None = None
    market_value_debt: float | None = None
    market_value_preferred: float | None = None
    size_premium: float | None = None


@dataclass
class SegmentWaccResult:
    name: str
    capital_weight: float
    result: WaccResult


def compute_segment_wacc(
    consolidated: WaccInputs, segments: list[SegmentOverride]
) -> list[SegmentWaccResult]:
    """One WACC per segment, defaulting unset fields to `consolidated`.

    `capital_weight` values need not sum to 1.0 here -- normalization
    happens in `weighted_average_wacc`, so callers can pass raw dollars
    (invested capital, revenue) instead of pre-computed shares.
    """
    out = []
    for seg in segments:
        if seg.cost_of_debt_pretax is not None or seg.interest_coverage_ratio is not None:
            cost_of_debt_pretax = seg.cost_of_debt_pretax
            interest_coverage_ratio = seg.interest_coverage_ratio
        else:
            cost_of_debt_pretax = consolidated.cost_of_debt_pretax
            interest_coverage_ratio = consolidated.interest_coverage_ratio

        seg_inputs = WaccInputs(
            risk_free_rate=consolidated.risk_free_rate,
            equity_risk_premium=consolidated.equity_risk_premium,
            unlevered_beta=seg.unlevered_beta,
            tax_rate_marginal=(
                seg.tax_rate_marginal
                if seg.tax_rate_marginal is not None
                else consolidated.tax_rate_marginal
            ),
            market_value_equity=(
                seg.market_value_equity
                if seg.market_value_equity is not None
                else consolidated.market_value_equity
            ),
            market_value_debt=(
                seg.market_value_debt
                if seg.market_value_debt is not None
                else consolidated.market_value_debt
            ),
            market_value_preferred=(
                seg.market_value_preferred
                if seg.market_value_preferred is not None
                else consolidated.market_value_preferred
            ),
            cost_of_debt_pretax=cost_of_debt_pretax,
            interest_coverage_ratio=interest_coverage_ratio,
            preferred_dividend_yield=consolidated.preferred_dividend_yield,
            size_premium=(
                seg.size_premium if seg.size_premium is not None else consolidated.size_premium
            ),
        )
        out.append(
            SegmentWaccResult(
                name=seg.name,
                capital_weight=seg.capital_weight,
                result=compute_wacc(seg_inputs),
            )
        )
    return out


def weighted_average_wacc(segment_results: list[SegmentWaccResult]) -> float:
    """Sum-of-parts WACC: capital-weighted average of segment WACCs.

    Compare this against `compute_wacc(consolidated).wacc` computed directly
    -- if the two are close, segment business risk isn't differentiated
    enough to matter and the simpler company-level number is fine for
    segment work too. If they diverge, the sum-of-parts number is the more
    defensible discount rate for valuing a segment in isolation (e.g. a
    single business unit's EBITDA), even though the company-level WACC
    remains correct for whole-company valuation.
    """
    total_weight = sum(s.capital_weight for s in segment_results)
    if total_weight <= 0:
        raise ValueError("Sum of capital_weight across segments must be positive")
    return sum(s.capital_weight * s.result.wacc for s in segment_results) / total_weight
