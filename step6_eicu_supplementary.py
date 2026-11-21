# -*- coding: utf-8 -*-
"""
step6 eICU 补充指标：PPV/NPV、ECE、各阈值混淆矩阵（原始与重校准）
运行：python step6_eicu_supplementary.py
"""
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent

d = pd.read_csv(HERE / "eicu_pred.csv")
y = d.label.values

def ece(y, p, M=10):
    e = 0.0
    for i in range(M):
        m = (p >= i/M) & (p < (i+1)/M)
        if m.sum():
            e += m.sum()/len(y) * abs(y[m].mean() - p[m].mean())
    return e

def cm_row(p, t):
    prd = (p >= t).astype(int)
    tp = int(((prd == 1) & (y == 1)).sum()); fp = int(((prd == 1) & (y == 0)).sum())
    tn = int(((prd == 0) & (y == 0)).sum()); fn = int(((prd == 0) & (y == 1)).sum())
    return {"threshold": t, "TP": tp, "FP": fp, "TN": tn, "FN": fn,
            "sensitivity": round(tp/(tp+fn), 3), "specificity": round(tn/(tn+fp), 3),
            "PPV": round(tp/(tp+fp), 3), "NPV": round(tn/(tn+fn), 3)}

rows, ece_rows = [], []
for stage, col in [("raw", "prob"), ("recalibrated", "prob_recal")]:
    p = d[col].values
    ece_rows.append({"stage": stage, "ECE": round(ece(y, p), 3)})
    for t in [.038, .097]:
        r = cm_row(p, t); r["stage"] = stage; rows.append(r)
detail = pd.DataFrame(rows)[["stage", "threshold", "TP", "FP", "TN", "FN",
                             "sensitivity", "specificity", "PPV", "NPV"]]
ece_df = pd.DataFrame(ece_rows)

out = HERE / "eicu_supplementary_metrics.xlsx"
with pd.ExcelWriter(out, engine="openpyxl") as w:
    ece_df.to_excel(w, "ECE", index=False)
    detail.to_excel(w, "Threshold_detail", index=False)
print(ece_df.to_string(index=False))
print(detail.to_string(index=False))
print("\n已保存:", out.name)
