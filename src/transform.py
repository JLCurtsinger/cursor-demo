#!/usr/bin/env python3
"""
transform.py

Clean and normalize the mock 340B onboarding datasets.

Expected repo layout:
  testRepo/
    data/
      claims_raw.csv
      eligibility.csv
    src/
      load_data.py
      transform.py
    outputs/

Usage from repo root:
  python3 src/transform.py

This script:
  - loads raw claims and eligibility files
  - normalizes dates
  - normalizes NDC values
  - trims text fields
  - converts numeric fields where appropriate
  - flags common data-quality issues
  - removes exact duplicate claim rows
  - writes cleaned CSV outputs to outputs/
"""

from __future__ import annotations

from pathlib import Path
import re
import sys
from typing import Iterable

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
OUTPUT_DIR = REPO_ROOT / "outputs"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from load_data import LoadedData, load_all_data


DATE_COLUMNS_CLAIMS = [
    "fill_date",
    "written_date",
]

DATE_COLUMNS_ELIGIBILITY = [
    "eligibility_start_date",
    "eligibility_end_date",
    "last_verified_date",
]

NUMERIC_COLUMNS_CLAIMS = [
    "quantity",
    "days_supply",
    "total_paid",
    "patient_pay",
    "ingredient_cost",
    "dispensing_fee",
    "usual_customary",
]


