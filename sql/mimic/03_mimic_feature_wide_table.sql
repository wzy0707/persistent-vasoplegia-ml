-- ============================================================================
-- Step 13【特征宽表】每个 stay 一行，供 R/Python 建模
-- 口径：
--   动态特征（MAP/NEE/血管药/生命体征/液体）窗口 [t0, landmark)，时间戳严格 < landmark；
--   化验取 landmark 前最近值（窗口 [intime-1day, landmark)）；
--   静态特征 = 人口学 + 体重 + 合并症；
--   最终宽表直接排除 prevalent（prev_flag=1），并挂上 incident 结局（vs_label）。
-- 预期：建模宽表 n=17,463，阳性 463（2.65%）。
-- 逐段 F5、逐段验证。每段开头 SET 与 CREATE 同批次。
-- ============================================================================
SET work_mem='256MB';
SET enable_nestloop=off;

-- ----------------------------------------------------------------------------
-- 13-1. MAP 特征（[t0, landmark)）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.tmp_feat_map;
CREATE TABLE mimiciv_derived.tmp_feat_map AS
SELECT m.stay_id,
    (ARRAY_AGG(m.map ORDER BY m.charttime))[1]      AS map_first,
    (ARRAY_AGG(m.map ORDER BY m.charttime DESC))[1] AS map_last,
    MIN(m.map)    AS map_min,
    MAX(m.map)    AS map_max,
    AVG(m.map)    AS map_mean,
    STDDEV_SAMP(m.map) AS map_sd,
    AVG(CASE WHEN m.map<65 THEN 1.0 ELSE 0 END) AS map_below65_frac
FROM mimiciv_derived.vs_cohort c
JOIN mimiciv_derived.vs_map_long m
  ON m.stay_id=c.stay_id AND m.charttime>=c.t0 AND m.charttime<c.landmark
GROUP BY m.stay_id;

-- ----------------------------------------------------------------------------
-- 13-2. NEE 时序特征（复用 Step12 网格结果 tmp_nee_grid_a，去掉 landmark 点）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.tmp_feat_nee;
CREATE TABLE mimiciv_derived.tmp_feat_nee AS
SELECT ng.stay_id,
    (ARRAY_AGG(ng.nee ORDER BY ng.ts))[1]      AS nee_first,
    (ARRAY_AGG(ng.nee ORDER BY ng.ts DESC))[1] AS nee_last,
    MIN(ng.nee) AS nee_min,
    MAX(ng.nee) AS nee_max,
    AVG(ng.nee) AS nee_mean,
    AVG(CASE WHEN ng.nee>=0.5 THEN 1.0 ELSE 0 END) AS nee_high_frac
FROM mimiciv_derived.vs_cohort c
JOIN mimiciv_derived.tmp_nee_grid_a ng
  ON ng.stay_id=c.stay_id AND ng.ts>=c.t0 AND ng.ts<c.landmark
GROUP BY ng.stay_id;

-- ----------------------------------------------------------------------------
-- 13-3. 血管药种类与各药峰值（[t0, landmark)）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.tmp_feat_drug;
CREATE TABLE mimiciv_derived.tmp_feat_drug AS
SELECT vd.stay_id,
    COUNT(DISTINCT vd.drug) AS n_drug,
    MAX(CASE WHEN vd.drug='norepinephrine' THEN 1 ELSE 0 END) AS ne_used,
    MAX(CASE WHEN vd.drug='phenylephrine' THEN 1 ELSE 0 END) AS pe_used,
    MAX(CASE WHEN vd.drug='vasopressin'    THEN 1 ELSE 0 END) AS vaso_used,
    MAX(CASE WHEN vd.drug='epinephrine'    THEN 1 ELSE 0 END) AS epi_used,
    MAX(CASE WHEN vd.drug='dopamine'       THEN 1 ELSE 0 END) AS dopa_used,
    MAX(CASE WHEN vd.drug='angiotensin_ii' THEN 1 ELSE 0 END) AS ang2_used,
    MAX(CASE WHEN vd.drug='dobutamine'     THEN 1 ELSE 0 END) AS dobut_used,
    MAX(CASE WHEN vd.drug='norepinephrine' THEN vd.drug_rate END) AS ne_maxrate,
    MAX(CASE WHEN vd.drug='phenylephrine' THEN vd.drug_rate END) AS pe_maxrate,
    MAX(CASE WHEN vd.drug='vasopressin'    THEN vd.drug_rate END) AS vaso_maxrate,
    MAX(CASE WHEN vd.drug='epinephrine'    THEN vd.drug_rate END) AS epi_maxrate,
    MAX(CASE WHEN vd.drug='dopamine'       THEN vd.drug_rate END) AS dopa_maxrate
