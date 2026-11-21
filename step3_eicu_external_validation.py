# -*- coding: utf-8 -*-
"""
eICU 第三步：外部验证 + 重校准（锁定重训模型，不重新拟合）
  读取 eICU 特征宽表 + e_label（需先用 导出e标签.sql 导出）
  推理链：pre.transform → final_calibrated.predict_proba（原始概率）
  重校准：logit(p_new)=0.389 + 0.814×logit(p_old)，新阈值 0.097
运行：python step3_eicu_external_validation.py
依赖：pip install pandas numpy scikit-learn statsmodels joblib openpyxl
"""
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import joblib
import statsmodels.api as sm
from sklearn.metrics import (roc_auc_score, average_precision_score,
                             brier_score_loss, confusion_matrix)

warnings.filterwarnings("ignore")

# ===================== 路径配置 =====================
HERE = Path(__file__).resolve().parent
MODEL = HERE / "vasoplegia_retrained.joblib"
OUT_PRED = HERE / "eicu_pred.csv"
OUT_XLSX = HERE / "eICU_validation_metrics.xlsx"
RECAL_A, RECAL_B = 0.389, 0.814          # 蓝图固定重校准参数
NEW_CUT = 0.097
SEED = 42
# ====================================================

def find_file(patterns):
    for pat in patterns:
        hits = [p for p in HERE.rglob(pat) if p.is_file()]
        if hits:
            return sorted(hits)[0]
    return None

# 1) 数据文件自动识别（兼容无扩展名）
wide_path = find_file(["eICU.csv", "eicu_wide.csv", "eICU"])
label_path = find_file(["e_label.csv", "e_label"])
if wide_path is None or label_path is None:
    raise FileNotFoundError(
        "找不到 eICU 特征表或 e_label。请确认文件在脚本目录或子目录，"
        "并先用 导出e标签.sql 导出 e_label。")
print("特征表:", wide_path.name, " 标签表:", label_path.name)

wide = pd.read_csv(wide_path)
lab = pd.read_csv(label_path)
if "label_type" in lab.columns:
    lab = lab[lab["label_type"].isin(["incident", "negative"])]

# 2) join 标签，核对队列（期望 2268，事件 165）
d = wide.merge(lab[["patientunitstayid", "label"]],
               on="patientunitstayid", how="inner")
print("外验队列 n=%d，事件 %d（%.2f%%）" % (len(d), d.label.sum(),
                                  100 * d.label.mean()))
assert len(d) == 2268 and int(d.label.sum()) == 165, "外验队列与金标准不符！"

# 3) 加载锁定重训模型，对齐特征顺序
bundle = joblib.load(MODEL)
features = bundle["features"]
y = d["label"].astype(int).values
X = d[features]

# 4) 推理链：pre.transform → calibrated.predict_proba
p = bundle["final_calibrated"].predict_proba(
    bundle["pre"].transform(X))[:, 1]

# 5) 固定重校准（蓝图公式，不重新估计，避免 in-sample 乐观偏倚）
pc = np.clip(p, 1e-6, 1 - 1e-6)
p_recal = 1 / (1 + np.exp(-(RECAL_A + RECAL_B * np.log(pc / (1 - pc)))))

def cal_int_slope(y, p):
    lp = np.log(np.clip(p, 1e-6, 1 - 1e-6) /
                (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    f = sm.Logit(y, sm.add_constant(lp)).fit(disp=0)
    return f.params[0], f.params[1]

def metric_row(name, y, p):
    ci, cs = cal_int_slope(y, p)
    return {"阶段": name, "AUROC": roc_auc_score(y, p),
            "AUPRC": average_precision_score(y, p),
            "Brier": brier_score_loss(y, p),
            "校准截距": ci, "校准斜率": cs}

res = pd.DataFrame([metric_row("原始（锁定模型直接外验）", y, p),
                    metric_row("重校准后", y, p_recal)])
for c in ["AUROC", "AUPRC", "Brier", "校准截距", "校准斜率"]:
    res[c] = res[c].round(3)

# 6) 阈值表现（新阈值 0.097）
def th_row(p, t):
    pred = (p >= t).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
    return {"阈值": t, "TP": tp, "FP": fp, "TN": tn, "FN": fn,
            "敏感度": round(tp / (tp + fn), 3),
            "特异度": round(tn / (tn + fp), 3)}
th = pd.DataFrame([th_row(p_recal, 0.0379), th_row(p_recal, NEW_CUT)])

# 7) 保存预测与指标
out = pd.DataFrame({"patientunitstayid": d["patientunitstayid"],
                    "label": y, "prob": p, "prob_recal": p_recal})
out.to_csv(OUT_PRED, index=False, encoding="utf-8-sig")
with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as w:
    res.to_excel(w, sheet_name="外验指标", index=False)
    th.to_excel(w, sheet_name="阈值表现", index=False)

print("\n===== eICU 外验指标（金标准：AUROC 0.893 / AUPRC 0.411 / 重校准Brier 0.053） =====")
print(res.to_string(index=False))
print("\n", th.to_string(index=False))
print("\n已保存:", OUT_PRED.name, "、", OUT_XLSX.name)
print("完成。")
