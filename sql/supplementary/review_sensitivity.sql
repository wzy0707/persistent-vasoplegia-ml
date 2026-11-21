-- ============================================================================
-- 审稿清单 CRITICAL#2 / #3 敏感性分析（MIMIC-IV 库执行）
-- 逐段 F5；每段独立出结果。建模口径：排除 63 例 prevalent（vs_prevalent.prev_flag=1）
-- 权威对照：incident 事件 463；建模队列 17,463；de novo 386 / cross 77
-- ============================================================================

-- ============ CRITICAL#2：MAP 缺失（2.5 结局定义） ============

-- 2a. 预测窗网格整体 MAP 缺失，以及高剂量(NEE>=0.5)时点的缺失
SELECT
    COUNT(*)                                              AS total_grid_points,
    COUNT(*) FILTER (WHERE f.map IS NULL)                 AS map_missing_points,
    ROUND(100.0 * COUNT(*) FILTER (WHERE f.map IS NULL)
          / COUNT(*), 2)                                  AS pct_map_missing,
    COUNT(*) FILTER (WHERE f.nee >= 0.5)                  AS highdose_points,
    COUNT(*) FILTER (WHERE f.nee >= 0.5 AND f.map IS NULL) AS highdose_missing,
    ROUND(100.0 * COUNT(*) FILTER (WHERE f.nee >= 0.5 AND f.map IS NULL)
          / NULLIF(COUNT(*) FILTER (WHERE f.nee >= 0.5), 0), 2) AS pct_highdose_missing
FROM mimiciv_derived.tmp_f_b f;

-- 2b. 完全没有 MAP 记录的患者数
SELECT COUNT(*) AS patients_without_any_map
FROM (
    SELECT stay_id FROM mimiciv_derived.tmp_f_b
    GROUP BY stay_id HAVING COUNT(map) = 0
) x;

-- 2c.【关键敏感性】缺失视为“不满足”：高剂量点必须同时观测到 MAP<65 才计入
--     重新做连续>=6h 窗口判定，给出新事件数（对照 463）
WITH flag AS (
    SELECT f.stay_id, f.ts,
        CASE WHEN f.nee >= 0.5 AND f.map IS NOT NULL AND f.map < 65 THEN 1 ELSE 0 END AS is_v,
        f.ts - ROW_NUMBER() OVER (PARTITION BY f.stay_id ORDER BY f.ts) * INTERVAL '5 minute' AS grp
    FROM mimiciv_derived.tmp_f_b f
    JOIN mimiciv_derived.vs_prevalent p ON p.stay_id = f.stay_id
    WHERE COALESCE(p.prev_flag, 0) = 0          -- 排除 prevalent
),
runs AS (
    SELECT stay_id, grp, MIN(ts) AS rs, MAX(ts) AS re
    FROM flag WHERE is_v = 1 GROUP BY stay_id, grp
)
SELECT
    (SELECT COUNT(*) FROM mimiciv_derived.vs_label l
       JOIN mimiciv_derived.vs_prevalent p ON p.stay_id=l.stay_id
       WHERE l.vasoplegia=1 AND COALESCE(p.prev_flag,0)=0) AS primary_events,
    COUNT(*) AS events_missing_as_fail
FROM (
    SELECT stay_id FROM runs GROUP BY stay_id
    HAVING MAX(CASE WHEN (re - rs) + INTERVAL '5 minute' >= INTERVAL '6 hour' THEN 1 ELSE 0 END) = 1
) y;

-- 2d. 完整病例：每个事件在其合格 6h 窗口内的 MAP 覆盖率，>=80% 者计数
WITH ev AS (   -- 原 463 事件及其窗口
    SELECT l.stay_id, l.vasoplegia_onset AS rs, l.vasoplegia_onset + INTERVAL '6 hour' AS re
    FROM mimiciv_derived.vs_label l
    JOIN mimiciv_derived.vs_prevalent p ON p.stay_id = l.stay_id
    WHERE l.vasoplegia = 1 AND COALESCE(p.prev_flag, 0) = 0
),
cov AS (
    SELECT e.stay_id,
        COUNT(*) AS pts,
        COUNT(f.map) AS pts_observed,
        ROUND(1.0 * COUNT(f.map) / COUNT(*), 4) AS map_coverage
    FROM ev e
    JOIN mimiciv_derived.tmp_f_b f
      ON f.stay_id = e.stay_id AND f.ts >= e.rs AND f.ts < e.re
    GROUP BY e.stay_id
)
SELECT
    COUNT(*) AS events_total,
    COUNT(*) FILTER (WHERE map_coverage >= 0.8) AS complete_case_events,
    ROUND(AVG(map_coverage), 4) AS mean_window_coverage,
    ROUND(AVG(100.0 * map_coverage), 2) AS mean_coverage_pct
FROM cov;

-- ============ CRITICAL#3：de novo / cross-landmark（3.3 / 2.5） ============

-- 3a. 计数核对（对照 de novo 386 / cross 77）
SELECT
    SUM(CASE WHEN l.vasoplegia_onset >  c.landmark THEN 1 ELSE 0 END) AS de_novo,
    SUM(CASE WHEN l.vasoplegia_onset = c.landmark THEN 1 ELSE 0 END) AS cross_landmark,
    COUNT(*) AS total_events
FROM mimiciv_derived.vs_label l
JOIN mimiciv_derived.vs_cohort c ON c.stay_id = l.stay_id
JOIN mimiciv_derived.vs_prevalent p ON p.stay_id = l.stay_id
WHERE l.vasoplegia = 1 AND COALESCE(p.prev_flag, 0) = 0;

-- 3b.【导出】逐患者类型标记，用于在 Python 中计算 de-novo-only 性能
--     导出为 CSV：stay_id, vasoplegia, onset_type
SELECT l.stay_id,
       l.vasoplegia,
       CASE WHEN l.vasoplegia = 0 THEN 'noncase'
            WHEN l.vasoplegia_onset >  c.landmark THEN 'de_novo'
            WHEN l.vasoplegia_onset = c.landmark THEN 'cross' END AS onset_type
FROM mimiciv_derived.vs_label l
JOIN mimiciv_derived.vs_cohort c ON c.stay_id = l.stay_id
JOIN mimiciv_derived.vs_prevalent p ON p.stay_id = l.stay_id
WHERE COALESCE(p.prev_flag, 0) = 0
ORDER BY l.stay_id;
-- ============================================================================
