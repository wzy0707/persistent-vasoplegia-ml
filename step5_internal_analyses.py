# -*- coding: utf-8 -*-
"""
step5 内部补充分析（补全路线）
  Table2 模型对比（LASSO / RF / XGB / 校准XGB）
  Table3 嵌套 M0/M1/M2（含 2000 次 bootstrap 95% CI、Brier、校准截距斜率）
  低剂量亚组（NEE<0.25）、治疗泄漏敏感性（全队列 in-sample + 按 landmark NEE 分层）
运行：python step5_internal_analyses.py
"""
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import joblib
import statsmodels.api as sm
from sklearn.model_selection import (train_test_split, StratifiedKFold,
                                     GridSearchCV)
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from xgboost import XGBClassifier
from sklearn.metrics import (roc_auc_score, average_precision_score,
                             brier_score_loss)

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
SEED = 42
N_BOOT = 2000
TREAT = {"nee_first", "nee_last", "nee_min", "nee_max", "nee_mean",
         "nee_high_frac", "n_drug", "ne_used", "pe_used", "vaso_used",
         "epi_used", "dopa_used", "ang2_used", "ne_maxrate", "pe_maxrate",
         "vaso_maxrate", "epi_maxrate", "dopa_maxrate", "n_bolus", "fluid_ml"}

# ---------- 数据与划分 ----------
m = pd.read_csv(HERE / "mimic_77_matrix.csv")
b = joblib.load(HERE / "vasoplegia_retrained.joblib")
allf, bin_cols = b["features"], b["bin_cols"]
y = m["vasoplegia"].astype(int).values
tr, te = train_test_split(range(len(m)), test_size=.3, stratify=y,
                          random_state=SEED)
SUBS = {"M0": allf,
        "M1": [c for c in allf if c != "nee_last"],
        "M2": [c for c in allf if c not in TREAT]}

def make_pre(cols):
    num = [c for c in cols if c not in bin_cols]
    bn = [c for c in cols if c in bin_cols]
    return ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")),
                          ("sc", StandardScaler())]), num),
        ("bin", SimpleImputer(strategy="most_frequent"), bn)])

def xgb_base():
    return XGBClassifier(n_estimators=200, max_depth=4, learning_rate=.05,
                         subsample=.8, colsample_bytree=.8, reg_lambda=1,
                         objective="binary:logistic", eval_metric="logloss",
                         random_state=SEED, verbosity=0)

def cal_slope(y, p):
    lp = np.log(np.clip(p, 1e-6, 1-1e-6) / (1-np.clip(p, 1e-6, 1-1e-6)))
    f = sm.Logit(y, sm.add_constant(lp)).fit(disp=0)
    return f.params[0], f.params[1]

def boot_ci(y, p, n=N_BOOT):
    rng = np.random.default_rng(SEED)
    au, ap = [], []
    for _ in range(n):
        ix = rng.integers(0, len(y), len(y))
        if len(np.unique(y[ix])) < 2:
            continue
        au.append(roc_auc_score(y[ix], p[ix]))
        ap.append(average_precision_score(y[ix], p[ix]))
    return (np.percentile(au, [2.5, 97.5]), np.percentile(ap, [2.5, 97.5]))

# ---------- Table2 模型对比 ----------
print("计算 Table2 模型对比 ...")
pre0 = make_pre(allf); Ztr = pre0.fit_transform(m[allf].iloc[tr]); Zte = pre0.transform(m[allf].iloc[te])
comp = []
gs = GridSearchCV(LogisticRegression(penalty="l1", solver="liblinear",
                                     max_iter=2000, random_state=SEED),
                  {"C": [.01, .03, .1, .3, 1, 3]},
                  cv=StratifiedKFold(5, shuffle=True, random_state=SEED),
                  scoring="roc_auc", n_jobs=-1).fit(Ztr, y[tr])
lasso = gs.best_estimator_
n_keep = int(np.sum(np.any(lasso.coef_ != 0, axis=0)))
pl = lasso.predict_proba(Zte)[:, 1]
comp.append(["LASSO logistic", n_keep, roc_auc_score(y[te], pl), np.nan])
rf = RandomForestClassifier(n_estimators=400, max_depth=None, min_samples_leaf=2,
                             n_jobs=-1, random_state=SEED).fit(Ztr, y[tr])
pr_ = rf.predict_proba(Zte)[:, 1]
comp.append(["Random forest", len(allf), roc_auc_score(y[te], pr_), np.nan])
xu = xgb_base().fit(Ztr, y[tr])
px = xu.predict_proba(Zte)[:, 1]
comp.append(["Extreme gradient boosting", len(allf), roc_auc_score(y[te], px),
             average_precision_score(y[te], px)])
pf = b["final_calibrated"].predict_proba(b["pre"].transform(m[allf].iloc[te]))[:, 1]
comp.append(["Calibrated XGBoost (final)", len(allf), roc_auc_score(y[te], pf),
             average_precision_score(y[te], pf)])
