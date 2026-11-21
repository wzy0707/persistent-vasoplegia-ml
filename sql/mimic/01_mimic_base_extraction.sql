-- ============================================================================
-- 课题：基于 MIMIC-IV 构建脓毒症血管麻痹综合征早期 ML 预测模型
-- 第一步：MIMIC-IV 自包含数据提取（PostgreSQL / pgAdmin 直接运行）
-- 适用：MIMIC-IV v2.2 / v3.0
--
-- 【特点】不依赖需命令行生成的 sepsis3 / sofa 派生表，只基于原始表：
--   感染 = 抗生素(prescriptions) 与 培养(microbiologyevents) 在时间窗内配对；
--   休克 = 感染且在 ICU 启动过血管活性药（ingredientevents，按 d_items.label 识别）。
--   请按本地 schema 名替换 mimiciv_hosp / mimiciv_icu / mimiciv_derived。
--
-- 【NEE 换算（去甲肾上腺素当量，μg·kg⁻¹·min⁻¹）】
--   NE×1 + Epi×1 + Dopamine×0.01 + Phenylephrine×0.1
--   + Vasopressin(U·min⁻¹)×2.5 + AngiotensinII(ng·kg⁻¹·min⁻¹)×0.0025
--   + Metaraminol×0.125；Dobutamine 为正性肌力药，不计入 NEE。
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Step 1. 血管活性药“活性成分事件”（ingredientevents JOIN d_items，按 label 归类）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.vs_drug_events;
CREATE TABLE mimiciv_derived.vs_drug_events AS
SELECT
    ie.subject_id, ie.hadm_id, ie.stay_id,
    ie.starttime, ie.endtime,
    ie.amount, ie.amountuom,
    CASE
        WHEN lower(di.label) LIKE '%norepinephrine%' THEN 'norepinephrine'
        WHEN lower(di.label) LIKE '%epinephrine%'
             AND lower(di.label) NOT LIKE '%norepinephrine%' THEN 'epinephrine'
        WHEN lower(di.label) LIKE '%dopamine%' THEN 'dopamine'
        WHEN lower(di.label) LIKE '%phenylephrine%' THEN 'phenylephrine'
        WHEN lower(di.label) LIKE '%vasopressin%' THEN 'vasopressin'
        WHEN lower(di.label) LIKE '%angiotensin ii%'
          OR lower(di.label) LIKE '%angiotensin 2%' THEN 'angiotensin_ii'
        WHEN lower(di.label) LIKE '%metaraminol%' THEN 'metaraminol'
        WHEN lower(di.label) LIKE '%dobutamine%' THEN 'dobutamine'
    END AS drug
FROM mimiciv_icu.inputevents ie
INNER JOIN mimiciv_icu.d_items di ON ie.itemid = di.itemid
WHERE ie.stay_id IS NOT NULL
  AND ie.amount IS NOT NULL
  AND COALESCE(ie.statusdescription,'') NOT IN ('Canceled','Rewritten')
  AND (
        lower(di.label) LIKE '%norepinephrine%'
     OR lower(di.label) LIKE '%epinephrine%'
     OR lower(di.label) LIKE '%dopamine%'
     OR lower(di.label) LIKE '%phenylephrine%'
     OR lower(di.label) LIKE '%vasopressin%'
     OR lower(di.label) LIKE '%angiotensin ii%'
     OR lower(di.label) LIKE '%metaraminol%'
     OR lower(di.label) LIKE '%dobutamine%'
      );

