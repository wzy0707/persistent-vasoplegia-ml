# -*- coding: utf-8 -*-
"""
step7 Table4 外部锚点：十分位 + 三层风险的 ICU/住院死亡、RRT（真实锚点）
运行：python step7_anchor_table.py
"""
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
SEED = 42

# 数据：宽表 stay_id 顺序 + 矩阵 + 模型
wide = pd.read_csv(HERE / "vs_ml_wide.csv")
m = pd.read_csv(HERE / "mimic_77_matrix.csv")
b = joblib.load(HERE / "vasoplegia_retrained.joblib")
anchor_path = list(HERE.rglob("vs_anchor.csv"))
if not anchor_path:
    raise FileNotFoundError(
        "vs_anchor.csv not found. Generate it with sql/mimic/05 and "
        "sql/supplementary/export_anchor.sql, then place the export in the project root.")
anchor = pd.read_csv(anchor_path[0])
y = m.vasoplegia.values
tr, te = train_test_split(range(len(m)), test_size=.3, stratify=y, random_state=SEED)
p = b["final_calibrated"].predict_proba(
    b["pre"].transform(m[b["features"]].iloc[te]))[:, 1]

d = pd.DataFrame({"stay_id": wide.stay_id.values[te], "y": y[te], "p": p})
d = d.merge(anchor, on="stay_id", how="left")

# 十分位（按预测概率排名强制 10 个等大组，rank 处理并列值）
d["decile"] = pd.qcut(d.p.rank(method="first"), 10, labels=False) + 1
dec = d.groupby("decile").agg(
    n=("p", "size"), events=("y", "sum"),
    icu_mortality=("icu_death", lambda x: 100*np.mean(x)),
    hosp_mortality=("hosp_death", lambda x: 100*np.mean(x)),
    rrt=("rrt_any", lambda x: 100*np.mean(x))).reset_index()

# 三层风险
d["stratum"] = pd.cut(d.p, bins=[-1, .038, .2, 99],
                      labels=["Low (<0.038)", "Intermediate (0.038-0.2)", "High (>=0.2)"])
strat = d.groupby("stratum", observed=True).agg(
    n=("p", "size"), events=("y", "sum"),
    icu_mortality=("icu_death", lambda x: 100*np.mean(x)),
    hosp_mortality=("hosp_death", lambda x: 100*np.mean(x)),
    rrt=("rrt_any", lambda x: 100*np.mean(x))).reset_index()

# 事件落在上四分位
upper4 = sorted(dec.decile.unique())[-4:]
ev_upper = int(d[(d.y == 1) & (d.decile.isin(upper4))].shape[0])
total_ev = int(d.y.sum())

out = HERE / "Table4_anchor.xlsx"
with pd.ExcelWriter(out, engine="openpyxl") as w:
    dec.round(1).to_excel(w, "Deciles", index=False)
    strat.round(1).to_excel(w, "Three_strata", index=False)
    pd.DataFrame([{"test_events": total_ev, "events_in_upper4_deciles": ev_upper,
                   "pct": round(100*ev_upper/total_ev, 1)}]
                 ).to_excel(w, "Event_placement", index=False)

print("===== 十分位（最低/最高） =====")
print(dec.round(1).iloc[[0, -1]].to_string(index=False))
print("\n===== 三层风险 =====")
print(strat.round(1).to_string(index=False))
print("\n事件落在上四分位: %d/%d (%.1f%%)" % (ev_upper, total_ev, 100*ev_upper/total_ev))
print("\n已保存:", out.name)
