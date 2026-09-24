"""Member-weighted prior-authorization exposure.

pa_classifier.py scores each plan's PA exposure but treats every plan
equally regardless of size -- a plan with 50 members counts the same as
one with 500,000. This module joins those plan-level scores to actual
CPSC enrollment so exposure can be reported the way RCM teams actually
care about it: "what share of MA *members* (not plans) are in
high-exposure plans."

This replaces the old delay_predictor.py, which computed a second score
using the same formula as pa_classifier.py under a different name and
attached fixed 72-hour/7-day CMS timing constants to every plan with no
real timing data behind them -- that was not a distinct model, it just
relabeled the same number. Public CMS files do not contain per-request
decision-timing data, so we are not able to build a real timing-delay
model from this data, and we are not going to fake one.
"""
from __future__ import annotations

import pandas as pd

from src.config import PROCESSED_DIR, TABLE_DIR, ensure_dirs
from src.data.load_cpsc import load_latest_cpsc_plan_enrollment


def run_member_weighted_exposure() -> pd.DataFrame:
    ensure_dirs()
    pa_path = PROCESSED_DIR / "prior_auth_exposure.csv"
    if not pa_path.exists():
        pa_path = PROCESSED_DIR / "pa_predictions.csv"
    pa = pd.read_csv(pa_path, dtype={"contract_id": str, "plan_id": str})
    pa["plan_id"] = pa["plan_id"].fillna("").astype(str)
    pa["plan_id"] = pa["plan_id"].where(pa["plan_id"].eq(""), pa["plan_id"].str.zfill(3))

    try:
        enrollment = load_latest_cpsc_plan_enrollment()
    except FileNotFoundError as exc:
        print(f"CPSC enrollment not available ({exc}); falling back to plan-count-only summary.")
        summary = pa.groupby(["plan_type", "risk_bucket"], as_index=False).agg(plans=("contract_id", "count"))
        summary["enrollment_weighted"] = False
        summary.to_csv(TABLE_DIR / "pa_exposure_by_members.csv", index=False)
        return summary

    merged = pa.merge(enrollment, on=["contract_id", "plan_id"], how="left")
    match_rate = merged["enrolled_mid"].notna().mean()
    print(f"Matched {match_rate:.1%} of scored plans to CPSC enrollment by contract_id + plan_id.")

    merged["enrolled_mid"] = merged["enrolled_mid"].fillna(0)
    merged["enrollment_weighted"] = True

    national = merged.groupby("risk_bucket", as_index=False).agg(
        plans=("contract_id", "count"),
        members=("enrolled_mid", "sum"),
    )
    total_members = national["members"].sum()
    national["member_share"] = national["members"] / total_members if total_members else 0.0
    national["match_rate"] = match_rate
    national.to_csv(TABLE_DIR / "pa_exposure_by_members_national.csv", index=False)

    by_type = merged.groupby(["plan_type", "risk_bucket"], as_index=False).agg(
        plans=("contract_id", "count"),
        members=("enrolled_mid", "sum"),
    )
    by_type.to_csv(TABLE_DIR / "pa_exposure_by_members.csv", index=False)

    print(national.to_string(index=False))
    high_share = national.loc[national["risk_bucket"] == "high", "member_share"].sum()
    print(
        f"\n{high_share:.1%} of matched MA members are enrolled in high "
        "prior-authorization-exposure plans (member-weighted, not plan-count-weighted)."
    )
    return national


def main() -> None:
    run_member_weighted_exposure()


if __name__ == "__main__":
    main()
