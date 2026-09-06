"""Refresh data/industry_betas.json and data/risk_free_rate.json from public
sources. Run periodically (e.g. a monthly GitHub Actions cron) and commit the
output — the browser app only ever reads the committed JSON, never fetches
these sources itself (Pyodide has no raw sockets, and Damodaran's site has no
CORS headers for in-browser fetch anyway).

NOT validated against a live network in this environment — Damodaran
occasionally reshuffles column layout/sheet names in these workbooks between
updates, so check the parsed output once after wiring this into CI before
trusting it unattended.

Requires: pandas, openpyxl, requests (dev-only; not part of the Pyodide app).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

BETAS_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls"
TBOND_URL = "https://www.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2025/all?type=daily_treasury_yield_curve&field_tdr_date_value=2025&page&_format=csv"


def update_industry_betas() -> None:
    resp = requests.get(BETAS_URL, timeout=30)
    resp.raise_for_status()
    tmp_path = DATA_DIR / "_betas_raw.xls"
    tmp_path.write_bytes(resp.content)

    # Damodaran's sheet has a multi-row header block before the data starts;
    # inspect the downloaded file once and adjust `skiprows`/column names
    # below if the layout has changed since this was written.
    df = pd.read_excel(tmp_path, sheet_name="Industry Averages", skiprows=9)
    df = df.rename(
        columns={
            "Industry Name": "industry",
            "Number of firms": "sample_size",
            "Unlevered beta": "unlevered_beta",
        }
    )
    df = df[["industry", "unlevered_beta", "sample_size"]].dropna(subset=["industry"])

    industries = {
        row["industry"]: {
            "unlevered_beta": round(float(row["unlevered_beta"]), 3),
            "sample_size": int(row["sample_size"]),
        }
        for _, row in df.iterrows()
    }

    payload = {
        "_source": BETAS_URL,
        "_as_of": dt.date.today().isoformat(),
        "industries": industries,
    }
    (DATA_DIR / "industry_betas.json").write_text(json.dumps(payload, indent=2))
    tmp_path.unlink(missing_ok=True)


def update_risk_free_rate() -> None:
    df = pd.read_csv(TBOND_URL)
    latest = df.iloc[-1]
    ten_year_pct = float(latest["10 Yr"])
    payload = {
        "_source": "US Treasury daily par yield curve, 10yr",
        "_as_of": str(latest.get("Date", dt.date.today().isoformat())),
        "risk_free_rate": round(ten_year_pct / 100, 5),
    }
    (DATA_DIR / "risk_free_rate.json").write_text(json.dumps(payload, indent=2))


if __name__ == "__main__":
    update_industry_betas()
    update_risk_free_rate()
    print("Data refresh complete.")
