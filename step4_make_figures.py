# -*- coding: utf-8 -*-
"""
最终步骤：四张投稿矢量图（Fig1 流程 / Fig2 性能四格 / Fig3 SHAP / Fig4 风险梯度）
全部基于真实数据与重训模型；每张图同时输出 PDF（矢量投稿）+ TIFF 600dpi + PNG 300dpi
运行：python step4_make_figures.py
依赖：pip install pandas numpy matplotlib scikit-learn xgboost shap joblib pillow openpyxl
"""
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import joblib

warnings.filterwarnings("ignore")

# ===================== 路径配置 =====================
HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "figures"
SEED = 42
RECAL_A, RECAL_B = 0.389, 0.814
# ====================================================

def find(patterns):
    for pat in patterns:
        h = [p for p in HERE.rglob(pat) if p.is_file()]
        if h:
            return sorted(h)[0]
    return None

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from sklearn.model_selection import train_test_split
from sklearn.metrics import (roc_curve, precision_recall_curve, roc_auc_score,
                             average_precision_score, brier_score_loss,
                             confusion_matrix)
rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7,
    "axes.linewidth": 0.7, "xtick.major.width": 0.7, "ytick.major.width": 0.7,
    "xtick.major.size": 3, "ytick.major.size": 3,
    "axes.spines.top": False, "axes.spines.right": False,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.02, "figure.dpi": 150})
C = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73",
     "red": "#D55E00", "purple": "#CC79A7", "grey": "#666666",
     "lgrey": "#BBBBBB"}

def save(fig, name):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for ext, dpi, kw in [("pdf", None, {}),
                         ("tiff", 600, {"pil_kwargs": {"compression": "tiff_lzw"}}),
                         ("png", 300, {})]:
        fig.savefig(OUT_DIR / f"{name}.{ext}", dpi=dpi, **kw)
    plt.close(fig)
    print("  ->", name, "PDF/TIFF/PNG 已保存")

# ================= 加载重训模型 =================
bundle = joblib.load(find(["vasoplegia_retrained.joblib"]))
features, bin15, num62 = bundle["features"], bundle["bin_cols"], bundle["num_cols"]
pre, calibrated = bundle["pre"], bundle["final_calibrated"]

# ================= MIMIC：重建工程矩阵（含 stay_id） =================
wide = pd.read_csv(find(["vs_ml_wide.csv", "vs_ml_wide"]))
d = wide.copy()
d["sbp_last"] = d["abps_last"].fillna(d["nbps_last"])
d["sbp_min"] = d["abps_min"].fillna(d["nbps_min"])
d["sbp_mean"] = d["abps_mean"].fillna(d["nbps_mean"])
d["dbp_last"] = d["abpd_last"].fillna(d["nbpd_last"])
d["temp_last"] = d["temp_c_last"].fillna(d["temp_fromf_last"])
r = d["race"].astype(str).str.lower()
h = r.str.contains("hispanic|latino", regex=True)
w_ = r.str.contains("white") & ~h
d["race_grp_hispanic"] = h.astype(int)
d["race_grp_white"] = w_.astype(int)
d["race_grp_other"] = (~h & ~w_).astype(int)
nm = d["first_careunit"].astype(str).str.lower()
is_med = nm.str.contains("medical") | nm.str.contains("micu")
is_sur = nm.str.contains("surgical") | nm.str.contains("sicu")
d["cu_grp_micu"] = is_med.astype(int)
d["cu_grp_sicu"] = ((~is_med) & is_sur).astype(int)
d["cu_grp_other"] = ((~is_med) & (~is_sur)).astype(int)

y_all = d["vasoplegia"].astype(int).values
tr, te = train_test_split(range(len(d)), test_size=0.3, stratify=y_all,
                          random_state=SEED)
Xte = d[features].iloc[te]
yte = y_all[te]
p_mimic = calibrated.predict_proba(pre.transform(Xte))[:, 1]

# 锚点 join（Fig4）
anchor = pd.read_csv(find(["vs_anchor.csv"]))
anc = d[["stay_id"]].iloc[te].merge(anchor, on="stay_id", how="left")

# ================= eICU 预测 =================
ep = pd.read_csv(find(["eicu_pred.csv"]))
ye, pe, pe_r = ep.label.values, ep.prob.values, ep.prob_recal.values

