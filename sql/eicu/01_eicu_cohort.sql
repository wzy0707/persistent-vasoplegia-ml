-- ============================================================================
-- Step 18【eICU 队列识别】与 MIMIC 同口径
--   成年 + 脓毒症 + 入ICU 6h 内升压药 + ICU 时长>=6h + 住院期间首次 ICU
--   在 eicu 数据库的查询窗口运行（表在 public schema）。逐段 F5。
-- ============================================================================
SET work_mem='256MB';

-- ----------------------------------------------------------------------------
-- 18-1. 成年患者（age 为文本，'> 89' 按 90 处理）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS eicu.tmp_e_adult;
CREATE TABLE eicu.tmp_e_adult AS
SELECT patientunitstayid, patienthealthsystemstayid, unitvisitnumber,
    gender, ethnicity, unittype,
    CASE WHEN age = '> 89' THEN 90.0
         WHEN age ~ '^[0-9.]+$' THEN age::numeric
         ELSE NULL END AS age_num,
    admissionheight, admissionweight,
    unitdischargeoffset, unitdischargestatus, hospitaldischargestatus
FROM eicu.patient
WHERE CASE WHEN age = '> 89' THEN 90.0
           WHEN age ~ '^[0-9.]+$' THEN age::numeric
           ELSE NULL END >= 18;

-- ----------------------------------------------------------------------------
-- 18-2. 脓毒症（diagnosis 表，宽泛匹配 sepsis/septic）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS eicu.tmp_e_sepsis;
CREATE TABLE eicu.tmp_e_sepsis AS
SELECT DISTINCT patientunitstayid
FROM eicu.diagnosis
WHERE diagnosisstring ILIKE '%sepsis%' OR diagnosisstring ILIKE '%septic%';

-- ----------------------------------------------------------------------------
-- 18-3. 入 ICU 6h 内（offset 0-360）使用过升压药
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS eicu.tmp_e_vaso;
CREATE TABLE eicu.tmp_e_vaso AS
SELECT DISTINCT patientunitstayid
FROM eicu.infusiondrug
WHERE infusionoffset BETWEEN 0 AND 360
  AND ( drugname ILIKE '%norepinephrine%' OR drugname ILIKE '%levophed%'
     OR drugname ILIKE '%levarterenol%' OR drugname ILIKE '%norepi%'
     OR drugname ILIKE '%epinephrine%' OR drugname ILIKE '%adrenaline%'
     OR drugname ILIKE '%dopamine%' OR drugname ILIKE '%intropin%'
     OR drugname ILIKE '%phenylephrine%' OR drugname ILIKE '%neosynephrine%'
     OR drugname ILIKE '%vasopressin%' OR drugname ILIKE '%pitressin%'
     OR drugname ILIKE '%argipressin%');

-- ----------------------------------------------------------------------------
-- 18-4. 住院期间首次 ICU（同一 patienthealthsystemstayid 取最小 unit stay）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS eicu.tmp_e_first;
CREATE TABLE eicu.tmp_e_first AS
SELECT patientunitstayid
FROM (
    SELECT patientunitstayid,
        ROW_NUMBER() OVER (PARTITION BY patienthealthsystemstayid
                           ORDER BY patientunitstayid) AS rn
    FROM eicu.tmp_e_adult
) t
WHERE rn = 1;

-- ----------------------------------------------------------------------------
-- 18-5. eICU 分析队列（ICU 时长 >= 6h）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS eicu.e_cohort;
CREATE TABLE eicu.e_cohort AS
SELECT a.patientunitstayid, a.patienthealthsystemstayid,
    a.gender, a.ethnicity, a.unittype, a.age_num,
    a.admissionheight, a.admissionweight,
    a.unitdischargeoffset, a.unitdischargestatus, a.hospitaldischargestatus
FROM eicu.tmp_e_adult a
WHERE a.unitdischargeoffset >= 360
  AND a.patientunitstayid IN (SELECT patientunitstayid FROM eicu.tmp_e_sepsis)
  AND a.patientunitstayid IN (SELECT patientunitstayid FROM eicu.tmp_e_vaso)
  AND a.patientunitstayid IN (SELECT patientunitstayid FROM eicu.tmp_e_first);

-- ----------------------------------------------------------------------------
-- 验证
-- ----------------------------------------------------------------------------
-- 1) 队列规模（参考：eICU 脓毒症休克通常数千~上万）
SELECT count(*) AS n_cohort FROM eicu.e_cohort;

-- 2) 脓毒症匹配到的诊断字符串（核对匹配口径）
SELECT diagnosisstring, count(*) cnt
FROM eicu.diagnosis
WHERE (diagnosisstring ILIKE '%sepsis%' OR diagnosisstring ILIKE '%septic%')
GROUP BY diagnosisstring ORDER BY cnt DESC LIMIT 15;

-- 3) 各步漏斗（成年/脓毒症/升压药/首次/最终）
SELECT
  (SELECT count(*) FROM eicu.tmp_e_adult) AS adult,
  (SELECT count(*) FROM eicu.tmp_e_sepsis) AS sepsis,
  (SELECT count(*) FROM eicu.tmp_e_vaso) AS vaso_6h,
  (SELECT count(*) FROM eicu.tmp_e_first) AS first_icu,
  (SELECT count(*) FROM eicu.e_cohort) AS final;
-- ============================================================================