FROM mimiciv_derived.vs_cohort c
JOIN mimiciv_derived.vs_vaso_dose vd
  ON vd.stay_id=c.stay_id AND vd.starttime>=c.t0 AND vd.starttime<c.landmark
GROUP BY vd.stay_id;

-- ----------------------------------------------------------------------------
-- 13-4. 生命体征：先按 (stay,label) 聚合，再 pivot
--   label 为 MIMIC d_items 标准名（若本地 label 不同，先跑：
--   SELECT label,count(*) FROM mimiciv_derived.vs_vitals_long GROUP BY 1 ORDER BY 1;）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.tmp_vit_agg;
CREATE TABLE mimiciv_derived.tmp_vit_agg AS
SELECT v.stay_id, v.label,
    (ARRAY_AGG(v.valuenum ORDER BY v.charttime))[1]      AS v_first,
    (ARRAY_AGG(v.valuenum ORDER BY v.charttime DESC))[1] AS v_last,
    MIN(v.valuenum) AS v_min,
    MAX(v.valuenum) AS v_max,
    AVG(v.valuenum) AS v_mean
FROM mimiciv_derived.vs_cohort c
JOIN mimiciv_derived.vs_vitals_long v
  ON v.stay_id=c.stay_id AND v.charttime>=c.t0 AND v.charttime<c.landmark
GROUP BY v.stay_id, v.label;

DROP TABLE IF EXISTS mimiciv_derived.tmp_feat_vit;
CREATE TABLE mimiciv_derived.tmp_feat_vit AS
SELECT stay_id,
    MAX(CASE WHEN label='Heart Rate' THEN v_last END) AS hr_last,
    MAX(CASE WHEN label='Heart Rate' THEN v_min  END) AS hr_min,
    MAX(CASE WHEN label='Heart Rate' THEN v_max  END) AS hr_max,
    MAX(CASE WHEN label='Heart Rate' THEN v_mean END) AS hr_mean,
    MAX(CASE WHEN label='Arterial Blood Pressure systolic' THEN v_last END) AS abps_last,
    MAX(CASE WHEN label='Arterial Blood Pressure systolic' THEN v_min  END) AS abps_min,
    MAX(CASE WHEN label='Arterial Blood Pressure systolic' THEN v_mean END) AS abps_mean,
    MAX(CASE WHEN label='Arterial Blood Pressure diastolic' THEN v_last END) AS abpd_last,
    MAX(CASE WHEN label='Arterial Blood Pressure diastolic' THEN v_mean END) AS abpd_mean,
    MAX(CASE WHEN label='Arterial Blood Pressure mean' THEN v_last END) AS abpm_last,
    MAX(CASE WHEN label='Arterial Blood Pressure mean' THEN v_mean END) AS abpm_mean,
    MAX(CASE WHEN label='Non Invasive Blood Pressure systolic' THEN v_last END) AS nbps_last,
    MAX(CASE WHEN label='Non Invasive Blood Pressure systolic' THEN v_min  END) AS nbps_min,
    MAX(CASE WHEN label='Non Invasive Blood Pressure systolic' THEN v_mean END) AS nbps_mean,
    MAX(CASE WHEN label='Non Invasive Blood Pressure diastolic' THEN v_last END) AS nbpd_last,
    MAX(CASE WHEN label='Non Invasive Blood Pressure mean' THEN v_last END) AS nbpm_last,
    MAX(CASE WHEN label='Respiratory Rate' THEN v_last END) AS rr_last,
    MAX(CASE WHEN label='Respiratory Rate' THEN v_mean END) AS rr_mean,
    MAX(CASE WHEN label='O2 saturation pulseoxymetry' THEN v_last END) AS spo2_last,
    MAX(CASE WHEN label='O2 saturation pulseoxymetry' THEN v_min  END) AS spo2_min,
    MAX(CASE WHEN label='O2 saturation pulseoxymetry' THEN v_mean END) AS spo2_mean,
    MAX(CASE WHEN label='Temperature Celsius'    THEN v_last END) AS temp_c_last,
    MAX(CASE WHEN label='Temperature Fahrenheit' THEN (v_last-32)*5/9 END) AS temp_fromf_last
