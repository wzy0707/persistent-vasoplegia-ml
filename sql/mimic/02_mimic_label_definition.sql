-- ============================================================================
-- Step 12【分步落表版·最终可复现版】
-- 每步只做一件事、落表 + 建索引，逐段 F5、逐段验证。
-- 逻辑已通过 10 个边界场景验证（12A 5 场景 + 12B 5 场景）。
-- 现场实际跑通（MIMIC-IV，队列 17,526）：
--   prevalent=63（排除）；建模队列 17,463；incident 阳性 463（2.65%），阴性 17,000。
--
-- 【重要】
-- 1) 每段开头的 SET work_mem / enable_nestloop 必须与该段 CREATE 在同一批次、同一窗口执行；
--    pgAdmin 新开标签是独立连接，会话级 SET 不会带过去。
-- 2) 执行前先确认没有遗留的旧查询（尤其第一步 SQL 里逐点子查询的老 12A）：
--      SELECT pid, state, wait_event_type, now()-query_start, LEFT(query,40)
--      FROM pg_stat_activity WHERE datname='mimiciv' AND state='active';
--    若有跑了很久的旧查询，先 pg_terminate_backend(pid) 终止。
-- ============================================================================

-- ============================================================================
-- 12A（prevalent，窗口 [t0, landmark]）
-- ============================================================================

-- A1. 5分钟网格
DROP TABLE IF EXISTS mimiciv_derived.tmp_grid_a;
CREATE TABLE mimiciv_derived.tmp_grid_a AS
SELECT c.stay_id, g.ts
FROM mimiciv_derived.vs_cohort c
CROSS JOIN LATERAL GENERATE_SERIES(c.t0, c.landmark, INTERVAL '5 minute') AS g(ts);
-- 验证：SELECT count(*) FROM mimiciv_derived.tmp_grid_a;   实际 1,279,398

-- A2. NEE 加/减事件（合并同点）
DROP TABLE IF EXISTS mimiciv_derived.tmp_nee_ev_a;
CREATE TABLE mimiciv_derived.tmp_nee_ev_a AS
SELECT stay_id, ts, SUM(delta) AS delta FROM (
    SELECT stay_id, starttime AS ts, nee_component AS delta FROM mimiciv_derived.vs_vaso_dose
    WHERE starttime <= (SELECT max(landmark) FROM mimiciv_derived.vs_cohort)
    UNION ALL
    SELECT stay_id, endtime AS ts, -nee_component FROM mimiciv_derived.vs_vaso_dose
    WHERE endtime <= (SELECT max(landmark) FROM mimiciv_derived.vs_cohort)
      AND endtime >= (SELECT min(t0) FROM mimiciv_derived.vs_cohort)
) u GROUP BY stay_id, ts;

