"""Load CPSC data for any specific month, plus contract->organization info.

Extends load_cpsc.py (which only loaded the latest month for PA-exposure
weighting) so the payer scorecard can compare enrollment across two
points in time and attach organization names.

enrolled_mid here uses the same low/high suppression-bound midpoint as
load_cpsc.py's load_latest_cpsc_plan_enrollment(): a plan-level or
contract-level number computed with a different suppressed-cell
assumption will not agree with the other, which showed up as
pa_match_rate exceeding 100% for some payers when these two loaders used
different formulas.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pandas as pd

from src.config import CPSC_DIR, PROCESSED_DIR, ensure_dirs
from src.data.load_cpsc import ENROLL_COLS, CPSC_SUPPRESSION_MARKER, SUPPRESSED_HIGH_FILL


def _month_from_zip_name(path: Path) -> str:
    match = re.search(r"(20\d{2}-\d{2})", path.name)
    if not match:
        raise ValueError(f"Could not parse YYYY-MM from {path.name}")
    return match.group(1)


def _all_cpsc_zips() -> list[Path]:
    zips = sorted(CPSC_DIR.glob("monthly-enrollment-cpsc-*.zip"))
    if not zips:
        raise FileNotFoundError(f"No CPSC zip files found in {CPSC_DIR}. Run scripts/download_optional_data.ps1 first.")
    return zips


def load_cpsc_plan_enrollment_for(zip_path: Path, cache_name: str, force_reload: bool = False) -> pd.DataFrame:
    ensure_dirs()
    cache_path = PROCESSED_DIR / cache_name
    report_month = _month_from_zip_name(zip_path)

    if not force_reload and cache_path.exists():
        cached = pd.read_parquet(cache_path)
        if not cached.empty and cached["report_month"].iloc[0] == report_month:
            print(f"Using cached CPSC enrollment for {report_month} ({len(cached):,} rows).")
            return cached

    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if "Enrollment_Info" in n and n.lower().endswith(".csv")]
        with zf.open(names[0]) as handle:
            df = pd.read_csv(handle, dtype=str, usecols=ENROLL_COLS, keep_default_na=False)

    df = df.rename(columns={"Contract Number": "contract_id", "Plan ID": "plan_id_raw", "Enrollment": "enrolled_raw"})
    df["contract_id"] = df["contract_id"].str.strip()
    plan_id_stripped = df["plan_id_raw"].str.strip()
    df["plan_id"] = plan_id_stripped.where(plan_id_stripped.eq(""), plan_id_stripped.str.zfill(3))
    df["enrolled_raw"] = df["enrolled_raw"].str.strip()
    df["is_suppressed"] = df["enrolled_raw"].eq(CPSC_SUPPRESSION_MARKER)
    df["enrolled"] = pd.to_numeric(df["enrolled_raw"].str.replace(",", "", regex=False), errors="coerce")

    # Same low/high midpoint formula as load_cpsc.py, for consistency
    # between the two loaders (see module docstring).
    df["enrolled_low"] = df["enrolled"].fillna(0)
    df["enrolled_high"] = df["enrolled"].where(~df["is_suppressed"], SUPPRESSED_HIGH_FILL)
    df["enrolled_high"] = df["enrolled_high"].fillna(df["enrolled_low"])
    df["enrolled_mid"] = (df["enrolled_low"] + df["enrolled_high"]) / 2

    contract_level = df.groupby("contract_id", as_index=False)["enrolled_mid"].sum()
    contract_level["report_month"] = report_month
    contract_level.to_parquet(cache_path, index=False)
    print(f"Loaded CPSC contract-level enrollment for {report_month}: {len(contract_level):,} contracts.")
    return contract_level


def load_cpsc_contract_info() -> pd.DataFrame:
    zip_path = _all_cpsc_zips()[-1]
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if "Contract_Info" in n and n.lower().endswith(".csv")]
        with zf.open(names[0]) as handle:
            df = pd.read_csv(handle, dtype=str, encoding="latin-1")
    df = df.rename(
        columns={
            "Contract ID": "contract_id",
            "Organization Marketing Name": "organization",
            "Parent Organization": "parent_organization",
            "Plan Type": "plan_type",
        }
    )
    df["contract_id"] = df["contract_id"].str.strip()
    return df.drop_duplicates("contract_id")[["contract_id", "organization", "parent_organization", "plan_type"]]


def load_first_and_latest_contract_enrollment() -> tuple[pd.DataFrame, pd.DataFrame]:
    zips = _all_cpsc_zips()
    # force_reload=True because the previous cached files were built with
    # the old (inconsistent) enrolled_mid formula.
    first = load_cpsc_plan_enrollment_for(zips[0], "cpsc_contract_enrollment_first.parquet", force_reload=True)
    latest = load_cpsc_plan_enrollment_for(zips[-1], "cpsc_contract_enrollment_latest.parquet", force_reload=True)
    return first, latest


def main() -> None:
    first, latest = load_first_and_latest_contract_enrollment()
    info = load_cpsc_contract_info()
    print(f"Contract info: {len(info):,} contracts with organization names.")


if __name__ == "__main__":
    main()