-- ----------------------------------------------------------------------------
-- Step 2. 感染判定：抗生素(prescriptions) + 培养(microbiologyevents) 时间窗配对
--   配对窗：培养在抗生素前 24h 内，或抗生素在培养后 72h 内。
--   suspected_infection_time 取二者较早者。
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.vs_infection;
CREATE TABLE mimiciv_derived.vs_infection AS
WITH abx AS (
    SELECT subject_id, hadm_id, starttime AS abx_time
    FROM mimiciv_hosp.prescriptions
    WHERE starttime IS NOT NULL
      AND (
            lower(drug) LIKE '%vancomycin%' OR lower(drug) LIKE '%meropenem%'
         OR lower(drug) LIKE '%imipenem%' OR lower(drug) LIKE '%ertapenem%'
         OR lower(drug) LIKE '%piperacillin%' OR lower(drug) LIKE '%ticarcillin%'
         OR lower(drug) LIKE '%ampicillin%' OR lower(drug) LIKE '%amoxicillin%'
         OR lower(drug) LIKE '%oxacillin%' OR lower(drug) LIKE '%nafcillin%'
         OR lower(drug) LIKE '%penicillin%'
         OR lower(drug) LIKE '%cefazolin%' OR lower(drug) LIKE '%ceftriaxone%'
         OR lower(drug) LIKE '%cefotaxime%' OR lower(drug) LIKE '%ceftazidime%'
         OR lower(drug) LIKE '%cefepime%' OR lower(drug) LIKE '%ceftaroline%'
         OR lower(drug) LIKE '%cefuroxime%' OR lower(drug) LIKE '%cefoxitin%'
         OR lower(drug) LIKE '%cefotetan%' OR lower(drug) LIKE '%cefiderocol%'
         OR lower(drug) LIKE 'cef%' OR lower(drug) LIKE '%cephalexin%'
         OR lower(drug) LIKE '%ciprofloxacin%' OR lower(drug) LIKE '%levofloxacin%'
         OR lower(drug) LIKE '%moxifloxacin%'
         OR lower(drug) LIKE '%azithromycin%' OR lower(drug) LIKE '%clarithromycin%'
         OR lower(drug) LIKE '%erythromycin%' OR lower(drug) LIKE '%metronidazole%'
         OR lower(drug) LIKE '%linezolid%' OR lower(drug) LIKE '%daptomycin%'
         OR lower(drug) LIKE '%clindamycin%' OR lower(drug) LIKE '%sulfamethoxazole%'
         OR lower(drug) LIKE '%trimethoprim%' OR lower(drug) LIKE '%doxycycline%'
         OR lower(drug) LIKE '%tigecycline%' OR lower(drug) LIKE '%gentamicin%'
         OR lower(drug) LIKE '%tobramycin%' OR lower(drug) LIKE '%amikacin%'
         OR lower(drug) LIKE '%aztreonam%'
          )
),
cult AS (
    SELECT subject_id, hadm_id, COALESCE(charttime, chartdate) AS cult_time
    FROM mimiciv_hosp.microbiologyevents
    WHERE COALESCE(charttime, chartdate) IS NOT NULL
),
pair AS (
    SELECT
        a.subject_id, a.hadm_id, a.abx_time, c.cult_time,
        LEAST(a.abx_time, c.cult_time) AS suspected_infection_time,
        ROW_NUMBER() OVER (
            PARTITION BY a.hadm_id
            ORDER BY LEAST(a.abx_time, c.cult_time), a.abx_time
        ) AS rn
    FROM abx a
    INNER JOIN cult c
        ON a.subject_id = c.subject_id AND a.hadm_id = c.hadm_id
       AND c.cult_time BETWEEN a.abx_time - INTERVAL '24 hour'
                          AND a.abx_time + INTERVAL '72 hour'
)
SELECT subject_id, hadm_id, abx_time, cult_time, suspected_infection_time
FROM pair WHERE rn = 1;

-- ----------------------------------------------------------------------------
-- Step 3. 基础队列：成人、感染、启动血管活性药；确定 t0 / landmark / 预测窗
--   t0       = 该 ICU 停留内首次血管活性药启动
--   landmark = t0 + 6h；预测窗 = landmark ~ t0 + 30h
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.vs_cohort;
CREATE TABLE mimiciv_derived.vs_cohort AS
WITH first_vaso AS (
    SELECT stay_id, MIN(starttime) AS t0
    FROM mimiciv_derived.vs_drug_events
    GROUP BY stay_id
),
base AS (
    SELECT
        p.subject_id, a.hadm_id, s.stay_id,
        p.gender, p.anchor_age AS age,
        a.race, a.insurance,
        s.first_careunit, s.last_careunit,
        s.intime, s.outtime,
        DATE_PART('epoch', (s.outtime - s.intime))/86400.0 AS icu_los_days,
        a.hospital_expire_flag, a.discharge_location,
        a.deathtime, p.dod,
        inf.suspected_infection_time,
        fv.t0,
        fv.t0 + INTERVAL '6 hour'  AS landmark,
        fv.t0 + INTERVAL '30 hour' AS pred_window_end
    FROM mimiciv_derived.vs_infection inf
    INNER JOIN mimiciv_hosp.admissions a ON inf.hadm_id = a.hadm_id
    INNER JOIN mimiciv_hosp.patients p   ON a.subject_id = p.subject_id
    INNER JOIN mimiciv_icu.icustays s    ON inf.hadm_id = s.hadm_id
    INNER JOIN first_vaso fv             ON s.stay_id = fv.stay_id
    WHERE p.anchor_age >= 18
      AND fv.t0 BETWEEN inf.suspected_infection_time - INTERVAL '24 hour'
                    AND inf.suspected_infection_time + INTERVAL '72 hour'
)
SELECT *
FROM base
WHERE outtime >= landmark;

