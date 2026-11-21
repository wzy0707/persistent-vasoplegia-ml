# -*- coding: utf-8 -*-
"""构建独立补充材料 docx：Fig S1 SHAP + Table S1/S2/S3 + in-sample 泄漏表。"""
import os
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "Supplementary_appendix.docx")
doc = Document()
st = doc.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(11)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")


def H(t, l=1):
    p = doc.add_heading(t, level=l)
    for r in p.runs: r.font.name = "Times New Roman"


def P(t, b=False, c=False):
    p = doc.add_paragraph(); r = p.add_run(t); r.bold = b
    if c: p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def hrules(t):
    pr = t._tbl.tblPr; bd = OxmlElement("w:tblBorders")
    for e in ("top", "bottom", "insideH"):
        x = OxmlElement("w:" + e); x.set(qn("w:val"), "single"); x.set(qn("w:sz"), "4")
        x.set(qn("w:space"), "0"); x.set(qn("w:color"), "404040"); bd.append(x)
    for e in ("left", "right", "insideV"):
        x = OxmlElement("w:" + e); x.set(qn("w:val"), "none"); bd.append(x)
    pr.append(bd)


def table(headers, rows, caption, note=None):
    P(caption, b=True)
    t = doc.add_table(rows=1, cols=len(headers)); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hrules(t)
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]; cell.text = ""; r = cell.paragraphs[0].add_run(h); r.bold = True; r.font.size = Pt(9)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for row in rows:
        cs = t.add_row().cells
        for i, v in enumerate(row):
            cs[i].text = ""; r = cs[i].paragraphs[0].add_run(str(v)); r.font.size = Pt(8.5)
            cs[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER if i else WD_ALIGN_PARAGRAPH.LEFT
    if note:
        p = doc.add_paragraph(); r = p.add_run(note); r.italic = True; r.font.size = Pt(8.5)
    doc.add_paragraph()


P("Supplementary Appendix", b=True, c=True)
P("Early prediction of persistent refractory vasoplegia in septic shock using machine learning: a retrospective "
  "two-database development and external validation study", c=True)
doc.add_paragraph()

# ---- Figure S1 SHAP ----
shp = os.path.join(BASE, "final_figures", "Figure3_shap.png")
doc.add_picture(shp, width=Inches(6.2)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("Figure S1. SHAP summary of the leading predictors. Computed on the pre-calibration XGBoost model "
              "(log-odds scale); each point is a patient, color is feature value and horizontal position is the "
              "contribution to predicted log-odds."); r.bold = True; r.font.size = Pt(9.5)

# ---- Table S1 候选模型 ----
table(["Model", "Predictors", "AUROC", "AUPRC"],
 [("LASSO logistic", "23", "0.941", "0.324"),
  ("Random forest", "77", "0.929", "0.343"),
  ("Extreme gradient boosting", "77", "0.943", "0.340"),
  ("Calibrated XGBoost (final)", "77", "0.941", "0.351")],
 "Table S1. Internal test-set comparison of candidate learners (n=5,239)",
 "AUPRC = area under the precision-recall curve.")

# ---- Table S2 风险分层 ----
table(["Risk stratum", "n", "Observed event rate, %", "ICU mortality, %", "Hospital mortality, %"],
 [("Decile 1 (lowest)", "524", "0.8", "3.1", "4.4"),
  ("Decile 10 (highest)", "524", "18.1", "54.0", "59.4"),
  ("Low risk", "4,486", "4.6", "9.9", "13.6"),
  ("Intermediate risk", "511", "14.9", "40.1", "47.2"),
  ("High risk", "242", "21.5", "65.3", "69.8")],
 "Table S2. Predicted-risk deciles and tiers with observed outcomes",
 "138 of 139 test events (99.3%) fell in the upper predicted quartile.")

# ---- Table S3 head-to-head ----
table(["Cohort / model", "AUROC", "AUPRC", "AUROC difference vs ML (95% CI)", "DeLong p"],
 [("MIMIC test (n=5,239)", "", "", "", ""),
  ("  Machine learning (full)", "0.941", "0.351", "reference", ""),
  ("  Six-variable logistic (refitted)", "0.873", "0.206", "0.068", "<0.0001"),
  ("  RSSS bedside score", "0.853", "0.158", "0.089 (0.057-0.121)", "<0.0001"),
 ("eICU external (n=2,268)", "", "", "", ""),
  ("  Machine learning (full)", "0.900", "0.410", "reference", ""),
  ("  Six-variable logistic (locked)", "0.748", "0.277", "0.152", "<0.0001"),
  ("  RSSS bedside score", "0.734", "0.247", "0.166 (0.126-0.206)", "<0.0001")],
 "Table S3. Full head-to-head comparison",
 "IDI and NRI were significant (p<0.05) for the machine learning model versus both comparators in both databases.")

# ---- in-sample 泄漏 ----
table(["Group", "n", "events", "AUROC", "AUPRC"],
 [("Full cohort (in-sample)", "17,463", "463", "0.996", "0.902"),
  ("Landmark NEE<0.5 (low)", "16,825", "240", "0.997", "0.892"),
  ("Landmark NEE>=0.5 (high)", "638", "223", "0.983", "0.974")],
 "Table S4. In-sample leakage analysis (apparent, optimistic performance)",
 "These are in-sample apparent estimates without a held-out split and are intentionally optimistic; they are not "
 "used for any clinical conclusion.")

P("The completed TRIPOD+AI checklist is supplied as a separate file.")
doc.save(OUT)
print("已保存:", OUT, "大小KB=%.1f" % (os.path.getsize(OUT) / 1024))