# ================= Fig1 流程 =================
def fig1():
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 4.4))
    for ax, t in zip(axes, ["MIMIC-IV (development / internal validation)",
                            "eICU-CRD (external validation)"]):
        ax.set_xlim(0, 100); ax.set_ylim(0, 104); ax.axis("off")
        ax.set_title(t, fontsize=7.6, fontweight="bold", pad=4)
    def box(ax, x, y, w, h, t, fc="white", fs=6.4):
        ax.add_patch(FancyBboxPatch((x-w/2, y-h/2), w, h,
            boxstyle="round,pad=0.4,rounding_size=1.0",
            lw=0.7, facecolor=fc, edgecolor=C["grey"]))
        ax.text(x, y, t, ha="center", va="center", fontsize=fs, linespacing=1.4)
    def arr(ax, x1, y1, x2, y2):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
            mutation_scale=6.5, lw=0.7, color=C["grey"], shrinkA=.5, shrinkB=.5))
    ax = axes[0]
    box(ax,32,95,58,11,"ICU admissions with infection\nand vasopressor initiation\nn = 17,526","#F2F2F2")
    arr(ax,32,89.5,32,80); box(ax,82,84.5,34,11.5,"Prevalent cases\nexcluded\nn = 63",fs=6)
    arr(ax,32,84.5,64.4,84.5); box(ax,32,74.5,58,11,"Incident cohort analysed\nn = 17,463","#F2F2F2")
    arr(ax,32,69,17.5,53); arr(ax,32,69,48,53)
    box(ax,17.5,46,31,14,"Persistent refractory\nvasoplegia\nn = 463 (2.65%)","#DCE9F5",5.9)
    box(ax,48,46,26,14,"No event\nn = 17,000",fs=6)
    ax.text(32,30,"70/30 stratified split:\n12,224 train / 5,239 test",ha="center",
            va="center",fontsize=6,style="italic",color=C["grey"])
    ax = axes[1]
    box(ax,32,95,58,10,"Eligible septic patients\nn = 4,481","#F2F2F2")
    arr(ax,32,89.6,32,75.5); box(ax,82,84.5,34,13.5,"ml/hr only n=2,105\nno usable record n=61",fs=5.8)
    arr(ax,32,84.5,64.4,84.5); box(ax,32,70.5,58,10,"Doses convertible\nn = 2,315","#F2F2F2")
    arr(ax,32,66.1,32,47.5); box(ax,82,58,34,11.5,"Prevalent, excluded\nn = 47",fs=6)
    arr(ax,32,58,64.4,58); box(ax,32,42.5,58,10,"Analysed\nn = 2,268","#F2F2F2")
    arr(ax,32,37.6,17.5,24); arr(ax,32,37.6,48,24)
    box(ax,17.5,17,31,14,"Event\nn = 165\n(7.28%)","#DCE9F5",6)
    box(ax,48,17,26,14,"No event\nn = 2,103",fs=6)
    fig.subplots_adjust(wspace=0.08); save(fig, "Figure1_flow")

# ================= Fig2 性能四格 =================
def calib_pts(y, p, n=10):
    q = np.quantile(p, np.linspace(0, 1, n+1)); q[0], q[-1] = -np.inf, np.inf
    po, oo = [], []
    for i in range(n):
        m = (p > q[i]) & (p <= q[i+1])
        if m.sum() >= 5: po.append(p[m].mean()); oo.append(y[m].mean())
    return np.array(po), np.array(oo)

def dca(y, p, th):
    n = len(y); bm, ba = [], []
    for t in th:
        prd = p >= t
        tp = np.sum(prd & (y == 1)); fp = np.sum(prd & (y == 0))
        bm.append(tp/n - fp/n*t/(1-t)); ba.append(y.mean()-(1-y.mean())*t/(1-t))
    return np.array(bm), np.array(ba)

def fig2():
    fig, ax = plt.subplots(2, 2, figsize=(7.1, 5.6))
    a = ax[0,0]
    fpr,tpr,_=roc_curve(yte,p_mimic); a.plot(fpr,tpr,color=C["blue"],lw=1.2,
        label=f"MIMIC-IV test (AUROC {roc_auc_score(yte,p_mimic):.3f})")
    fpr,tpr,_=roc_curve(ye,pe); a.plot(fpr,tpr,color=C["orange"],lw=1.2,ls="--",
        label=f"eICU-CRD (AUROC {roc_auc_score(ye,pe):.3f})")
    a.plot([0,1],[0,1],color=C["lgrey"],lw=.6,ls=":")
    a.set_xlabel("1 - Specificity"); a.set_ylabel("Sensitivity")
    a.set_title("A   Discrimination (ROC)",loc="left",fontweight="bold")
    a.legend(loc="lower right",frameon=False); a.set_xlim(-.01,1.01); a.set_ylim(-.01,1.01)
    a = ax[0,1]
    pr,rc,_=precision_recall_curve(yte,p_mimic); a.plot(rc,pr,color=C["blue"],lw=1.2,
        label=f"MIMIC-IV (AUPRC {average_precision_score(yte,p_mimic):.3f})")
    pr,rc,_=precision_recall_curve(ye,pe); a.plot(rc,pr,color=C["orange"],lw=1.2,ls="--",
        label=f"eICU (AUPRC {average_precision_score(ye,pe):.3f})")
    a.axhline(yte.mean(),color=C["lgrey"],lw=.6,ls=":")
    a.set_xlabel("Recall (Sensitivity)"); a.set_ylabel("Precision (PPV)")
    a.set_title("B   Precision-recall",loc="left",fontweight="bold")
    a.legend(loc="upper right",frameon=False); a.set_xlim(0,1.01); a.set_ylim(0,1.02)
    a = ax[1,0]
    po,oo=calib_pts(yte,p_mimic); a.plot(po,oo,"o-",color=C["blue"],ms=3.4,lw=1,label="MIMIC-IV test")
    po,oo=calib_pts(ye,pe); a.plot(po,oo,"s--",color=C["orange"],ms=3.2,lw=1,label="eICU raw")
    po,oo=calib_pts(ye,pe_r); a.plot(po,oo,"^-",color=C["green"],ms=3.2,lw=1,label="eICU recalibrated")
    lim=min(1,max(p_mimic.max(),pe.max())*1.12); a.plot([0,lim],[0,lim],color=C["lgrey"],lw=.6,ls=":")
    a.set_xlim(0,lim); a.set_ylim(0,lim)
    a.set_xlabel("Predicted probability"); a.set_ylabel("Observed proportion")
    a.set_title("C   Calibration",loc="left",fontweight="bold"); a.legend(loc="upper left",frameon=False,fontsize=6)
    a = ax[1,1]
    th=np.linspace(.01,.30,120); bm,ba=dca(yte,p_mimic,th)
    a.plot(th,bm,color=C["blue"],lw=1.2,label="Model (MIMIC-IV)")
    a.plot(th,ba,color=C["grey"],lw=.8,ls="--",label="Treat all")
    a.axhline(0,color=C["lgrey"],lw=.6,ls=":")
    a.set_xlabel("Threshold probability"); a.set_ylabel("Net benefit")
    a.set_title("D   Decision-curve analysis",loc="left",fontweight="bold")
    a.legend(loc="upper right",frameon=False)
    fig.tight_layout(pad=.6); save(fig, "Figure2_performance")

