# Cursor Onboarding – Mock 340B ETL Project
## Purpose
This repo is a small, realistic simulation of a 340B data workflow.  
It is designed to demonstrate how to use Cursor to:
- inspect messy data
- plan transformations
- implement cleaning logic
- validate outputs
- generate simple reports
---
## Project Structure

testRepo/
data/
claims_raw.csv
eligibility.csv
src/
load_data.py
transform.py
report.py
outputs/

---

## Data Notice

All files in `data/` are synthetic demo data created for onboarding.  

They do not contain real patient information, real claim records, or real PHI.

---


## Data Overview
### claims_raw.csv
Mock pharmacy claims data with intentional issues:
- mixed date formats
- duplicate rows
- missing patient_id
- inconsistent NDC formatting
- reversals and rejected claims
### eligibility.csv
Mock eligibility data:
- overlapping eligibility periods
- missing end dates
- inactive/pending statuses
- patients not present in claims
---
## Workflow
### 1. Inspect Data (Cursor Ask mode)
Goal: understand structure and issues before coding
Example prompts:
- "Summarize claims_raw.csv structure"
- "What data quality issues exist in this file?"
---
### 2. Plan Transformations (Cursor Plan mode)
Goal: define approach before implementation
Example:
- "Plan how to clean and normalize this dataset for 340B matching"
---
### 3. Load Data
Run:

cd /Users/justincurtsinger/Documents/onboarding/testRepo
python3 src/load_data.py

What it does:
- loads both datasets
- validates required columns
- prints summaries
---
### 4. Transform Data
Run:

cd /Users/justincurtsinger/Documents/onboarding/testRepo
python3 src/transform.py

What it does:
- standardizes dates (YYYY-MM-DD)
- normalizes NDC to 11-digit format
- removes exact duplicates
- converts numeric fields
- adds data quality flags
Outputs:

outputs/claims_clean.csv
outputs/eligibility_clean.csv

---
### 5. Generate Report
Run:

cd /Users/justincurtsinger/Documents/onboarding/testRepo
python3 src/report.py

What it does:
- summarizes data quality issues
- aggregates pharmacy and payer data
- produces QA outputs
Outputs:

outputs/claim_quality_summary.csv
outputs/eligibility_quality_summary.csv
outputs/pharmacy_summary.csv
outputs/payer_summary.csv
outputs/report_summary.txt

---
## Key Concepts to Learn
### 1. Always Inspect First
Use Cursor Ask mode before writing code.
### 2. Plan Before Coding
Use Plan mode to structure approach.
### 3. Constrain Scope
When using Agent mode:
- select only relevant files
- avoid broad, uncontrolled changes
### 4. Iterate, Don’t Overwrite
Refine prompts instead of rewriting everything.
### 5. Validate Outputs
Always check:
- row counts
- missing values
- unexpected drops/spikes
---
## Suggested Exercises
1. Fix NDC normalization logic
2. Improve date parsing edge cases
3. Identify why certain claims fail eligibility
4. Add a match rate calculation
5. Introduce a bug and debug it using Cursor
---
## Next Step (Not Implemented Yet)
Create `match.py`:
- join claims to eligibility
- match on:
  - patient_id
  - fill_date between start_date and end_date
- calculate match rate
---
## Notes
- This repo is intentionally small and imperfect
- The goal is to practice workflow, not perfection
- Focus on reasoning and iteration, not memorization