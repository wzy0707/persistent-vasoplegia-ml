-- ============================================================================
-- Step 25【eICU MAP 提取】为标签提供低血压依据
--   vitalperiodic.systemicmean = MAP；只取 0-1800min（标签所需），避免数据过大
--   在 eicu 库查询窗口运行。
-- ============================================================================
DROP TABLE IF EXISTS eicu.e_map;
CREATE TABLE eicu.e_map AS
SELECT patientunitstayid, observationoffset AS off,
       systemicmean::numeric AS map
FROM eicu.vitalperiodic
WHERE patientunitstayid IN (SELECT patientunitstayid FROM eicu.e_cohort)
  AND observationoffset BETWEEN 0 AND 1800
  AND systemicmean IS NOT NULL
  AND systemicmean::text ~ '^[0-9.]+$'
  AND systemicmean::numeric BETWEEN 0 AND 200;

-- 校验：行数/患者覆盖/MAP 范围
SELECT count(*) rows, count(DISTINCT patientunitstayid) patients,
  round(min(map),1) min_map, round(max(map),1) max_map, round(avg(map),1) avg_map
FROM eicu.e_map;
-- ============================================================================
