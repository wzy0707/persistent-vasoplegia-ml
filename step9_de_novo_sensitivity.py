# -*- coding: utf-8 -*-
"""
Step9 CRITICAL#3 敏感性：de-novo-only 性能
  (1) 同一重训模型，测试集剔除 cross 后重算 AUROC/AUPRC
  (2) 训练/测试均剔除 cross 后完全重训
依赖：3B.csv（stay_id, onset_type）、vs_ml_wide.csv、mimic_77_matrix.csv（递归查找）
"""
from pathlib import Path
import numpy as np, pandas as pd, joblib
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.calibration import CalibratedClassifierCV
from xgboost import XGBClassifier

HERE = Path(__file__).resolve().parent
def find(name):
    h = list(HERE.rglob(name)); return h[0] if h else None
def find_any(names):
    for n in names:
        p = find(n)
        if p is not None: return p
    return None

mm = pd.read_csv(find("mimic_77_matrix.csv"))
mm.insert(0, "stay_id", pd.read_csv(find("vs_ml_wide.csv"),
                                    usecols=["stay_id"]).stay_id)
b3_path = find_any(["3B.csv", "3B", "3B类型.csv", "onset_type.csv", "3B.xlsx"])
if b3_path is None:
    raise FileNotFoundError(
        "找不到 3B 类型文件（含 stay_id, onset_type）。请把 3B.csv 放到本脚本所在文件夹后重跑。")
b3 = pd.read_excel(b3_path) if str(b3_path).endswith(".xlsx") else pd.read_csv(b3_path)
mm = mm.merge(b3[["stay_id", "onset_type"]], on="stay_id")
y = mm.vasoplegia.to_numpy(); ot = mm.onset_type.to_numpy()
tr, te = train_test_split(np.arange(len(mm)), test_size=.3,
                          random_state=42, stratify=y)
b = joblib.load(find("vasoplegia_retrained.joblib"))
p = b["final_calibrated"].predict_proba(
    b["pre"].transform(mm.iloc[te][b["features"]]))[:, 1]

keep = te[ot[te] != "cross"]
pk = p[ot[te] != "cross"]
rows = [
    {"Analysis": "Full test set", "n": len(te), "events": int(y[te].sum()),
     "AUROC": round(roc_auc_score(y[te], p), 3),
     "AUPRC": round(average_precision_score(y[te], p), 3)},
    {"Analysis": "De-novo-only (same model, cross removed)", "n": len(keep),
     "events": int(y[keep].sum()),
     "AUROC": round(roc_auc_score(y[keep], pk), 3),
     "AUPRC": round(average_precision_score(y[keep], pk), 3)},
]
trd = tr[ot[tr] != "cross"]
pre = b["pre"]
Xtr = pre.fit_transform(mm.iloc[trd][b["features"]])
Xte = pre.transform(mm.iloc[keep][b["features"]])
xgb = XGBClassifier(n_estimators=200, max_depth=4, learning_rate=.05,
                    subsample=.8, colsample_bytree=.8, reg_lambda=1,
                    objective="binary:logistic", eval_metric="logloss",
                    random_state=42).fit(Xtr, y[trd])
cal = CalibratedClassifierCV(xgb, method="isotonic",
                             cv=StratifiedKFold(5, shuffle=True, random_state=42)
                             ).fit(Xtr, y[trd])
pn = cal.predict_proba(Xte)[:, 1]
rows.append({"Analysis": "De-novo-only (retrained without cross)",
             "n": len(keep), "events": int(y[keep].sum()),
             "AUROC": round(roc_auc_score(y[keep], pn), 3),
             "AUPRC": round(average_precision_score(y[keep], pn), 3)})

out = HERE/"de_novo_sensitivity.xlsx"
pd.DataFrame(rows).to_excel(out, index=False)
print(pd.DataFrame(rows).to_string(index=False))
print("\n已保存:", out)
