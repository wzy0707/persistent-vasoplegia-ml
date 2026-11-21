# Early prediction of persistent refractory vasoplegia in septic shock — machine learning

A reproducible two-database machine-learning pipeline that predicts **persistent refractory
vasoplegia** within the first 6 hours of vasopressor therapy. The model is developed and
internally validated in **MIMIC-IV** and externally validated in **eICU-CRD**.

- **Development / internal validation:** MIMIC-IV — 17,463 patients, 463 events (2.65%)
- **External validation:** eICU-CRD — 2,268 patients, 165 events (7.28%)
- **Model:** calibrated XGBoost (isotonic calibration), 77 predictors
- **Internal performance:** AUROC 0.941, AUPRC 0.351, Brier 0.020
- **External performance:** AUROC 0.900, AUPRC 0.410 (after recalibration Brier 0.052)

> **No patient data are included in this repository.** MIMIC-IV and eICU-CRD are
> credentialed, restricted-access PhysioNet databases. Every data file and the trained model
> are regenerated locally from the SQL and Python code below. See *Data access*.

## Outcome definition

The primary outcome is persistent refractory vasoplegia: norepinephrine-equivalent exposure
(NEE) >= 0.5 sustained for at least 6 consecutive hours (72 five-minute grid points) together
with MAP < 65 mmHg. Missing MAP does not interrupt a high-dose episode. The prediction
landmark is `t0 + 6 h`, where `t0` is the first vasopressor; the prediction window runs from
the landmark to `t0 + 30 h`.

## Repository structure

```
.
├── README.md                  # this file
├── LICENSE                    # MIT (code only; not a data licence)
├── requirements.txt          # pinned Python dependencies
├── .gitignore                 # excludes regenerated patient data / model / outputs
├── step1_*.py ... step12_*.py # analysis pipeline (run in order)
├── sql/
│   ├── mimic/                 # 5 MIMIC extraction scripts
│   ├── eicu/                  # 5 eICU extraction scripts
│   ├── supplementary/         # pH, 48-h, label/anchor exports, QA
│   └── README.md
├── docs/
│   └── feature_dictionary.md  # all 77 predictors with definitions
├── tools/                     # optional manuscript/export utilities
└── figures/                   # output directory for generated figures
```

## Environment setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Tested with Python 3.10/3.11. Pinned versions are in `requirements.txt`; the core stack is
numpy, pandas, scikit-learn, xgboost, statsmodels, shap, matplotlib and openpyxl.

## Data access

1. Complete PhysioNet credentialing: https://physionet.org/settings/credentialing/
2. Load MIMIC-IV and eICU-CRD into PostgreSQL.
3. Run the scripts in `sql/` in the order described in `sql/README.md`.
4. Export the resulting tables to CSV **in the project root**:
   - MIMIC: `vs_ml_wide.csv` (17,463 x 88)
   - eICU: eICU wide table plus `e_label` (use `sql/supplementary/export_eicu_label.sql`)
   - anchor: `vs_anchor.csv` (use `sql/supplementary/export_anchor.sql`)

## Reproduction pipeline

Run the step scripts from the project root. Each script resolves its inputs relative to its
own location and writes outputs back to the root.

| Step | Script | Input | Output |
|---|---|---|---|
| 1 | `step1_mimic_engineering_univariate.py` | `vs_ml_wide.csv` | `mimic_77_matrix.csv`, univariate workbook |
| 2 | `step2_retrain_model.py` | `mimic_77_matrix.csv` | `vasoplegia_retrained.joblib`, metrics workbook |
| 3 | `step3_eicu_external_validation.py` | eICU wide + `e_label` + model | `eicu_pred.csv`, validation workbook |
| 4 | `step4_make_figures.py` | model + data | Figures 1–4 (PDF/TIFF/PNG) |
| 5 | `step5_internal_analyses.py` | matrix + model | candidate/nested/subgroup/leakage workbook |
| 6 | `step6_eicu_supplementary.py` | `eicu_pred.csv` | PPV/NPV/ECE workbook |
| 7 | `step7_anchor_table.py` | wide + matrix + model + anchor | anchor outcome workbook |
| 8 | `step8_head_to_head_ress.py` | both databases + pH | head-to-head vs RSSS and logistic score |
| 9 | `step9_de_novo_sensitivity.py` | matrix + onset type | de-novo-only sensitivity |
| 10 | `step10_low_dose_bootstrap.py` | matrix + model | low-dose bootstrap CIs |
| 11 | `step11_48h_performance.py` | matrix + 48-h label | 48-hour window performance |
| 12 | `step12_enhanced_calibration_dca.py` | model + data | enhanced calibration & decision-curve figures |

