# -*- coding: utf-8 -*-
"""
Step12 MINOR#16：增强版 Figure2
  C 校准：rank 强制 10 分位 + Wilson 95%CI + LOWESS 平滑
  D DCA：MIMIC + eICU 双库净收益
  A/B 保持与 step4 一致；输出 PDF/TIFF/PNG 到 enhanced_figures/
"""
from pathlib import Path
import warnings
import numpy as np, pandas as pd, joblib
warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "enhanced_figures"; SEED = 42
def find(patterns):
    for pat in patterns:
        h = [p for p in HERE.rglob(pat) if p.is_file()]
        if h: return sorted(h)[0]
    return None

import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
from sklearn.model_selection import train_test_split
from sklearn.metrics import (roc_curve, precision_recall_curve, roc_auc_score,
                             average_precision_score)
from statsmodels.nonparametric.smoothers_lowess import lowess
rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
                 "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
                 "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 6.5,
                 "axes.linewidth": .7, "xtick.major.width": .7, "ytick.major.width": .7,
                 "xtick.major.size": 3, "ytick.major.size": 3,
                 "axes.spines.top": False, "axes.spines.right": False,
                 "savefig.bbox": "tight", "savefig.pad_inches": .02, "figure.dpi": 150})
C = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73", "grey": "#666666", "lgrey": "#BBBBBB"}

# ---------- 数据（同 step4） ----------
bundle = joblib.load(find(["vasoplegia_retrained.joblib"]))
features, pre, calibrated = bundle["features"], bundle["pre"], bundle["final_calibrated"]
wide = pd.read_csv(find(["vs_ml_wide.csv", "vs_ml_wide"])); d = wide.copy()
d["sbp_last"] = d.abps_last.fillna(d.nbps_last)
d["sbp_min"] = d.abps_min.fillna(d.nbps_min)
d["sbp_mean"] = d.abps_mean.fillna(d.nbps_mean)
d["dbp_last"] = d.abpd_last.fillna(d.nbpd_last)
d["temp_last"] = d.temp_c_last.fillna(d.temp_fromf_last)
r = d.race.astype(str).str.lower(); h = r.str.contains("hispanic|latino", regex=True)
w_ = r.str.contains("white") & ~h
d["race_grp_hispanic"] = h.astype(int); d["race_grp_white"] = w_.astype(int); d["race_grp_other"] = (~h & ~w_).astype(int)
nm = d.first_careunit.astype(str).str.lower(); im = nm.str.contains("medical") | nm.str.contains("micu")
isu = nm.str.contains("surgical") | nm.str.contains("sicu")
d["cu_grp_micu"] = im.astype(int); d["cu_grp_sicu"] = ((~im) & isu).astype(int); d["cu_grp_other"] = ((~im) & (~isu)).astype(int)
y_all = d.vasoplegia.astype(int).to_numpy()
tr, te = train_test_split(range(len(d)), test_size=.3, stratify=y_all, random_state=SEED)
p_mimic = calibrated.predict_proba(pre.transform(d[features].iloc[te]))[:, 1]; yte = y_all[te]
ep = pd.read_csv(find(["eicu_pred.csv"])); ye, pe, pe_r = ep.label.values, ep.prob.values, ep.prob_recal.values

