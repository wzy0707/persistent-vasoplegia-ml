-- ============================================================================
-- MAJOR#12 敏感性：预测窗由 30h 延长至 48h
-- 平行复刻 12B，表名加 _48 后缀，不修改权威 vs_label
-- 末段对比 30h 与 48h 标签，导出 48h 标签发我
-- ============================================================================

-- B1. 48h 网格（landmark → t0+48h）
DROP TABLE IF EXISTS mimiciv_derived.tmp_grid_b48;
CREATE TABLE mimiciv_derived.tmp_grid_b48 AS
SELECT c.stay_id, g.ts
FROM mimiciv_derived.vs_cohort c
CROSS JOIN LATERAL GENERATE_SERIES(
    c.landmark, c.t0 + INTERVAL '48 hour', INTERVAL '5 minute') AS g(ts);

-- B2. NEE 事件（至 48h）
DROP TABLE IF EXISTS mimiciv_derived.tmp_nee_ev_b48;
CREATE TABLE mimiciv_derived.tmp_nee_ev_b48 AS
SELECT stay_id, ts, SUM(delta) AS delta FROM (
    SELECT stay_id, starttime AS ts, nee_component AS delta FROM mimiciv_derived.vs_vaso_dose
    WHERE starttime <= (SELECT max(t0 + INTERVAL '48 hour') FROM mimiciv_derived.vs_cohort)
    UNION ALL
    SELECT stay_id, endtime AS ts, -nee_component FROM mimiciv_derived.vs_vaso_dose
    WHERE endtime <= (SELECT max(t0 + INTERVAL '48 hour') FROM mimiciv_derived.vs_cohort)
      AND endtime >= (SELECT min(t0) FROM mimiciv_derived.vs_cohort)
) u GROUP BY stay_id, ts;

