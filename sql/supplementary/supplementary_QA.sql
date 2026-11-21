-- ============================================================================
-- 补充核对 SQL（补全路线）：核对稿件中需要数据库验证的几处计数
-- 分库执行：MIMIC 段在 mimiciv 库；eICU 段在 eicu 库
-- ============================================================================

-- ============ MIMIC 段 ============

-- 1) 结局构成：de novo（onset 晚于 landmark）vs 跨 landmark（onset=landmark）
--    目标：de novo 382，cross-landmark 81，合计 463
SELECT
    SUM(CASE WHEN l.vasoplegia_onset >  c.landmark THEN 1 ELSE 0 END) AS de_novo,
    SUM(CASE WHEN l.vasoplegia_onset = c.landmark THEN 1 ELSE 0 END) AS cross_landmark,
    COUNT(*) AS total_events
FROM mimiciv_derived.vs_label l
JOIN mimiciv_derived.vs_cohort c ON c.stay_id = l.stay_id
WHERE l.vasoplegia = 1;

-- 2) 瞬态非事件：landmark 点处于高剂量状态但未持续满 6h、最终非事件
--    目标：约 86
SELECT COUNT(*) AS transient_noncases
FROM mimiciv_derived.tmp_f_b f
JOIN mimiciv_derived.vs_cohort c ON c.stay_id = f.stay_id
WHERE f.ts = c.landmark
  AND f.nee >= 0.5
  AND (f.map IS NULL OR f.map < 65)
  AND f.stay_id NOT IN (
      SELECT stay_id FROM mimiciv_derived.vs_label WHERE vasoplegia = 1);

-- ============ eICU 段 ============

-- 3) 外验构念效度：事件 vs 非事件的 ICU/住院死亡率
--    目标：事件约 0.697 / 0.776；非事件约 0.188 / 0.248
SELECT l.label,
    COUNT(*) AS n,
    ROUND(AVG(CASE WHEN p.unitdischargestatus = 'Expired'
                   THEN 1 ELSE 0 END)::numeric, 3) AS icu_mortality,
    ROUND(AVG(CASE WHEN p.hospitaldischargestatus = 'Expired'
                   THEN 1 ELSE 0 END)::numeric, 3) AS hosp_mortality
FROM eicu.e_label l
JOIN eicu.patient p ON p.patientunitstayid = l.patientunitstayid
WHERE l.label_type IN ('incident', 'negative')
GROUP BY l.label
ORDER BY l.label;
-- ============================================================================
