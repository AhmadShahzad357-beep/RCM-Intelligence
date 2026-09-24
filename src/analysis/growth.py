"""Build state/county growth tables from the processed long table.

This replaces the notebook-only step that used to produce
ma_scp_state_growth.csv / ma_scp_county_growth.csv -- those files were
required by src/models/opportunity_scoring.py but nothing in src/ created
them, so scripts/run_pipeline.ps1 alone could not reproduce the pipeline.
Running this script after src.data.load_ma_scp now produces both files,
using the suppression-safe balanced panel from src/data/suppression.py.

County growth also carries a representative FIPS code, so
opportunity_scoring.py can merge against the penetration file on FIPS
instead of on state+county name text (which is prone to St./Saint-style
mismatches).
"""
from __future__ import annotations

import pandas as pd

from src.config import PROCESSED_DIR, TABLE_DIR, ensure_dirs
from src.data.suppression import add_bounded_enrollment, balanced_panel_growth, bounded_group_summary


def load_long() -> pd.DataFrame:
    path = PROCESSED_DIR / "ma_scp_long.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run src.data.load_ma_scp first.")
    return pd.read_parquet(path)


def _representative_fips(ma: pd.DataFrame) -> pd.DataFrame:
    """One FIPS code per state+county: the most frequently reported value,
    since a handful of source rows can carry blank/inconsistent FIPS.
    """
    have_fips = ma[ma["fips_code"].notna()].copy()
    counts = (
        have_fips.groupby(["state", "county", "fips_code"], as_index=False)
        .size()
        .sort_values("size", ascending=False)
    )
    rep = counts.drop_duplicates(["state", "county"], keep="first")
    rep["fips"] = rep["fips_code"].astype("Int64").astype(str).str.zfill(5)
    return rep[["state", "county", "fips"]]


def build_growth_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    ensure_dirs()
    ma = add_bounded_enrollment(load_long())

    state = balanced_panel_growth(ma, ["state"])
    county = balanced_panel_growth(ma, ["state", "county"])

    state_supp = bounded_group_summary(ma, ["state"])[["state", "suppressed_row_share"]]
    county_supp = bounded_group_summary(ma, ["state", "county"])[["state", "county", "suppressed_row_share"]]
    state = state.merge(state_supp, on="state", how="left")
    county = county.merge(county_supp, on=["state", "county"], how="left")

    fips_lookup = _representative_fips(ma)
    county = county.merge(fips_lookup, on=["state", "county"], how="left")
    unmatched = county["fips"].isna().sum()
    if unmatched:
        print(f"Warning: {unmatched} / {len(county)} counties have no FIPS code from source data (will fall back to name match).")

    state.to_csv(TABLE_DIR / "ma_scp_state_growth.csv", index=False)
    county.to_csv(TABLE_DIR / "ma_scp_county_growth.csv", index=False)

    print(
        f"State growth: {state.attrs.get('entities_in_balanced_panel')} / "
        f"{state.attrs.get('entities_seen_total')} states had a full "
        f"{state.attrs.get('n_periods')}-month numeric panel."
    )
    print(
        f"County growth: {county.attrs.get('entities_in_balanced_panel')} / "
        f"{county.attrs.get('entities_seen_total')} counties had a full "
        f"{county.attrs.get('n_periods')}-month numeric panel."
    )
    return state, county


def main() -> None:
    build_growth_tables()


if __name__ == "__main__":
    main()
