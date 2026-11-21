# -*- coding: utf-8 -*-
"""
Step10 MAJOR#8：低剂量亚组（landmark NEE < 0.25）bootstrap 95% CI
  复现 step5 的 M0 / M2 低剂量口径，对 AUROC、AUPRC 各做 2000 次 bootstrap
  仅 33 个事件，CI 较宽，正文据此弱化结论
"""
from pathlib import Path
import warnings
import numpy as np, pandas as pd, joblib
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.calibration import CalibratedClassifierCV
from xgboost import XGBClassifier
from sklearn.metrics import roc_auc_score, average_precision_score

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
SEED, N_BOOT = 42, 2000
def find(name):
    h = list(HERE.rglob(name)); return h[0] if h else None
TREAT = {"nee_first", "nee_last", "nee_min", "nee_max", "nee_mean",
         "nee_high_frac", "n_drug", "ne_used", "pe_used", "vaso_used",
         "epi_used", "dopa_used", "ang2_used", "ne_maxrate", "pe_maxrate",
         "vaso_maxrate", "epi_maxrate", "dopa_maxrate", "n_bolus", "fluid_ml"}

m = pd.read_csv(find("mimic_77_matrix.csv"))
b = joblib.load(find("vasoplegia_retrained.joblib"))
allf, bin_cols = b["features"], b["bin_cols"]
y = m.vasoplegia.astype(int).to_numpy()
tr, te = train_test_split(range(len(m)), test_size=.3, stratify=y, random_state=SEED)
SUBS = {"M0": allf, "M2": [c for c in allf if c not in TREAT]}

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

land = m.nee_last.to_numpy()
low_idx = np.array(te)[land[te] < .25]
rng = np.random.default_rng(SEED)
rows = []
for name, cols in SUBS.items():
    pre = make_pre(cols)
    cal = CalibratedClassifierCV(xgb_base(), method="isotonic",
                                 cv=StratifiedKFold(5, shuffle=True, random_state=SEED))
    cal.fit(pre.fit_transform(m[cols].iloc[tr]), y[tr])
    p = cal.predict_proba(pre.transform(m[cols].iloc[low_idx]))[:, 1]
    yy = y[low_idx]
    au, ap = [], []
    for _ in range(N_BOOT):
        ix = rng.integers(0, len(yy), len(yy))
        if len(np.unique(yy[ix])) < 2: continue
        au.append(roc_auc_score(yy[ix], p[ix]))
        ap.append(average_precision_score(yy[ix], p[ix]))
    ca, cp = np.percentile(au, [2.5, 97.5]), np.percentile(ap, [2.5, 97.5])
    rows.append({"Model": name, "n": len(low_idx), "events": int(yy.sum()),
                 "AUROC": round(roc_auc_score(yy, p), 3),
                 "AUROC 95% CI": f"{ca[0]:.3f} to {ca[1]:.3f}",
                 "AUPRC": round(average_precision_score(yy, p), 3),
                 "AUPRC 95% CI": f"{cp[0]:.3f} to {cp[1]:.3f}"})

out = HERE/"low_dose_bootstrap.xlsx"
pd.DataFrame(rows).to_excel(out, index=False)
print("低剂量亚组（landmark NEE < 0.25），全队列 NEE<0.25 共 %d 人" % int((land < .25).sum()))
print(pd.DataFrame(rows).to_string(index=False))
print("\n已保存:", out)
