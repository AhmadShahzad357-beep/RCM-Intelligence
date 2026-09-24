"""Load the latest CPSC (Contract/Plan/State/County) enrollment file.

CPSC gives plan-level (not just state/county-level) enrollment, which is
what we need to weight PA exposure by actual membership instead of by
plan count. Only the most recent month is loaded here -- this is a
current-snapshot weighting, not a time series.

Suppression marker note: CPSC uses "*" for suppressed cells, unlike the
MA SCP files (src/data/load_ma_scp.py), which use ".". Handled separately
here for that reason.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pandas as pd

from src.config import CPSC_DIR, PROCESSED_DIR, ensure_dirs

ENROLL_COLS = ["Contract Number", "Plan ID", "State", "County", "Enrollment"]
CPSC_SUPPRESSION_MARKER = "*"
SUPPRESSED_HIGH_FILL = 10  # CMS suppresses counts under 11; conservative ceiling

CACHE_PATH = PROCESSED_DIR / "cpsc_plan_enrollment_latest.parquet"


def _month_from_zip_name(path: Path) -> str:
    match = re.search(r"(20\d{2}-\d{2})", path.name)
    if not match:
        raise ValueError(f"Could not parse YYYY-MM from {path.name}")
    return match.group(1)


def _latest_cpsc_zip() -> Path:
    zips = sorted(CPSC_DIR.glob("monthly-enrollment-cpsc-*.zip"))
    if not zips:
        raise FileNotFoundError(
            f"No CPSC zip files found in {CPSC_DIR}. Run scripts/download_optional_data.ps1 first."
        )
    return zips[-1]


def load_latest_cpsc_plan_enrollment(force_reload: bool = False) -> pd.DataFrame:
    """Plan-level enrollment (summed across state/county) from the most
    recent CPSC monthly file. Cached to parquet after the first parse --
    the source CSV is ~186MB, so re-parsing it on every call is wasteful.
    Pass force_reload=True to re-parse even if a cache exists (e.g. if a
    newer CPSC month has since been downloaded).
    """
    zip_path = _latest_cpsc_zip()
    report_month = _month_from_zip_name(zip_path)

    if not force_reload and CACHE_PATH.exists():
        cached = pd.read_parquet(CACHE_PATH)
        if not cached.empty and cached["report_month"].iloc[0] == report_month:
            print(f"Using cached CPSC plan-level enrollment for {report_month} ({len(cached):,} rows).")
            return cached

    with zipfile.ZipFile(zip_path) as zf:
        enroll_names = [n for n in zf.namelist() if "Enrollment_Info" in n and n.lower().endswith(".csv")]
        if len(enroll_names) != 1:
            raise ValueError(f"Expected exactly one enrollment CSV in {zip_path.name}, found {enroll_names}")
        with zf.open(enroll_names[0]) as handle:
            df = pd.read_csv(handle, dtype=str, usecols=ENROLL_COLS, keep_default_na=False)

    df = df.rename(
        columns={
            "Contract Number": "contract_id",
            "Plan ID": "plan_id_raw",
            "State": "state",
            "County": "county",
            "Enrollment": "enrolled_raw",
        }
    )
    df["contract_id"] = df["contract_id"].str.strip()
    plan_id_stripped = df["plan_id_raw"].str.strip()
    df["plan_id"] = plan_id_stripped.where(plan_id_stripped.eq(""), plan_id_stripped.str.zfill(3))

    df["enrolled_raw"] = df["enrolled_raw"].str.strip()
    df["is_enrollment_suppressed"] = df["enrolled_raw"].eq(CPSC_SUPPRESSION_MARKER)
    df["enrolled"] = pd.to_numeric(df["enrolled_raw"].str.replace(",", "", regex=False), errors="coerce")
    df["enrolled_low"] = df["enrolled"].fillna(0)
    df["enrolled_high"] = df["enrolled"].where(~df["is_enrollment_suppressed"], SUPPRESSED_HIGH_FILL)
    df["enrolled_high"] = df["enrolled_high"].fillna(df["enrolled_low"])

    plan_level = (
        df.groupby(["contract_id", "plan_id"], as_index=False)
        .agg(
            enrolled_low=("enrolled_low", "sum"),
            enrolled_high=("enrolled_high", "sum"),
            county_rows=("county", "size"),
            suppressed_rows=("is_enrollment_suppressed", "sum"),
        )
    )
    plan_level["report_month"] = report_month
    plan_level["enrolled_mid"] = (plan_level["enrolled_low"] + plan_level["enrolled_high"]) / 2

    ensure_dirs()
    plan_level.to_parquet(CACHE_PATH, index=False)
    print(f"Loaded CPSC plan-level enrollment for {report_month}: {len(plan_level):,} contract-plan rows.")
    return plan_level


def main() -> None:
    load_latest_cpsc_plan_enrollment(force_reload=True)


if __name__ == "__main__":
    main()
