# -*- coding: utf-8 -*-
"""
MIMIC 第二步：按蓝图规格从头重训（不依赖原始 pkl）
  70/30 分层划分 seed42 → XGBoost（正则化）→ 5 折等渗校准（isotonic, StratifiedKFold seed42）
  输出测试集 AUROC/AUPRC/Brier/校准斜率/阈值混淆矩阵，并保存重训模型供外验与出图
运行：python step2_retrain_model.py
依赖：pip install pandas numpy scikit-learn xgboost statsmodels joblib
"""
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, FunctionTransformer
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (roc_auc_score, average_precision_score,
                             brier_score_loss, confusion_matrix)
from xgboost import XGBClassifier
import statsmodels.api as sm

warnings.filterwarnings("ignore")

# ===================== 路径配置 =====================
HERE = Path(__file__).resolve().parent
INPUT_MATRIX = HERE / "mimic_77_matrix.csv"
OUT_MODEL = HERE / "vasoplegia_retrained.joblib"
OUT_METRICS = HERE / "MIMIC_retrained_metrics.xlsx"
CUT = 0.037909218668937684          # 蓝图原始操作阈值
SEED = 42
# ====================================================

mat = pd.read_csv(INPUT_MATRIX)
features = [c for c in mat.columns if c != "vasoplegia"]
y = mat["vasoplegia"].astype(int).values
assert len(features) == 77

# 15 二值（推断：9 个静态二值 + 6 个 race/cu 哑变量），其余 62 为数值
BIN15 = ["male", "diabetes", "hypertension", "chf", "chronic_pulmonary",
         "chronic_liver", "ckd", "metastatic_cancer", "arrhythmia",
         "race_grp_hispanic", "race_grp_white", "race_grp_other",
         "cu_grp_micu", "cu_grp_sicu", "cu_grp_other"]
NUM62 = [c for c in features if c not in BIN15]
assert len(BIN15) == 15 and len(NUM62) == 62

# ---------- 70/30 分层划分（金标准：12224/5239，测试事件139） ----------
Xtr, Xte, ytr, yte = train_test_split(
    mat[features], y, test_size=0.3, stratify=y, random_state=SEED)
print("train=%d(事件%d)  test=%d(事件%d)" % (len(Xtr), ytr.sum(), len(Xte), yte.sum()))

# ---------- 预处理器：62 数值 median+standardize；15 二值原样透传 ----------
pre = ColumnTransformer([
    ("num", Pipeline([("imp", SimpleImputer(strategy="median")),
                      ("sc", StandardScaler())]), NUM62),
    ("bin", FunctionTransformer(), BIN15)])

# ---------- 基础 XGBoost（正则化，固定非测试集调参） ----------
xgb = XGBClassifier(
    n_estimators=200, max_depth=4, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
    objective="binary:logistic", eval_metric="logloss",
    random_state=SEED, verbosity=0, n_jobs=-1)

# ---------- 5 折等渗校准（在训练集内部完成，测试集完全不参与） ----------
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
calibrated = CalibratedClassifierCV(xgb, method="isotonic", cv=cv)

pre.fit(Xtr)
Ztr = pre.transform(Xtr)
calibrated.fit(Ztr, ytr)

# ---------- 测试集推理（pre.transform → calibrated.predict_proba） ----------
p = calibrated.predict_proba(pre.transform(Xte))[:, 1]

def cal_intercept_slope(y, p):
    lp = np.log(np.clip(p, 1e-6, 1 - 1e-6) /
                (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    f = sm.Logit(y, sm.add_constant(lp)).fit(disp=0)
    return f.params[0], f.params[1]

ci, cslope = cal_intercept_slope(yte, p)
auroc = roc_auc_score(yte, p)
auprc = average_precision_score(yte, p)
brier = brier_score_loss(yte, p)

# 阈值混淆矩阵（cut=0.0379）
pred = (p >= CUT).astype(int)
cm = confusion_matrix(yte, pred)
tn, fp, fn, tp = cm.ravel()
sens = tp / (tp + fn)
spec = tn / (tn + fp)

# ---------- 与金标准对照 ----------
cmp = pd.DataFrame({
    "指标": ["AUROC", "AUPRC", "Brier", "校准截距", "校准斜率",
            "敏感度@0.038", "特异度@0.038", "TN", "FP", "FN", "TP"],
    "本次重训": ["%.3f" % auroc, "%.3f" % auprc, "%.3f" % brier,
              "%.2f" % ci, "%.2f" % cslope, "%.3f" % sens, "%.3f" % spec,
              tn, fp, fn, tp],
    "蓝图金标准": [0.950, 0.378, 0.020, "-", 1.03,
              0.906, 0.879, 4485, 615, 13, 126]})
print("\n===== 测试集指标 vs 金标准 =====")
print(cmp.to_string(index=False))

# ---------- 保存重训模型（结构对齐蓝图：pre + final_calibrated） ----------
bundle = {"pre": pre, "final_calibrated": calibrated, "xgb": xgb,
          "features": features, "bin_cols": BIN15, "num_cols": NUM62,
          "cut": CUT}
joblib.dump(bundle, OUT_MODEL)
with pd.ExcelWriter(OUT_METRICS, engine="openpyxl") as w:
    cmp.to_excel(w, sheet_name="测试集指标", index=False)
print("\n已保存模型:", OUT_MODEL.name)
print("已保存指标:", OUT_METRICS.name)
print("完成。")
