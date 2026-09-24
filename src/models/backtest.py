"""Rolling-origin backtest for the national enrollment forecast.

The original approach fit models on a single 3-month holdout and used the
*same* holdout both to pick the winning model and to report its accuracy --
that's selection bias, and with only 29 monthly points a single cutoff can
look great by chance. This module re-runs the holdout test at several
different cutoff points ("rolling origin") and reports the average error
across all of them, plus a naive-baseline comparison (MASE) so a MAPE
number can't be read in isolation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, mean_squared_error

from src.config import PROCESSED_DIR, TABLE_DIR, ensure_dirs

HOLDOUT_MONTHS = 3
MIN_TRAIN_MONTHS = 12  # don't fit a model on fewer than a year of points


def _naive_last_value(train: pd.Series, horizon: int) -> np.ndarray:
    return np.repeat(train.iloc[-1], horizon)


def _moving_average_3m(train: pd.Series, horizon: int) -> np.ndarray:
    return np.repeat(train.tail(3).mean(), horizon)


def _linear_drift(train: pd.Series, horizon: int) -> np.ndarray:
    drift = (train.iloc[-1] - train.iloc[0]) / max(len(train) - 1, 1)
    return np.array([train.iloc[-1] + drift * i for i in range(1, horizon + 1)])


BASELINE_MODELS = {
    "naive_last_value": _naive_last_value,
    "moving_average_3m": _moving_average_3m,
    "linear_drift": _linear_drift,
}


def _mase(actual: np.ndarray, predicted: np.ndarray, train: pd.Series) -> float:
    """Mean Absolute Scaled Error: MAE of the model / MAE of a naive
    one-step-ahead forecast on the training data. < 1 means the model beats
    a naive "next month = this month" forecast; >= 1 means it doesn't.
    """
    naive_errors = train.diff().abs().dropna()
    scale = naive_errors.mean()
    if scale == 0 or np.isnan(scale):
        return float("nan")
    mae = mean_absolute_error(actual, predicted)
    return float(mae / scale)


def rolling_origin_splits(ts: pd.DataFrame, holdout_months: int = HOLDOUT_MONTHS, min_train_months: int = MIN_TRAIN_MONTHS):
    """Yield (train, test) pairs sliding the test window back through history."""
    n = len(ts)
    splits = []
    for end in range(min_train_months + holdout_months, n + 1):
        train = ts.iloc[: end - holdout_months]
        test = ts.iloc[end - holdout_months : end]
        if len(train) < min_train_months or len(test) < holdout_months:
            continue
        splits.append((train, test))
    return splits


def run_backtest(target: str = "observed_enrollment") -> pd.DataFrame:
    ensure_dirs()
    path = PROCESSED_DIR / "ma_scp_monthly_national.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run src.data.load_ma_scp first.")
    ts = pd.read_parquet(path).sort_values("report_month")[["report_month", target]]

    splits = rolling_origin_splits(ts)
    if not splits:
        raise ValueError(
            f"Not enough history for a rolling backtest: {len(ts)} months, "
            f"need at least {MIN_TRAIN_MONTHS + HOLDOUT_MONTHS}."
        )

    rows = []
    for split_id, (train, test) in enumerate(splits):
        train_series = train[target]
        actual = test[target].to_numpy()
        for model_name, fn in BASELINE_MODELS.items():
            pred = fn(train_series, len(test))
            rows.append(
                {
                    "split_id": split_id,
                    "train_end": train["report_month"].iloc[-1],
                    "test_start": test["report_month"].iloc[0],
                    "test_end": test["report_month"].iloc[-1],
                    "model": model_name,
                    "target": target,
                    "mae": mean_absolute_error(actual, pred),
                    "rmse": mean_squared_error(actual, pred) ** 0.5,
                    "mape": mean_absolute_percentage_error(actual, pred),
                    "mase": _mase(actual, pred, train_series),
                }
            )

    detail = pd.DataFrame(rows)
    summary = (
        detail.groupby(["model", "target"], as_index=False)
        .agg(
            n_splits=("split_id", "nunique"),
            mean_mape=("mape", "mean"),
            std_mape=("mape", "std"),
            mean_mase=("mase", "mean"),
            mean_rmse=("rmse", "mean"),
        )
        .sort_values("mean_mape")
    )

    detail.to_csv(TABLE_DIR / "backtest_detail.csv", index=False)
    summary.to_csv(TABLE_DIR / "backtest_summary.csv", index=False)

    print(f"Ran {detail['split_id'].nunique()} rolling-origin splits.")
    print(summary.to_string(index=False))
    print(
        "\nRead mean_mase: < 1.0 means the model beats a naive month-to-month "
        "forecast on average across all splits, not just the final one."
    )
    return summary


def main() -> None:
    run_backtest()


if __name__ == "__main__":
    main()
