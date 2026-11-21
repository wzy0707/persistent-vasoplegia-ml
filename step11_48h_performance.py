# -*- coding: utf-8 -*-
"""
Step11 MAJOR#12：48h 预测窗下的模型性能
  同一重训模型、同一 77 特征，仅替换为 48h 标签（label_48h.csv），重算 AUROC/AUPRC/Brier
  与 30h 主口径并列，证明窗口选择不改变结论
"""
from pathlib import Path
import numpy as np, pandas as pd, joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss

HERE = Path(__file__).resolve().parent
def find(name):
    h = list(HERE.rglob(name)); return h[0] if h else None

mm = pd.read_csv(find("mimic_77_matrix.csv"))
mm.insert(0, "stay_id", pd.read_csv(find("vs_ml_wide.csv"),
                                    usecols=["stay_id"]).stay_id)
mm = mm.merge(pd.read_csv(find("label_48h.csv"))[["stay_id", "vasoplegia_48"]],
              on="stay_id")
y30 = mm.vasoplegia.to_numpy(); y48 = mm.vasoplegia_48.to_numpy()
tr, te = train_test_split(np.arange(len(mm)), test_size=.3,
                          random_state=42, stratify=y30)
b = joblib.load(find("vasoplegia_retrained.joblib"))
p = b["final_calibrated"].predict_proba(
    b["pre"].transform(mm.iloc[te][b["features"]]))[:, 1]

rows = []
for label_name, yy in [("30h window (primary)", y30), ("48h window (sensitivity)", y48)]:
    rows.append({"Window": label_name, "test events": int(yy[te].sum()),
                 "AUROC": round(roc_auc_score(yy[te], p), 3),
                 "AUPRC": round(average_precision_score(yy[te], p), 3),
                 "Brier": round(brier_score_loss(yy[te], p), 3)})
# 全队列新增事件
extra = int(((y30 == 0) & (y48 == 1)).sum())
out = HERE/"window_48h_performance.xlsx"
pd.DataFrame(rows).to_excel(out, index=False)
print("全队列：延长至 48h 新增事件 %d 例（48h 共 %d 事件）" % (extra, y48.sum()))
print(pd.DataFrame(rows).to_string(index=False))
print("\n已保存:", out)
