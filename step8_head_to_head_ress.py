# -*- coding: utf-8 -*-
"""
Step8 head-to-head：最终 ML 模型 vs 两个可解释基准
  (1) 已发表 RESS 点评分（Heo 2025，忠实切点）
  (2) 六变量 logistic（同六变量，MIMIC 训练，eICU 锁定外推）
同集 AUROC/AUPRC + DeLong ΔAUC(95%CI,p) + IDI/NRI
依赖：ph_mimic.csv / ph_eicu.csv（递归查找）
"""
from pathlib import Path
import numpy as np, pandas as pd, joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from scipy.stats import norm

HERE = Path(__file__).resolve().parent
def find(name):
    h = list(HERE.rglob(name)); return h[0] if h else None
def find_any(names):
    for n in names:
        p = find(n)
        if p is not None: return p
    return None
SIX = ["lactate_last", "sbp_last", "hr_last", "temp_last", "wbc_last", "ph_last"]

def _pts(x, cuts, pts):
    """按第一个匹配阈值给分（嵌套互斥分段）；NaN 归参考段 0"""
    arr = x.to_numpy()
    out = np.full(len(arr), np.nan)
    for c, p in zip(cuts, pts[:-1]):
        out = np.where((arr < c) & np.isnan(out), p, out)
    out = np.where(np.isnan(out), pts[-1], out)
    return np.where(x.isna().to_numpy(), 0, out)

def ress_score(df):
    s = np.zeros(len(df))
    s += _pts(df.lactate_last, [2.4, 4.6, 6], [0, 3, 6, 7])
    s += _pts(df.sbp_last, [80, 100, 140], [8, 5, 2, 0])
    s += _pts(df.wbc_last, [4, 25], [3, 0, 1])
    s += _pts(df.ph_last, [7.27, 7.35], [6, 4, 0])
    s += _pts(df.temp_last, [35, 36, 38], [3, 2, 0, 1])
    s += _pts(df.hr_last, [60, 100, 120], [1, 0, 1, 3])
    return s

def _midrank(x):
    J = np.argsort(x, kind="mergesort"); Z = x[J]; N = len(x); T = np.empty(N); i = 0
    while i < N:
        j = i
        while j < N and Z[j] == Z[i]: j += 1
        T[i:j] = 0.5*(i+j-1)+1; i = j
    out = np.empty(N); out[J] = T; return out

def delong(y, s1, s2):
    o = np.argsort(-y); y, s1, s2 = y[o], s1[o], s2[o]
    m = int(y.sum()); n = len(y)-m; S = np.vstack([s1, s2])
    tx = np.array([_midrank(S[r, :m]) for r in range(2)])
    ty = np.array([_midrank(S[r, m:]) for r in range(2)])
    tz = np.array([_midrank(S[r]) for r in range(2)])
    auc = tz[:, :m].sum(1)/m/n-(m+1)/2/n
    v01 = (tz[:, :m]-tx)/n; v10 = 1-(tz[:, m:]-ty)/m
    cov = np.cov(v01)/m+np.cov(v10)/n
    L = np.array([1, -1]); se = np.sqrt(L @ cov @ L); d = auc[0]-auc[1]
    z = d/se; p = 2*norm.sf(abs(z))
    return d, d-1.96*se, d+1.96*se, p

def idi_nri(y, p_new, p_ref):
    ev, ne = y == 1, y == 0
    idi = (p_new[ev].mean()-p_new[ne].mean())-(p_ref[ev].mean()-p_ref[ne].mean())
    nrie = np.mean((p_new-p_ref)[ev] > 0)-np.mean((p_new-p_ref)[ev] < 0)
    nrin = np.mean((p_ref-p_new)[ne] > 0)-np.mean((p_ref-p_new)[ne] < 0)
    return idi, nrie+nrin

def fill6(df):
    for c in SIX:
        df[c] = df[c].fillna(df[c].median() if not df[c].isna().all() else
                             {"lactate_last":2,"sbp_last":120,"hr_last":90,
                              "temp_last":37,"wbc_last":10,"ph_last":7.4}[c])
    return df

# ================= MIMIC =================
mm = pd.read_csv(find("mimic_77_matrix.csv"))
mm.insert(0, "stay_id", pd.read_csv(find("vs_ml_wide.csv"), usecols=["stay_id"]).stay_id)
mm = mm.merge(pd.read_csv(find("ph_mimic.csv")), on="stay_id", how="left")
mm = fill6(mm); y = mm.vasoplegia.to_numpy()
tr, te = train_test_split(np.arange(len(mm)), test_size=.3, random_state=42, stratify=y)

b = joblib.load(find("vasoplegia_retrained.joblib"))
p_ml = b["final_calibrated"].predict_proba(
    b["pre"].transform(mm.iloc[te][b["features"]]))[:, 1]
sc_ress = ress_score(mm)
ress_lr = LogisticRegression().fit(sc_ress[tr].reshape(-1, 1), y[tr])
p_ress = ress_lr.predict_proba(sc_ress[te].reshape(-1, 1))[:, 1]
six_clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(
    mm.iloc[tr][SIX], y[tr])
p_six = six_clf.predict_proba(mm.iloc[te][SIX])[:, 1]

def block(cohort, y, p_ml, p_ref, ref_score, name):
    rows = []
    for model, pv, sc in [("ML (77 predictors)", p_ml, p_ml),
                          (name, p_ref, ref_score)]:
        rows.append({"Cohort": cohort, "Model": model,
                     "AUROC": round(roc_auc_score(y, sc), 3),
                     "AUPRC": round(average_precision_score(y, sc), 3)})
    d, lo, hi, p = delong(y.astype(float), p_ml, ref_score)
    idi, nri = idi_nri(y, p_ml, p_ref)
    rows.append({"Cohort": cohort, "Model": "ML vs " + name, "AUROC": "",
                 "AUPRC": "", "dAUC": round(d, 3), "95% CI": f"{lo:.3f} to {hi:.3f}",
                 "p": round(p, 4), "IDI": round(idi, 4), "NRI": round(nri, 3)})
    return rows

all_rows = []
all_rows += block("MIMIC test (n=5239)", y[te], p_ml, p_ress, sc_ress[te], "RESS (published)")
all_rows += block("MIMIC test (n=5239)", y[te], p_ml, p_six, p_six, "Six-variable logistic")

# ================= eICU（锁定外推） =================
ew = pd.read_csv(find_any(["eICU.csv", "eicu_wide.csv", "eICU"])).merge(
    pd.read_csv(find("ph_eicu.csv")), on="patientunitstayid", how="left")
ew = fill6(ew).merge(pd.read_csv(find("eicu_pred.csv")), on="patientunitstayid")
sc = ress_score(ew)
p_ress_e = ress_lr.predict_proba(sc.reshape(-1, 1))[:, 1]
p_six_e = six_clf.predict_proba(ew[SIX])[:, 1]
ye = ew.label.to_numpy()
all_rows += block("eICU (n=2268)", ye, ew.prob.to_numpy(), p_ress_e, sc, "RESS (published)")
all_rows += block("eICU (n=2268)", ye, ew.prob.to_numpy(), p_six_e, p_six_e, "Six-variable logistic")

out = HERE/"head_to_head_RESS.xlsx"
pd.DataFrame(all_rows).to_excel(out, index=False)
print(pd.DataFrame(all_rows).to_string(index=False))
print("\n已保存:", out)
