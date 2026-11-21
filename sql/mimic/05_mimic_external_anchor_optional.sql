-- ============================================================================
-- Step 16【外部锚点取数】证明模型预测的是"真难治"而非泵速记录
--   锚点：ICU 内死亡、住院死亡、ICU 时长(LOS)、住院期间肾脏替代治疗(RRT)
--   与 vs_ml_wide 同队列（已排除 prevalent），按 stay_id 关联。
-- 逐段 F5、逐段验证。
-- ============================================================================
SET work_mem='256MB';

-- ----------------------------------------------------------------------------
-- 16-1. 死亡与 ICU 时长（来自 icustays / admissions）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.tmp_anchor_death;
CREATE TABLE mimiciv_derived.tmp_anchor_death AS
SELECT ic.stay_id,
    CASE WHEN a.deathtime IS NOT NULL
          AND a.deathtime >= ic.intime
          AND a.deathtime <= ic.outtime
         THEN 1 ELSE 0 END AS icu_death,
    COALESCE(a.hospital_expire_flag, 0) AS hosp_death,
    ic.los AS icu_los
FROM mimiciv_derived.vs_cohort c
JOIN mimiciv_icu.icustays ic ON ic.stay_id = c.stay_id
LEFT JOIN mimiciv_hosp.admissions a ON a.hadm_id = c.hadm_id;

-- ----------------------------------------------------------------------------
-- 16-2. 住院期间 RRT（ICD 编码，住院内任何肾脏替代）
--   ICD-9: 39.95 血液透析 / 39.96 其他透析 / 39.97 腹膜透析
--   ICD-10: 5A1D* 肾脏滤过（含血透/CRRT/腹膜）、5A1F* 尿液处理、5A1G*
-- 说明：ICD 编码无精确时间，rrt_any 为"住院期间是否曾 RRT"，作为外部锚点足够；
--       若需严格 landmark 后 RRT，需另用 procedureevents/chartevents 细化。
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.tmp_anchor_rrt;
CREATE TABLE mimiciv_derived.tmp_anchor_rrt AS
SELECT c.stay_id,
    MAX(CASE
        WHEN p.icd_version = 9 AND (
                p.icd_code LIKE '39.95%' OR p.icd_code LIKE '39.96%'
             OR p.icd_code LIKE '39.97%' OR p.icd_code LIKE '54.98%')
         THEN 1
        WHEN p.icd_version = 10 AND (
                p.icd_code LIKE '5A1D%' OR p.icd_code LIKE '5A1F%'
             OR p.icd_code LIKE '5A1G%')
         THEN 1
        ELSE 0 END) AS rrt_any
FROM mimiciv_derived.vs_cohort c
JOIN mimiciv_hosp.procedures_icd p ON p.hadm_id = c.hadm_id
GROUP BY c.stay_id;

-- ----------------------------------------------------------------------------
-- 16-3. 外部锚点表（限定建模队列 vs_ml_wide）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS mimiciv_derived.vs_anchor;
CREATE TABLE mimiciv_derived.vs_anchor AS
SELECT w.stay_id,
    d.icu_death,
    d.hosp_death,
    d.icu_los,
    COALESCE(r.rrt_any, 0) AS rrt_any
FROM mimiciv_derived.vs_ml_wide w
JOIN mimiciv_derived.tmp_anchor_death d ON d.stay_id = w.stay_id
LEFT JOIN mimiciv_derived.tmp_anchor_rrt r ON r.stay_id = w.stay_id;

-- ----------------------------------------------------------------------------
-- 验证
-- ----------------------------------------------------------------------------
-- 1) 行数应 = 17,463
SELECT count(*) AS n FROM mimiciv_derived.vs_anchor;

-- 2) 全队列锚点事件率（参考基线）
SELECT count(*) n,
    sum(icu_death) icu_deaths, round(avg(icu_death),4) icu_death_rate,
    sum(hosp_death) hosp_deaths, round(avg(hosp_death),4) hosp_death_rate,
    sum(rrt_any) rrt_cases, round(avg(rrt_any),4) rrt_rate,
    round(avg(icu_los)::numeric,3) mean_los
FROM mimiciv_derived.vs_anchor;

-- 3) 按结局核对：阳性(vasoplegia=1) 锚点应明显更差
SELECT w.vasoplegia, count(*) n,
    round(avg(a.icu_death),3) icu_death_rate,
    round(avg(a.hosp_death),3) hosp_death_rate,
    round(avg(a.rrt_any),3) rrt_rate,
    round(avg(a.icu_los)::numeric,3) mean_los
FROM mimiciv_derived.vs_anchor a
JOIN mimiciv_derived.vs_ml_wide w ON w.stay_id=a.stay_id
GROUP BY w.vasoplegia ORDER BY w.vasoplegia;
-- ============================================================================
