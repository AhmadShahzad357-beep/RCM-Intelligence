"""Tests for suppression-aware aggregation (src/data/suppression.py)."""
import pandas as pd
import pytest

from src.data.suppression import (
    CMS_SUPPRESSION_THRESHOLD,
    add_bounded_enrollment,
    balanced_panel_growth,
    bounded_group_summary,
)


@pytest.fixture
def sample_ma():
    return pd.DataFrame(
        {
            "state": ["TX", "TX", "TX", "CA", "CA", "CA"],
            "county": ["A", "A", "A", "B", "B", "B"],
            "report_month": ["2024-01", "2024-02", "2024-03", "2024-01", "2024-02", "2024-03"],
            "enrolled": [100.0, 110.0, None, 500.0, 520.0, 540.0],
            "enrolled_raw": ["100", "110", ".", "500", "520", "540"],
            "is_enrollment_suppressed": [False, False, True, False, False, False],
            "is_enrollment_numeric": [True, True, False, True, True, True],
        }
    )


def test_add_bounded_enrollment_low_is_zero_for_suppressed(sample_ma):
    out = add_bounded_enrollment(sample_ma)
    suppressed_row = out[out["is_enrollment_suppressed"]]
    assert (suppressed_row["enrolled_low"] == 0).all()


def test_add_bounded_enrollment_high_uses_threshold_minus_one(sample_ma):
    out = add_bounded_enrollment(sample_ma)
    suppressed_row = out[out["is_enrollment_suppressed"]]
    assert (suppressed_row["enrolled_high"] == CMS_SUPPRESSION_THRESHOLD - 1).all()


def test_add_bounded_enrollment_non_suppressed_low_equals_high(sample_ma):
    out = add_bounded_enrollment(sample_ma)
    clean_rows = out[~out["is_enrollment_suppressed"]]
    assert (clean_rows["enrolled_low"] == clean_rows["enrolled_high"]).all()
    assert (clean_rows["enrolled_low"] == clean_rows["enrolled"]).all()


def test_bounded_group_summary_reports_suppression_share(sample_ma):
    ma = add_bounded_enrollment(sample_ma)
    summary = bounded_group_summary(ma, ["state"])
    tx_row = summary[summary["state"] == "TX"].iloc[0]
    assert tx_row["suppressed_rows"] == 1
    assert tx_row["source_rows"] == 3
    assert tx_row["suppressed_row_share"] == pytest.approx(1 / 3)


def test_bounded_group_summary_observed_sum_ignores_suppressed(sample_ma):
    ma = add_bounded_enrollment(sample_ma)
    summary = bounded_group_summary(ma, ["state"])
    tx_row = summary[summary["state"] == "TX"].iloc[0]
    # observed-only sum should only include the two numeric TX rows (100+110)
    assert tx_row["enrolled_base"] == 210.0


def test_balanced_panel_growth_excludes_entities_with_gaps(sample_ma):
    # TX has a suppressed (non-numeric) month, so it should NOT appear in
    # a balanced panel that requires every entity to be numeric every month.
    result = balanced_panel_growth(sample_ma, ["state"])
    assert "TX" not in result["state"].values
    assert "CA" in result["state"].values


def test_balanced_panel_growth_computes_correct_pct(sample_ma):
    result = balanced_panel_growth(sample_ma, ["state"])
    ca_row = result[result["state"] == "CA"].iloc[0]
    # CA: 500 -> 540 = 8% growth
    assert ca_row["growth_pct"] == pytest.approx((540 - 500) / 500)
