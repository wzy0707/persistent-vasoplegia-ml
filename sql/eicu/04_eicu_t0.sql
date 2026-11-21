-- ============================================================================
-- Step 27【eICU t0 确定】t0 = 首次升压药给药 offset（与 MIMIC 一致，非入科）
--   在 eicu 库查询窗口运行。
-- ============================================================================
DROP TABLE IF EXISTS eicu.e_t0;
CREATE TABLE eicu.e_t0 AS
SELECT patientunitstayid, min(infusionoffset) AS t0
FROM eicu.infusiondrug
WHERE patientunitstayid IN (SELECT patientunitstayid FROM eicu.e_cohort)
  AND infusionoffset BETWEEN 0 AND 360
  AND drugrate ~ '^[0-9.]+$' AND drugrate::numeric > 0
  AND (drugname ILIKE '%norepinephrine%' OR drugname ILIKE '%levophed%'
    OR drugname ILIKE '%epinephrine%' OR drugname ILIKE '%adrenaline%'
    OR drugname ILIKE '%dopamine%' OR drugname ILIKE '%phenylephrine%'
    OR drugname ILIKE '%neosynephrine%' OR drugname ILIKE '%vasopressin%'
    OR drugname ILIKE '%pitressin%')
GROUP BY 1;

-- 校验：覆盖 + t0 分布（首次升压药在入科后多久）
SELECT count(*) n,
  round(min(t0),0) min_t0, round(max(t0),0) max_t0, round(avg(t0),1) avg_t0
FROM eicu.e_t0;

SELECT t0_bucket, count(*) n FROM (
  SELECT CASE WHEN t0<60 THEN '0-60' WHEN t0<120 THEN '60-120'
              WHEN t0<180 THEN '120-180' WHEN t0<240 THEN '180-240'
              ELSE '240-360' END t0_bucket
  FROM eicu.e_t0) x GROUP BY t0_bucket ORDER BY t0_bucket;
-- ============================================================================
