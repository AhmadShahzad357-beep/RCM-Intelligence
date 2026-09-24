from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pandas as pd

from src.config import MA_SCP_DIR, PROCESSED_DIR, TABLE_DIR, ensure_dirs
from src.data.suppression import add_bounded_enrollment, bounded_group_summary


def month_from_zip_name(path: Path) -> str:
    match = re.search(r"(20\d{2}-\d{2})", path.name)
    if not match:
        raise ValueError(f"Could not parse YYYY-MM from {path.name}")
    return match.group(1)


def read_ma_scp_zip(zip_path: Path) -> pd.DataFrame:
    report_month = month_from_zip_name(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        csv_names = [name for name in zf.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError(f"Expected exactly one CSV in {zip_path.name}, found {csv_names}")
        csv_name = csv_names[0]
        with zf.open(csv_name) as handle:
            df = pd.read_csv(handle, dtype=str, keep_default_na=False)

    df["source_zip"] = zip_path.name
    df["source_csv"] = csv_name
    df["report_month_label"] = report_month
    return df


def build_ma_scp_long(raw_dir: Path = MA_SCP_DIR) -> pd.DataFrame:
    zip_paths = sorted(raw_dir.glob("*.zip"))
    if not zip_paths:
        raise FileNotFoundError(f"No MA SCP ZIP files found in {raw_dir}")

    raw = pd.concat([read_ma_scp_zip(path) for path in zip_paths], ignore_index=True)
    raw["source_row_number"] = raw.groupby("source_zip").cumcount() + 1

    ma = pd.DataFrame(
        {
            "report_month": pd.PeriodIndex(raw["report_month_label"], freq="M").to_timestamp(),
            "report_month_label": raw["report_month_label"],
            "state": raw["State"].astype(str).str.strip().str.upper(),
            "county": raw["County"].astype(str).str.strip(),
            "plan_type": raw["PLAN TYPE"].astype(str).str.strip(),
            "ssa_code_raw": raw["SSA Code"].astype(str).str.strip(),
            "fips_code_raw": raw["FIPS Code"].astype(str).str.strip(),
            "enrolled_raw": raw["Enrolled"].astype(str).str.strip(),
            "source_zip": raw["source_zip"],
            "source_csv": raw["source_csv"],
            "source_row_number": raw["source_row_number"],
        }
    )

    ma["ssa_code"] = pd.to_numeric(ma["ssa_code_raw"], errors="coerce").astype("Int64")
    ma["fips_code"] = pd.to_numeric(ma["fips_code_raw"], errors="coerce").astype("Int64")
    ma["enrolled"] = pd.to_numeric(ma["enrolled_raw"].str.replace(",", "", regex=False), errors="coerce")
    ma["is_enrollment_suppressed"] = ma["enrolled_raw"].eq(".")
    ma["is_enrollment_blank"] = ma["enrolled_raw"].eq("")
    ma["is_enrollment_numeric"] = ma["enrolled"].notna()
    ma["has_state"] = ma["state"].ne("")
    ma["has_county"] = ma["county"].ne("")
    ma["has_plan_type"] = ma["plan_type"].ne("")
    ma["has_fips"] = ma["fips_code"].notna()
    ma["state_county_key"] = ma["state"] + "|" + ma["county"] + "|" + ma["fips_code_raw"]
    ma["enrolled_observed_filled_zero"] = ma["enrolled"].fillna(0)
    ma["enrolled_missing_reason"] = "numeric"
    ma.loc[ma["is_enrollment_suppressed"], "enrolled_missing_reason"] = "cms_suppressed_dot"
    ma.loc[ma["is_enrollment_blank"], "enrolled_missing_reason"] = "blank"
    ma.loc[ma["enrolled"].isna() & ~ma["is_enrollment_suppressed"] & ~ma["is_enrollment_blank"], "enrolled_missing_reason"] = "non_numeric"
    ma["is_duplicate_business_key"] = ma.duplicated(
        ["report_month", "state", "county", "fips_code_raw", "plan_type"], keep=False
    )

    return ma.sort_values(["report_month", "state", "county", "plan_type"]).reset_index(drop=True)


def create_monthly_tables(ma: pd.DataFrame) -> dict[str, pd.DataFrame]:
    monthly = (
        ma.groupby(["report_month", "report_month_label"], as_index=False)
        .agg(
            observed_enrollment=("enrolled", "sum"),
            source_rows=("enrolled_raw", "size"),
            numeric_rows=("is_enrollment_numeric", "sum"),
            suppressed_rows=("is_enrollment_suppressed", "sum"),
            states=("state", "nunique"),
            counties=("state_county_key", "nunique"),
            plan_types=("plan_type", "nunique"),
        )
        .sort_values("report_month")
    )
    monthly["mom_change"] = monthly["observed_enrollment"].diff()
    monthly["mom_growth_pct"] = monthly["observed_enrollment"].pct_change()
    monthly["suppressed_row_share"] = monthly["suppressed_rows"] / monthly["source_rows"]

    state_monthly = (
        ma.groupby(["report_month", "report_month_label", "state"], as_index=False)
        .agg(
            observed_enrollment=("enrolled", "sum"),
            source_rows=("enrolled_raw", "size"),
            numeric_rows=("is_enrollment_numeric", "sum"),
            suppressed_rows=("is_enrollment_suppressed", "sum"),
            counties=("state_county_key", "nunique"),
            plan_types=("plan_type", "nunique"),
        )
        .sort_values(["state", "report_month"])
    )
    state_monthly["mom_change"] = state_monthly.groupby("state")["observed_enrollment"].diff()
    state_monthly["mom_growth_pct"] = state_monthly.groupby("state")["observed_enrollment"].pct_change()

    plan_monthly = (
        ma.groupby(["report_month", "report_month_label", "plan_type"], as_index=False)
        .agg(
            observed_enrollment=("enrolled", "sum"),
            numeric_rows=("is_enrollment_numeric", "sum"),
            suppressed_rows=("is_enrollment_suppressed", "sum"),
            counties=("state_county_key", "nunique"),
        )
        .sort_values(["plan_type", "report_month"])
    )
    plan_monthly["mom_change"] = plan_monthly.groupby("plan_type")["observed_enrollment"].diff()
    plan_monthly["mom_growth_pct"] = plan_monthly.groupby("plan_type")["observed_enrollment"].pct_change()

    return {
        "ma_scp_monthly_national": monthly,
        "ma_scp_state_monthly": state_monthly,
        "ma_scp_plan_monthly": plan_monthly,
    }


def main() -> None:
    ensure_dirs()
    ma = build_ma_scp_long()
    ma = add_bounded_enrollment(ma)
    ma.to_parquet(PROCESSED_DIR / "ma_scp_long.parquet", index=False)
    ma.head(1000).to_csv(TABLE_DIR / "ma_scp_long_profile_sample.csv", index=False)
    for name, table in create_monthly_tables(ma).items():
        table.to_parquet(PROCESSED_DIR / f"{name}.parquet", index=False)
        table.to_csv(TABLE_DIR / f"{name}.csv", index=False)

    national_bounds = bounded_group_summary(ma, ["report_month", "report_month_label"])
    national_bounds.to_csv(TABLE_DIR / "ma_scp_national_bounds.csv", index=False)

    print(f"Wrote MA SCP long table with {len(ma):,} rows.")
    latest = national_bounds.sort_values("report_month").iloc[-1]
    print(
        f"Latest month ({latest['report_month_label']}): observed={latest['enrolled_base']:,.0f}, "
        f"low={latest['enrolled_low']:,.0f}, high={latest['enrolled_high']:,.0f}, "
        f"suppressed_row_share={latest['suppressed_row_share']:.1%}"
    )


if __name__ == "__main__":
    main()

