-- ============================================================================
-- 课题：基于 MIMIC-IV 构建脓毒症血管麻痹综合征早期 ML 预测模型
-- 纳入排除流程图：每一步计数 SQL（PostgreSQL / pgAdmin 直接运行）
--
-- 【使用顺序】
--   先完整运行《脓毒症血管麻痹_MIMIC第一步数据提取.sql》（已含 vs_infection、
--   vs_cohort、vs_weight、vs_prevalent、vs_label 等），再运行本脚本：
--     Section 1 漏斗每级“纳入数/排除数”；
--     Section 2 最终队列 事件组/对照组；
--     Section 3 训练/内部验证划分。
--   口径：每位患者仅首次 ICU（rn=1）；schema 名按本地替换。
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Section 1. 漏斗：每一级“纳入数 / 排除数”（对应流程图自上而下）
-- ----------------------------------------------------------------------------
WITH src AS (
    SELECT s.stay_id, s.subject_id, s.hadm_id, s.intime, s.outtime,
           p.anchor_age AS age, fv.t0, inf.suspected_infection_time,
           ROW_NUMBER() OVER (PARTITION BY s.subject_id ORDER BY s.intime, s.stay_id) AS rn
    FROM mimiciv_icu.icustays s
    INNER JOIN mimiciv_hosp.patients p ON s.subject_id = p.subject_id
    LEFT JOIN (SELECT stay_id, MIN(starttime) AS t0
               FROM mimiciv_derived.vs_drug_events GROUP BY stay_id) fv
           ON s.stay_id = fv.stay_id
    LEFT JOIN mimiciv_derived.vs_infection inf ON s.hadm_id = inf.hadm_id
),
tagged AS (
    SELECT *,
        (suspected_infection_time IS NOT NULL) AS f_inf,
        (suspected_infection_time IS NOT NULL AND t0 IS NOT NULL
            AND t0 BETWEEN suspected_infection_time - INTERVAL '24 hour'
                       AND suspected_infection_time + INTERVAL '72 hour') AS f_shock,
        (age >= 18) AS f_adult,
        (rn = 1) AS f_first,
        EXISTS (SELECT 1 FROM mimiciv_derived.vs_weight w
                WHERE w.stay_id = src.stay_id AND w.weight_kg IS NOT NULL) AS f_vars,
        (t0 IS NOT NULL AND outtime >= t0 + INTERVAL '6 hour') AS f_land
    FROM src
),
final AS (
    SELECT t.*, COALESCE(pp.prev_flag,0) AS is_prev
    FROM tagged t
    LEFT JOIN mimiciv_derived.vs_prevalent pp ON t.stay_id = pp.stay_id
),
funnel AS (
    SELECT 1 AS ord, '01 全库 ICU 停留' AS step, COUNT(*) AS n FROM final
    UNION ALL SELECT 2, '02 感染(抗生素+培养配对)',
        COUNT(*) FILTER (WHERE f_inf) FROM final
    UNION ALL SELECT 3, '03 脓毒症休克(感染+升压药)',
        COUNT(*) FILTER (WHERE f_inf AND f_shock) FROM final
    UNION ALL SELECT 4, '04 成人(>=18)',
        COUNT(*) FILTER (WHERE f_inf AND f_shock AND f_adult) FROM final
    UNION ALL SELECT 5, '05 首次 ICU 停留',
        COUNT(*) FILTER (WHERE f_inf AND f_shock AND f_adult AND f_first) FROM final
    UNION ALL SELECT 6, '06 关键变量完整(体重)',
        COUNT(*) FILTER (WHERE f_inf AND f_shock AND f_adult AND f_first AND f_vars) FROM final
    UNION ALL SELECT 7, '07 ICU停留>=landmark(6h)',
        COUNT(*) FILTER (WHERE f_inf AND f_shock AND f_adult AND f_first AND f_vars AND f_land) FROM final
    UNION ALL SELECT 8, '08 最终建模队列(landmark时未血管麻痹)',
        COUNT(*) FILTER (WHERE f_inf AND f_shock AND f_adult AND f_first
                          AND f_vars AND f_land AND is_prev = 0) FROM final
)
SELECT step,
       n                                  AS retained_n,
       LAG(n) OVER (ORDER BY ord) - n     AS excluded_n
FROM funnel
ORDER BY ord;

