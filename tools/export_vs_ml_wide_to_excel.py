# -*- coding: utf-8 -*-
"""
导出 MIMIC 最终建模宽表 mimiciv_derived.vs_ml_wide 为 Excel / CSV
运行前：pip install psycopg2-binary pandas openpyxl
在 VSCode 终端里运行：python export_vs_ml_wide_to_excel.py
"""
import psycopg2
import pandas as pd

# ===================== 按本地修改 =====================
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="mimiciv",          # 你的 MIMIC 库名（截图里是 mimiciv）
    user="postgres",
    password="你的密码",        # 改成真实密码
)
OUT_XLSX = "vs_ml_wide.xlsx"
OUT_CSV = "vs_ml_wide.csv"
# =====================================================

# 1) 读取最终宽表
sql = "SELECT * FROM mimiciv_derived.vs_ml_wide ORDER BY stay_id"
df = pd.read_sql(sql, conn)
conn.close()

# 2) 导出前核对（期望 17463 行 × 88 列，事件 463）
print("数据维度:", df.shape)
print("事件数:", int(df.vasoplegia.sum()),
      " 非事件:", int((df.vasoplegia == 0).sum()))
assert df.shape == (17463, 88), "维度与金标准不符，请检查！"
assert int(df.vasoplegia.sum()) == 463, "事件数与金标准不符，请检查！"

# 3) 导出 Excel（单工作表，含表头）
df.to_excel(OUT_XLSX, index=False, engine="openpyxl")
print("已导出 Excel:", OUT_XLSX)

# 4) 同时导出一份 CSV（utf-8-sig，Excel 双击不乱码，作为稳妥备份）
df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
print("已导出 CSV:", OUT_CSV)

# 5) 读回验证
chk = pd.read_excel(OUT_XLSX, engine="openpyxl")
print("读回校验:", chk.shape, "事件数:", int(chk.vasoplegia.sum()))
print("全部完成。")
