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
# Import future annotation behavior so type hints are treated as strings internally.
# This helps avoid circular type evaluation issues and keeps typing behavior modern.
from __future__ import annotations


# dataclass is used to create a lightweight structured object for returning
# multiple datasets together in a clean and typed format.
from dataclasses import dataclass

# Path is used for safe and platform-independent filesystem path handling.
from pathlib import Path

# Iterable is used for typing collections of required column names.
from typing import Iterable

# Pandas is the core data-processing library used throughout this demo.
# It handles CSV loading, validation, transformation, and reporting.
import pandas as pd


# Determine the repository root dynamically based on the location of this file.
# This allows the script to work consistently regardless of where it is run from.
REPO_ROOT = Path(__file__).resolve().parents[1]

# Define the location of the input data directory.
DATA_DIR = REPO_ROOT / "data"


# Define the expected claims source file path.
CLAIMS_FILE = DATA_DIR / "claims_raw.csv"

# Define the expected eligibility source file path.
ELIGIBILITY_FILE = DATA_DIR / "eligibility.csv"


# Define the minimum required columns needed for claims processing.
# These fields are validated before downstream transformation or reporting begins.
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


# Define the minimum required columns needed for eligibility processing.
# These ensure the eligibility dataset contains the core matching fields.
ELIGIBILITY_REQUIRED_COLUMNS = {
    "patient_id",
    "eligibility_start_date",
    "eligibility_end_date",
    "eligibility_status",
}


# Create a structured container object that groups claims and eligibility
# DataFrames together into a single reusable object.
@dataclass(frozen=True)
class LoadedData:
    claims: pd.DataFrame
    eligibility: pd.DataFrame


# Internal helper function used to safely read CSV files into pandas DataFrames.
# All columns are loaded as strings so messy source formatting is preserved
# for later cleaning and normalization steps.
def _read_csv(path: Path) -> pd.DataFrame:
    """Read a CSV as strings so messy source data is preserved for cleaning later."""
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find {path}. Run this from the repo root and confirm data files exist."
        )

    return pd.read_csv(path, dtype=str, keep_default_na=False)


# Internal helper function used to verify that all required columns exist
# before downstream processing begins. This prevents later runtime failures
# caused by missing source fields.
def _validate_columns(df: pd.DataFrame, required_columns: Iterable[str], file_label: str) -> None:
    """Raise a clear error if a required input column is missing."""
    required = set(required_columns)
    actual = set(df.columns)
    missing = sorted(required - actual)

    if missing:
        raise ValueError(
            f"{file_label} is missing required columns: {', '.join(missing)}"
        )


# Load the raw claims dataset and validate its required schema.
# This function serves as the primary claims loader for downstream scripts.
def load_claims(path: Path | str = CLAIMS_FILE) -> pd.DataFrame:
    """Load raw claim data and validate minimum required columns."""
    claims = _read_csv(Path(path))
    _validate_columns(claims, CLAIMS_REQUIRED_COLUMNS, "claims_raw.csv")
    return claims


# Load the raw eligibility dataset and validate its required schema.
# This function serves as the primary eligibility loader for downstream scripts.
def load_eligibility(path: Path | str = ELIGIBILITY_FILE) -> pd.DataFrame:
    """Load eligibility data and validate minimum required columns."""
    eligibility = _read_csv(Path(path))
    _validate_columns(eligibility, ELIGIBILITY_REQUIRED_COLUMNS, "eligibility.csv")
    return eligibility


# Load both source datasets together and package them into a single object.
# This simplifies passing related datasets between scripts and functions.
def load_all_data(
    claims_path: Path | str = CLAIMS_FILE,
    eligibility_path: Path | str = ELIGIBILITY_FILE,
) -> LoadedData:
    """Load both source files and return them together."""
    return LoadedData(
        claims=load_claims(claims_path),
        eligibility=load_eligibility(eligibility_path),
    )


# Generate a compact terminal summary of a DataFrame for quick inspection.
# This is useful during onboarding, debugging, and ETL validation workflows.
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


# Main execution entrypoint for standalone script usage.
# This loads both datasets and prints summaries for quick validation.
def main() -> None:
    loaded = load_all_data()

    summarize_dataframe(loaded.claims, "claims_raw.csv")
    summarize_dataframe(loaded.eligibility, "eligibility.csv")

    print("\nLoad complete.")


# Standard Python script entrypoint check.
# This ensures main() only runs when the file is executed directly.
if __name__ == "__main__":
    main()