def clean_string_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Trim whitespace and convert obvious placeholder nulls to empty strings."""
    cleaned = df.copy()

    null_placeholders = {
        "nan",
        "none",
        "null",
        "n/a",
        "na",
        "<na>",
    }

    for column in cleaned.columns:
        cleaned[column] = cleaned[column].astype(str).str.strip()
        cleaned[column] = cleaned[column].apply(
            lambda value: "" if value.strip().lower() in null_placeholders else value
        )

    return cleaned


def parse_date_series(series: pd.Series) -> pd.Series:
    """Parse mixed-format source dates into ISO YYYY-MM-DD strings."""
    values = series.replace("", pd.NA)
    try:
        parsed = pd.to_datetime(values, format="mixed", errors="coerce")
    except (TypeError, ValueError):
        parsed = pd.to_datetime(values, errors="coerce")
    return parsed.dt.strftime("%Y-%m-%d").fillna("")


def normalize_date_columns(df: pd.DataFrame, date_columns: Iterable[str]) -> pd.DataFrame:
    """Normalize selected date columns when they are present."""
    cleaned = df.copy()

    for column in date_columns:
        if column in cleaned.columns:
            original_column = f"{column}_raw"
            if original_column not in cleaned.columns:
                cleaned[original_column] = cleaned[column]
            cleaned[column] = parse_date_series(cleaned[column])

    return cleaned


def normalize_ndc(value: str) -> str:
    """
    Normalize NDC-like values to 11 digits when possible.

    This deliberately uses a simple demo-friendly approach:
      - remove non-digits
      - left-pad to 11 digits if fewer than 11 digits
      - keep blank if no digits exist
      - preserve overlong values as-is for later issue review
    """
    digits = re.sub(r"\D", "", str(value or ""))

    if not digits:
        return ""

    if len(digits) < 11:
        return digits.zfill(11)

    return digits


def normalize_numeric_columns(df: pd.DataFrame, numeric_columns: Iterable[str]) -> pd.DataFrame:
    """Convert selected numeric columns to numeric values when present."""
    cleaned = df.copy()

    for column in numeric_columns:
        if column in cleaned.columns:
            cleaned[column] = (
                cleaned[column]
                .astype(str)
                .str.replace("$", "", regex=False)
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")

    return cleaned


def add_claim_quality_flags(claims: pd.DataFrame) -> pd.DataFrame:
    """Add row-level flags that make demo validation easier."""
    cleaned = claims.copy()

    cleaned["missing_patient_id"] = cleaned["patient_id"].eq("")
    cleaned["missing_fill_date"] = cleaned["fill_date"].eq("")
    cleaned["missing_ndc"] = cleaned["ndc"].eq("")
    cleaned["invalid_ndc_length"] = ~cleaned["ndc"].str.len().eq(11) & cleaned["ndc"].ne("")
    cleaned["missing_pharmacy_npi"] = cleaned["pharmacy_npi"].eq("")
    cleaned["missing_prescriber_npi"] = cleaned["prescriber_npi"].eq("")

    if "transaction_type" in cleaned.columns:
        cleaned["is_reversal"] = (
            cleaned["transaction_type"].astype(str).str.upper().str.strip().eq("REVERSAL")
        )
    elif "reversal_flag" in cleaned.columns:
        flag = cleaned["reversal_flag"].astype(str).str.strip().str.upper()
        cleaned["is_reversal"] = flag.isin(["Y", "YES", "TRUE", "1"])
    elif "claim_status" in cleaned.columns:
        cleaned["is_reversal"] = (
            cleaned["claim_status"].astype(str).str.upper().str.strip().eq("REVERSED")
        )
    else:
        cleaned["is_reversal"] = False

    if "claim_status" in cleaned.columns:
        cleaned["is_rejected"] = cleaned["claim_status"].str.upper().eq("REJECTED")
    else:
        cleaned["is_rejected"] = False

    return cleaned


def add_eligibility_quality_flags(eligibility: pd.DataFrame) -> pd.DataFrame:
    """Add row-level flags for eligibility data-quality review."""
    cleaned = eligibility.copy()

    cleaned["missing_patient_id"] = cleaned["patient_id"].eq("")
    cleaned["missing_eligibility_start_date"] = cleaned["eligibility_start_date"].eq("")
    if "eligibility_end_date_raw" in cleaned.columns:
        cleaned["open_ended_eligibility"] = cleaned["eligibility_end_date_raw"].eq("")
    else:
        cleaned["open_ended_eligibility"] = cleaned["eligibility_end_date"].eq("")
    cleaned["inactive_or_pending_status"] = ~cleaned["eligibility_status"].str.upper().eq("ACTIVE")

    start = pd.to_datetime(cleaned["eligibility_start_date"].replace("", pd.NA), errors="coerce")
    end = pd.to_datetime(cleaned["eligibility_end_date"].replace("", pd.NA), errors="coerce")
    cleaned["eligibility_end_before_start"] = end.notna() & start.notna() & (end < start)

    return cleaned


def transform_claims(claims: pd.DataFrame) -> pd.DataFrame:
    """Clean and normalize raw claims."""
    cleaned = clean_string_columns(claims)
    cleaned = normalize_date_columns(cleaned, DATE_COLUMNS_CLAIMS)

    if "ndc" in cleaned.columns:
        cleaned["ndc_raw"] = cleaned["ndc"]
        cleaned["ndc"] = cleaned["ndc"].apply(normalize_ndc)

    cleaned = normalize_numeric_columns(cleaned, NUMERIC_COLUMNS_CLAIMS)

    if "gross_amount" not in cleaned.columns and "total_paid" in cleaned.columns:
        cleaned["gross_amount"] = cleaned["total_paid"]
    if "patient_paid_amount" not in cleaned.columns and "patient_pay" in cleaned.columns:
        cleaned["patient_paid_amount"] = cleaned["patient_pay"]
    if (
        "plan_paid_amount" not in cleaned.columns
        and "total_paid" in cleaned.columns
        and "patient_pay" in cleaned.columns
    ):
        cleaned["plan_paid_amount"] = cleaned["total_paid"] - cleaned["patient_pay"]

    before_dedup = len(cleaned)
    cleaned = cleaned.drop_duplicates().reset_index(drop=True)
    cleaned.attrs["removed_exact_duplicate_count_at_transform"] = before_dedup - len(cleaned)

    cleaned = add_claim_quality_flags(cleaned)
    return cleaned


def transform_eligibility(eligibility: pd.DataFrame) -> pd.DataFrame:
    """Clean and normalize raw eligibility records."""
    cleaned = clean_string_columns(eligibility)
    cleaned = normalize_date_columns(cleaned, DATE_COLUMNS_ELIGIBILITY)
    cleaned = add_eligibility_quality_flags(cleaned)
    return cleaned


def transform_all(data: LoadedData) -> LoadedData:
    """Transform claims and eligibility together."""
    return LoadedData(
        claims=transform_claims(data.claims),
        eligibility=transform_eligibility(data.eligibility),
    )


def print_quality_summary(claims: pd.DataFrame, eligibility: pd.DataFrame) -> None:
    """Print compact issue counts for terminal review."""
    claim_flags = [
        "missing_patient_id",
        "missing_fill_date",
        "missing_ndc",
        "invalid_ndc_length",
        "missing_pharmacy_npi",
        "missing_prescriber_npi",
        "is_reversal",
        "is_rejected",
    ]

    eligibility_flags = [
        "missing_patient_id",
        "missing_eligibility_start_date",
        "open_ended_eligibility",
        "inactive_or_pending_status",
        "eligibility_end_before_start",
    ]

    print("\nClaim quality summary")
    print("---------------------")
    print(f"Rows after transform: {len(claims):,}")
    for flag in claim_flags:
        if flag in claims.columns:
            print(f"{flag}: {int(claims[flag].sum()):,}")

    removed_count = claims.attrs.get("removed_exact_duplicate_count_at_transform")
    if removed_count is not None:
        print(f"exact duplicate rows removed: {int(removed_count):,}")

    print("\nEligibility quality summary")
    print("---------------------------")
    print(f"Rows after transform: {len(eligibility):,}")
    for flag in eligibility_flags:
        if flag in eligibility.columns:
            print(f"{flag}: {int(eligibility[flag].sum()):,}")


def write_outputs(transformed: LoadedData) -> None:
    """Write transformed datasets to the outputs directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    claims_output = OUTPUT_DIR / "claims_clean.csv"
    eligibility_output = OUTPUT_DIR / "eligibility_clean.csv"

    transformed.claims.to_csv(claims_output, index=False)
    transformed.eligibility.to_csv(eligibility_output, index=False)

    print("\nWrote outputs")
    print("-------------")
    print(claims_output)
    print(eligibility_output)


def main() -> None:
    raw = load_all_data()
    transformed = transform_all(raw)

    print_quality_summary(transformed.claims, transformed.eligibility)
    write_outputs(transformed)

    print("\nTransform complete.")


if __name__ == "__main__":
    main()
