"""Payer (parent organization) scorecard.

Combines three signals per payer, all from public CMS data:
  1. Growth  -- CPSC contract-level enrollment, first vs. latest month
  2. Scale   -- latest total enrollment
  3. PA burden -- member-weighted share of that payer's enrollment sitting
     in high prior-authorization-exposure plans

Data-quality guards applied here (found from a first real run):
  - enrolled_mid now uses the SAME suppression low/high midpoint formula
    as src/data/load_cpsc.py. An earlier version of this file used a
    different formula in load_cpsc_payer.py, which made pa_match_rate
    exceed 100% for some payers -- two independently-aggregated numbers
    that should have matched didn't, because they used different
    suppressed-cell assumptions.
  - Eligibility for ranking now requires a minimum enrollment at BOTH the
    first and latest snapshot, not just the latest. Without that, a payer
    that went from ~50 to ~2,000 members shows as "3,785% growth" and can
    dominate the ranking on a tiny, noisy base.
  - pa_match_rate is clipped for display and flagged if the two
    enrollment sources disagree by more than 5%, since a payer-level
    number built on a poor match is misleading even when the run overall
    looks fine.
"""
from __future__ import annotations

import pandas as pd

from src.config import PROCESSED_DIR, TABLE_DIR, ensure_dirs
from src.data.load_cpsc_payer import load_cpsc_contract_info, load_first_and_latest_contract_enrollment

MIN_MEMBERS = 5000
MIN_PA_MATCH = 0.50
MATCH_RATE_FLAG_THRESHOLD = 1.05  # >105% signals the two sources disagree


def _load_pa_scores() -> pd.DataFrame:
    pa_path = PROCESSED_DIR / "prior_auth_exposure.csv"
    if not pa_path.exists():
        pa_path = PROCESSED_DIR / "pa_predictions.csv"
    pa = pd.read_csv(pa_path, dtype={"contract_id": str, "plan_id": str})
    pa["plan_id"] = pa["plan_id"].fillna("").astype(str)
    pa["plan_id"] = pa["plan_id"].where(pa["plan_id"].eq(""), pa["plan_id"].str.zfill(3))
    return pa[["contract_id", "plan_id", "risk_bucket", "prior_auth_exposure_score"]]


def _load_plan_enrollment_latest() -> pd.DataFrame:
    path = PROCESSED_DIR / "cpsc_plan_enrollment_latest.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run src.data.load_cpsc first.")
    return pd.read_parquet(path)[["contract_id", "plan_id", "enrolled_mid"]]


