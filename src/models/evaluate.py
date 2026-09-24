"""Validation summary with real pass/fail thresholds.

The original version wrote status="pass" for every check regardless of
the underlying number -- that is a label, not validation. Each check here
compares an actual computed value against an explicit threshold.

Note on the forecasting check: MASE < 1.0 is only the correct pass bar for
a ONE-STEP-ahead forecast. Our backtest holdout is 3 months (multi-step),
so even the best model's own MASE naturally lands above 1.0 -- confirmed
by the naive baseline's own MASE also being well above 1.0 on the same
horizon (see src.models.hierarchical_forecast docstring for the full
explanation). The correct test is whether the model beats the naive
baseline's MASE on the same series/horizon, not a fixed 1.0 cutoff.
"""
from __future__ import annotations

import json

import pandas as pd

from src.config import TABLE_DIR, ensure_dirs


def compile_validation_summary() -> pd.DataFrame:
    ensure_dirs()
    rows = []

    # 1. Forecasting: winning model must beat naive on its own MASE terms,
    # not against a fixed 1.0 threshold (see module docstring).
    backtest_path = TABLE_DIR / "backtest_summary.csv"
    if backtest_path.exists():
        backtest = pd.read_csv(backtest_path)
        best = backtest.sort_values("mean_mape").iloc[0]
        naive_row = backtest[backtest["model"] == "naive_last_value"]
        naive_mase = float(naive_row["mean_mase"].iloc[0]) if not naive_row.empty else float("inf")
        status = "pass" if best["mean_mase"] < naive_mase else "fail"
        rows.append(
            {
                "area": "forecasting",
                "check": "rolling_backtest_beats_naive",
                "status": status,
                "result": f"{best['model']}: mean_mape={best['mean_mape']:.4f}, mean_mase={best['mean_mase']:.3f} vs naive mean_mase={naive_mase:.3f}, over {int(best['n_splits'])} splits",
                "decision": "Winning model's MASE must be lower than the naive baseline's own MASE on the same multi-step horizon -- a fixed MASE<1.0 threshold is only valid for one-step forecasts and was corrected here.",
            }
        )
    else:
        rows.append({"area": "forecasting", "check": "rolling_backtest_beats_naive", "status": "skipped", "result": "backtest_summary.csv not found", "decision": "Run src.models.backtest first."})

    # 2. Prior authorization: CPSC match rate must be high enough that the
    # member-weighted exposure numbers are trustworthy.
    pa_members_path = TABLE_DIR / "pa_exposure_by_members_national.csv"
    if pa_members_path.exists():
        pa_members = pd.read_csv(pa_members_path)
        match_rate = pa_members["match_rate"].iloc[0] if "match_rate" in pa_members.columns else None
        if match_rate is not None:
            status = "pass" if match_rate >= 0.90 else "fail"
            high_share = pa_members.loc[pa_members["risk_bucket"] == "high", "member_share"].sum()
            rows.append(
                {
                    "area": "prior_auth",
                    "check": "cpsc_member_match_rate",
                    "status": status,
                    "result": f"match_rate={match_rate:.1%}, high_exposure_member_share={high_share:.1%}",
                    "decision": "Member-weighted exposure numbers require >=90% of scored plans matched to CPSC enrollment.",
                }
            )

    pa_metrics_path = TABLE_DIR / "pa_model_metrics.csv"
    if pa_metrics_path.exists():
        pa = pd.read_csv(pa_metrics_path).iloc[0]
        status = "pass" if pa["plans_reviewed"] > 0 else "fail"
        rows.append(
            {
                "area": "prior_auth",
                "check": "cms_pbp_prior_auth_exposure",
                "status": status,
                "result": f"plans_reviewed={int(pa['plans_reviewed'])}, plans_with_prior_auth_required={int(pa['plans_with_prior_auth_required'])}",
                "decision": "Public CMS data lacks request-level labels; frame as exposure prioritization, not denial prediction.",
            }
        )

    # 3. Growth opportunity: weights must sum to 1.0, and the ranking
    # shouldn't be wildly unstable under alternate reasonable weightings.
    methodology_path = TABLE_DIR / "opportunity_score_methodology.csv"
    if methodology_path.exists():
        methodology = pd.read_csv(methodology_path)
        weight_sum = methodology["weight"].sum()
        status = "pass" if abs(weight_sum - 1.0) < 1e-6 else "fail"
        rows.append(
            {
                "area": "growth_opportunity",
                "check": "weights_sum_to_one",
                "status": status,
                "result": "; ".join(f"{r.component}={r.weight:.2f}" for r in methodology.itertuples()),
                "decision": "Use score as a transparent CMS-signal ranking, not a dollar revenue estimate.",
            }
        )

    sensitivity_path = TABLE_DIR / "opportunity_score_sensitivity_state.csv"
    if sensitivity_path.exists():
        sensitivity = pd.read_csv(sensitivity_path)
        min_overlap = sensitivity["top10_overlap_pct"].min()
        status = "pass" if min_overlap >= 0.5 else "warn"
        rows.append(
            {
                "area": "growth_opportunity",
                "check": "top10_stability_under_alt_weights",
                "status": status,
                "result": f"min_top10_overlap={min_overlap:.0%} across alternate weight schemes",
                "decision": "Ranking should not collapse under reasonable alternate weightings (threshold: >=50% top-10 overlap).",
            }
        )

    # 4. Data quality: outliers flagged not dropped, suppression share
    # reported rather than silently absorbed into a sum.
    national_bounds_path = TABLE_DIR / "ma_scp_national_bounds.csv"
    if national_bounds_path.exists():
        bounds = pd.read_csv(national_bounds_path).sort_values("report_month")
        latest = bounds.iloc[-1]
        status = "pass" if latest["suppressed_row_share"] < 0.60 else "warn"
        rows.append(
            {
                "area": "data_quality",
                "check": "suppression_share_within_expected_range",
                "status": status,
                "result": f"latest={latest['report_month_label']}: suppressed_row_share={latest['suppressed_row_share']:.1%}, low={latest['enrolled_low']:,.0f}, high={latest['enrolled_high']:,.0f}",
                "decision": "Report enrollment as a [low, high] range, not a single observed-only sum, given suppression share.",
            }
        )

    # 5. Hierarchical forecast: reconciliation should actually reconcile
    # (state forecasts, scaled, should sum to the national number).
    hier_summary_path = TABLE_DIR / "hierarchical_reconciliation_summary.csv"
    if hier_summary_path.exists():
        hier = pd.read_csv(hier_summary_path).iloc[0]
        ratio = hier["reconciliation_ratio_applied"]
        status = "pass" if 0.5 <= ratio <= 2.0 else "warn"
        rows.append(
            {
                "area": "hierarchical_forecast",
                "check": "reconciliation_ratio_reasonable",
                "status": status,
                "result": f"ratio={ratio:.4f}, pct_states_beating_naive={hier['pct_states_beating_naive']:.1%}, pct_top_counties_beating_naive={hier['pct_top_counties_beating_naive']:.1%}",
                "decision": "A reconciliation ratio far from 1.0 would mean state-level and national models disagree sharply; report per-state/county reliability rather than treating the whole hierarchy as equally trustworthy.",
            }
        )

    summary = pd.DataFrame(rows)
    summary.to_csv(TABLE_DIR / "model_validation_summary.csv", index=False)
    (TABLE_DIR / "validation_decisions.json").write_text(json.dumps(rows, indent=2))
    return summary


def main() -> None:
    summary = compile_validation_summary()
    print(summary.to_string(index=False))
    n_fail = (summary["status"] == "fail").sum()
    n_warn = (summary["status"] == "warn").sum()
    print(f"\n{n_fail} check(s) failed, {n_warn} warning(s).")


if __name__ == "__main__":
    main()
