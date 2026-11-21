-- ============================================================================
-- RESS 评分补提取：动脉 pH（唯一不在 77 列的变量）
-- MIMIC：走 chartevents（itemid 223830 动脉优先，220274 静脉兜底），不依赖 bg 表
-- eICU：走 lab 表（labname='pH'）
-- 各取 [t0, landmark] 内最后值；导出 CSV 发我
-- ============================================================================

-- ==================== MIMIC 段 ====================
DROP TABLE IF EXISTS mimiciv_derived.vs_ph;
CREATE TABLE mimiciv_derived.vs_ph AS
WITH ph AS (
    SELECT c.stay_id, ce.charttime, ce.value::double precision AS ph,
           ROW_NUMBER() OVER (
               PARTITION BY c.stay_id
               ORDER BY CASE WHEN ce.itemid = 223830 THEN 0 ELSE 1 END,
                        ce.charttime DESC) AS rn
    FROM mimiciv_derived.vs_cohort c
    JOIN mimiciv_icu.chartevents ce ON ce.stay_id = c.stay_id
    WHERE ce.itemid IN (223830, 220274)          -- 动脉优先，静脉兜底
      AND ce.value ~ '^[0-9]+(\.[0-9]+)?$'
      AND ce.value::double precision BETWEEN 6.5 AND 8.0
      AND ce.charttime >= c.t0
      AND ce.charttime <= c.landmark
)
SELECT stay_id, ph AS ph_last
FROM ph WHERE rn = 1;

-- 核对覆盖（建模队列 17,463）
SELECT COUNT(*) AS patients_with_ph,
       COUNT(*) FILTER (WHERE ph_last < 7.27) AS acidemic_severe,
       COUNT(*) FILTER (WHERE ph_last < 7.35) AS acidemic_any
FROM mimiciv_derived.vs_ph;

-- 导出 MIMIC pH（保存为 ph_mimic.csv）
SELECT stay_id, ph_last FROM mimiciv_derived.vs_ph ORDER BY stay_id;

-- ==================== eICU 段 ====================
DROP TABLE IF EXISTS eicu.e_ph;
CREATE TABLE eicu.e_ph AS
WITH l AS (
    SELECT t.patientunitstayid, lab.labresult::float AS ph,
           ROW_NUMBER() OVER (
               PARTITION BY t.patientunitstayid
               ORDER BY lab.labresultoffset DESC) AS rn
    FROM eicu.e_t0 t
    JOIN eicu.lab lab
      ON lab.patientunitstayid = t.patientunitstayid
     AND lab.labname = 'pH'
     AND lab.labresultoffset >= t.t0
     AND lab.labresultoffset < t.t0 + 360
    WHERE lab.labresult IS NOT NULL
)
SELECT patientunitstayid, ph AS ph_last
FROM l WHERE rn = 1;

-- 核对覆盖
SELECT COUNT(*) AS patients_with_ph,
       COUNT(*) FILTER (WHERE ph_last < 7.27) AS acidemic_severe,
       COUNT(*) FILTER (WHERE ph_last < 7.35) AS acidemic_any
FROM eicu.e_ph;

-- 导出 eICU pH（保存为 ph_eicu.csv）
SELECT patientunitstayid, ph_last FROM eicu.e_ph ORDER BY patientunitstayid;
-- ============================================================================