-- A3. NEE 累计（事件点，分段常数）
DROP TABLE IF EXISTS mimiciv_derived.tmp_nee_run_a;
CREATE TABLE mimiciv_derived.tmp_nee_run_a AS
SELECT stay_id, ts,
    SUM(delta) OVER (PARTITION BY stay_id ORDER BY ts, delta
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS nee
FROM mimiciv_derived.tmp_nee_ev_a;

-- A4. NEE 前向填充到网格
DROP TABLE IF EXISTS mimiciv_derived.tmp_nee_grid_a;
CREATE TABLE mimiciv_derived.tmp_nee_grid_a AS
WITH pts AS (
    SELECT stay_id, ts, nee AS val, 0 AS is_grid FROM mimiciv_derived.tmp_nee_run_a
    UNION ALL
    SELECT stay_id, ts, NULL::double precision, 1 FROM mimiciv_derived.tmp_grid_a
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
CREATE INDEX idx_tmp_nee_grid_a ON mimiciv_derived.tmp_nee_grid_a(stay_id, ts);

-- A5. MAP 前向填充到网格
DROP TABLE IF EXISTS mimiciv_derived.tmp_map_grid_a;
CREATE TABLE mimiciv_derived.tmp_map_grid_a AS
WITH pts AS (
    SELECT stay_id, charttime AS ts, map AS val, 0 AS is_grid FROM mimiciv_derived.vs_map_long
    WHERE charttime <= (SELECT max(landmark) FROM mimiciv_derived.vs_cohort)
    UNION ALL
    SELECT stay_id, ts, NULL::double precision, 1 FROM mimiciv_derived.tmp_grid_a
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
CREATE INDEX idx_tmp_map_grid_a ON mimiciv_derived.tmp_map_grid_a(stay_id, ts);

-- A6a. 合并网格状态落表（强制 hash join，避免 128 万行 nested loop）
SET work_mem='256MB';
SET enable_nestloop=off;
DROP TABLE IF EXISTS mimiciv_derived.tmp_f_a;
CREATE TABLE mimiciv_derived.tmp_f_a AS
SELECT gd.stay_id, gd.ts, COALESCE(ng.nee,0) AS nee, mg.map
FROM mimiciv_derived.tmp_grid_a gd
LEFT JOIN mimiciv_derived.tmp_nee_grid_a ng ON ng.stay_id=gd.stay_id AND ng.ts=gd.ts
LEFT JOIN mimiciv_derived.tmp_map_grid_a mg ON mg.stay_id=gd.stay_id AND mg.ts=gd.ts;
-- 验证：SELECT count(*) FROM mimiciv_derived.tmp_f_a;   实际 1,279,398（866ms）

-- A6b. 窗口判定（连续≥6h）
SET work_mem='256MB';
SET enable_nestloop=off;
ANALYZE mimiciv_derived.tmp_f_a;
DROP TABLE IF EXISTS mimiciv_derived.vs_prevalent;
CREATE TABLE mimiciv_derived.vs_prevalent AS
WITH flag AS (
    SELECT stay_id, ts,
        CASE WHEN COALESCE(nee,0)>=0.5 AND (map IS NULL OR map<65) THEN 1 ELSE 0 END AS is_v,
        ts - ROW_NUMBER() OVER (PARTITION BY stay_id ORDER BY ts)*INTERVAL '5 minute' AS grp
    FROM mimiciv_derived.tmp_f_a
),
runs AS (
    SELECT stay_id, grp, MIN(ts) AS rs, MAX(ts) AS re
    FROM flag WHERE is_v=1 GROUP BY stay_id, grp
)
SELECT c.stay_id,
    MAX(CASE WHEN (r.re-r.rs)+INTERVAL '5 minute'>=INTERVAL '6 hour' THEN 1 ELSE 0 END) AS prev_flag,
    MIN(CASE WHEN (r.re-r.rs)+INTERVAL '5 minute'>=INTERVAL '6 hour' THEN r.rs END) AS prev_onset
FROM mimiciv_derived.vs_cohort c
LEFT JOIN runs r ON c.stay_id=r.stay_id
GROUP BY c.stay_id;
-- 验证：SELECT prev_flag, count(*) FROM mimiciv_derived.vs_prevalent GROUP BY 1 ORDER BY 1;
-- 实际：0=17,463  1=63

-- ============================================================================
-- 12B（incident，窗口 [landmark, pred_window_end]）
-- ============================================================================

-- B1. 5分钟网格
DROP TABLE IF EXISTS mimiciv_derived.tmp_grid_b;
CREATE TABLE mimiciv_derived.tmp_grid_b AS
SELECT c.stay_id, g.ts
FROM mimiciv_derived.vs_cohort c
CROSS JOIN LATERAL GENERATE_SERIES(c.landmark, c.pred_window_end, INTERVAL '5 minute') AS g(ts);
-- 验证：SELECT count(*) FROM mimiciv_derived.tmp_grid_b;   实际 5,065,014

-- B2. NEE 事件（从 t0 起算，保证 landmark 点承接正确）
DROP TABLE IF EXISTS mimiciv_derived.tmp_nee_ev_b;
CREATE TABLE mimiciv_derived.tmp_nee_ev_b AS
SELECT stay_id, ts, SUM(delta) AS delta FROM (
    SELECT stay_id, starttime AS ts, nee_component AS delta FROM mimiciv_derived.vs_vaso_dose
    WHERE starttime <= (SELECT max(pred_window_end) FROM mimiciv_derived.vs_cohort)
    UNION ALL
    SELECT stay_id, endtime AS ts, -nee_component FROM mimiciv_derived.vs_vaso_dose
    WHERE endtime <= (SELECT max(pred_window_end) FROM mimiciv_derived.vs_cohort)
      AND endtime >= (SELECT min(t0) FROM mimiciv_derived.vs_cohort)
) u GROUP BY stay_id, ts;

-- B3. NEE 累计
DROP TABLE IF EXISTS mimiciv_derived.tmp_nee_run_b;
CREATE TABLE mimiciv_derived.tmp_nee_run_b AS
SELECT stay_id, ts,
    SUM(delta) OVER (PARTITION BY stay_id ORDER BY ts, delta
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS nee
FROM mimiciv_derived.tmp_nee_ev_b;

-- B4. NEE 前向填充到网格
DROP TABLE IF EXISTS mimiciv_derived.tmp_nee_grid_b;
CREATE TABLE mimiciv_derived.tmp_nee_grid_b AS
WITH pts AS (
    SELECT stay_id, ts, nee AS val, 0 AS is_grid FROM mimiciv_derived.tmp_nee_run_b
    UNION ALL
    SELECT stay_id, ts, NULL::double precision, 1 FROM mimiciv_derived.tmp_grid_b
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
CREATE INDEX idx_tmp_nee_grid_b ON mimiciv_derived.tmp_nee_grid_b(stay_id, ts);

-- B5. MAP 前向填充到网格（不设 landmark 下限，承接 landmark 前最近 MAP）
DROP TABLE IF EXISTS mimiciv_derived.tmp_map_grid_b;
CREATE TABLE mimiciv_derived.tmp_map_grid_b AS
WITH pts AS (
    SELECT stay_id, charttime AS ts, map AS val, 0 AS is_grid FROM mimiciv_derived.vs_map_long
    WHERE charttime <= (SELECT max(pred_window_end) FROM mimiciv_derived.vs_cohort)
    UNION ALL
    SELECT stay_id, ts, NULL::double precision, 1 FROM mimiciv_derived.tmp_grid_b
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
CREATE INDEX idx_tmp_map_grid_b ON mimiciv_derived.tmp_map_grid_b(stay_id, ts);

-- B6a. 合并网格状态落表（强制 hash join）
SET work_mem='256MB';
SET enable_nestloop=off;
DROP TABLE IF EXISTS mimiciv_derived.tmp_f_b;
CREATE TABLE mimiciv_derived.tmp_f_b AS
SELECT gd.stay_id, gd.ts, COALESCE(ng.nee,0) AS nee, mg.map
FROM mimiciv_derived.tmp_grid_b gd
LEFT JOIN mimiciv_derived.tmp_nee_grid_b ng ON ng.stay_id=gd.stay_id AND ng.ts=gd.ts
LEFT JOIN mimiciv_derived.tmp_map_grid_b mg ON mg.stay_id=gd.stay_id AND mg.ts=gd.ts;
-- 验证：SELECT count(*) FROM mimiciv_derived.tmp_f_b;   实际 5,065,014（2.1s）

-- B6b. 窗口判定（incident；排除 prevalent）
-- 口径：incident 段从 landmark 网格点起算，须在 [landmark, pred_window_end] 内连续满 6h；
--       跨 landmark 的段按 landmark 起算（onset=landmark）；prevalent（prev_flag=1）强制为 0。
SET work_mem='256MB';
SET enable_nestloop=off;
ANALYZE mimiciv_derived.tmp_f_b;
DROP TABLE IF EXISTS mimiciv_derived.vs_label;
CREATE TABLE mimiciv_derived.vs_label AS
WITH flag AS (
    SELECT stay_id, ts,
        CASE WHEN COALESCE(nee,0)>=0.5 AND (map IS NULL OR map<65) THEN 1 ELSE 0 END AS is_v,
        ts - ROW_NUMBER() OVER (PARTITION BY stay_id ORDER BY ts)*INTERVAL '5 minute' AS grp
    FROM mimiciv_derived.tmp_f_b
),
runs AS (
    SELECT stay_id, grp, MIN(ts) AS rs, MAX(ts) AS re
    FROM flag WHERE is_v=1 GROUP BY stay_id, grp
)
SELECT c.stay_id,
    CASE WHEN p.prev_flag=1 THEN 0
         ELSE COALESCE(MAX(CASE WHEN (r.re-r.rs)+INTERVAL '5 minute'>=INTERVAL '6 hour' THEN 1 ELSE 0 END),0)
    END AS vasoplegia,
    CASE WHEN p.prev_flag=1 THEN NULL
         ELSE MIN(CASE WHEN (r.re-r.rs)+INTERVAL '5 minute'>=INTERVAL '6 hour' THEN r.rs END)
    END AS vasoplegia_onset
FROM mimiciv_derived.vs_cohort c
LEFT JOIN mimiciv_derived.vs_prevalent p ON c.stay_id=p.stay_id
LEFT JOIN runs r ON c.stay_id=r.stay_id
GROUP BY c.stay_id, p.prev_flag;
-- 验证：SELECT vasoplegia, count(*) FROM mimiciv_derived.vs_label GROUP BY 1 ORDER BY 1;
-- 实际：0=17,063（含 63 例 prevalent）  1=463
-- 建模时：排除 63 例 prevalent，建模队列 n=17,463，阳性 463（2.65%），阴性 17,000。
-- ============================================================================
