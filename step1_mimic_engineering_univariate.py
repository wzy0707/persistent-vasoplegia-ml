# -*- coding: utf-8 -*-
"""
MIMIC 第一步分析：88→77 特征工程 + Table 1（基线特征）+ 单因素 Logistic
运行：python step1_mimic_engineering_univariate.py
依赖：pip install pandas numpy scipy statsmodels scikit-learn openpyxl
输入：vs_ml_wide.csv（17463×88）
输出：mimic_77_matrix.csv（干净建模矩阵）、MIMIC_table1_univariate.xlsx
"""
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
from sklearn.metrics import roc_auc_score

warnings.filterwarnings("ignore")

# ===================== 路径配置（按本地修改） =====================
HERE = Path(__file__).resolve().parent
INPUT_CSV = HERE / "vs_ml_wide.csv"          # 首选：脚本同目录
OUT_MATRIX = HERE / "mimic_77_matrix.csv"
OUT_XLSX = HERE / "MIMIC_table1_univariate.xlsx"
CU_SCHEME = "A"   # care-unit 方案：A=MICU优先(默认)；B=SICU优先；C=纯单元精确
# ==================================================================

# 同目录没有时，自动在当前目录及所有子目录递归查找
# 兼容 pgAdmin 导出“无扩展名”的情况：vs_ml_wide.csv 或名为 vs_ml_wide 的文件
if not INPUT_CSV.exists():
    with_csv = [p for p in HERE.rglob("vs_ml_wide*.csv") if p.is_file()]
    no_ext = [p for p in HERE.rglob("vs_ml_wide") if p.is_file()]
    hits = with_csv if with_csv else no_ext
    if hits:
        INPUT_CSV = sorted(hits)[0]
        print("脚本同目录未找到，自动使用:", INPUT_CSV, "\n")
    else:
        raise FileNotFoundError(
            "找不到 vs_ml_wide 数据文件。两种解决办法：\n"
            "1) 把数据文件（vs_ml_wide 或 vs_ml_wide.csv）放到脚本所在文件夹后重跑；\n"
            r"2) 或把上面的 INPUT_CSV 改成完整路径，例如 "
            r'INPUT_CSV = r"C:\Users\12431\Desktop\persistent-vasoplegia-ml\vs_ml_wide"')

raw = pd.read_csv(INPUT_CSV)
print("原始宽表:", raw.shape)
assert raw.shape == (17463, 88), "输入维度应为 17463×88"

# ---------- 5.3 先打印 race / first_careunit 分布 ----------
print("\n===== race 取值分布（前 10） =====")
print(raw["race"].value_counts().head(10).to_string())
print("\n===== first_careunit 取值分布 =====")
print(raw["first_careunit"].value_counts().to_string())

df = raw.copy()

# ---------- (a) 血压：有创优先，无创补 ----------
df["sbp_last"] = df["abps_last"].fillna(df["nbps_last"])
df["sbp_min"] = df["abps_min"].fillna(df["nbps_min"])
df["sbp_mean"] = df["abps_mean"].fillna(df["nbps_mean"])
df["dbp_last"] = df["abpd_last"].fillna(df["nbpd_last"])

# ---------- (b) 体温：摄氏优先，华氏转换列补 ----------
df["temp_last"] = df["temp_c_last"].fillna(df["temp_fromf_last"])

# ---------- (c) race 哑变量（互斥完备） ----------
r = df["race"].astype(str).str.lower()
h = r.str.contains("hispanic|latino", regex=True)
w_ = r.str.contains("white") & ~h
df["race_grp_hispanic"] = h.astype(int)
df["race_grp_white"] = w_.astype(int)
df["race_grp_other"] = (~h & ~w_).astype(int)

# ---------- (d) care unit 哑变量（first_careunit 为完整名称，按关键词） ----------
nm = df["first_careunit"].astype(str).str.lower()
is_med = nm.str.contains("medical") | nm.str.contains("micu")
is_sur = nm.str.contains("surgical") | nm.str.contains("sicu")
if CU_SCHEME == "B":          # SICU 优先：混合单元归 SICU
    cu_sicu = is_sur
    cu_micu = (~cu_sicu) & is_med
elif CU_SCHEME == "C":        # 纯单元精确：仅纯 MICU / 纯 SICU
    cu_micu = is_med & ~is_sur
    cu_sicu = is_sur & ~is_med
else:                         # A（默认）：MICU 优先，混合单元归 MICU
    cu_micu = is_med
    cu_sicu = (~cu_micu) & is_sur
df["cu_grp_micu"] = cu_micu.astype(int)
df["cu_grp_sicu"] = cu_sicu.astype(int)
df["cu_grp_other"] = ((~cu_micu) & (~cu_sicu)).astype(int)

print("\n===== care-unit 分组计数（方案 %s） =====" % CU_SCHEME)
print("MICU=%d  SICU=%d  OTHER=%d" % (
    df["cu_grp_micu"].sum(), df["cu_grp_sicu"].sum(), df["cu_grp_other"].sum()))
print("race 分组: hispanic=%d white=%d other=%d" % (
    df["race_grp_hispanic"].sum(), df["race_grp_white"].sum(), df["race_grp_other"].sum()))

