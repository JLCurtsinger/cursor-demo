#!/usr/bin/env python3
"""
load_data.py

Small utility module for loading the mock 340B onboarding datasets.

Expected repo layout:
  testRepo/
    data/
      claims_raw.csv
      eligibility.csv
    src/
      load_data.py

Usage from repo root:
  python3 src/load_data.py

This script:
  - loads claims_raw.csv and eligibility.csv
  - validates required columns
  - prints a compact summary of each file
  - exposes load_claims(), load_eligibility(), and load_all_data()
    for reuse by later transform/match/report scripts
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"

CLAIMS_FILE = DATA_DIR / "claims_raw.csv"
ELIGIBILITY_FILE = DATA_DIR / "eligibility.csv"


CLAIMS_REQUIRED_COLUMNS = {
    "claim_id",
    "rx_number",
    "patient_id",
    "fill_date",
    "ndc",
    "quantity",
    "days_supply",
    "pharmacy_npi",
    "prescriber_npi",
}

ELIGIBILITY_REQUIRED_COLUMNS = {
    "patient_id",
    "eligibility_start_date",
    "eligibility_end_date",
    "eligibility_status",
}


@dataclass(frozen=True)
class LoadedData:
    claims: pd.DataFrame
    eligibility: pd.DataFrame


def _read_csv(path: Path) -> pd.DataFrame:
    """Read a CSV as strings so messy source data is preserved for cleaning later."""
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find {path}. Run this from the repo root and confirm data files exist."
        )

    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _validate_columns(df: pd.DataFrame, required_columns: Iterable[str], file_label: str) -> None:
    """Raise a clear error if a required input column is missing."""
    required = set(required_columns)
    actual = set(df.columns)
    missing = sorted(required - actual)

    if missing:
        raise ValueError(
            f"{file_label} is missing required columns: {', '.join(missing)}"
        )


def load_claims(path: Path | str = CLAIMS_FILE) -> pd.DataFrame:
    """Load raw claim data and validate minimum required columns."""
    claims = _read_csv(Path(path))
    _validate_columns(claims, CLAIMS_REQUIRED_COLUMNS, "claims_raw.csv")
    return claims


def load_eligibility(path: Path | str = ELIGIBILITY_FILE) -> pd.DataFrame:
    """Load eligibility data and validate minimum required columns."""
    eligibility = _read_csv(Path(path))
    _validate_columns(eligibility, ELIGIBILITY_REQUIRED_COLUMNS, "eligibility.csv")
    return eligibility


def load_all_data(
    claims_path: Path | str = CLAIMS_FILE,
    eligibility_path: Path | str = ELIGIBILITY_FILE,
) -> LoadedData:
    """Load both source files and return them together."""
    return LoadedData(
        claims=load_claims(claims_path),
        eligibility=load_eligibility(eligibility_path),
    )


def summarize_dataframe(df: pd.DataFrame, label: str) -> None:
    """Print a simple terminal-friendly summary for onboarding demos."""
    print(f"\n{label}")
    print("-" * len(label))
    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns):,}")
    print("Column names:")
    print(", ".join(df.columns))

    empty_counts = (df == "").sum().sort_values(ascending=False)
    empty_counts = empty_counts[empty_counts > 0]

    if empty_counts.empty:
        print("Empty string values: none")
    else:
        print("Columns with empty string values:")
        for column_name, count in empty_counts.items():
            print(f"  {column_name}: {count:,}")

    print("\nPreview:")
    print(df.head(5).to_string(index=False))


def main() -> None:
    loaded = load_all_data()

    summarize_dataframe(loaded.claims, "claims_raw.csv")
    summarize_dataframe(loaded.eligibility, "eligibility.csv")

    print("\nLoad complete.")


if __name__ == "__main__":
    main()
