# Feature dictionary — 77 model predictors

All predictors are measured over the landmark window from `t0` (first vasopressor) to
`t0 + 6 h`. The label `vasoplegia` is **not** a predictor. The preprocessing pipeline treats
62 numeric columns (median imputation + standardization) and 15 binary columns (passed through).

The 20 columns marked **[T]** are treatment-related; the leakage analysis (M2) drops them and
retains the other 57 non-treatment predictors.

## Demographics & comorbidities
| Feature | Type | Description |
|---|---|---|
| `age` | numeric | Age at ICU admission (years) |
| `male` | binary | Sex = male (1) vs female (0) |
| `weight_kg` | numeric | Body weight (kg) |
| `diabetes` | binary | Diabetes comorbidity |
| `hypertension` | binary | Hypertension comorbidity |
| `chf` | binary | Congestive heart failure |
| `chronic_pulmonary` | binary | Chronic pulmonary disease |
| `chronic_liver` | binary | Chronic liver disease |
| `ckd` | binary | Chronic kidney disease |
| `metastatic_cancer` | binary | Metastatic cancer |
| `arrhythmia` | binary | Cardiac arrhythmia |

## MAP hemodynamics (non-treatment)
| Feature | Type | Description |
|---|---|---|
| `map_first` | numeric | First mean arterial pressure in window (mmHg) |
| `map_last` | numeric | Last MAP (mmHg) |
| `map_min` | numeric | Minimum MAP (mmHg) |
| `map_max` | numeric | Maximum MAP (mmHg) |
| `map_mean` | numeric | Mean MAP (mmHg) |
| `map_sd` | numeric | Standard deviation of MAP |
| `map_below65_frac` | numeric | Fraction of grid points with MAP < 65 |

## Vasoactive exposure — treatment **[T]**
| Feature | Type | Description |
|---|---|---|
| `nee_first` **[T]** | numeric | First norepinephrine-equivalent exposure |
| `nee_last` **[T]** | numeric | Last NEE (strongest univariate signal) |
| `nee_min` **[T]** | numeric | Minimum NEE |
| `nee_max` **[T]** | numeric | Maximum NEE |
| `nee_mean` **[T]** | numeric | Mean NEE |
| `nee_high_frac` **[T]** | numeric | Fraction of time NEE >= 0.5 |
| `n_drug` **[T]** | numeric | Number of distinct vasoactive agents |
| `ne_used` **[T]** | binary | Norepinephrine used |
| `pe_used` **[T]** | binary | Phenylephrine used |
| `vaso_used` **[T]** | binary | Vasopressin used |
| `epi_used` **[T]** | binary | Epinephrine used |
| `dopa_used` **[T]** | binary | Dopamine used |
| `ang2_used` **[T]** | binary | Angiotensin II used |
| `ne_maxrate` **[T]** | numeric | Max norepinephrine rate |
| `pe_maxrate` **[T]** | numeric | Max phenylephrine rate |
| `vaso_maxrate` **[T]** | numeric | Max vasopressin rate |
| `epi_maxrate` **[T]** | numeric | Max epinephrine rate |
| `dopa_maxrate` **[T]** | numeric | Max dopamine rate |

## Other vital signs
| Feature | Type | Description |
|---|---|---|
| `hr_last` | numeric | Last heart rate |
| `hr_min` | numeric | Minimum heart rate |
| `hr_max` | numeric | Maximum heart rate |
| `hr_mean` | numeric | Mean heart rate |
| `rr_last` | numeric | Last respiratory rate |
| `rr_mean` | numeric | Mean respiratory rate |
| `spo2_last` | numeric | Last SpO2 (%) |
| `spo2_min` | numeric | Minimum SpO2 (%) |
| `spo2_mean` | numeric | Mean SpO2 (%) |

## Laboratory values
| Feature | Type | Description |
|---|---|---|
| `lactate_last` | numeric | Last lactate |
| `lactate_max` | numeric | Maximum lactate |
| `creat_last` | numeric | Last creatinine |
| `wbc_last` | numeric | Last white blood cell count |
| `hgb_last` | numeric | Last hemoglobin |
| `hct_last` | numeric | Last hematocrit |
| `plt_last` | numeric | Last platelet count |
| `na_last` | numeric | Last sodium |
| `k_last` | numeric | Last potassium |
| `cl_last` | numeric | Last chloride |
| `hco3_last` | numeric | Last bicarbonate |
| `glucose_last` | numeric | Last glucose |
| `ca_last` | numeric | Last calcium |
| `mg_last` | numeric | Last magnesium |
| `phos_last` | numeric | Last phosphate |
| `bili_last` | numeric | Last bilirubin |
| `albumin_last` | numeric | Last albumin |
| `bun_last` | numeric | Last blood urea nitrogen |
| `aniongap_last` | numeric | Last anion gap |

## Fluids — treatment **[T]**
| Feature | Type | Description |
|---|---|---|
| `n_bolus` **[T]** | numeric | Number of fluid boluses |
| `fluid_ml` **[T]** | numeric | Total fluid administered (mL) |

## Engineered features
| Feature | Type | Description |
|---|---|---|
| `sbp_last` | numeric | Last systolic BP (merged invasive/non-invasive) |
| `sbp_min` | numeric | Minimum systolic BP |
| `sbp_mean` | numeric | Mean systolic BP |
| `dbp_last` | numeric | Last diastolic BP |
| `temp_last` | numeric | Last temperature (merged sources, Celsius) |
| `race_grp_hispanic` | binary | Race group: Hispanic |
| `race_grp_other` | binary | Race group: other/unknown |
| `race_grp_white` | binary | Race group: white (reference group implicit) |
| `cu_grp_micu` | binary | Care unit: medical ICU |
| `cu_grp_other` | binary | Care unit: other |
| `cu_grp_sicu` | binary | Care unit: surgical ICU |

## NEE conversion factors
Norepinephrine-equivalent dose combines agents as:
NE ×1 + epinephrine ×1 + dopamine ×0.01 + phenylephrine ×0.1 + vasopressin (U/min) ×2.5 +
angiotensin II (ng/kg/min) ×0.0025 + metaraminol ×0.125. Dobutamine is not counted.
The eICU pipeline has 5 agents (no angiotensin II or metaraminol).