-- ----------------------------------------------------------------------------
-- Step 4. 体重：chartevents 入院/每日体重 + inputevents.patientweight
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.vs_weight;
DROP TABLE IF EXISTS mimiciv_derived.vs_weight;
CREATE TABLE mimiciv_derived.vs_weight AS
WITH cw AS (
    SELECT stay_id, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY valuenum) AS weight_kg
    FROM mimiciv_icu.chartevents
    WHERE itemid IN (226512, 224639) AND valuenum BETWEEN 30 AND 300
    GROUP BY stay_id
),
iw AS (
    SELECT stay_id, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY patientweight) AS weight_kg
    FROM mimiciv_icu.inputevents
    WHERE patientweight BETWEEN 30 AND 300
    GROUP BY stay_id
)
SELECT c.stay_id, COALESCE(cw.weight_kg, iw.weight_kg) AS weight_kg
FROM mimiciv_derived.vs_cohort c
LEFT JOIN cw ON c.stay_id = cw.stay_id
LEFT JOIN iw ON c.stay_id = iw.stay_id;

UPDATE mimiciv_derived.vs_weight w
SET weight_kg = g.med
FROM (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY weight_kg) AS med
      FROM mimiciv_derived.vs_weight WHERE weight_kg IS NOT NULL) g
WHERE w.weight_kg IS NULL;

-- ----------------------------------------------------------------------------
-- Step 5. 血管活性药区间剂量（体重标准化）+ NEE 分量
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.vs_vaso_dose;
CREATE TABLE mimiciv_derived.vs_vaso_dose AS
WITH calc AS (
    SELECT
        d.stay_id, d.drug, d.starttime, d.endtime,
        DATE_PART('epoch',(d.endtime-d.starttime))/60.0 AS duration_min,
        d.amount, d.amountuom, wt.weight_kg,
        CASE
            WHEN d.drug IN ('norepinephrine','epinephrine','dopamine',
                            'phenylephrine','metaraminol')
            THEN (d.amount * CASE d.amountuom
                    WHEN 'mg' THEN 1000 WHEN 'g' THEN 1000000
                    WHEN 'ng' THEN 0.001 ELSE 1 END)
                 / NULLIF(DATE_PART('epoch',(d.endtime-d.starttime))/60.0,0)
                 / NULLIF(wt.weight_kg,0)
            WHEN d.drug = 'vasopressin'
            THEN d.amount
                 / NULLIF(DATE_PART('epoch',(d.endtime-d.starttime))/60.0,0)
            WHEN d.drug = 'angiotensin_ii'
            THEN (d.amount * CASE d.amountuom
                    WHEN 'mg' THEN 1000000 WHEN 'mcg' THEN 1000
                    WHEN 'microgram' THEN 1000 ELSE 1 END)
                 / NULLIF(DATE_PART('epoch',(d.endtime-d.starttime))/60.0,0)
                 / NULLIF(wt.weight_kg,0)
        END AS drug_rate
    FROM mimiciv_derived.vs_drug_events d
    INNER JOIN mimiciv_derived.vs_cohort c ON d.stay_id = c.stay_id
    INNER JOIN mimiciv_derived.vs_weight wt ON d.stay_id = wt.stay_id
    WHERE DATE_PART('epoch',(d.endtime-d.starttime)) > 0
)
SELECT stay_id, drug, starttime, endtime, duration_min,
       amount, amountuom, weight_kg, drug_rate,
    CASE drug
        WHEN 'norepinephrine' THEN 1.0 * drug_rate
        WHEN 'epinephrine'     THEN 1.0 * drug_rate
        WHEN 'dopamine'        THEN 0.01 * drug_rate
        WHEN 'phenylephrine'   THEN 0.1 * drug_rate
        WHEN 'metaraminol'     THEN 0.125 * drug_rate
        WHEN 'vasopressin'     THEN 2.5 * drug_rate
        WHEN 'angiotensin_ii'  THEN 0.0025 * drug_rate
        WHEN 'dobutamine'      THEN 0
    END AS nee_component
