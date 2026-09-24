"""Growth-opportunity scoring for states and counties.

Fixes applied here (see project review):
1. growth_rate_rank and momentum_rank were both derived from the same
   underlying month-over-month trend and weighted separately -- that is
   double counting. Momentum is now a tie-breaker only, not a separate
   weighted component.
2. Penetration was ranked so that HIGH penetration scored HIGHER, which
   rewards markets that are already saturated -- the opposite of where
   growth headroom actually is. Replaced with headroom_rank = 1 -
   penetration_rank, so low-penetration markets (more room to grow) score
   higher.
3. County-level merge to the penetration file now joins on FIPS code
   instead of state+county name text, which is prone to mismatches
   ("St. Louis" vs "Saint Louis", etc.). Falls back to name-based merge
   only for the (small) set of counties with no FIPS from source data.
4. Weights (45% growth / 30% scale / 25% headroom) are not derived from
   data -- they are a judgment call, same as the original 40/30/20/10.
   A sensitivity table is written showing how much the top-10 ranking
   changes under two alternate weight schemes, so the choice of weights
   is visible and defensible rather than hidden.
"""
from __future__ import annotations

import zipfile

import pandas as pd

from src.config import RAW_DIR, TABLE_DIR, ensure_dirs


PENETRATION_DIR = RAW_DIR / "ma_penetration"

STATE_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI",
    "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT",
    "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND",
    "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
    "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY", "Puerto Rico": "PR",
}

# growth_rate_rank + enrollment_scale_rank + headroom_rank must sum to 1.0
WEIGHTS = {"growth_rate_rank": 0.45, "enrollment_scale_rank": 0.30, "headroom_rank": 0.25}

# Alternate schemes used only for the sensitivity check below, not for the
# headline score.
ALT_WEIGHTS = [
    {"growth_rate_rank": 0.60, "enrollment_scale_rank": 0.20, "headroom_rank": 0.20},
    {"growth_rate_rank": 0.30, "enrollment_scale_rank": 0.30, "headroom_rank": 0.40},
]


def _number(value: object) -> float:
    text = str(value).replace(",", "").replace("%", "").strip()
    if text in {"", "*", "nan", "None"}:
        return float("nan")
    return float(text)


def load_penetration() -> pd.DataFrame:
    zip_files = sorted(PENETRATION_DIR.glob("*.zip"))
    if not zip_files:
        raise FileNotFoundError(f"No MA penetration ZIP found under {PENETRATION_DIR}")
    zip_path = zip_files[-1]
    with zipfile.ZipFile(zip_path) as zf:
        csv_name = next(name for name in zf.namelist() if name.lower().endswith(".csv"))
        with zf.open(csv_name) as handle:
            df = pd.read_csv(handle, dtype=str)
    out = df.rename(
        columns={
            "State Name": "state_name",
            "County Name": "county",
            "FIPS": "fips",
            "Eligibles": "eligible_beneficiaries",
            "Enrolled": "ma_enrolled",
            "Penetration": "ma_penetration",
        }
    )
    out["state"] = out["state_name"].map(STATE_ABBR)
    out["eligible_beneficiaries"] = out["eligible_beneficiaries"].map(_number)
    out["ma_enrolled"] = out["ma_enrolled"].map(_number)
    out["ma_penetration"] = out["ma_penetration"].map(_number) / 100
    out["fips"] = out["fips"].astype(str).str.zfill(5)
    return out[["state", "state_name", "county", "fips", "eligible_beneficiaries", "ma_enrolled", "ma_penetration"]]


def percentile(series: pd.Series) -> pd.Series:
    return series.rank(pct=True).fillna(0)


def _score(df: pd.DataFrame, weights: dict) -> pd.Series:
    return (
        100
        * (
            weights["growth_rate_rank"] * df["growth_rate_rank"]
            + weights["enrollment_scale_rank"] * df["enrollment_scale_rank"]
            + weights["headroom_rank"] * df["headroom_rank"]
        )
    ).round(2)