def decile(y, p, n=10):
    order = np.argsort(p); ranks = np.empty(len(p)); ranks[order] = np.arange(len(p))
    grp = np.minimum((ranks*n//len(p)), n-1)
    po, oo, lo, hi = [], [], [], []
    for g in range(n):
        m = grp == g; k = int(y[m].sum()); nn = int(m.sum()); ctr = k/nn; z = 1.96
        den = 1+z*z/nn; cen = (ctr+z*z/(2*nn))/den
        margin = z*np.sqrt(ctr*(1-ctr)/nn+z*z/(4*nn*nn))/den
        po.append(p[m].mean()); oo.append(ctr); lo.append(cen-margin); hi.append(cen+margin)
    return map(np.array, (po, oo, lo, hi))

def smooth(y, p):
    s = lowess(y, p, frac=.4, return_sorted=True); return s[:, 0], s[:, 1]

def dca(y, p, th):
    n = len(y); out = []
    for t in th:
        prd = p >= t; tp = np.sum(prd & (y == 1)); fp = np.sum(prd & (y == 0))
        out.append(tp/n-fp/n*t/(1-t))
    return np.array(out)

fig, ax = plt.subplots(2, 2, figsize=(7.1, 5.6))
a = ax[0, 0]
fpr, tpr, _ = roc_curve(yte, p_mimic); a.plot(fpr, tpr, color=C["blue"], lw=1.2, label=f"MIMIC test (AUROC {roc_auc_score(yte,p_mimic):.3f})")
fpr, tpr, _ = roc_curve(ye, pe_r); a.plot(fpr, tpr, color=C["orange"], lw=1.2, ls="--", label=f"eICU (AUROC {roc_auc_score(ye,pe_r):.3f})")
a.plot([0, 1], [0, 1], color=C["lgrey"], lw=.6, ls=":"); a.set_xlabel("1 - Specificity"); a.set_ylabel("Sensitivity")
a.set_title("A   Discrimination (ROC)", loc="left", fontweight="bold"); a.legend(loc="lower right", frameon=False); a.set_xlim(-.01, 1.01); a.set_ylim(-.01, 1.01)

a = ax[0, 1]
pr, rc, _ = precision_recall_curve(yte, p_mimic); a.plot(rc, pr, color=C["blue"], lw=1.2, label=f"MIMIC (AUPRC {average_precision_score(yte,p_mimic):.3f})")
pr, rc, _ = precision_recall_curve(ye, pe_r); a.plot(rc, pr, color=C["orange"], lw=1.2, ls="--", label=f"eICU (AUPRC {average_precision_score(ye,pe_r):.3f})")
a.axhline(yte.mean(), color=C["lgrey"], lw=.6, ls=":"); a.set_xlabel("Recall (Sensitivity)"); a.set_ylabel("Precision (PPV)")
a.set_title("B   Precision-recall", loc="left", fontweight="bold"); a.legend(loc="upper right", frameon=False); a.set_xlim(0, 1.01); a.set_ylim(0, 1.02)

a = ax[1, 0]
for y, p, col, mk, lab in [(yte, p_mimic, C["blue"], "o", "MIMIC test"),
                           (ye, pe_r, C["green"], "^", "eICU recalibrated")]:
    po, oo, lo, hi = decile(y, p)
    a.errorbar(po, oo, yerr=[oo-lo, hi-oo], fmt=mk, color=col, ms=3.3, lw=.8, capsize=2, label=lab)
    sx, sy = smooth(y, p); a.plot(sx, sy, color=col, lw=.9, ls="-", alpha=.8)
po, oo, _, _ = decile(ye, pe); a.plot(po, oo, color=C["orange"], lw=.8, ls="--", label="eICU raw")
lim = min(1, max(p_mimic.max(), pe_r.max())*1.12); a.plot([0, lim], [0, lim], color=C["lgrey"], lw=.6, ls=":")
a.set_xlim(0, lim); a.set_ylim(0, lim); a.set_xlabel("Predicted probability"); a.set_ylabel("Observed proportion")
a.set_title("C   Calibration (deciles, 95% CI, smoothed)", loc="left", fontweight="bold"); a.legend(loc="upper left", frameon=False)

a = ax[1, 1]
th = np.linspace(.01, .40, 150)
a.plot(th, dca(yte, p_mimic, th), color=C["blue"], lw=1.2, label="Model MIMIC")
a.plot(th, dca(ye, pe_r, th), color=C["green"], lw=1.2, ls="-", label="Model eICU")
a.plot(th, yte.mean()-(1-yte.mean())*th/(1-th), color=C["grey"], lw=.8, ls="--", label="Treat all MIMIC")
a.plot(th, ye.mean()-(1-ye.mean())*th/(1-th), color=C["orange"], lw=.8, ls="--", label="Treat all eICU")
a.axhline(0, color=C["lgrey"], lw=.6, ls=":"); a.set_xlabel("Threshold probability"); a.set_ylabel("Net benefit")
a.set_title("D   Decision-curve analysis", loc="left", fontweight="bold"); a.legend(loc="upper right", frameon=False)
fig.tight_layout(pad=.6)

OUT_DIR.mkdir(parents=True, exist_ok=True)
name = "Figure2_performance_enhanced"
for ext, dpi, kw in [("pdf", None, {}), ("tiff", 600, {"pil_kwargs": {"compression": "tiff_lzw"}}), ("png", 300, {})]:
    fig.savefig(OUT_DIR/f"{name}.{ext}", dpi=dpi, **kw)
plt.close(fig)
print("已保存增强版 Figure2（PDF/TIFF/PNG）到", OUT_DIR)
