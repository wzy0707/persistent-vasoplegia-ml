-- ============================================================================
-- pH 提取诊断：先跑这两段，把结果发我，我再锁定最终提取 SQL
-- ============================================================================

-- 1) 找血气表（可能命名不同或在别的 schema）
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_name ILIKE '%bg%'
   OR table_name ILIKE '%blood%gas%'
   OR table_name ILIKE '%gas%'
ORDER BY table_schema, table_name;

-- 2) 找 chartevents 中 pH 相关的 d_items 标签与 itemid
SELECT itemid, label, category
FROM mimiciv_icu.d_items
WHERE label ILIKE '%ph%'
ORDER BY label;

-- 3) 顺带确认 hosp schema 下实际有哪些表（看 bg 是否真的没装）
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'mimiciv_hosp'
ORDER BY table_name;
-- ============================================================================