FROM mimiciv_derived.tmp_vit_agg
GROUP BY stay_id;

-- ----------------------------------------------------------------------------
-- 13-5. 化验：按 (stay,label) 取最近/最大/最小，再 pivot
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.tmp_lab_agg;
CREATE TABLE mimiciv_derived.tmp_lab_agg AS
SELECT l.stay_id, l.label,
    (ARRAY_AGG(l.valuenum ORDER BY l.charttime DESC))[1] AS last_val,
    MAX(l.valuenum) AS max_val,
    MIN(l.valuenum) AS min_val
FROM mimiciv_derived.vs_cohort c
JOIN mimiciv_derived.vs_labs_long l
  ON l.stay_id=c.stay_id AND l.charttime<c.landmark
GROUP BY l.stay_id, l.label;

DROP TABLE IF EXISTS mimiciv_derived.tmp_feat_lab;
CREATE TABLE mimiciv_derived.tmp_feat_lab AS
SELECT stay_id,
    MAX(CASE WHEN label='Lactate'         THEN last_val END) AS lactate_last,
    MAX(CASE WHEN label='Lactate'         THEN max_val  END) AS lactate_max,
    MAX(CASE WHEN label='Creatinine'      THEN last_val END) AS creat_last,
    MAX(CASE WHEN label='WBC'             THEN last_val END) AS wbc_last,
    MAX(CASE WHEN label='Hemoglobin'      THEN last_val END) AS hgb_last,
    MAX(CASE WHEN label='Hematocrit'      THEN last_val END) AS hct_last,
    MAX(CASE WHEN label='Platelet Count'  THEN last_val END) AS plt_last,
    MAX(CASE WHEN label='Sodium'          THEN last_val END) AS na_last,
    MAX(CASE WHEN label='Potassium'       THEN last_val END) AS k_last,
    MAX(CASE WHEN label='Chloride'        THEN last_val END) AS cl_last,
    MAX(CASE WHEN label='Bicarbonate'     THEN last_val END) AS hco3_last,
    MAX(CASE WHEN label='Glucose'         THEN last_val END) AS glucose_last,
    MAX(CASE WHEN label='Calcium, Total'  THEN last_val END) AS ca_last,
    MAX(CASE WHEN label='Magnesium'       THEN last_val END) AS mg_last,
    MAX(CASE WHEN label='Phosphate'       THEN last_val END) AS phos_last,
    MAX(CASE WHEN label='Bilirubin, Total' THEN last_val END) AS bili_last,
    MAX(CASE WHEN label='Albumin'         THEN last_val END) AS albumin_last,
    MAX(CASE WHEN label='Urea Nitrogen'   THEN last_val END) AS bun_last,
    MAX(CASE WHEN label='Anion Gap'       THEN last_val END) AS aniongap_last
FROM mimiciv_derived.tmp_lab_agg
GROUP BY stay_id;

-- ----------------------------------------------------------------------------
-- 13-6. 液体推注（Step7 已限 [t0,landmark]）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.tmp_feat_fluid;
CREATE TABLE mimiciv_derived.tmp_feat_fluid AS
SELECT f.stay_id,
    COUNT(*) AS n_bolus,
    COALESCE(SUM(CASE WHEN lower(COALESCE(f.amountuom,'ml'))='l'
                      THEN f.amount*1000 ELSE f.amount END),0) AS fluid_ml
FROM mimiciv_derived.vs_fluid_bolus f
GROUP BY f.stay_id;

