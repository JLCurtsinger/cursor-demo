#!/usr/bin/env python3
"""
report.py

Create simple QA/reporting outputs for the mock 340B onboarding repo.

Expected repo layout:
  testRepo/
    data/
      claims_raw.csv
      eligibility.csv
    src/
      load_data.py
      transform.py
      report.py
    outputs/

Usage from repo root:
  python3 src/report.py

This script:
  - ensures cleaned files exist by running transform logic if needed
  - loads outputs/claims_clean.csv and outputs/eligibility_clean.csv
  - creates high-level QA summaries
  - writes:
      outputs/claim_quality_summary.csv
      outputs/eligibility_quality_summary.csv
      outputs/pharmacy_summary.csv
      outputs/payer_summary.csv
      outputs/report_summary.txt
"""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
OUTPUT_DIR = REPO_ROOT / "outputs"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from load_data import load_all_data
from transform import transform_all, write_outputs


CLAIMS_CLEAN_FILE = OUTPUT_DIR / "claims_clean.csv"
ELIGIBILITY_CLEAN_FILE = OUTPUT_DIR / "eligibility_clean.csv"


CLAIM_FLAG_COLUMNS = [
    "missing_patient_id",
    "missing_fill_date",
    "missing_ndc",
    "invalid_ndc_length",
    "missing_pharmacy_npi",
    "missing_prescriber_npi",
    "is_reversal",
    "is_rejected",
]

ELIGIBILITY_FLAG_COLUMNS = [
    "missing_patient_id",
    "missing_eligibility_start_date",
    "open_ended_eligibility",
    "inactive_or_pending_status",
    "eligibility_end_before_start",
]


def ensure_clean_outputs() -> None:
    """Create cleaned files if transform.py has not been run yet."""
    if CLAIMS_CLEAN_FILE.exists() and ELIGIBILITY_CLEAN_FILE.exists():
        return

    print("Cleaned files not found. Running transform logic first.")
    raw = load_all_data()
    transformed = transform_all(raw)
    write_outputs(transformed)


def load_clean_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load transformed claims and eligibility files."""
    ensure_clean_outputs()

    claims = pd.read_csv(CLAIMS_CLEAN_FILE, dtype=str, keep_default_na=False)
    eligibility = pd.read_csv(ELIGIBILITY_CLEAN_FILE, dtype=str, keep_default_na=False)

    return claims, eligibility


def count_true_values(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Count boolean-like true values for selected flag columns."""
    rows = []

    for column in columns:
        if column not in df.columns:
            continue

        normalized = df[column].astype(str).str.lower().isin(["true", "1", "yes"])
        rows.append(
            {
                "check_name": column,
                "issue_count": int(normalized.sum()),
                "total_rows": int(len(df)),
                "issue_rate": round(float(normalized.mean()), 4) if len(df) else 0.0,
            }
        )

    return pd.DataFrame(rows)


def summarize_pharmacy_activity(claims: pd.DataFrame) -> pd.DataFrame:
    """Summarize claim volume by pharmacy."""
    if "pharmacy_name" not in claims.columns:
        claims["pharmacy_name"] = ""

    summary = (
        claims.groupby(["pharmacy_npi", "pharmacy_name"], dropna=False)
        .size()
        .reset_index(name="claim_count")
        .sort_values(["claim_count", "pharmacy_npi"], ascending=[False, True])
    )

    return summary


def summarize_payer_activity(claims: pd.DataFrame) -> pd.DataFrame:
    """Summarize claim volume and financial fields by payer."""
    working = claims.copy()

    if "gross_amount" not in working.columns and "total_paid" in working.columns:
        working["gross_amount"] = working["total_paid"]
    if "patient_paid_amount" not in working.columns and "patient_pay" in working.columns:
        working["patient_paid_amount"] = working["patient_pay"]

    for column in ["gross_amount", "patient_paid_amount", "plan_paid_amount"]:
        if column in working.columns:
            working[column] = pd.to_numeric(working[column], errors="coerce").fillna(0.0)

    if "gross_amount" in working.columns and "patient_paid_amount" in working.columns:
        if "plan_paid_amount" not in working.columns:
            working["plan_paid_amount"] = (
                working["gross_amount"] - working["patient_paid_amount"]
            ).round(2)

    group_columns: list[str] = []
    if "payer_type" in working.columns:
        group_columns.append("payer_type")
    if "payer_name" in working.columns:
        group_columns.append("payer_name")
    elif "primary_payer" in working.columns:
        working = working.copy()
        working["payer_name"] = working["primary_payer"]
        group_columns.append("payer_name")

    if not group_columns:
        return pd.DataFrame()

    aggregations = {"claim_id": "count"}

    for column in ["gross_amount", "patient_paid_amount", "plan_paid_amount"]:
        if column in working.columns:
            aggregations[column] = "sum"

    summary = working.groupby(group_columns, dropna=False).agg(aggregations).reset_index()
    summary = summary.rename(columns={"claim_id": "claim_count"})

    money_columns = ["gross_amount", "patient_paid_amount", "plan_paid_amount"]
    for column in money_columns:
        if column in summary.columns:
            summary[column] = summary[column].round(2)

    return summary.sort_values("claim_count", ascending=False)


