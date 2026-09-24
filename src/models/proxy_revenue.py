"""Proxy revenue: convert enrollment forecasts into a dollar range.

This is NOT a real revenue forecast -- it is a labeled proxy, exactly as
docs/assumptions.md requires: "Revenue forecasting should be presented as
proxy revenue or opportunity forecasting unless internal billing/
remittance data is added." We have no internal billing data, so every
number here stays explicitly a proxy.

PMPM (per-member-per-month) scenario assumptions, sourced from public CMS/
MedPAC reporting rather than invented:
  - CMS's own MA county benchmark example (the max Medicare will pay a
    plan per enrollee/month) is cited publicly around $1,279/month
    (CMS 2026 ratebook methodology, per public secondary reporting).
  - MedPAC (Mar 2026 report to Congress) estimates MA payments run about
    14% higher than FFS spending for comparable beneficiaries, and
    average rebates funding supplemental benefits are about $222 per
    enrollee per month in 2026 (nearly $2,664/year).
  - These are NATIONAL AVERAGES. The actual CMS MA ratebook publishes a
    distinct benchmark per county, which this project does not currently
    download/parse -- using it would let this be a true per-county PMPM
    instead of one national number applied everywhere. That is a clearly
    flagged limitation, not hidden.

Three scenarios (not a single point estimate):
  low  = $1,100/member/month  (below-average-benchmark counties, no rebate uplift)
  base = $1,300/member/month  (near the published national benchmark example)
  high = $1,550/member/month  (benchmark + typical rebate/star-bonus uplift)

Two enrollment bases are reported, per the project owner's explicit
choice: the full national reconciled forecast, and a second, narrower
figure using only the states/counties whose forecast beat a naive
baseline in backtesting (src.models.hierarchical_forecast) -- the second
is the more defensible number to lead with, since it excludes members in
markets where the forecast is not shown to be reliable.
"""
from __future__ import annotations

import pandas as pd

from src.config import TABLE_DIR, ensure_dirs

PMPM_SCENARIOS = {"low": 1100, "base": 1300, "high": 1550}
PMPM_SOURCE_NOTE = (
    "National-average PMPM assumption from public CMS/MedPAC reporting "
    "(2026 MA county benchmark example ~$1,279/month; MedPAC-estimated MA "
    "payments ~14% above FFS; average rebates ~$222/enrollee/month). Not "
    "the actual per-county CMS ratebook -- a single national PMPM is "
    "applied to every member, which is the main precision limitation of "
    "this proxy."
)


def _revenue_table(member_months: float, label: str) -> pd.DataFrame:
    rows = []
    for scenario, pmpm in PMPM_SCENARIOS.items():
        rows.append(
            {
                "basis": label,
                "scenario": scenario,
                "pmpm_assumption": pmpm,
                "member_months_next_3m": member_months,
                "proxy_revenue_next_3m": member_months * pmpm,
            }
        )
    return pd.DataFrame(rows)


def build_proxy_revenue() -> pd.DataFrame:
    ensure_dirs()

    # Basis 1: full national reconciled forecast (from hierarchical_forecast.py).
    hier_summary = pd.read_csv(TABLE_DIR / "hierarchical_reconciliation_summary.csv").iloc[0]
    national_member_months = float(hier_summary["national_forecast_total_next_3m"])
    national_table = _revenue_table(national_member_months, "full_national_reconciled_forecast")

    # Basis 2: only states/counties whose forecast beat naive in backtesting.
    state_fc = pd.read_csv(TABLE_DIR / "hierarchical_state_forecast.csv")
    reliable_states = state_fc[state_fc["beats_naive"]]
    reliable_member_months = float(reliable_states["reconciled_forecast_total_next_3m"].sum())
    reliable_table = _revenue_table(reliable_member_months, "reliable_states_only_beats_naive")

    combined = pd.concat([national_table, reliable_table], ignore_index=True)
    combined["pmpm_source_note"] = PMPM_SOURCE_NOTE
    combined.to_csv(TABLE_DIR / "proxy_revenue_scenarios.csv", index=False)

    reliable_share = reliable_member_months / national_member_months if national_member_months else float("nan")

    print(f"Full national reconciled 3-month member-months: {national_member_months:,.0f}")
    print(f"Reliable-states-only (beats_naive) 3-month member-months: {reliable_member_months:,.0f} ({reliable_share:.1%} of national)")
    print(f"\n{len(reliable_states)} / {len(state_fc)} states included in the reliable-only basis.")
    print("\nProxy revenue by scenario (next 3 months):")
    print(combined[["basis", "scenario", "pmpm_assumption", "proxy_revenue_next_3m"]].to_string(index=False))
    print(f"\n{PMPM_SOURCE_NOTE}")
    return combined


def main() -> None:
    build_proxy_revenue()


if __name__ == "__main__":
    main()