# ---------- 组装 77 列 ----------
EXCLUDE = ["stay_id", "subject_id", "hadm_id", "race", "first_careunit", "dobut_used",
           "abps_last", "abps_min", "abps_mean", "abpd_last", "abpd_mean",
           "abpm_last", "abpm_mean", "nbps_last", "nbps_min", "nbps_mean",
           "nbpd_last", "nbpm_last", "temp_c_last", "temp_fromf_last",
           "vasoplegia", "vasoplegia_onset"]
direct = [c for c in raw.columns if c not in EXCLUDE]
ENG = ["sbp_last", "sbp_min", "sbp_mean", "dbp_last", "temp_last",
       "race_grp_hispanic", "race_grp_other", "race_grp_white",
       "cu_grp_micu", "cu_grp_other", "cu_grp_sicu"]
features = direct + ENG
assert len(direct) == 66 and len(features) == 77, (len(direct), len(features))

mat = df[features + ["vasoplegia"]].copy()
y = mat["vasoplegia"].astype(int)
print("\n77 矩阵:", mat.shape, " 事件:", int(y.sum()), " 阳性率: %.4f" % y.mean())

# 自然二值列（非空取值仅 {0,1}）
bin_cols = [c for c in features
            if set(mat[c].dropna().unique()).issubset({0, 1})]
num_cols = [c for c in features if c not in bin_cols]
print("自然二值列 %d 个，连续列 %d 个" % (len(bin_cols), len(num_cols)))

# 保存干净矩阵（供后续建模/外验对齐）
mat.to_csv(OUT_MATRIX, index=False, encoding="utf-8-sig")
print("已保存矩阵:", OUT_MATRIX.name)

# ================= Table 1 =================
g1 = mat[y == 1]
g0 = mat[y == 0]
rows = []

def smd_num(a, b):
    a, b = a.dropna(), b.dropna()
    if len(a) < 2 or len(b) < 2:
        return np.nan
    sp = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    return (a.mean() - b.mean()) / sp if sp > 0 else np.nan

def smd_bin(a, b):
    p1, p0 = a.mean(), b.mean()
    den = np.sqrt((p1 * (1 - p1) + p0 * (1 - p0)) / 2)
    return (p1 - p0) / den if den > 0 else np.nan

for c in num_cols:
    a, b = g1[c], g0[c]
    p = stats.mannwhitneyu(a.dropna(), b.dropna()).pvalue
    rows.append({
        "变量": c, "类型": "连续", "缺失": int(mat[c].isna().sum()),
        "事件组 mean±SD": "%.2f ± %.2f" % (a.mean(), a.std(ddof=1)),
        "非事件组 mean±SD": "%.2f ± %.2f" % (b.mean(), b.std(ddof=1)),
        "事件组 median[IQR]": "%.2f [%.2f, %.2f]" % (a.median(), a.quantile(.25), a.quantile(.75)),
        "非事件组 median[IQR]": "%.2f [%.2f, %.2f]" % (b.median(), b.quantile(.25), b.quantile(.75)),
        "P": p, "SMD": smd_num(a, b)})

for c in bin_cols:
    a, b = g1[c], g0[c]
    tab = pd.crosstab(mat[c], y)
    if tab.shape == (2, 2):
        p = stats.chi2_contingency(tab, correction=False)[1]
    else:
        p = np.nan
    rows.append({
        "变量": c, "类型": "二值", "缺失": int(mat[c].isna().sum()),
        "事件组 mean±SD": "%d (%.1f%%)" % (a.sum(), 100 * a.mean()),
        "非事件组 mean±SD": "%d (%.1f%%)" % (b.sum(), 100 * b.mean()),
        "事件组 median[IQR]": "", "非事件组 median[IQR]": "",
        "P": p, "SMD": smd_bin(a, b)})

table1 = pd.DataFrame(rows)

# ================= 单因素 Logistic =================
uni = []
for c in features:
    x = mat[c].astype(float)
    x = x.fillna(x.median())          # 单因素缺失用中位数补
    X = sm.add_constant(x)
    try:
        fit = sm.Logit(y, X).fit(disp=0, maxiter=200)
        coef = fit.params[c]
        ci = fit.conf_int().loc[c].tolist()
        pv = fit.pvalues[c]
        orv, lo, hi = np.exp(coef), np.exp(ci[0]), np.exp(ci[1])
    except Exception as e:
        orv = lo = hi = pv = np.nan
    try:
        auc = roc_auc_score(y, x)
        auc = max(auc, 1 - auc)
    except Exception:
        auc = np.nan
    uni.append({"变量": c, "类型": "二值" if c in bin_cols else "连续",
                "OR": orv, "OR_95CI_low": lo, "OR_95CI_high": hi,
                "P": pv, "单变量AUC": auc})

univ = pd.DataFrame(uni).sort_values("P")
univ["OR (95% CI)"] = univ.apply(
    lambda d: "%.3f (%.3f, %.3f)" % (d["OR"], d["OR_95CI_low"], d["OR_95CI_high"]), axis=1)

# ================= 导出 Excel =================
with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as w:
    table1.to_excel(w, sheet_name="Table1_基线", index=False)
    univ.to_excel(w, sheet_name="单因素Logistic", index=False)
print("已导出:", OUT_XLSX.name)

# 控制台预览
print("\n===== 单因素 P 最小的前 12 个变量 =====")
print(univ[["变量", "OR (95% CI)", "P", "单变量AUC"]].head(12).to_string(index=False))
print("\n|SMD|>0.1 的变量数:", int((table1["SMD"].abs() > 0.1).sum()))
print("完成。")