def _add_ranks(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["growth_rate_rank"] = percentile(out["growth_pct"])
    out["enrollment_scale_rank"] = percentile(out["last_enrollment"])
    out["penetration_rank"] = percentile(out["ma_penetration"])
    out["headroom_rank"] = 1 - out["penetration_rank"]
    out["momentum_rank"] = percentile(out["avg_mom_growth_pct"])  # tie-breaker only, not weighted
    return out


def _sensitivity(df: pd.DataFrame, key_cols: list[str]) -> pd.DataFrame:
    headline_top10 = set(map(tuple, df.nlargest(10, "opportunity_score")[key_cols].values))
    rows = []
    for i, alt in enumerate(ALT_WEIGHTS, start=1):
        alt_score = _score(df, alt)
        alt_top10 = set(map(tuple, df.assign(_alt=alt_score).nlargest(10, "_alt")[key_cols].values))
        overlap = len(headline_top10 & alt_top10)
        rows.append(
            {
                "scheme": f"alt_{i}",
                "weights": str(alt),
                "top10_overlap_with_headline": overlap,
                "top10_overlap_pct": overlap / 10,
            }
        )
    return pd.DataFrame(rows)


def score_opportunities() -> tuple[pd.DataFrame, pd.DataFrame]:
    ensure_dirs()
    state_growth = pd.read_csv(TABLE_DIR / "ma_scp_state_growth.csv")
    county_growth = pd.read_csv(TABLE_DIR / "ma_scp_county_growth.csv", dtype={"fips": str})
    penetration = load_penetration()

    state_pen = (
        penetration.groupby("state", as_index=False)
        .agg(
            eligible_beneficiaries=("eligible_beneficiaries", "sum"),
            penetration_enrolled=("ma_enrolled", "sum"),
        )
    )
    state_pen["ma_penetration"] = state_pen["penetration_enrolled"] / state_pen["eligible_beneficiaries"]

    state = state_growth.merge(state_pen[["state", "eligible_beneficiaries", "ma_penetration"]], on="state", how="left")
    state = _add_ranks(state)
    state["opportunity_score"] = _score(state, WEIGHTS)
    state["score_explanation"] = (
        f"Weighted CMS ranking: {WEIGHTS['growth_rate_rank']:.0%} growth rate, "
        f"{WEIGHTS['enrollment_scale_rank']:.0%} enrollment scale, "
        f"{WEIGHTS['headroom_rank']:.0%} penetration headroom (1 - penetration); "
        "momentum used only as a tie-breaker, not a separate weight"
    )
    state["recommendation"] = state.apply(
        lambda r: f"Prioritize {r['state']} for RCM outreach: score {r['opportunity_score']:.1f}, "
        f"latest enrollment {r['last_enrollment']:,.0f}, growth {r['growth_pct']:.2%}, "
        f"penetration {r['ma_penetration']:.1%}.",
        axis=1,
    )
    state = state.sort_values(["opportunity_score", "momentum_rank"], ascending=False)

    # County merge: prefer FIPS; fall back to state+county name for rows
    # where FIPS wasn't available from the source data.
    pen_county = penetration[["fips", "state", "county", "eligible_beneficiaries", "ma_penetration"]].rename(
        columns={"eligible_beneficiaries": "pen_eligible", "ma_penetration": "pen_penetration"}
    )
    county = county_growth.merge(pen_county[["fips", "pen_eligible", "pen_penetration"]], on="fips", how="left")
    fips_matched = county["pen_penetration"].notna()

    name_fallback = county_growth.merge(
        pen_county[["state", "county", "pen_eligible", "pen_penetration"]],
        on=["state", "county"],
        how="left",
        suffixes=("", "_byname"),
    )
    county.loc[~fips_matched, "pen_eligible"] = name_fallback.loc[~fips_matched, "pen_eligible"]
    county.loc[~fips_matched, "pen_penetration"] = name_fallback.loc[~fips_matched, "pen_penetration"]
    county = county.rename(columns={"pen_eligible": "eligible_beneficiaries", "pen_penetration": "ma_penetration"})

    matched_share = county["ma_penetration"].notna().mean()
    print(f"County penetration match rate: {matched_share:.1%} ({fips_matched.sum()} by FIPS, rest by name fallback).")

    county = _add_ranks(county)
    county["opportunity_score"] = _score(county, WEIGHTS)
    county["score_explanation"] = state["score_explanation"].iloc[0]
    county["recommendation"] = county.apply(
        lambda r: f"Review {r['state']} {r['county']} for market outreach: score {r['opportunity_score']:.1f}, "
        f"latest enrollment {r['last_enrollment']:,.0f}, growth {r['growth_pct']:.2%}, "
        f"penetration {r['ma_penetration']:.1%}.",
        axis=1,
    )
    county = county.sort_values(["opportunity_score", "momentum_rank"], ascending=False)

    state.to_csv(TABLE_DIR / "dashboard_state_opportunities.csv", index=False)
    county.to_csv(TABLE_DIR / "dashboard_county_opportunities.csv", index=False)

    pd.DataFrame(
        [
            {"component": "growth_rate_rank", "weight": WEIGHTS["growth_rate_rank"], "source": "CMS MA SCP first-to-last observed enrollment growth (balanced panel)"},
            {"component": "enrollment_scale_rank", "weight": WEIGHTS["enrollment_scale_rank"], "source": "CMS MA SCP latest observed enrollment"},
            {"component": "headroom_rank", "weight": WEIGHTS["headroom_rank"], "source": "1 - CMS MA state/county penetration (low penetration = more headroom)"},
        ]
    ).to_csv(TABLE_DIR / "opportunity_score_methodology.csv", index=False)

    state_sensitivity = _sensitivity(state, ["state"])
    county_sensitivity = _sensitivity(county, ["state", "county"])
    state_sensitivity.to_csv(TABLE_DIR / "opportunity_score_sensitivity_state.csv", index=False)
    county_sensitivity.to_csv(TABLE_DIR / "opportunity_score_sensitivity_county.csv", index=False)

    print("\nState top-10 stability under alternate weight schemes:")
    print(state_sensitivity.to_string(index=False))
    print("\nCounty top-10 stability under alternate weight schemes:")
    print(county_sensitivity.to_string(index=False))

    return state, county


def main() -> None:
    state, county = score_opportunities()
    print(state[["state", "opportunity_score", "last_enrollment", "growth_pct", "ma_penetration"]].head(10).to_string(index=False))
    print(county[["state", "county", "opportunity_score", "last_enrollment", "growth_pct", "ma_penetration"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
