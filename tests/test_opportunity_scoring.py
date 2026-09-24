"""Tests for opportunity-score ranking logic
(src/models/opportunity_scoring.py)."""
import pandas as pd
import pytest

from src.models.opportunity_scoring import WEIGHTS, _add_ranks, _score, percentile


def test_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_percentile_ranks_between_zero_and_one():
    s = pd.Series([10, 20, 30, 40])
    ranks = percentile(s)
    assert ranks.min() >= 0
    assert ranks.max() <= 1
    # highest value should have the highest percentile rank
    assert ranks.iloc[3] == ranks.max()


def test_percentile_fills_missing_with_zero():
    s = pd.Series([10, None, 30])
    ranks = percentile(s)
    assert ranks.iloc[1] == 0


def test_headroom_rank_is_inverse_of_penetration():
    # This is the specific bug fixed in the review: low penetration
    # (more headroom) should score HIGHER, not lower.
    df = pd.DataFrame(
        {
            "growth_pct": [0.1, 0.1],
            "last_enrollment": [1000, 1000],
            "avg_mom_growth_pct": [0.01, 0.01],
            "ma_penetration": [0.20, 0.80],  # first has low penetration, second high
        }
    )
    ranked = _add_ranks(df)
    low_pen_headroom = ranked.iloc[0]["headroom_rank"]
    high_pen_headroom = ranked.iloc[1]["headroom_rank"]
    assert low_pen_headroom > high_pen_headroom


def test_score_is_between_zero_and_hundred():
    df = pd.DataFrame(
        {
            "growth_pct": [0.05, 0.10, 0.20],
            "last_enrollment": [1000, 5000, 10000],
            "avg_mom_growth_pct": [0.01, 0.02, 0.03],
            "ma_penetration": [0.3, 0.5, 0.1],
        }
    )
    ranked = _add_ranks(df)
    scores = _score(ranked, WEIGHTS)
    assert scores.between(0, 100).all()


def test_higher_growth_scale_and_headroom_gives_higher_score():
    df = pd.DataFrame(
        {
            "growth_pct": [0.01, 0.30],
            "last_enrollment": [100, 100000],
            "avg_mom_growth_pct": [0.001, 0.03],
            "ma_penetration": [0.9, 0.1],
        }
    )
    ranked = _add_ranks(df)
    scores = _score(ranked, WEIGHTS)
    # second row dominates on all three components -> must score higher
    assert scores.iloc[1] > scores.iloc[0]