def build_payer_scorecard() -> pd.DataFrame:
    ensure_dirs()
    first, latest = load_first_and_latest_contract_enrollment()
    info = load_cpsc_contract_info()

    growth = first[["contract_id", "enrolled_mid"]].rename(columns={"enrolled_mid": "enrolled_first"}).merge(
        latest[["contract_id", "enrolled_mid"]].rename(columns={"enrolled_mid": "enrolled_latest"}),
        on="contract_id",
        how="outer",
    )
    growth["contract_status"] = "continuing"
    growth.loc[growth["enrolled_first"].isna(), "contract_status"] = "new_since_first_month"
    growth.loc[growth["enrolled_latest"].isna(), "contract_status"] = "terminated_since_first_month"
    growth["enrolled_first"] = growth["enrolled_first"].fillna(0)
    growth["enrolled_latest"] = growth["enrolled_latest"].fillna(0)

    growth = growth.merge(info, on="contract_id", how="left")
    growth["parent_organization"] = growth["parent_organization"].fillna(growth["organization"]).fillna("Unknown")
    growth["parent_organization"] = growth["parent_organization"].astype(str)

    payer_growth = growth.groupby("parent_organization", as_index=False).agg(
        enrolled_first=("enrolled_first", "sum"),
        enrolled_latest=("enrolled_latest", "sum"),
        contracts_continuing=("contract_status", lambda s: (s == "continuing").sum()),
        contracts_new=("contract_status", lambda s: (s == "new_since_first_month").sum()),
        contracts_terminated=("contract_status", lambda s: (s == "terminated_since_first_month").sum()),
    )
    payer_growth["growth_abs"] = payer_growth["enrolled_latest"] - payer_growth["enrolled_first"]
    payer_growth["growth_pct"] = payer_growth["growth_abs"] / payer_growth["enrolled_first"].replace(0, pd.NA)

    pa = _load_pa_scores()
    plan_enroll = _load_plan_enrollment_latest()
    pa_weighted = pa.merge(plan_enroll, on=["contract_id", "plan_id"], how="inner")
    pa_weighted = pa_weighted.merge(info[["contract_id", "parent_organization"]], on="contract_id", how="left")
    pa_weighted["parent_organization"] = pa_weighted["parent_organization"].fillna("Unknown").astype(str)

    pa_by_payer = pa_weighted.groupby("parent_organization", as_index=False).apply(
        lambda g: pd.Series(
            {
                "matched_members": g["enrolled_mid"].sum(),
                "high_exposure_members": g.loc[g["risk_bucket"].eq("high"), "enrolled_mid"].sum(),
                "avg_exposure_score_member_weighted": (
                    (g["prior_auth_exposure_score"] * g["enrolled_mid"]).sum() / g["enrolled_mid"].sum()
                    if g["enrolled_mid"].sum() > 0 else float("nan")
                ),
            }
        ),
        include_groups=False,
    ).reset_index()
    pa_by_payer["high_exposure_member_share"] = (
        pa_by_payer["high_exposure_members"] / pa_by_payer["matched_members"].replace(0, pd.NA)
    )

    scorecard = payer_growth.merge(pa_by_payer, on="parent_organization", how="left")
    scorecard["pa_match_rate"] = scorecard["matched_members"] / scorecard["enrolled_latest"].replace(0, pd.NA)
    scorecard["pa_match_rate_flagged"] = scorecard["pa_match_rate"].fillna(0) > MATCH_RATE_FLAG_THRESHOLD

    scorecard["growth_rank"] = scorecard["growth_pct"].rank(pct=True).fillna(0)
    scorecard["scale_rank"] = scorecard["enrolled_latest"].rank(pct=True).fillna(0)
    scorecard["pa_burden_rank"] = scorecard["avg_exposure_score_member_weighted"].rank(pct=True).fillna(0)

    scorecard["priority_score"] = (
        100 * (0.40 * scorecard["growth_rank"] + 0.30 * scorecard["scale_rank"] + 0.30 * scorecard["pa_burden_rank"])
    ).round(2)

    # Require minimum scale at BOTH snapshots -- otherwise a payer growing
    # off a tiny base (e.g. 50 -> 2,000 members) shows an explosive,
    # unstable growth_pct that dominates the ranking on noise.
    eligible = (
        (scorecard["enrolled_latest"] >= MIN_MEMBERS)
        & (scorecard["enrolled_first"] >= MIN_MEMBERS)
        & (scorecard["pa_match_rate"].fillna(0) >= MIN_PA_MATCH)
        & (~scorecard["pa_match_rate_flagged"])
    )
    scorecard["eligible_for_ranking"] = eligible

    scorecard = scorecard.sort_values("priority_score", ascending=False)
    scorecard.to_csv(TABLE_DIR / "payer_scorecard_full.csv", index=False)

    ranked = scorecard[scorecard["eligible_for_ranking"]].copy()
    ranked.to_csv(TABLE_DIR / "payer_scorecard_ranked.csv", index=False)

    n_flagged = int(scorecard["pa_match_rate_flagged"].sum())
    print(
        f"Scored {len(scorecard)} parent organizations; {len(ranked)} eligible for ranking "
        f"(>= {MIN_MEMBERS:,} members at both snapshots, >= {MIN_PA_MATCH:.0%} PA match). "
        f"{n_flagged} payer(s) flagged for pa_match_rate > {MATCH_RATE_FLAG_THRESHOLD:.0%} (excluded from ranking, kept in full file)."
    )
    cols = ["parent_organization", "priority_score", "enrolled_first", "enrolled_latest", "growth_pct", "high_exposure_member_share", "pa_match_rate"]
    print(ranked[cols].head(15).to_string(index=False))
    return scorecard


def main() -> None:
    build_payer_scorecard()


if __name__ == "__main__":
    main()