def calculate_basic_metrics(claims: pd.DataFrame, eligibility: pd.DataFrame) -> dict[str, int]:
    """Calculate simple high-level metrics."""
    unique_claim_patients = (
        claims["patient_id"].replace("", pd.NA).dropna().nunique()
        if "patient_id" in claims.columns
        else 0
    )
    unique_eligibility_patients = (
        eligibility["patient_id"].replace("", pd.NA).dropna().nunique()
        if "patient_id" in eligibility.columns
        else 0
    )

    active_eligibility_rows = 0
    if "eligibility_status" in eligibility.columns:
        active_eligibility_rows = int(
            eligibility["eligibility_status"].astype(str).str.upper().eq("ACTIVE").sum()
        )

    return {
        "total_clean_claim_rows": int(len(claims)),
        "total_clean_eligibility_rows": int(len(eligibility)),
        "unique_claim_patients": int(unique_claim_patients),
        "unique_eligibility_patients": int(unique_eligibility_patients),
        "active_eligibility_rows": int(active_eligibility_rows),
    }


def build_text_report(
    metrics: dict[str, int],
    claim_quality: pd.DataFrame,
    eligibility_quality: pd.DataFrame,
    pharmacy_summary: pd.DataFrame,
    payer_summary: pd.DataFrame,
) -> str:
    """Build a plain-text report for quick review in terminal or Cursor."""
    lines: list[str] = []

    lines.append("Mock 340B QA Report")
    lines.append("===================")
    lines.append("")
    lines.append("Basic metrics")
    lines.append("-------------")
    for key, value in metrics.items():
        lines.append(f"{key}: {value:,}")

    lines.append("")
    lines.append("Claim quality checks")
    lines.append("--------------------")
    if claim_quality.empty:
        lines.append("No claim quality flags found.")
    else:
        for _, row in claim_quality.iterrows():
            lines.append(
                f"{row['check_name']}: {int(row['issue_count']):,} "
                f"of {int(row['total_rows']):,} rows "
                f"({float(row['issue_rate']):.2%})"
            )

    lines.append("")
    lines.append("Eligibility quality checks")
    lines.append("--------------------------")
    if eligibility_quality.empty:
        lines.append("No eligibility quality flags found.")
    else:
        for _, row in eligibility_quality.iterrows():
            lines.append(
                f"{row['check_name']}: {int(row['issue_count']):,} "
                f"of {int(row['total_rows']):,} rows "
                f"({float(row['issue_rate']):.2%})"
            )

    lines.append("")
    lines.append("Top pharmacies by claim volume")
    lines.append("------------------------------")
    if pharmacy_summary.empty:
        lines.append("No pharmacy summary available.")
    else:
        for _, row in pharmacy_summary.head(10).iterrows():
            pharmacy_npi = row.get("pharmacy_npi", "")
            pharmacy_name = row.get("pharmacy_name", "")
            lines.append(f"{pharmacy_npi} | {pharmacy_name}: {int(row['claim_count']):,}")

    lines.append("")
    lines.append("Payer summary")
    lines.append("-------------")
    if payer_summary.empty:
        lines.append("No payer summary available.")
    else:
        for _, row in payer_summary.head(10).iterrows():
            payer_type = row.get("payer_type", "")
            payer_name = row.get("payer_name", "")
            claim_count = int(row.get("claim_count", 0))
            gross_amount = float(row.get("gross_amount", 0.0))
            lines.append(
                f"{payer_type} | {payer_name}: {claim_count:,} claims, "
                f"${gross_amount:,.2f} gross"
            )

    lines.append("")
    lines.append("Recommended next step")
    lines.append("---------------------")
    lines.append(
        "Run match.py next to join cleaned claims to active eligibility periods and calculate match rates."
    )

    return "\n".join(lines) + "\n"


def write_report_outputs(
    claim_quality: pd.DataFrame,
    eligibility_quality: pd.DataFrame,
    pharmacy_summary: pd.DataFrame,
    payer_summary: pd.DataFrame,
    text_report: str,
) -> None:
    """Write report artifacts to outputs/."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    claim_quality.to_csv(OUTPUT_DIR / "claim_quality_summary.csv", index=False)
    eligibility_quality.to_csv(OUTPUT_DIR / "eligibility_quality_summary.csv", index=False)
    pharmacy_summary.to_csv(OUTPUT_DIR / "pharmacy_summary.csv", index=False)

    if not payer_summary.empty:
        payer_summary.to_csv(OUTPUT_DIR / "payer_summary.csv", index=False)
    else:
        pd.DataFrame().to_csv(OUTPUT_DIR / "payer_summary.csv", index=False)

    (OUTPUT_DIR / "report_summary.txt").write_text(text_report, encoding="utf-8")


def main() -> None:
    claims, eligibility = load_clean_data()

    metrics = calculate_basic_metrics(claims, eligibility)
    claim_quality = count_true_values(claims, CLAIM_FLAG_COLUMNS)
    eligibility_quality = count_true_values(eligibility, ELIGIBILITY_FLAG_COLUMNS)
    pharmacy_summary = summarize_pharmacy_activity(claims)
    payer_summary = summarize_payer_activity(claims)

    text_report = build_text_report(
        metrics=metrics,
        claim_quality=claim_quality,
        eligibility_quality=eligibility_quality,
        pharmacy_summary=pharmacy_summary,
        payer_summary=payer_summary,
    )

    write_report_outputs(
        claim_quality=claim_quality,
        eligibility_quality=eligibility_quality,
        pharmacy_summary=pharmacy_summary,
        payer_summary=payer_summary,
        text_report=text_report,
    )

    print(text_report)
    print("Wrote report outputs to outputs/.")


if __name__ == "__main__":
    main()