### Key fixed parameters
- Train/test split: 70/30 stratified, `random_state=42` (12,224 / 5,239; 139 test events).
- XGBoost: 200 estimators, depth 4, learning rate 0.05, subsample/colsample 0.8,
  `reg_lambda=1`, `objective=binary:logistic`, seed 42.
- Calibration: `CalibratedClassifierCV` with isotonic regression, 5-fold.
- External recalibration (locked, not refit): `logit(p_new) = 0.389 + 0.814 * logit(p_old)`,
  new cutpoint 0.097; MIMIC cutpoint 0.0379.

## Expected headline results

| Setting | AUROC | AUPRC | Brier |
|---|---|---|---|
| MIMIC internal (test) | 0.941 | 0.351 | 0.020 |
| eICU external (raw) | 0.900 | 0.410 | 0.053 |
| eICU external (recalibrated) | 0.900 | 0.410 | 0.052 |

Nested leakage analysis (internal): full 77-feature model AUROC 0.942; after dropping
`nee_last` (M1, 76 features) 0.939; after dropping all 20 treatment features (M2,
57 features) 0.916 — non-treatment features alone retain most of the discrimination.

## Citation

If you use this code, please cite the accompanying paper and the two source databases.
The manuscript is currently under review at *Annals of Intensive Care*; replace the year,
volume and DOI below with the final bibliographic details once it is published.

Wang Z. Early prediction of persistent refractory vasoplegia in septic shock using machine
learning: a retrospective two-database development and external validation study. *Annals of
Intensive Care* (under review).

```bibtex
@article{wang2026vasoplegia,
  author  = {Wang, Zhengyi},
  title   = {Early prediction of persistent refractory vasoplegia in septic shock using
             machine learning: a retrospective two-database development and external
             validation study},
  journal = {Annals of Intensive Care},
  year    = {2026},
  note    = {Under review; add volume, pages and DOI on publication}
}
```

Please also credit the underlying databases:

- Johnson AEW, Bulgarelli L, Shen L, et al. MIMIC-IV, a freely accessible electronic health
  record dataset. *Scientific Data*. 2023;10(1):1.
- Pollard TJ, Johnson AEW, Raffa JD, et al. The eICU Collaborative Research Database, a
  freely available multi-center database for critical care research. *Scientific Data*.
  2018;5:180178.

```bibtex
@article{johnson2023mimiciv,
  author  = {Johnson, Alistair E. W. and Bulgarelli, Lucas and Shen, Leo and others},
  title   = {{MIMIC-IV}, a freely accessible electronic health record dataset},
  journal = {Scientific Data},
  volume  = {10},
  number  = {1},
  pages   = {1},
  year    = {2023}
}

@article{pollard2018eicu,
  author  = {Pollard, Tom J. and Johnson, Alistair E. W. and Raffa, Jesse D. and others},
  title   = {The {eICU} Collaborative Research Database, a freely available multi-center
             database for critical care research},
  journal = {Scientific Data},
  volume  = {5},
  pages   = {180178},
  year    = {2018}
}
```

## License

Code released under the MIT License. The licence does not cover MIMIC-IV or eICU-CRD data;
see `LICENSE` and the PhysioNet data use agreement.
