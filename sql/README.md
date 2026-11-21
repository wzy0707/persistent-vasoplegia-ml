# SQL extraction layer

These scripts run against a local PostgreSQL build of the PhysioNet databases
(MIMIC-IV v2.x and eICU-CRD). They contain no patient data; they only query the source
tables. You must first complete PhysioNet credentialing and load the databases yourself.

## Prerequisites
1. Credentialed PhysioNet account (https://physionet.org/settings/credentialing/).
2. MIMIC-IV and eICU-CRD loaded in PostgreSQL (e.g. via the PhysioNet loading scripts).
3. A client such as pgAdmin or `psql`.

## MIMIC-IV (`mimic/`) — run in numeric order
| Order | Script | Output / purpose |
|---|---|---|
| 1 | `01_mimic_base_extraction.sql` | Cohort, 5-min grid, vasopressor dosing, MAP |
| 2 | `02_mimic_label_definition.sql` | Outcome label: NEE >= 0.5 for >= 6 h with MAP < 65 |
| 3 | `03_mimic_feature_wide_table.sql` | `vs_ml_wide` (17,463 x 88) |
| 4 | `04_mimic_funnel_QA.sql` | Independent funnel/QA counts |
| 5 | `05_mimic_external_anchor_optional.sql` | Optional anchor table |

Expected QA counts: source cohort 17,526 -> 63 prevalent excluded -> 17,463 modelling rows;
463 incident events (2.65%).

## eICU-CRD (`eicu/`) — run in numeric order
| Order | Script | Output / purpose |
|---|---|---|
| 1 | `01_eicu_cohort.sql` | Infection + vasopressor cohort |
| 2 | `02_eicu_dose_NEE.sql` | Dose conversion and NEE |
| 3 | `03_eicu_MAP.sql` | MAP extraction |
| 4 | `04_eicu_t0.sql` | `t0` determination |
| 5 | `05_eicu_wide_table.sql` | Feature wide table (2,268 rows) |

## Supplementary analyses (`supplementary/`)
| Script | Purpose |
|---|---|
| `06_pH_extraction.sql` | Arterial/venous pH extraction (itemid 223830 primary, 220274 fallback) |
| `06b_pH_diagnostic.sql` | pH coverage diagnostics |
| `07_48h_sensitivity.sql` | Extended 48-hour outcome window |
| `export_eicu_label.sql` | Exports the eICU label (`e_label`) needed by step3 |
| `export_anchor.sql` | Exports `vs_anchor.csv` needed by step7 |
| `review_sensitivity.sql` | Reviewer-requested sensitivity extractions |
| `supplementary_QA.sql` | Additional QA cross-checks |

After running the SQL, export the resulting tables to CSV at the **project root** so the
Python step scripts (which resolve paths relative to their own directory) can find them.