# ================= Fig3 SHAP =================
def get_tree():
    cc = getattr(calibrated, "calibrated_classifiers_", None)
    if cc:
        for at in ("estimator", "base_estimator", "estimator_"):
            e = getattr(cc[0], at, None)
            if e is not None and hasattr(e, "get_booster"):
                return e
    return None

def fig3():
    import shap
    tree = get_tree()
    if tree is None:   # 兜底：在训练变换矩阵上单独拟合一棵
        from xgboost import XGBClassifier
        Ztr = pre.transform(d[features].iloc[tr])
        tree = XGBClassifier(n_estimators=200, max_depth=4, learning_rate=.05,
                             subsample=.8, colsample_bytree=.8, eval_metric="logloss",
                             random_state=SEED, verbosity=0).fit(Ztr, y_all[tr])
    Zte = pre.transform(Xte)
    names = num62 + bin15                       # ColumnTransformer 输出顺序
    Zdf = pd.DataFrame(Zte, columns=names)
    n = min(2000, len(Zdf)); bg = Zdf.sample(n=n, random_state=SEED)
    expl = shap.TreeExplainer(tree)
    sv = expl(bg)
    fig = plt.figure(figsize=(6.3, 4.4))
    shap.plots.beeswarm(sv, max_display=15, show=False, plot_size=(6.3, 4.4))
    plt.title("Predictor contributions (SHAP)", fontsize=8.5, fontweight="bold", loc="left")
    plt.xlabel("SHAP value (impact on predicted risk)", fontsize=8)
    save(fig, "Figure3_shap")

# ================= Fig4 风险梯度（真实锚点） =================
def fig4():
    strata = [("Low\n(<0.038)", p_mimic < .038),
              ("Intermediate\n(0.038-0.2)", (p_mimic >= .038) & (p_mimic < .2)),
              ("High\n(>=0.2)", p_mimic >= .2)]
    icu, hos, rrt = [], [], []
    for _, msk in strata:
        a = anc[msk]
        icu.append(100*a.icu_death.mean()); hos.append(100*a.hosp_death.mean())
        rrt.append(100*a.rrt_any.mean())
    x = np.arange(3); w = .26
    fig, ax = plt.subplots(figsize=(3.6, 2.9))
    ax.bar(x-w, icu, w, label="ICU mortality", color=C["blue"], lw=0)
    ax.bar(x, hos, w, label="Hospital mortality", color=C["orange"], lw=0)
    ax.bar(x+w, rrt, w, label="Renal replacement", color=C["green"], lw=0)
    for xi, vals in zip(x, zip(icu, hos, rrt)):
        for off, v in zip([-w, 0, w], vals):
            ax.text(xi+off, v+1.2, f"{v:.0f}", ha="center", fontsize=5.8)
    ax.set_xticks(x); ax.set_xticklabels([s[0] for s in strata], fontsize=6.8)
    ax.set_ylabel("Patients, %"); ax.set_ylim(0, max(icu+hos)*1.25)
    ax.legend(frameon=False, fontsize=6.3, loc="upper left")
    ax.set_title("Outcome gradient across predicted risk (MIMIC test)",
                 loc="left", fontsize=8, fontweight="bold")
    fig.tight_layout(pad=.4); save(fig, "Figure4_risk_gradient")

print("开始生成四张矢量图 ...")
fig1(); fig2(); fig3(); fig4()
print("\n全部完成，输出目录:", OUT_DIR)
