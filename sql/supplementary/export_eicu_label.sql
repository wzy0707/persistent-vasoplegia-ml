-- 导出 eICU 标签表 e_label（供外部验证 join）
-- 在 pgAdmin 选中 eICU 库执行，再用右键结果面板“保存结果到文件”导出为 e_label.csv
SELECT patientunitstayid, label, label_type
FROM eicu.e_label
WHERE label_type IN ('incident', 'negative')
ORDER BY patientunitstayid;
-- 预期：2268 行；其中 label=1（incident）165，label=0（negative）2103