table2 = pd.DataFrame(comp, columns=["Model", "Predictors", "AUROC", "AUPRC"])

# ---------- Table3 嵌套模型 ----------
print("计算 Table3 嵌套模型 + bootstrap CI（耗时较长）...")
rows3 = []
pred_store = {}
for name, cols in SUBS.items():
    pre = make_pre(cols)
    cal = CalibratedClassifierCV(xgb_base(), method="isotonic",
                                 cv=StratifiedKFold(5, shuffle=True, random_state=SEED))
    cal.fit(pre.fit_transform(m[cols].iloc[tr]), y[tr])
    p = cal.predict_proba(pre.transform(m[cols].iloc[te]))[:, 1]
    pred_store[name] = p
    ci_a, ci_p = boot_ci(y[te], p)
    ci, cs = cal_slope(y[te], p)
    rows3.append([name, len(cols), roc_auc_score(y[te], p), ci_a,
                  average_precision_score(y[te], p), ci_p,
                  brier_score_loss(y[te], p), ci, cs])
table3 = pd.DataFrame(rows3, columns=["Model", "n_pred", "AUROC", "AUROC_CI",
                                      "AUPRC", "AUPRC_CI", "Brier",
                                      "Cal_intercept", "Cal_slope"])

# ---------- 低剂量亚组（NEE<0.25） ----------
print("计算低剂量亚组 ...")
land = m["nee_last"].values
low_idx = np.array(te)[land[te] < .25]
sub_rows = []
for name, cols in [("M0", allf), ("M2", SUBS["M2"])]:
    pre = make_pre(cols)
    cal = CalibratedClassifierCV(xgb_base(), method="isotonic",
                                 cv=StratifiedKFold(5, shuffle=True, random_state=SEED))
    cal.fit(pre.fit_transform(m[cols].iloc[tr]), y[tr])
    p = cal.predict_proba(pre.transform(m[cols].iloc[low_idx]))[:, 1]
    sub_rows.append([name, len(low_idx), y[low_idx].sum(),
                     roc_auc_score(y[low_idx], p),
                     average_precision_score(y[low_idx], p)])
subgroup = pd.DataFrame(sub_rows, columns=["Model", "n_low_dose", "events",
                                           "AUROC", "AUPRC"])
subgroup["full_cohort_n_below0.25"] = int((land < .25).sum())

# ---------- 治疗泄漏：全队列 in-sample + 分层 ----------
print("计算治疗泄漏敏感性 ...")
preF = make_pre(allf); Zall = preF.fit_transform(m[allf])
calF = CalibratedClassifierCV(xgb_base(), method="isotonic",
                              cv=StratifiedKFold(5, shuffle=True, random_state=SEED)).fit(Zall, y)
pall = calF.predict_proba(Zall)[:, 1]
leak = [["Full cohort (in-sample)", len(m), y.sum(),
         roc_auc_score(y, pall), average_precision_score(y, pall)]]
for nm, msk in [("Landmark NEE<0.5 (low)", land < .5),
                ("Landmark NEE>=0.5 (high)", land >= .5)]:
    leak.append([nm, int(msk.sum()), int(y[msk].sum()),
                 roc_auc_score(y[msk], pall[msk]),
                 average_precision_score(y[msk], pall[msk])])
leakage = pd.DataFrame(leak, columns=["Group", "n", "events", "AUROC", "AUPRC"])

# ---------- 保存 ----------
out = HERE / "internal_supplementary_analyses.xlsx"
with pd.ExcelWriter(out, engine="openpyxl") as w:
    table2.round(3).to_excel(w, "Table2_model_compare", index=False)
    t3 = table3.copy()
    t3["AUROC_CI"] = t3["AUROC_CI"].map(lambda x: f"{x[0]:.3f}-{x[1]:.3f}")
    t3["AUPRC_CI"] = t3["AUPRC_CI"].map(lambda x: f"{x[0]:.3f}-{x[1]:.3f}")
    t3.round(3).to_excel(w, "Table3_nested", index=False)
    subgroup.round(3).to_excel(w, "Low_dose_subgroup", index=False)
    leakage.round(3).to_excel(w, "Leakage_sensitivity", index=False)

print("\n===== Table2 模型对比 ====="); print(table2.round(3).to_string(index=False))
print("\n===== Table3 嵌套模型 =====")
for r in rows3:
    print("%s n=%d AUROC=%.3f (%.3f-%.3f) AUPRC=%.3f Brier=%.3f slope=%.3f" %
          (r[0], r[1], r[2], r[3][0], r[3][1], r[4], r[6], r[8]))
print("\n===== 低剂量亚组 ====="); print(subgroup.round(3).to_string(index=False))
print("\n===== 泄漏敏感性 ====="); print(leakage.round(3).to_string(index=False))
print("\n已保存:", out.name)