-- ----------------------------------------------------------------------------
-- 13-7. 最终建模宽表（排除 prevalent，挂结局）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.vs_ml_wide;
CREATE TABLE mimiciv_derived.vs_ml_wide AS
SELECT
    c.stay_id, c.subject_id, c.hadm_id,
    c.age,
    CASE WHEN c.gender='M' THEN 1 ELSE 0 END AS male,
    c.race,
    c.first_careunit,
    w.weight_kg,
    cm.diabetes, cm.hypertension, cm.chf, cm.chronic_pulmonary,
    cm.chronic_liver, cm.ckd, cm.metastatic_cancer, cm.arrhythmia,
    mp.map_first, mp.map_last, mp.map_min, mp.map_max, mp.map_mean, mp.map_sd, mp.map_below65_frac,
    ne.nee_first, ne.nee_last, ne.nee_min, ne.nee_max, ne.nee_mean, ne.nee_high_frac,
    dr.n_drug, dr.ne_used, dr.pe_used, dr.vaso_used, dr.epi_used, dr.dopa_used,
    dr.ang2_used, dr.dobut_used, dr.ne_maxrate, dr.pe_maxrate, dr.vaso_maxrate,
    dr.epi_maxrate, dr.dopa_maxrate,
    vt.hr_last, vt.hr_min, vt.hr_max, vt.hr_mean,
    vt.abps_last, vt.abps_min, vt.abps_mean, vt.abpd_last, vt.abpd_mean, vt.abpm_last, vt.abpm_mean,
    vt.nbps_last, vt.nbps_min, vt.nbps_mean, vt.nbpd_last, vt.nbpm_last,
    vt.rr_last, vt.rr_mean, vt.spo2_last, vt.spo2_min, vt.spo2_mean,
    vt.temp_c_last, vt.temp_fromf_last,
    lb.lactate_last, lb.lactate_max, lb.creat_last, lb.wbc_last, lb.hgb_last, lb.hct_last,
    lb.plt_last, lb.na_last, lb.k_last, lb.cl_last, lb.hco3_last, lb.glucose_last,
    lb.ca_last, lb.mg_last, lb.phos_last, lb.bili_last, lb.albumin_last, lb.bun_last, lb.aniongap_last,
    COALESCE(fl.n_bolus,0) AS n_bolus,
    COALESCE(fl.fluid_ml,0) AS fluid_ml,
    lab.vasoplegia,
    lab.vasoplegia_onset
FROM mimiciv_derived.vs_cohort c
JOIN mimiciv_derived.vs_prevalent p ON c.stay_id=p.stay_id AND p.prev_flag=0
JOIN mimiciv_derived.vs_label    lab ON c.stay_id=lab.stay_id
LEFT JOIN mimiciv_derived.vs_weight   w   ON c.stay_id=w.stay_id
LEFT JOIN mimiciv_derived.vs_comorbid cm  ON c.stay_id=cm.stay_id
LEFT JOIN mimiciv_derived.tmp_feat_map  mp ON c.stay_id=mp.stay_id
LEFT JOIN mimiciv_derived.tmp_feat_nee  ne ON c.stay_id=ne.stay_id
LEFT JOIN mimiciv_derived.tmp_feat_drug dr ON c.stay_id=dr.stay_id
LEFT JOIN mimiciv_derived.tmp_feat_vit  vt ON c.stay_id=vt.stay_id
LEFT JOIN mimiciv_derived.tmp_feat_lab  lb ON c.stay_id=lb.stay_id
LEFT JOIN mimiciv_derived.tmp_feat_fluid fl ON c.stay_id=fl.stay_id;

-- ============================================================================
-- 验证
-- ============================================================================
-- 1) 行数与阳性率：预期 n=17,463，阳性 463
SELECT vasoplegia, count(*) FROM mimiciv_derived.vs_ml_wide GROUP BY 1 ORDER BY 1;

-- 2) 各特征非空率（应大部分非空；若某类整列 NULL，多为 label 不匹配，
--    先跑 SELECT DISTINCT label FROM vs_vitals_long / vs_labs_long 核对）
SELECT count(*) n,
    count(map_last) map_n, count(nee_last) nee_n, count(hr_last) hr_n,
    count(lactate_last) lact_n, count(creat_last) creat_n,
    count(abps_last) art_n, count(nbps_last) nbp_n,
    count(temp_c_last) tempc_n, count(fluid_ml) fluid_n
FROM mimiciv_derived.vs_ml_wide;
-- ============================================================================
