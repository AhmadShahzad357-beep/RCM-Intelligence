"""Tests for the rolling-origin backtest and MASE calculation
(src/models/backtest.py)."""
import numpy as np
import pandas as pd
import pytest

from src.models.backtest import (
    BASELINE_MODELS,
    _linear_drift,
    _mase,
    _moving_average_3m,
    _naive_last_value,
    rolling_origin_splits,
)


def test_naive_last_value_repeats_last_point():
    train = pd.Series([10, 20, 30])
    result = _naive_last_value(train, horizon=3)
    assert list(result) == [30, 30, 30]


def test_moving_average_3m_uses_last_three_points():
    train = pd.Series([10, 20, 30, 100])  # last 3 = 20,30,100 -> mean 50
    result = _moving_average_3m(train, horizon=2)
    assert list(result) == [50.0, 50.0]


def test_linear_drift_extrapolates_constant_slope():
    train = pd.Series([10, 20, 30, 40])  # slope = 10/month
    result = _linear_drift(train, horizon=2)
    assert result[0] == pytest.approx(50.0)
    assert result[1] == pytest.approx(60.0)


def test_mase_perfect_forecast_is_zero():
    train = pd.Series(range(1, 20))  # steady +1 per step
    actual = np.array([20.0, 21.0, 22.0])
    predicted = np.array([20.0, 21.0, 22.0])
    assert _mase(actual, predicted, train) == pytest.approx(0.0)


def test_mase_naive_forecast_scales_to_roughly_one_for_one_step():
    # A one-step-ahead naive-style error should land near 1.0 when actual
    # error magnitude matches the in-sample naive error magnitude.
    train = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])  # naive in-sample MAE = 1.0
    actual = np.array([6.0])
    predicted = np.array([5.0])  # off by exactly the naive step size
    assert _mase(actual, predicted, train) == pytest.approx(1.0)


def test_mase_returns_nan_when_train_is_flat():
    train = pd.Series([5.0, 5.0, 5.0, 5.0])  # zero naive error -> scale = 0
    actual = np.array([5.0])
    predicted = np.array([6.0])
    assert np.isnan(_mase(actual, predicted, train))


def test_rolling_origin_splits_respects_minimums():
    ts = pd.DataFrame({"report_month": pd.date_range("2020-01-01", periods=20, freq="MS"), "y": range(20)})
    splits = rolling_origin_splits(ts, holdout_months=3, min_train_months=12)
    for train, test in splits:
        assert len(train) >= 12
        assert len(test) == 3


def test_rolling_origin_splits_count_matches_available_windows():
    ts = pd.DataFrame({"report_month": pd.date_range("2020-01-01", periods=20, freq="MS"), "y": range(20)})
    splits = rolling_origin_splits(ts, holdout_months=3, min_train_months=12)
    # windows possible: end ranges from 15 to 20 inclusive -> 6 splits
    assert len(splits) == 6


def test_baseline_models_registry_has_expected_keys():
    assert set(BASELINE_MODELS.keys()) == {"naive_last_value", "moving_average_3m", "linear_drift"}