FROM calc;

-- ----------------------------------------------------------------------------
-- Step 6. MAP 序列（itemid: 220052 ART MAP / 220181 NBP MAP / 225312）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.vs_map_long;
CREATE TABLE mimiciv_derived.vs_map_long AS
SELECT c.stay_id, ce.charttime, AVG(ce.valuenum) AS map
FROM mimiciv_derived.vs_cohort c
INNER JOIN mimiciv_icu.chartevents ce ON c.stay_id = ce.stay_id
WHERE ce.itemid IN (220052, 220181, 225312)
  AND ce.valuenum BETWEEN 20 AND 200
  AND ce.charttime BETWEEN c.t0 AND c.pred_window_end
GROUP BY c.stay_id, ce.charttime;

-- ----------------------------------------------------------------------------
-- Step 7. 液体推注（inputevents JOIN d_items，landmark 前）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.vs_fluid_bolus;
CREATE TABLE mimiciv_derived.vs_fluid_bolus AS
SELECT c.stay_id, ie.starttime, ie.endtime, di.label,
       ie.amount, ie.amountuom
FROM mimiciv_derived.vs_cohort c
INNER JOIN mimiciv_icu.inputevents ie ON c.stay_id = ie.stay_id
LEFT JOIN mimiciv_icu.d_items di ON ie.itemid = di.itemid
WHERE (lower(di.label) LIKE '%bolus%'
    OR lower(di.label) LIKE '%normal saline%'
    OR lower(di.label) LIKE '%lactated ringers%'
    OR lower(di.label) LIKE '%hartmann%')
  AND ie.amount IS NOT NULL
  AND ie.starttime BETWEEN c.t0 AND c.landmark;

-- ----------------------------------------------------------------------------
-- Step 8. landmark 前生命体征（长表）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.vs_vitals_long;
CREATE TABLE mimiciv_derived.vs_vitals_long AS
SELECT c.stay_id, ce.charttime, di.label, ce.valuenum
FROM mimiciv_derived.vs_cohort c
INNER JOIN mimiciv_icu.chartevents ce ON c.stay_id = ce.stay_id
LEFT JOIN mimiciv_icu.d_items di ON ce.itemid = di.itemid
WHERE ce.itemid IN (
        220045, 220050, 220051, 220052,
        220179, 220180, 220181,
        220210, 220277, 223761, 223762
      )
  AND ce.valuenum IS NOT NULL
  AND ce.charttime BETWEEN c.intime AND c.landmark;

-- ----------------------------------------------------------------------------
-- Step 9. landmark 前实验室检查（长表，按 d_labitems 标准名）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.vs_labs_long;
CREATE TABLE mimiciv_derived.vs_labs_long AS
SELECT c.stay_id, le.charttime, dl.label, le.valuenum
FROM mimiciv_derived.vs_cohort c
INNER JOIN mimiciv_hosp.labevents le ON c.hadm_id = le.hadm_id
INNER JOIN mimiciv_hosp.d_labitems dl ON le.itemid = dl.itemid
WHERE dl.label IN (
        'Lactate','Creatinine','WBC','Hemoglobin','Hematocrit','Platelet Count',
        'Sodium','Potassium','Chloride','Bicarbonate','Glucose','Calcium, Total',
        'Magnesium','Phosphate','Bilirubin, Total','Albumin','Urea Nitrogen','Anion Gap'
      )
  AND le.valuenum IS NOT NULL
  AND le.charttime <= c.landmark
  AND le.charttime >= c.intime - INTERVAL '1 day';