-- B3. NEE 累计
DROP TABLE IF EXISTS mimiciv_derived.tmp_nee_run_b48;
CREATE TABLE mimiciv_derived.tmp_nee_run_b48 AS
SELECT stay_id, ts,
    SUM(delta) OVER (PARTITION BY stay_id ORDER BY ts, delta
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS nee
FROM mimiciv_derived.tmp_nee_ev_b48;

-- B4. NEE 前向填充
DROP TABLE IF EXISTS mimiciv_derived.tmp_nee_grid_b48;
CREATE TABLE mimiciv_derived.tmp_nee_grid_b48 AS
WITH pts AS (
    SELECT stay_id, ts, nee AS val, 0 AS is_grid FROM mimiciv_derived.tmp_nee_run_b48
    UNION ALL
    SELECT stay_id, ts, NULL::double precision, 1 FROM mimiciv_derived.tmp_grid_b48
),
mark AS (
    SELECT stay_id, ts, is_grid, val,
        SUM(CASE WHEN val IS NOT NULL THEN 1 ELSE 0 END)
            OVER (PARTITION BY stay_id ORDER BY ts, is_grid
                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS grp
    FROM pts
),
filled AS (
    SELECT stay_id, ts, is_grid,
        MAX(val) OVER (PARTITION BY stay_id, grp ORDER BY ts, is_grid
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS nee
    FROM mark
)
SELECT stay_id, ts, nee FROM filled WHERE is_grid = 1;
CREATE INDEX idx_tmp_nee_grid_b48 ON mimiciv_derived.tmp_nee_grid_b48(stay_id, ts);

-- B5. MAP 前向填充
DROP TABLE IF EXISTS mimiciv_derived.tmp_map_grid_b48;
CREATE TABLE mimiciv_derived.tmp_map_grid_b48 AS
WITH pts AS (
    SELECT stay_id, charttime AS ts, map AS val, 0 AS is_grid FROM mimiciv_derived.vs_map_long
    WHERE charttime <= (SELECT max(t0 + INTERVAL '48 hour') FROM mimiciv_derived.vs_cohort)
    UNION ALL
    SELECT stay_id, ts, NULL::double precision, 1 FROM mimiciv_derived.tmp_grid_b48
),
mark AS (
    SELECT stay_id, ts, is_grid, val,
        SUM(CASE WHEN val IS NOT NULL THEN 1 ELSE 0 END)
            OVER (PARTITION BY stay_id ORDER BY ts, is_grid
                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS grp
    FROM pts
),
filled AS (
    SELECT stay_id, ts, is_grid,
        MAX(val) OVER (PARTITION BY stay_id, grp ORDER BY ts, is_grid
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS map
    FROM mark
)
SELECT stay_id, ts, map FROM filled WHERE is_grid = 1;
CREATE INDEX idx_tmp_map_grid_b48 ON mimiciv_derived.tmp_map_grid_b48(stay_id, ts);

-- B6a. 合并网格
SET work_mem='256MB';
SET enable_nestloop=off;
DROP TABLE IF EXISTS mimiciv_derived.tmp_f_b48;
CREATE TABLE mimiciv_derived.tmp_f_b48 AS
SELECT gd.stay_id, gd.ts, COALESCE(ng.nee,0) AS nee, mg.map
FROM mimiciv_derived.tmp_grid_b48 gd
LEFT JOIN mimiciv_derived.tmp_nee_grid_b48 ng ON ng.stay_id=gd.stay_id AND ng.ts=gd.ts
LEFT JOIN mimiciv_derived.tmp_map_grid_b48 mg ON mg.stay_id=gd.stay_id AND mg.ts=gd.ts;

-- B6b. 窗口判定（排除 prevalent，规则同 12B）
SET work_mem='256MB';
SET enable_nestloop=off;
ANALYZE mimiciv_derived.tmp_f_b48;
DROP TABLE IF EXISTS mimiciv_derived.vs_label_48;
CREATE TABLE mimiciv_derived.vs_label_48 AS
WITH flag AS (
    SELECT stay_id, ts,
        CASE WHEN COALESCE(nee,0)>=0.5 AND (map IS NULL OR map<65) THEN 1 ELSE 0 END AS is_v,
        ts - ROW_NUMBER() OVER (PARTITION BY stay_id ORDER BY ts)*INTERVAL '5 minute' AS grp
    FROM mimiciv_derived.tmp_f_b48
),
runs AS (
    SELECT stay_id, grp, MIN(ts) AS rs, MAX(ts) AS re
    FROM flag WHERE is_v=1 GROUP BY stay_id, grp
)
SELECT c.stay_id,
    CASE WHEN p.prev_flag=1 THEN 0
         ELSE COALESCE(MAX(CASE WHEN (r.re-r.rs)+INTERVAL '5 minute'>=INTERVAL '6 hour' THEN 1 ELSE 0 END),0)
    END AS vasoplegia_48,
    CASE WHEN p.prev_flag=1 THEN NULL
         ELSE MIN(CASE WHEN (r.re-r.rs)+INTERVAL '5 minute'>=INTERVAL '6 hour' THEN r.rs END)
    END AS onset_48
FROM mimiciv_derived.vs_cohort c
LEFT JOIN mimiciv_derived.vs_prevalent p ON c.stay_id=p.stay_id
LEFT JOIN runs r ON c.stay_id=r.stay_id
GROUP BY c.stay_id, p.prev_flag;

-- ============ 对比 30h vs 48h（建模队列 17,463，排除 prevalent） ============
SELECT l.vasoplegia AS label_30h, l48.vasoplegia_48 AS label_48h, COUNT(*) AS n
FROM mimiciv_derived.vs_label l
JOIN mimiciv_derived.vs_label_48 l48 ON l.stay_id=l48.stay_id
JOIN mimiciv_derived.vs_prevalent p ON l.stay_id=p.stay_id
WHERE p.prev_flag = 0
GROUP BY l.vasoplegia, l48.vasoplegia_48
ORDER BY 1,2;

-- 导出 48h 标签（保存为 label_48h.csv）
SELECT l48.stay_id, l48.vasoplegia_48, l48.onset_48
FROM mimiciv_derived.vs_label_48 l48
JOIN mimiciv_derived.vs_prevalent p ON l48.stay_id=p.stay_id
WHERE p.prev_flag = 0
ORDER BY l48.stay_id;
-- ============================================================================
