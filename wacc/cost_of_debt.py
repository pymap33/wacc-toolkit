"""Synthetic credit rating -> default spread, for companies without a
directly observable marginal cost of debt (no traded bonds, no recent
issuance).

The table below is a static approximation of the interest-coverage-ratio
bucket structure Damodaran publishes and updates periodically
(https://pages.stern.nyu.edu/~adamodar/). It intentionally ships with the
package rather than being scraped live at runtime (see scripts/update_data.py
and data/synthetic_ratings.json) so the browser build has no network
dependency. Refresh data/synthetic_ratings.json periodically and this module
will pick it up; the constants here are the fallback if that file is
missing.

Bucket boundaries are for large-cap, non-financial issuers. Spreads are in
decimal (0.01 = 100 bps) over the risk-free rate.
"""

from __future__ import annotations

import json
from pathlib import Path

_DEFAULT_TABLE = [
    # (min_icr_exclusive, max_icr_inclusive, rating, spread)
    (-999.0, 0.20, "D", 0.1500),
    (0.20, 0.65, "C", 0.1000),
    (0.65, 0.80, "CC", 0.0800),
    (0.80, 1.25, "CCC", 0.0650),
    (1.25, 1.50, "B-", 0.0500),
    (1.50, 1.75, "B", 0.0425),
    (1.75, 2.00, "B+", 0.0350),
    (2.00, 2.50, "BB", 0.0275),
    (2.50, 3.00, "BBB", 0.0200),
    (3.00, 4.25, "A-", 0.0150),
    (4.25, 5.50, "A", 0.0125),
    (5.50, 6.50, "A+", 0.0100),
    (6.50, 8.50, "AA", 0.0080),
    (8.50, 999.0, "AAA", 0.0060),
]


def _load_table() -> list[tuple[float, float, str, float]]:
    data_path = Path(__file__).resolve().parent.parent / "data" / "synthetic_ratings.json"
    if not data_path.exists():
        return _DEFAULT_TABLE
    rows = json.loads(data_path.read_text())
    return [(r["min_icr"], r["max_icr"], r["rating"], r["spread"]) for r in rows]


def synthetic_rating_spread(interest_coverage_ratio: float) -> tuple[str, float]:
    """Map an interest coverage ratio (EBIT / interest expense) to a
    synthetic rating and default spread over the risk-free rate."""
    table = _load_table()
    for min_icr, max_icr, rating, spread in table:
        if min_icr < interest_coverage_ratio <= max_icr:
            return rating, spread
    # Fell off both ends of the table (e.g. NaN input) — treat as distressed.
    return "D", table[0][3]
