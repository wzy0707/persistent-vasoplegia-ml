-- ============================================================================
-- Step 23【eICU 升压药剂量标准化 + NEE】
--   单位转换依据 drugname 末尾单位；ml/hr / 无单位 / Unknown 一律舍弃（浓度未知）
--   儿茶酚胺统一 mcg/kg/min；vasopressin 统一 U/min
--   NEE = NE + Epi + 0.01*Dopa + 0.1*PE + 2.5*Vaso（eICU 共有成分）
--   在 eicu 库查询窗口运行。
-- ============================================================================
DROP TABLE IF EXISTS eicu.e_vaso_dose;
CREATE TABLE eicu.e_vaso_dose AS
WITH rec AS (
  SELECT i.patientunitstayid, i.infusionoffset,
         c.admissionweight AS w,
         i.drugname,
         i.drugrate::numeric AS r,
         CASE
           WHEN i.drugname ILIKE '%norepinephrine%' OR i.drugname ILIKE '%levophed%' THEN 'NE'
           WHEN i.drugname ILIKE '%epinephrine%' OR i.drugname ILIKE '%adrenaline%' THEN 'Epi'
           WHEN i.drugname ILIKE '%dopamine%' THEN 'Dopa'
           WHEN i.drugname ILIKE '%phenylephrine%' OR i.drugname ILIKE '%neosynephrine%' THEN 'PE'
           WHEN i.drugname ILIKE '%vasopressin%' OR i.drugname ILIKE '%pitressin%' THEN 'Vaso'
         END AS drug
  FROM eicu.infusiondrug i
  JOIN eicu.e_cohort c USING (patientunitstayid)
  WHERE i.drugrate ~ '^[0-9.]+$'
),
std AS (
  SELECT patientunitstayid, infusionoffset, drug,
    -- 儿茶酚胺 -> mcg/kg/min
    CASE WHEN drug IN ('NE','Epi','Dopa','PE') THEN
      CASE
        WHEN drugname ILIKE '%(mcg/kg/min)%' THEN r
        WHEN drugname ILIKE '%(mcg/min)%'    THEN r/NULLIF(w,0)
        WHEN drugname ILIKE '%(mg/kg/min)%'  THEN r*1000
        WHEN drugname ILIKE '%(mg/min)%'     THEN r*1000/NULLIF(w,0)
        WHEN drugname ILIKE '%(mcg/kg/hr)%'  THEN r/60.0
        WHEN drugname ILIKE '%(mcg/hr)%'     THEN r/60.0/NULLIF(w,0)
        WHEN drugname ILIKE '%(mg/hr)%'      THEN r*1000/60.0/NULLIF(w,0)
      END
    END AS cate,
    -- vasopressin -> U/min
    CASE WHEN drug='Vaso' THEN
      CASE
        WHEN drugname ILIKE '%(units/kg/min)%' THEN r*NULLIF(w,0)
        WHEN drugname ILIKE '%(units/min)%'    THEN r
        WHEN drugname ILIKE '%(units/kg/hr)%'  THEN r*NULLIF(w,0)/60.0
        WHEN drugname ILIKE '%(units/hr)%'     THEN r/60.0
      END
    END AS vas
  FROM rec
),
agg AS (
  SELECT patientunitstayid, infusionoffset, drug,
         max(COALESCE(cate,vas)) AS dose
  FROM std
  WHERE COALESCE(cate,vas) IS NOT NULL
  GROUP BY 1,2,3
)
SELECT patientunitstayid, infusionoffset,
  max(CASE WHEN drug='NE'   THEN dose END) AS ne,
  max(CASE WHEN drug='Epi'  THEN dose END) AS epi,
  max(CASE WHEN drug='Dopa' THEN dose END) AS dopa,
  max(CASE WHEN drug='PE'   THEN dose END) AS pe,
  max(CASE WHEN drug='Vaso' THEN dose END) AS vaso,
  COALESCE(max(CASE WHEN drug='NE'   THEN dose END),0)
+ COALESCE(max(CASE WHEN drug='Epi'  THEN dose END),0)
+ 0.01*COALESCE(max(CASE WHEN drug='Dopa' THEN dose END),0)
+ 0.1 *COALESCE(max(CASE WHEN drug='PE'   THEN dose END),0)
+ 2.5 *COALESCE(max(CASE WHEN drug='Vaso' THEN dose END),0) AS nee
FROM agg
GROUP BY 1,2;

-- 校验1：行数与患者覆盖
SELECT count(*) rows, count(DISTINCT patientunitstayid) patients
FROM eicu.e_vaso_dose;

-- 校验2：NEE 分布（看是否合理，0.5 阈值附近）
SELECT round(nee,3) nee, count(*) n
FROM eicu.e_vaso_dose
WHERE nee>0
GROUP BY 1 ORDER BY n DESC LIMIT 20;
-- ============================================================================
