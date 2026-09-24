from __future__ import annotations

import pandas as pd

CMS_SUPPRESSION_THRESHOLD = 11
SUPPRESSED_HIGH_FILL = CMS_SUPPRESSION_THRESHOLD - 1


def add_bounded_enrollment(ma: pd.DataFrame) -> pd.DataFrame:
    out = ma.copy()
    out["enrolled_low"] = out["enrolled"].fillna(0)
    out["enrolled_high"] = out["enrolled"].where(
        ~out["is_enrollment_suppressed"], SUPPRESSED_HIGH_FILL
    )
    out["enrolled_high"] = out["enrolled_high"].fillna(out["enrolled_low"])
    return out


def bounded_group_summary(ma: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    g = (
        ma.groupby(group_cols, as_index=False)
        .agg(
            enrolled_base=("enrolled", "sum"),
            enrolled_low=("enrolled_low", "sum"),
            enrolled_high=("enrolled_high", "sum"),
            source_rows=("enrolled_raw", "size"),
            suppressed_rows=("is_enrollment_suppressed", "sum"),
        )
    )
    g["suppressed_row_share"] = g["suppressed_rows"] / g["source_rows"]
    g["enrolled_bound_width"] = g["enrolled_high"] - g["enrolled_low"]
    return g


def balanced_panel_growth(
    ma: pd.DataFrame,
    entity_cols: list[str],
    period_col: str = "report_month",
) -> pd.DataFrame:
    clean = ma[ma["is_enrollment_numeric"]].copy()
    n_periods = ma.groupby(period_col)[period_col].size().shape[0]

    counts = clean.groupby(entity_cols)[period_col].nunique()
    always_numeric = counts[counts == n_periods].index

    if isinstance(always_numeric, pd.MultiIndex):
        mask = clean.set_index(entity_cols).index.isin(always_numeric)
    else:
        mask = clean[entity_cols[0]].isin(always_numeric)
    balanced = clean[mask]

    balanced = balanced.groupby(entity_cols + [period_col], as_index=False)["enrolled"].sum()
    balanced = balanced.sort_values(entity_cols + [period_col])

    first = balanced.groupby(entity_cols, as_index=False).first().rename(
        columns={"enrolled": "first_enrollment", period_col: "first_period"}
    )
    last = balanced.groupby(entity_cols, as_index=False).last().rename(
        columns={"enrolled": "last_enrollment", period_col: "last_period"}
    )
    out = first.merge(last, on=entity_cols)
    out["growth_abs"] = out["last_enrollment"] - out["first_enrollment"]
    out["growth_pct"] = out["growth_abs"] / out["first_enrollment"]

    mom = balanced.copy()
    mom["mom_growth_pct"] = mom.groupby(entity_cols)["enrolled"].pct_change()
    momentum = mom.groupby(entity_cols, as_index=False)["mom_growth_pct"].mean().rename(
        columns={"mom_growth_pct": "avg_mom_growth_pct"}
    )
    out = out.merge(momentum, on=entity_cols, how="left")
    return out.sort_values("growth_pct", ascending=False)