-- ----------------------------------------------------------------------------
-- Step 10. 基础疾病（宽表，flag）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.vs_comorbid;
CREATE TABLE mimiciv_derived.vs_comorbid AS
SELECT c.stay_id,
 MAX(CASE WHEN (dx.icd_version=9  AND dx.icd_code LIKE '250%')
            OR (dx.icd_version=10 AND (dx.icd_code LIKE 'E08%' OR dx.icd_code LIKE 'E10%'
                OR dx.icd_code LIKE 'E11%' OR dx.icd_code LIKE 'E13%')) THEN 1 ELSE 0 END) AS diabetes,
 MAX(CASE WHEN (dx.icd_version=9  AND dx.icd_code LIKE '40%')
            OR (dx.icd_version=10 AND dx.icd_code LIKE 'I1%') THEN 1 ELSE 0 END) AS hypertension,
 MAX(CASE WHEN (dx.icd_version=9  AND dx.icd_code LIKE '428%')
            OR (dx.icd_version=10 AND dx.icd_code LIKE 'I50%') THEN 1 ELSE 0 END) AS chf,
 MAX(CASE WHEN (dx.icd_version=9  AND dx.icd_code BETWEEN '490' AND '496')
            OR (dx.icd_version=10 AND (dx.icd_code LIKE 'J4%' OR dx.icd_code LIKE 'J47%'))
           THEN 1 ELSE 0 END) AS chronic_pulmonary,
 MAX(CASE WHEN (dx.icd_version=9  AND (dx.icd_code LIKE '571%' OR dx.icd_code LIKE '572%'))
            OR (dx.icd_version=10 AND (dx.icd_code LIKE 'K70%' OR dx.icd_code LIKE 'K71%'
                OR dx.icd_code LIKE 'K72%' OR dx.icd_code LIKE 'K73%' OR dx.icd_code LIKE 'K74%'))
           THEN 1 ELSE 0 END) AS chronic_liver,
 MAX(CASE WHEN (dx.icd_version=9  AND dx.icd_code LIKE '585%')
            OR (dx.icd_version=10 AND dx.icd_code LIKE 'N18%') THEN 1 ELSE 0 END) AS ckd,
 MAX(CASE WHEN (dx.icd_version=10 AND dx.icd_code LIKE 'C7%')
            OR (dx.icd_version=9 AND dx.icd_code BETWEEN '196' AND '199')
           THEN 1 ELSE 0 END) AS metastatic_cancer,
 MAX(CASE WHEN (dx.icd_version=9  AND dx.icd_code LIKE '427%')
            OR (dx.icd_version=10 AND (dx.icd_code LIKE 'I46%' OR dx.icd_code LIKE 'I47%'
                OR dx.icd_code LIKE 'I48%' OR dx.icd_code LIKE 'I49%'))
           THEN 1 ELSE 0 END) AS arrhythmia
FROM mimiciv_derived.vs_cohort c
LEFT JOIN mimiciv_hosp.diagnoses_icd dx ON c.hadm_id = dx.hadm_id
GROUP BY c.stay_id;

-- ----------------------------------------------------------------------------
-- Step 11. 最终队列宽表（静态 + 体重 + 基础疾病 + 随访死亡）
--   动态/早期严重度特征请在 R/Python 从 Step 5/8/9 长表聚合。
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.vs_analysis_cohort;
CREATE TABLE mimiciv_derived.vs_analysis_cohort AS
SELECT
    c.*, w.weight_kg,
    cm.diabetes, cm.hypertension, cm.chf, cm.chronic_pulmonary,
    cm.chronic_liver, cm.ckd, cm.metastatic_cancer, cm.arrhythmia,
    CASE WHEN c.dod IS NOT NULL
          AND DATE_PART('day', c.dod - c.intime) <= 28 THEN 1 ELSE 0 END AS death_28d,
    CASE WHEN c.dod IS NOT NULL
          AND DATE_PART('day', c.dod - c.intime) <= 90 THEN 1 ELSE 0 END AS death_90d
FROM mimiciv_derived.vs_cohort c
LEFT JOIN mimiciv_derived.vs_weight w    ON c.stay_id = w.stay_id
LEFT JOIN mimiciv_derived.vs_comorbid cm ON c.stay_id = cm.stay_id;

-- 【提示】Step12 标签判定请运行 02_MIMIC_标签判定_步骤12.sql（本文件不含慢速内嵌版）
