"""Hierarchical (national -> state -> top-county) enrollment forecast.

Method: each series (national, each state, each of the top counties by
latest enrollment) is forecast independently with the linear_drift model.
State forecasts are reconciled to the national forecast by proportional
scaling (top-down reconciliation): every state's forecast is scaled by
the same ratio so they sum exactly to the national number. This is a
simplified reconciliation (proportional scaling), not full MinT/
trace-minimization reconciliation.

Reliability note: MASE < 1.0 is the correct pass/fail threshold only for
ONE-STEP-ahead forecasts. Our holdout is 3 months (multi-step), and a
3-month-ahead naive forecast itself has MASE well above 1.0 purely from
the scale mismatch (denominator is a 1-step in-sample error; numerator is
a 3-step-ahead error). Comparing to a fixed 1.0 threshold on a multi-step
forecast is the wrong test and was corrected here: a series is now
flagged "reliable" if linear_drift's MASE beats the NAIVE model's own
MASE on the same series and same 3-month horizon, not an arbitrary 1.0.

County forecasts are NOT reconciled to their state total, because only
the top N counties by enrollment are modeled here, not every county in
the state -- forcing them to sum to the state total would silently
attribute the state's full growth to a partial set of counties.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import PROCESSED_DIR, TABLE_DIR, ensure_dirs
from src.models.backtest import BASELINE_MODELS, HOLDOUT_MONTHS, MIN_TRAIN_MONTHS, _mase, rolling_origin_splits

FUTURE_MONTHS = 3
TOP_N_COUNTIES = 25
LINEAR_DRIFT = BASELINE_MODELS["linear_drift"]
NAIVE = BASELINE_MODELS["naive_last_value"]


def _forecast_series(ts: pd.DataFrame, target_col: str, future_months: int = FUTURE_MONTHS) -> dict:
    series = ts.sort_values("report_month")[target_col].reset_index(drop=True)
    n_months = len(series)

    forecast_values = LINEAR_DRIFT(series, future_months)

    mean_mase_drift = float("nan")
    mean_mase_naive = float("nan")
    n_splits = 0
    if n_months >= MIN_TRAIN_MONTHS + HOLDOUT_MONTHS:
        ts_sorted = ts.sort_values("report_month").reset_index(drop=True).assign(**{target_col: series})
        splits = rolling_origin_splits(ts_sorted, holdout_months=HOLDOUT_MONTHS, min_train_months=MIN_TRAIN_MONTHS)
        drift_mases, naive_mases = [], []
        for train, test in splits:
            train_series = train[target_col]
            actual = test[target_col].to_numpy()
            drift_mases.append(_mase(actual, LINEAR_DRIFT(train_series, len(test)), train_series))
            naive_mases.append(_mase(actual, NAIVE(train_series, len(test)), train_series))
        if drift_mases:
            mean_mase_drift = float(np.nanmean(drift_mases))
            mean_mase_naive = float(np.nanmean(naive_mases))
            n_splits = len(drift_mases)

    return {
        "n_months_history": n_months,
        "n_backtest_splits": n_splits,
        "mean_mase_linear_drift": mean_mase_drift,
        "mean_mase_naive_baseline": mean_mase_naive,
        "beats_naive": (mean_mase_drift < mean_mase_naive) if n_splits > 0 else False,
        "forecast_total_next_3m": float(forecast_values.sum()),
        "forecast_month_1": float(forecast_values[0]) if len(forecast_values) > 0 else float("nan"),
        "forecast_month_2": float(forecast_values[1]) if len(forecast_values) > 1 else float("nan"),
        "forecast_month_3": float(forecast_values[2]) if len(forecast_values) > 2 else float("nan"),
    }


def _load_national_future_total() -> tuple[float, dict]:
    national_path = PROCESSED_DIR / "ma_scp_monthly_national.parquet"
    national = pd.read_parquet(national_path).sort_values("report_month")
    result = _forecast_series(national, "observed_enrollment")
    return result["forecast_total_next_3m"], result


def build_state_forecasts() -> pd.DataFrame:
    path = PROCESSED_DIR / "ma_scp_state_monthly.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run src.data.load_ma_scp first.")
    state_monthly = pd.read_parquet(path)

    rows = []
    for state, group in state_monthly.groupby("state"):
        result = _forecast_series(group, "observed_enrollment")
        result["state"] = state
        rows.append(result)
    return pd.DataFrame(rows)


def build_county_forecasts(top_n: int = TOP_N_COUNTIES) -> pd.DataFrame:
    growth_path = TABLE_DIR / "ma_scp_county_growth.csv"
    long_path = PROCESSED_DIR / "ma_scp_long.parquet"
    if not growth_path.exists() or not long_path.exists():
        raise FileNotFoundError("Missing county growth or long table. Run src.analysis.growth and src.data.load_ma_scp first.")

    growth = pd.read_csv(growth_path)
    top_counties = growth.nlargest(top_n, "last_enrollment")[["state", "county"]]

    long = pd.read_parquet(long_path)
    county_monthly = (
        long.merge(top_counties, on=["state", "county"], how="inner")
        .groupby(["state", "county", "report_month"], as_index=False)["enrolled"]
        .sum()
        .rename(columns={"enrolled": "observed_enrollment"})
    )

    rows = []
    for (state, county), group in county_monthly.groupby(["state", "county"]):
        result = _forecast_series(group, "observed_enrollment")
        result["state"] = state
        result["county"] = county
        rows.append(result)
    return pd.DataFrame(rows)


def reconcile_and_save() -> None:
    ensure_dirs()

    national_total, national_detail = _load_national_future_total()

    state_fc = build_state_forecasts()
    raw_state_sum = state_fc["forecast_total_next_3m"].sum()
    reconciliation_ratio = national_total / raw_state_sum if raw_state_sum else 1.0
    state_fc["reconciled_forecast_total_next_3m"] = state_fc["forecast_total_next_3m"] * reconciliation_ratio
    state_fc = state_fc.sort_values("reconciled_forecast_total_next_3m", ascending=False)
    state_fc.to_csv(TABLE_DIR / "hierarchical_state_forecast.csv", index=False)

    county_fc = build_county_forecasts()
    county_fc = county_fc.merge(
        state_fc[["state", "reconciled_forecast_total_next_3m"]].rename(
            columns={"reconciled_forecast_total_next_3m": "parent_state_reconciled_forecast"}
        ),
        on="state",
        how="left",
    )
    county_fc["share_of_state_forecast"] = county_fc["forecast_total_next_3m"] / county_fc["parent_state_reconciled_forecast"]
    county_fc = county_fc.sort_values("forecast_total_next_3m", ascending=False)
    county_fc.to_csv(TABLE_DIR / "hierarchical_county_forecast.csv", index=False)

    summary = pd.DataFrame(
        [
            {
                "national_forecast_total_next_3m": national_total,
                "national_mase_linear_drift": national_detail["mean_mase_linear_drift"],
                "national_mase_naive_baseline": national_detail["mean_mase_naive_baseline"],
                "national_beats_naive": national_detail["beats_naive"],
                "raw_sum_of_state_forecasts": raw_state_sum,
                "reconciliation_ratio_applied": reconciliation_ratio,
                "pct_states_beating_naive": state_fc["beats_naive"].mean(),
                "pct_top_counties_beating_naive": county_fc["beats_naive"].mean(),
                "top_n_counties_modeled": TOP_N_COUNTIES,
                "note": "'beats_naive' = linear_drift's MASE is lower than a naive model's own MASE on the same series/horizon -- the correct multi-step comparison, not a fixed MASE<1.0 threshold. County forecasts are not reconciled to state totals; only top N counties are modeled.",
            }
        ]
    )
    summary.to_csv(TABLE_DIR / "hierarchical_reconciliation_summary.csv", index=False)

    print(f"National 3-month-ahead forecast: {national_total:,.0f}")
    print(f"National: linear_drift MASE={national_detail['mean_mase_linear_drift']:.3f} vs naive MASE={national_detail['mean_mase_naive_baseline']:.3f} (beats_naive={national_detail['beats_naive']})")
    print(f"Raw sum of {len(state_fc)} state forecasts: {raw_state_sum:,.0f} (reconciliation ratio: {reconciliation_ratio:.4f})")
    print(f"States where linear_drift beats naive: {state_fc['beats_naive'].sum()} / {len(state_fc)}")
    print(f"Top counties where linear_drift beats naive: {county_fc['beats_naive'].sum()} / {len(county_fc)}")
    print("\nTop 10 states by reconciled forecast:")
    print(state_fc[["state", "reconciled_forecast_total_next_3m", "mean_mase_linear_drift", "mean_mase_naive_baseline", "beats_naive"]].head(10).to_string(index=False))
    print("\nTop 10 counties by forecast:")
    print(county_fc[["state", "county", "forecast_total_next_3m", "share_of_state_forecast", "mean_mase_linear_drift", "beats_naive"]].head(10).to_string(index=False))


def main() -> None:
    reconcile_and_save()


if __name__ == "__main__":
    main()
