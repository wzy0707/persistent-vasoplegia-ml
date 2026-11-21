-- 导出外部锚点表 vs_anchor（供 Fig4 风险梯度计算）
-- 在 pgAdmin 选中 MIMIC 库执行，结果保存为 vs_anchor.csv
SELECT stay_id, icu_death, hosp_death, icu_los, rrt_any
FROM mimiciv_derived.vs_anchor
ORDER BY stay_id;
-- 预期：17463 行