-- ----------------------------------------------------------------------------
-- Section 2. 最终建模队列：事件组 / 对照组（landmark 后 24h 是否新发）
-- ----------------------------------------------------------------------------
WITH src AS (
    SELECT s.stay_id, s.subject_id, s.intime, s.outtime,
           p.anchor_age AS age, fv.t0, inf.suspected_infection_time,
           ROW_NUMBER() OVER (PARTITION BY s.subject_id ORDER BY s.intime, s.stay_id) AS rn
    FROM mimiciv_icu.icustays s
    INNER JOIN mimiciv_hosp.patients p ON s.subject_id = p.subject_id
    LEFT JOIN (SELECT stay_id, MIN(starttime) AS t0
               FROM mimiciv_derived.vs_drug_events GROUP BY stay_id) fv
           ON s.stay_id = fv.stay_id
    LEFT JOIN mimiciv_derived.vs_infection inf ON s.hadm_id = inf.hadm_id
),
eligible AS (
    SELECT s.stay_id
    FROM src s
    LEFT JOIN mimiciv_derived.vs_prevalent pp ON s.stay_id = pp.stay_id
    WHERE s.rn = 1
      AND s.age >= 18
      AND s.suspected_infection_time IS NOT NULL
      AND s.t0 IS NOT NULL
      AND s.t0 BETWEEN s.suspected_infection_time - INTERVAL '24 hour'
                   AND s.suspected_infection_time + INTERVAL '72 hour'
      AND s.outtime >= s.t0 + INTERVAL '6 hour'
      AND EXISTS (SELECT 1 FROM mimiciv_derived.vs_weight w
                  WHERE w.stay_id = s.stay_id AND w.weight_kg IS NOT NULL)
      AND COALESCE(pp.prev_flag,0) = 0
)
SELECT
    COUNT(*)                                             AS final_cohort_n,
    COUNT(*) FILTER (WHERE COALESCE(l.vasoplegia,0) = 1) AS events_vasoplegia,
    COUNT(*) FILTER (WHERE COALESCE(l.vasoplegia,0) = 0) AS non_events
FROM eligible e
LEFT JOIN mimiciv_derived.vs_label l ON e.stay_id = l.stay_id;

-- ----------------------------------------------------------------------------
-- Section 3. 训练 / 内部验证（按 stay_id 哈希 70/30，可复现；按时间切分见注释）
-- ----------------------------------------------------------------------------
WITH src AS (
    SELECT s.stay_id, s.subject_id, s.intime, s.outtime,
           p.anchor_age AS age, fv.t0, inf.suspected_infection_time,
           ROW_NUMBER() OVER (PARTITION BY s.subject_id ORDER BY s.intime, s.stay_id) AS rn
    FROM mimiciv_icu.icustays s
    INNER JOIN mimiciv_hosp.patients p ON s.subject_id = p.subject_id
    LEFT JOIN (SELECT stay_id, MIN(starttime) AS t0
               FROM mimiciv_derived.vs_drug_events GROUP BY stay_id) fv
           ON s.stay_id = fv.stay_id
    LEFT JOIN mimiciv_derived.vs_infection inf ON s.hadm_id = inf.hadm_id
),
eligible AS (
    SELECT s.stay_id, s.intime
    FROM src s
    LEFT JOIN mimiciv_derived.vs_prevalent pp ON s.stay_id = pp.stay_id
    WHERE s.rn = 1
      AND s.age >= 18
      AND s.suspected_infection_time IS NOT NULL
      AND s.t0 IS NOT NULL
      AND s.t0 BETWEEN s.suspected_infection_time - INTERVAL '24 hour'
                   AND s.suspected_infection_time + INTERVAL '72 hour'
      AND s.outtime >= s.t0 + INTERVAL '6 hour'
      AND EXISTS (SELECT 1 FROM mimiciv_derived.vs_weight w
                  WHERE w.stay_id = s.stay_id AND w.weight_kg IS NOT NULL)
      AND COALESCE(pp.prev_flag,0) = 0
)
SELECT
    CASE WHEN ABS(HASHTEXT(e.stay_id::text)) % 10 < 7
         THEN 'train' ELSE 'internal_test' END AS split,
    COUNT(*) AS n,
    COUNT(*) FILTER (WHERE COALESCE(l.vasoplegia,0)=1) AS events
FROM eligible e
LEFT JOIN mimiciv_derived.vs_label l ON e.stay_id = l.stay_id
GROUP BY 1 ORDER BY 1;

-- 按时间切分（替代哈希）：CASE WHEN intime < TIMESTAMP '2180-01-01' THEN 'train'
--   ELSE 'internal_test' END；分界点按你库 intime 分布选取。

-- ============================================================================
-- Section 4. 外部验证（eICU-CRD / 本院）人数：在对应库运行同口径脚本后填入
--   eICU-CRD n=______（血管麻痹 n=______）；本院 n=______（血管麻痹 n=______）。
-- ============================================================================
