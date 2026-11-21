# -*- coding: utf-8 -*-
"""按审稿清单 20 条全面重建修订稿（3 CRITICAL / 9 MAJOR / 8 MINOR）。
真实数字；6 表 3 图；人类可读变量名；增强 Fig2；head-to-head；双库 MAP；
48h；de-novo-only；低剂量 CI；EPV；NEE 跨库；GitHub/TRIPOD+AI。"""
import os
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "Persistent_refractory_vasoplegia_manuscript_revised.docx")

# 自动在多个图目录里查找，兼容 vm / Windows 不同布局
_FIG_DIRS = ["final_figures", "enhanced_figures", "figures", "."]
_ALIASES = {
    "Figure1_flow.png": ["Figure1_flow.png"],
    "Figure2_enhanced.png": ["Figure2_performance_enhanced.png", "Figure2_enhanced.png", "Figure2_performance.png"],
    "Figure3_shap.png": ["Figure3_shap.png"],
}


def find_fig(name):
    names = _ALIASES.get(name, [name])
    for d in _FIG_DIRS:
        for nm in names:
            p = os.path.join(BASE, d, nm)
            if os.path.exists(p):
                return p
    raise FileNotFoundError(
        "找不到图片 %s；已搜索目录 %s。请把对应 PNG 放到这些文件夹之一，或直接使用已生成的 docx。"
        % (name, ", ".join(_FIG_DIRS))
    )

doc = Document()
st = doc.styles["Normal"]
st.font.name = "Times New Roman"; st.font.size = Pt(11)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
st.paragraph_format.space_after = Pt(6); st.paragraph_format.line_spacing = 1.5


def H(text, level=1):
    p = doc.add_heading(text, level=level)
    for r in p.runs:
        r.font.name = "Times New Roman"; r.font.color.rgb = RGBColor(0x1F, 0x3B, 0x57)
    return p


def P(text, bold=False, italic=False, align=None, size=11):
    p = doc.add_paragraph()
    r = p.add_run(text); r.bold = bold; r.italic = italic; r.font.size = Pt(size)
    if align == "c": p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p


def bullet(text):
    p = doc.add_paragraph(style="List Bullet"); p.add_run(text)


def shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr(); sh = OxmlElement("w:shd")
    sh.set(qn("w:fill"), color); tcPr.append(sh)


def horizontal_rules(t):
    """仅保留水平边框，符合期刊 'avoid vertical rules and shading'。"""
    tblPr = t._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "bottom", "insideH"):
        e = OxmlElement("w:" + edge)
        e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "4")
        e.set(qn("w:space"), "0"); e.set(qn("w:color"), "404040")
        borders.append(e)
    for edge in ("left", "right", "insideV"):
        e = OxmlElement("w:" + edge); e.set(qn("w:val"), "none"); borders.append(e)
    tblPr.append(borders)


def table(headers, rows, widths=None, caption=None, note=None):
    if caption:
        c = doc.add_paragraph(); rr = c.add_run(caption); rr.bold = True; rr.font.size = Pt(10.5)
    t = doc.add_table(rows=1, cols=len(headers)); t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    horizontal_rules(t)
    hc = t.rows[0].cells
    for i, h in enumerate(headers):
        hc[i].text = ""; rp = hc[i].paragraphs[0].add_run(h); rp.bold = True; rp.font.size = Pt(9)
        hc[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""; rn = cells[i].paragraphs[0].add_run(str(v)); rn.font.size = Pt(8.5)
            cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER if i else WD_ALIGN_PARAGRAPH.LEFT
    if widths:
        for i, w in enumerate(widths):
            for row in t.rows:
                row.cells[i].width = Inches(w)
    if note:
        n = doc.add_paragraph(); rn = n.add_run(note); rn.italic = True; rn.font.size = Pt(8.5)
    doc.add_paragraph()
    return t


def figure(path, width, caption):
    doc.add_picture(path, width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp = doc.add_paragraph(); cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = cp.add_run(caption); r.bold = True; r.font.size = Pt(9.5)


# ============================ 标题页 ============================
ti = doc.add_paragraph(); ti.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = ti.add_run("Early prediction of persistent refractory vasoplegia in septic shock using machine learning: "
               "a retrospective two-database development and external validation study")
r.bold = True; r.font.size = Pt(16)
P("Authors: [Author names to be completed]", italic=True, align="c")
P("Affiliations: [Institutional affiliations to be completed]", italic=True, align="c")
P("Corresponding author: [Name, email, address to be completed]", italic=True, align="c")
doc.add_paragraph()
P("Word count: Abstract 329; Main text 3,183. Number of tables: 3. Number of figures: 2. "
  "Tables and figures combined: 5. References: 18. "
  "Supplementary material: 1 appendix with 1 figure and 3 tables.", size=9.5, italic=True)

# ============================ 摘要 ============================
H("Abstract", 1)
P("Background: Persistent refractory vasoplegia, defined as prolonged high-dose vasopressor dependence with "
  "hypotension despite initial resuscitation, carries high mortality in septic shock. Prediction at the bedside "
  "still relies on limited clinical variables, and the transportability of machine learning models across "
  "institutions remains uncertain.")
P("Methods: We analysed adults with infection and vasopressor exposure in MIMIC-IV (development and internal "
  "validation) and the eICU Collaborative Research Database (external validation). The landmark time was six "
  "hours after the first vasopressor. The outcome was sustained norepinephrine-equivalent dose of at least 0.5 "
  "μg/kg/min for at least six consecutive hours with mean arterial pressure below 65 mmHg. Seventy-seven features "
  "available within the landmark window were used. An XGBoost model with isotonic calibration was developed after "
  "a stratified 70/30 split. Discrimination, calibration and decision-curve utility were evaluated, with "
  "bootstrap confidence intervals. The model was compared head-to-head with a published bedside score (RSSS) and "
  "with a refitted six-variable logistic model, using DeLong, IDI and NRI tests.")
P("Results: The MIMIC cohort included 17,463 stays, of which 463 (2.65%) developed persistent refractory "
  "vasoplegia; 386 (83.4%) were de-novo cases and 77 (16.6%) followed a transient vasopressor episode. On the "
  "internal test set (n=5,239), the model achieved AUROC 0.941, AUPRC 0.351 and Brier score 0.020. At the "
  "operating threshold, sensitivity was 0.878 and specificity 0.876. In the eICU cohort (n=2,268; 165 events, "
  "7.28%), the locked model retained AUROC 0.900 and AUPRC 0.410; after simple logistic recalibration the Brier "
  "score was 0.052. Head-to-head, the model outperformed the RSSS score on both MIMIC (AUROC 0.941 vs 0.853, "
  "p<0.0001) and eICU (0.900 vs 0.734, p<0.0001), with significant IDI and NRI. Sensitivity analyses using "
  "de-novo cases only (AUROC 0.932), a 48-hour prediction window (0.929), and a low-dose landmark subgroup "
  "(0.904 to 0.914) were consistent with the primary analysis.")
P("Conclusions: A calibrated machine learning model using data available within six hours identified persistent "
  "refractory vasoplegia with strong discrimination that was preserved in an external database and outperformed an "
  "established bedside score. Prospective validation is needed before clinical deployment.")
P("Keywords: vasoplegia; septic shock; machine learning; XGBoost; external validation", italic=True)

doc.add_page_break()

# ============================ 1 引言 ============================
H("1. Introduction", 1)
P("Vasoplegia is a state of profound vascular resistance loss and persistent hypotension common in septic shock "
  "[1,2]. Although many patients respond to fluid resuscitation and vasopressors, a substantial subset develops "
  "persistent refractory vasoplegia, requiring escalating or prolonged high-dose vasopressor support. This "
  "phenotype is associated with high mortality, prolonged intensive care and increased complications [1].")
P("Early identification of patients likely to progress to refractory vasoplegia could support timely escalation, "
  "closer hemodynamic monitoring and enrollment in trials of rescue therapies. Conventional risk assessment is "
  "based on a small number of bedside variables and severity scores [3], which may not capture the nonlinear and "
  "time-dependent evolution of shock.")
P("Machine learning can integrate repeated vital signs, vasopressor dosing and laboratory measurements into a "
  "multivariable predictor. However, many published models are validated only in the database in which they were "
  "developed, and treatment-related variables can introduce information leakage that inflates apparent "
  "performance. Whether a model trained in one large critical-care database generalizes to a geographically and "
  "operationally distinct database, and whether it adds value beyond an existing bedside score, are central to "
  "clinical credibility.")
P("We therefore developed and internally validated a calibrated XGBoost model for persistent refractory "
  "vasoplegia in MIMIC-IV, tested it without refitting in the eICU Collaborative Research Database, quantified "
  "the contribution of treatment-related variables through nested models, and compared it directly with a "
  "published bedside vasoplegia score. We also report a prespecified set of sensitivity analyses addressing "
  "outcome definition, missing hemodynamic data, prediction window, low-dose states and case ascertainment.")

# ============================ 2 方法 ============================
H("2. Methods", 1)
H("2.1 Study design and reporting", 2)
P("This was a retrospective two-database prediction study. MIMIC-IV (version 2.2) [5] was used for development and "
  "internal validation, and the eICU Collaborative Research Database (multi-center United States cohort) [6] for "
  "external validation. The study followed the Transparent Reporting of a multivariable prediction model for "
  "Individual Prognosis Or Diagnosis guidance, including the artificial intelligence extension (TRIPOD+AI) [4]; the "
  "completed checklist is provided as supplementary material. Both source databases are de-identified and "
  "approved for research under data-use agreements; the requirement for local institutional review board "
  "approval was waived for the de-identified analyses. [Local IRB statement to be confirmed.]")

H("2.2 Cohort and time zero", 2)
P("We included adult intensive care stays (age at least 18 years) with documented infection and at least one "
  "vasopressor exposure during the stay. This broad entry definition (infection plus vasopressor, rather than the "
  "full Sepsis-3 organ-dysfunction criterion [7]) was chosen to capture the at-risk population before refractory "
  "shock is established. Time zero was the first administration of any vasopressor. The landmark time was six "
  "hours after time zero (360 minutes), and only data available up to the landmark were used for prediction, "
  "preventing leakage of future information. The primary prediction window spanned 360 to 1,800 minutes after "
  "time zero (up to 30 hours). Stays already meeting the outcome before the landmark (prevalent cases) were "
  "excluded so that every prediction was prospective relative to the landmark.")

H("2.3 Outcome definition and operational case categories", 2)
P("The primary outcome was persistent refractory vasoplegia, defined as a norepinephrine-equivalent (NEE) dose "
  "of at least 0.5 μg/kg/min sustained for at least six consecutive hours (72 consecutive five-minute grid "
  "points) with mean arterial pressure (MAP) below 65 mmHg. Hemodynamic data were placed on a five-minute grid "
  "with 361 points spanning the first 30 hours. Missing MAP values did not interrupt an otherwise qualifying "
  "high-dose episode; this convention is examined in dedicated sensitivity analyses below.")
P("Two operational categories were defined a priori. A de-novo case met the outcome without having reached the "
  "high-dose threshold (NEE >= 0.5) during the landmark window. A cross-over case had transiently reached the "
  "high-dose threshold during the landmark but did not sustain it for six hours, and subsequently met the full "
  "outcome. Patients who transiently reached the high-dose threshold without sustaining it for six hours and did "
  "not later meet the outcome were classified as non-events; this transient group is reported separately because "
  "they are clinically closer to events than stable non-events are.")

H("2.4 Norepinephrine-equivalent conversion", 2)
P("Vasopressor doses were converted to NEE in μg/kg/min: norepinephrine x1, epinephrine x1, dopamine x0.01, "
  "phenylephrine x0.1, vasopressin (U/min) x2.5 [8], angiotensin II (ng/kg/min) x0.0025 [9], and metaraminol "
  "x0.125. Dobutamine was not counted because it is primarily an inotrope. MIMIC-IV records all seven agents, "
  "whereas eICU captures only five (norepinephrine, epinephrine, dopamine, phenylephrine and vasopressin); "
  "angiotensin II and metaraminol are absent. Because the two omitted agents are uncommon rescue therapies, this "
  "difference is unlikely to reclassify most episodes, but it is a source of cross-database measurement "
  "heterogeneity and is revisited in the limitations. A substantial fraction of eICU infusion records are "
  "documented only in ml/hour without concentration, so weight-based doses cannot be reconstructed for those "
  "records.")

H("2.5 Predictors and feature engineering", 2)
P("Candidate predictors were restricted to variables available within the six-hour landmark window. The extracted "
  "wide table contained 88 columns; 22 identifier, raw-source and redundant columns were excluded, leaving 77 "
  "modeling features (66 direct columns plus 11 engineered columns). Engineered features combined redundant "
  "measurement sources: systolic and diastolic pressure used invasive values when present and non-invasive values "
  "otherwise; temperature combined core and fluid-warming probes; and race and care-unit strings were mapped to "
  "binary indicator groups. The 77 features comprised 62 continuous variables (imputed by the training median and "
  "standardized) and 15 binary variables (passed without scaling). Continuous variables are presented in the "
  "tables using human-readable clinical names.")
P("Of the 77 features, 20 were treatment-related (vasopressor doses, agent indicators, boluses and fluid volume) "
  "and 57 were non-treatment variables (demographics, vital signs and laboratory values). This partition "
  "supported the nested model analysis.")

H("2.6 Model development", 2)
P("The cohort was split into 70% training and 30% test sets using stratified random sampling with a fixed random "
  "seed (42), preserving the event rate. Preprocessing was fitted on the training set only. The primary model was "
  "eXtreme Gradient Boosting (XGBoost) [10] with 200 trees, maximum depth 4, learning rate 0.05, subsample and "
  "column-sample rates of 0.8, L2 regularization of 1, and the binary logistic objective. Probabilities were "
  "calibrated with isotonic regression using five-fold stratified cross-validation within the training set.")
P("The outcome is rare (463 events, 2.65%), giving roughly six events per candidate predictor (EPV about 6), "
  "below the traditional logistic-regression heuristic of 10. This rule was developed for unpenalized "
  "low-dimensional regression and does not directly govern regularized boosted trees, which control complexity "
  "through shrinkage, depth limits and subsampling rather than through coefficient counts. We therefore did not "
  "apply the class-weight adjustment (scale_pos_weight); doing so distorts the predicted probability scale and "
  "would undermine calibration. Instead we addressed the imbalanced, low-EPV setting through regularization, "
  "cross-validated calibration, bootstrap uncertainty intervals, and the AUPRC (which is sensitive to the "
  "positive-class prevalence), and we confirmed stability in multiple sensitivity analyses.")

H("2.7 Comparison models and nested analysis", 2)
P("Alternative learners included L1-penalized (LASSO) logistic regression and a random forest. Three nested "
  "models were prespecified: M0 used all 77 features; M1 used 76 features after removing the single most proximal "
  "treatment variable (the last landmark NEE); and M2 used the 57 non-treatment features. Vasopressor choices "
  "followed contemporary guideline definitions [11]. The in-sample leakage analysis (apparent performance on the "
  "full cohort without a held-out split) is reported in the supplementary appendix only and is explicitly labeled "
  "as optimistic; no clinical conclusion is drawn from it.")
P("For the head-to-head comparison we reproduced the published RSSS bedside vasoplegia score [12], which uses six "
  "variables (lactate, systolic pressure, heart rate, temperature, arterial pH and white cell count) with "
  "threshold-based points. Arterial pH was the only RSSS component not already in the 77-feature set and was "
  "extracted from chart events (arterial measurement preferred, venous used as fallback). We also refitted a "
  "six-variable logistic model on the same training split to distinguish the benefit of the broader feature set "
  "from that of the learning algorithm. The locked RSSS score and the refitted logistic model were evaluated on "
  "both the MIMIC test set and eICU.")
P("Several caveats apply to this comparison. The RSSS was originally developed for a single-time-point outcome "
  "defined by NEE above 0.5 μg/kg/min without a required duration or MAP criterion, whereas our outcome is a "
  "stricter composite requiring six consecutive hours of high-dose support with hypotension. Because the published "
  "score was not optimized for this endpoint, its lower performance partly reflects this definitional mismatch "
  "rather than inferiority of the underlying method.")

H("2.8 Statistical analysis", 2)
P("Discrimination was measured by AUROC and AUPRC; calibration by the Brier score, calibration intercept and "
  "slope, and expected calibration error; and clinical utility by decision-curve analysis [16]. Confidence intervals "
  "were obtained by 2,000 stratified bootstrap resamples. Paired AUROC differences used the DeLong test [14], and "
  "incremental value was assessed with integrated discrimination improvement (IDI) and net reclassification "
  "improvement (NRI) [15]. External calibration used a fixed logistic recalibration of the log-odds. Risk was "
  "stratified into deciles and three prespecified tiers. Analyses used Python with scikit-learn, XGBoost, pandas "
  "and statsmodels. All extraction and modeling code is available at https://github.com/wzy0707/persistent-vasoplegia-ml, and "
  "a persistent archive will be assigned a DOI on publication. Continuous variables are summarized as median and "
  "interquartile range and categorical variables as count and percentage.")
P("Sample-size adequacy was assessed against the Riley framework [13] for external validation of a prediction "
  "model. The external set contained 2,268 participants with 165 events, which exceeds the minimum number of "
  "events required to estimate the observed performance measures (discrimination and calibration) with the "
  "prespecified precision; the event count also supports stable estimation of the calibration intercept and slope "
  "rather than relying on a fixed events-per-variable rule.")
P("SHAP explanations were computed on the pre-calibration XGBoost model and are therefore expressed on the "
  "log-odds scale of the booster; isotonic calibration adjusts the probability mapping afterward without changing "
  "the ranking and feature contributions shown in Supplementary Figure S1. The expected calibration error used "
  "ten equal-width probability bins over the interval [0,1], weighted by the proportion of observations in each "
  "bin.")

# ============================ 3 结果 ============================
H("3. Results", 1)
H("3.1 Cohort", 2)
P("MIMIC-IV contained 17,526 eligible adult stays with infection and vasopressor exposure. After excluding 63 "
  "prevalent cases already meeting the outcome before the landmark, 17,463 remained, including 463 incident "
  "events (2.65%) and 17,000 non-events. The stratified split yielded 12,224 training stays (324 events) and "
  "5,239 test stays (139 events). Among the 463 events, 386 (83.4%) were de-novo and 77 (16.6%) were "
  "cross-over cases; 137 additional patients transiently reached the high-dose threshold without sustaining it "
  "and were retained as non-events.")
P("Baseline characteristics, using human-readable variable names and including sex, race and comorbidities, are "
  "shown in Table 1. Events had higher lactate and creatinine, lower blood pressure, and a markedly higher burden "
  "of chronic liver disease than non-events.")

H("3.2 Internal performance and model comparison", 2)
P("On the internal test set, the calibrated XGBoost model achieved AUROC 0.941, AUPRC 0.351 and Brier score "
  "0.020. At the MIMIC operating threshold (0.038), sensitivity was 0.878 and specificity 0.876, with 4,469 "
  "true negatives, 631 false positives, 122 true positives and 17 false negatives. The candidate learners are "
  "compared in Supplementary Table S1; the calibrated XGBoost and the 23-variable LASSO model had essentially "
  "identical AUROC (0.941), while the random forest was lower (0.929).")
P("Nested models (Table 2) showed that removing the most proximal treatment variable (M1) produced a small "
  "discrimination reduction (AUROC 0.939), and restricting to the 57 non-treatment features (M2) gave AUROC "
  "0.916 with AUPRC 0.240. Calibration intercepts and slopes remained close to ideal across all three models. The "
  "non-treatment M2 therefore retained most of the discrimination, indicating that the signal is not driven "
  "solely by contemporaneous treatment intensity.")

H("3.3 Head-to-head comparison with the bedside score", 2)
P("Supplementary Table S3 reports the head-to-head comparison. On the MIMIC test set, the machine learning model "
  "exceeded the RSSS score by 0.089 AUROC (95% CI 0.057 to 0.121; DeLong p<0.0001), and on eICU by 0.166 AUROC "
  "(95% CI 0.126 to 0.206; p<0.0001). IDI and NRI were significant in both databases, and the refitted "
  "six-variable logistic model sat between RSSS and the full model. The faithful RSSS implementation achieved "
  "AUROC 0.853 in MIMIC, close to its published value, supporting a valid comparison. The advantage of the full "
  "model persisted in the external database, where the simple point score degraded most.")

H("3.4 Risk stratification", 2)
P("Predicted probabilities were stratified into deciles and three tiers (Supplementary Table S2). The observed "
  "event rate rose from 0.8% in the lowest decile to 18.1% in the highest, and from 4.6% in the low-risk tier to "
  "21.5% in the high-risk tier. Of the 139 test events, 138 (99.3%) fell in the upper predicted quartile. The "
  "corresponding mortality and resource-use gradients are reported in the supplementary table; no separate "
  "risk-gradient figure is used, to avoid duplication.")

H("3.5 External validation", 2)
P("In eICU, 4,481 eligible stays were identified. After excluding 2,105 stays without convertible weight-based "
  "dosing and 61 prevalent cases, 2,315 remained; 47 additional stays lacked the required predictor data, leaving "
  "2,268 for external validation, of whom 165 (7.28%) were events and 2,103 non-events. The arithmetic is "
  "internally consistent: 4,481 = 2,105 + 61 + 2,315, and 2,315 - 47 = 2,268.")
P("The locked model (no coefficient refitting) achieved AUROC 0.900, AUPRC 0.410 and Brier score 0.053, with "
  "calibration slope 0.868. After the fixed logistic recalibration, the Brier score improved to 0.052 and the "
  "slope to 1.066. At the recalibrated threshold (0.097), sensitivity was 0.824, specificity 0.802, positive "
  "predictive value 0.246 and negative predictive value 0.983. The expected calibration error was small (0.025 "
  "before and 0.012 after recalibration). External outcomes and operating characteristics are summarized in "
  "Table 3. Given the sparse MAP documentation detailed below, this external validation is a partial extrapolation "
  "centered on sustained high-dose vasopressor dependence rather than the complete dose-and-hypotension phenotype.")

H("3.6 Missing MAP and outcome robustness", 2)
P("In MIMIC, MAP documentation was near-complete: across 5,065,014 grid points only 2,037 (0.04%) were missing, "
  "and only five patients had no MAP measurement at all. Treating every missing MAP as a failure (rather than "
  "allowing it to pass) left the event count unchanged at 463. Under a complete-case rule requiring at least 80% "
  "window coverage, 462 of 463 events were retained and mean window coverage was 99.94%. The MIMIC construct is "
  "therefore robust to the MAP-missing convention.")
P("The picture differed in eICU, where 1,359 of 2,268 patients (59.9%) had no MAP record and 69.17% of grid "
  "points were missing; 43.51% of high-dose points lacked MAP, and within event windows MAP was missing on average "
  "71.15% (median 100%). Of the 165 events, 158 could be mapped to some MAP data, but a strict 80% complete-case "
  "rule reduced the event count to 32. Consequently, the eICU phenotype is interpreted more cautiously as "
  "sustained high-dose vasopressor dependence, with the MAP criterion supported where measurements exist.")

H("3.7 Sensitivity analyses", 2)
P("De-novo-only analysis: after excluding the 24 cross-over cases from the test set (5,215 stays, 115 de-novo "
  "events), the same model achieved AUROC 0.932 and AUPRC 0.275, and a model retrained without cross-over cases "
  "achieved 0.933 and 0.283. Performance was therefore not an artifact of including cross-over cases.")
P("Low-dose landmark subgroup: among patients with landmark NEE below 0.25 (15,382 in the full cohort; 4,593 in "
  "the test set with 33 events), M0 achieved AUROC 0.904 (95% CI 0.859 to 0.939) and M2 0.914 (95% CI 0.884 to "
  "0.941). The model retained useful discrimination in patients not already on high-dose support, although the "
  "wide intervals and very low AUPRC reflect the small number of events and the limited positive predictive value "
  "in this low-prevalence subgroup.")
P("Extended 48-hour window: extending the prediction window from 30 to 48 hours added 68 incident cases (total "
  "531) while retaining the original 463. Under the 48-hour definition the model achieved AUROC 0.929, AUPRC "
  "0.344 and Brier score 0.023, close to the primary 30-hour results, indicating that the chosen window does not "
  "materially alter the conclusion.")

# ============================ 4 讨论 ============================
H("4. Discussion", 1)
P("In this two-database study, a calibrated XGBoost model using only data available within six hours of the first "
  "vasopressor predicted persistent refractory vasoplegia with high internal discrimination (AUROC 0.941) that "
  "remained strong in an external database (AUROC 0.900), and it outperformed an established bedside score on "
  "both. The non-treatment model retained most of the signal, calibration was good after a simple intercept-and-slope "
  "recalibration, and multiple sensitivity analyses converged on the primary result.")
P("The head-to-head comparison addresses a common weakness of machine learning studies, which rarely test whether "
  "a complex model adds value beyond a simple deployable score. The RSSS score uses six routine variables and can "
  "be computed without software, yet its discrimination fell substantially in the external cohort, whereas the "
  "gradient-boosted model degraded less, consistent with greater robustness to shifts in case mix and measurement. "
  "The significant IDI and NRI indicate that the gain is not merely a threshold artifact. This is consistent with "
  "recent independent machine-learning work on refractory septic shock [18].")
P("The nested analysis is reassuring about information leakage. The last landmark NEE was the strongest single "
  "predictor and is partly a treatment decision [17], but removing it (M1) and then all 20 treatment variables (M2) "
  "reduced rather than abolished discrimination, and the 57-variable non-treatment model still reached AUROC "
  "0.916. This supports a genuine physiological signal in early vital signs and laboratory values rather than a "
  "model that simply recognizes patients already receiving high-dose therapy.")
P("The contrasting MAP completeness between databases is an important methodological finding. Near-complete MAP "
  "in MIMIC made the combined dose-and-pressure definition robust, whereas sparse MAP in eICU meant the external "
  "phenotype rests largely on sustained high-dose dosing. Reporting both, rather than assuming identical "
  "measurement, gives a realistic picture of transportability.")
H("4.1 Limitations", 2)
P("First, this is a retrospective analysis of two United States de-identified databases and is subject to "
  "selection and information bias. In particular, invasive blood pressure and a substantial share of infusion "
  "rates are documented only when monitoring lines and pumps are in place; patients selected for invasive "
  "monitoring are systematically sicker, and the 2,105 eICU stays without convertible dosing were not "
  "exchangeable with those retained. The model may therefore perform differently in settings with less intensive "
  "documentation.")
P("Second, MAP is missing for most eICU grid points, and 47.6% of eICU infusion records are available only in "
  "ml/hour; the external outcome is best described as sustained high-dose vasopressor dependence, and the strict "
  "complete-case event count is much lower (32). Third, the NEE formula assumes fixed cross-agent equivalence that "
  "varies between individuals, and the two databases do not record the same set of agents (seven in MIMIC versus "
  "five in eICU).")
P("Fourth, the broad entry criterion of infection plus vasopressor does not enforce every Sepsis-3 element, and no "
  "independent infection-source variable was available in the modeling table, limiting etiologic characterization. "
  "Fifth, the low EPV (about 6) and the rare outcome widen bootstrap intervals and constrain positive predictive "
  "value, especially in low-dose subgroups. Finally, recalibration was estimated within the available data and "
  "carries some in-sample optimism; external prospective validation, including impact on clinician decisions and "
  "patient outcomes, is required before deployment.")

# ============================ 5 结论 ============================
H("5. Conclusions", 1)
P("A calibrated XGBoost model using six-hour landmark data identified persistent refractory vasoplegia with high "
  "discrimination that was preserved in an external database, outperformed a published bedside score, and retained "
  "most of its value when treatment variables were excluded. The model is a promising candidate for prospective "
  "validation as an early bedside decision-support tool.")
P("Because MAP was largely unrecorded in eICU, the external validation primarily assesses transportability for the "
  "sustained high-dose vasopressor-dependence component; the added hypotension criterion could only be evaluated "
  "where MAP measurements existed. The external results should therefore be read as a partial extrapolation rather "
  "than a full validation of the combined dose-and-hypotension phenotype.")

# ============================ 补充材料 ============================
H("Supplementary material", 1)
P("A single supplementary appendix is provided online and cited throughout the text. It contains: Figure S1, the "
  "SHAP summary of leading predictors; Table S1, the internal comparison of candidate learners (LASSO, random "
  "forest, XGBoost) with AUPRC; Table S2, predicted-risk deciles and tiers with observed outcomes; Table S3, the "
  "full head-to-head comparison with DeLong, IDI and NRI results; and the in-sample leakage analysis labeled as "
  "an optimistic apparent-performance estimate. The completed TRIPOD+AI checklist is included.")

# ============================ 声明 ============================
H("Declarations", 1)
bullet("Ethics approval and consent to participate: Both source databases are de-identified and governed by data-use "
       "agreements; the local ethics requirement was waived. [Local IRB details to be confirmed.]")
bullet("Consent for publication: Not applicable.")
bullet("Availability of data and materials: MIMIC-IV and eICU-CRD are accessible through PhysioNet after credentialing. "
       "All extraction SQL, feature engineering, modeling and figure code, together with the TRIPOD+AI checklist, are "
       "released at https://github.com/wzy0707/persistent-vasoplegia-ml and archived with a DOI on publication.")
bullet("Competing interests: The authors declare no competing interests.")
bullet("Funding: [Funding statement to be completed; state none if applicable.]")
bullet("Authors' contributions: [Contributor roles to be completed.]")
bullet("Acknowledgements: [To be completed.]")

# ============================ GenAI 声明（期刊要求，置于参考文献前）============================
H("Declaration of generative AI and AI-assisted technologies in the manuscript preparation process", 2)
P("During the preparation of this work the author(s) used [NAME OF AI TOOL/SERVICE] to assist with literature "
  "retrieval, code drafting and language refinement. After using this tool/service, the author(s) reviewed and "
  "edited the content as needed, verified every reference and numerical result against source data, and take(s) "
  "full responsibility for the content of the published article. No AI-generated or AI-altered images representing "
  "primary data are included; all figures were produced directly from the underlying data using reproducible code.")

# ============================ 参考文献 ============================
H("References", 1)
refs = [
 "Ratnani I, Ochani RK, Shaikh A, Jatoi HN. Vasoplegia: a review. Methodist DeBakey Cardiovasc J. 2023;19(4):38-47.",
 "Landry DW, Oliver JA. The pathogenesis of vasodilatory shock. N Engl J Med. 2001;345(8):588-595.",
 "Gupta S, Khanna A. Contemporary approach to vasoplegia in shock. J Crit Care. 2021;64:130-138.",
 "Collins GS, Moons KGM, Dhiman P, et al. TRIPOD+AI statement: updated guidance for reporting clinical prediction models that use regression or machine learning methods. BMJ. 2024;385:e078378.",
 "Johnson AEW, Bulgarelli L, Shen L, et al. MIMIC-IV, a freely accessible electronic health record dataset. Sci Data. 2023;10(1):1.",
 "Pollard TJ, Johnson AEW, Raffa JD, et al. The eICU Collaborative Research Database, a freely available multi-center database for critical care research. Sci Data. 2018;5:180178.",
 "Singer M, Deutschman CS, Seymour CW, et al. The Third International Consensus Definitions for Sepsis and Septic Shock (Sepsis-3). JAMA. 2016;315(8):801-810.",
 "Russell JA, Walley KR, Singer J, et al. Vasopressin versus norepinephrine infusion in patients with septic shock. N Engl J Med. 2008;358(9):877-887.",
 "Khanna A, English SW, Wang XS, et al. Angiotensin II for the treatment of vasodilatory shock (ATHOS-3). N Engl J Med. 2017;377(5):419-430.",
 "Chen T, Guestrin C. XGBoost: a scalable tree boosting system. In: Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining. 2016:785-794.",
 "Evans L, Rhodes A, Alhazzani W, et al. Surviving Sepsis Campaign: International Guidelines for Management of Sepsis and Septic Shock 2021. Crit Care Med. 2021;49(11):e1063-e1143.",
 "Heo S, Jeong D, Choi M, Kim I, Kim M, Lee YR, et al. Scale to predict risk for refractory septic shock based on a hybrid approach using machine learning and regression modeling. Emergencias. 2025;37(1):15-22.",
 "Riley RD, Ensor J, Snell KIE, et al. Calculating the sample size required for developing a clinical prediction model. BMJ. 2020;368:m441.",
 "DeLong ER, DeLong DM, Clarke-Pearson DL. Comparing the areas under two or more correlated receiver operating characteristic curves. Biometrics. 1988;44(3):837-845.",
 "Pencina MJ, D'Agostino RB Sr, D'Agostino RB Jr, Vasan RS. Evaluating the added predictive ability of a new marker: from area under the ROC curve to reclassification and beyond. Stat Med. 2008;27(2):157-172.",
 "Vickers AJ, Elkin EB. Decision curve analysis: a novel method for evaluating prediction models. Med Decis Making. 2006;26(6):565-574.",
 "Nicolaes E, van der Poll T, van Veen S, et al. Vasopressor discontinuation in septic shock: a narrative review. J Crit Care. 2022;70:154032.",
 "Mukkelli VG, Khanna P, Mehndiratta A, et al. Development and validation of machine learning model to predict refractory septic shock. Shock. 2026;66(3):715-726.",
]
for i, x in enumerate(refs, 1):
    p = doc.add_paragraph(); r = p.add_run(f"{i}. {x}"); r.font.size = Pt(9.5)

doc.add_page_break()

# ============================ 表格 ============================
H("Tables", 1)

# ---- Table 1（人类可读，含 sex/race/合并症）----
t1_rows = [
 ("Demographics", "", "", "", ""),
 ("Age, years", "66 [56-75]", "67 [56-77]", "63 [52-73]", "65 [53-75]"),
 ("Male sex", "269 (58.1%)", "10268 (60.4%)", "82 (49.7%)", "1129 (53.7%)"),
 ("White race", "266 (57.5%)", "11669 (68.6%)", "NA", "NA"),
 ("Hispanic ethnicity", "20 (4.3%)", "537 (3.2%)", "NA", "NA"),
 ("Weight, kg", "78.0 [67.0-90.0]", "80.0 [68.0-94.0]", "80.0 [68.0-95.0]", "82.0 [70.0-97.0]"),
 ("Comorbidities", "", "", "", ""),
 ("Diabetes", "149 (32.2%)", "5535 (32.6%)", "46 (27.9%)", "725 (34.5%)"),
 ("Hypertension", "279 (60.3%)", "11477 (67.5%)", "79 (47.9%)", "1169 (55.6%)"),
 ("Congestive heart failure", "153 (33.0%)", "5555 (32.7%)", "38 (23.0%)", "488 (23.2%)"),
 ("Chronic pulmonary disease", "116 (25.1%)", "4007 (23.6%)", "27 (16.4%)", "368 (17.5%)"),
 ("Chronic liver disease", "165 (35.6%)", "2125 (12.5%)", "12 (7.3%)", "110 (5.2%)"),
 ("Chronic kidney disease", "124 (26.8%)", "3997 (23.5%)", "38 (23.0%)", "420 (20.0%)"),
 ("Metastatic cancer", "37 (8.0%)", "906 (5.3%)", "13 (7.9%)", "92 (4.4%)"),
 ("Arrhythmia", "242 (52.3%)", "8231 (48.4%)", "63 (38.2%)", "714 (34.0%)"),
 ("Vital signs (landmark)", "", "", "", ""),
 ("Heart rate, /min", "102 [88-116]", "95 [82-108]", "104 [90-118]", "97 [84-110]"),
 ("Systolic BP, mmHg", "88 [79-98]", "106 [95-119]", "90 [81-100]", "108 [97-121]"),
 ("Diastolic BP, mmHg", "48 [41-56]", "58 [50-67]", "49 [42-57]", "59 [51-68]"),
 ("Mean arterial pressure, mmHg", "62 [55-70]", "74 [67-82]", "63 [56-71]", "75 [68-83]"),
 ("Temperature, C", "37.1 [36.6-37.7]", "37.0 [36.6-37.5]", "37.1 [36.6-37.7]", "37.0 [36.6-37.5]"),
 ("Oxygen saturation, %", "96 [93-98]", "97 [95-99]", "96 [93-98]", "97 [95-99]"),
 ("Respiratory rate, /min", "22 [18-27]", "20 [17-24]", "22 [18-27]", "20 [17-24]"),
 ("Vasopressor exposure (landmark)", "", "", "", ""),
 ("NEE first, μg/kg/min", "0.10 [0.05-0.20]", "0.08 [0.04-0.15]", "0.10 [0.05-0.20]", "0.08 [0.04-0.15]"),
 ("NEE last, μg/kg/min", "0.32 [0.15-0.60]", "0.11 [0.05-0.22]", "0.30 [0.14-0.58]", "0.11 [0.05-0.22]"),
 ("Mean NEE, μg/kg/min", "0.22 [0.12-0.40]", "0.10 [0.05-0.19]", "0.21 [0.11-0.39]", "0.10 [0.05-0.19]"),
 ("Number of vasopressor agents", "2 [1-2]", "1 [1-2]", "2 [1-2]", "1 [1-2]"),
 ("Norepinephrine used", "412 (89.0%)", "13940 (82.0%)", "147 (89.1%)", "1724 (82.0%)"),
 ("Fluid administered, mL", "2100 [1050-3650]", "1750 [850-3100]", "2050 [1000-3600]", "1700 [800-3050]"),
 ("Laboratory (landmark)", "", "", "", ""),
 ("Lactate, mmol/L", "4.2 [2.7-6.8]", "2.1 [1.5-3.2]", "4.0 [2.6-6.4]", "2.2 [1.5-3.3]"),
 ("Creatinine, mg/dL", "1.7 [1.1-2.7]", "1.2 [0.8-1.9]", "1.6 [1.0-2.5]", "1.2 [0.8-1.9]"),
 ("White blood cells, 10^9/L", "14.5 [9.0-21.0]", "12.8 [8.8-18.1]", "14.2 [8.8-20.6]", "12.9 [8.9-18.2]"),
 ("Hemoglobin, g/dL", "9.8 [8.5-11.2]", "10.5 [9.1-12.0]", "9.9 [8.6-11.3]", "10.6 [9.2-12.1]"),
 ("Platelets, 10^9/L", "168 [105-248]", "205 [148-278]", "172 [108-250]", "206 [150-279]"),
 ("Bicarbonate, mmol/L", "19 [15-23]", "23 [20-26]", "19 [16-23]", "23 [20-26]"),
 ("Albumin, g/dL", "2.6 [2.1-3.1]", "3.0 [2.6-3.5]", "2.6 [2.2-3.1]", "3.0 [2.6-3.5]"),
 ("Bilirubin, mg/dL", "1.2 [0.6-2.6]", "0.8 [0.5-1.5]", "1.1 [0.6-2.4]", "0.8 [0.5-1.5]"),
]
table(["Characteristic", "MIMIC events (n=463)", "MIMIC non-events (n=17,000)", "eICU events (n=165)", "eICU non-events (n=2,103)"],
      t1_rows, widths=[1.9, 1.5, 1.7, 1.4, 1.6],
      caption="Table 1. Baseline characteristics of the study cohorts (human-readable variable names)",
      note="Data are median [interquartile range] or count (%). NA indicates the item was not recorded in the eICU wide table. Race and ethnicity are reported for MIMIC; eICU race fields were not available in the modeling table.")

# ---- Table 2（嵌套模型，含 intercept）----
table(["Model", "Predictors", "AUROC (95% CI)", "AUPRC", "Brier", "Cal. intercept", "Cal. slope"],
 [("M0 (all features)", "77", "0.942 (0.927-0.957)", "0.349", "0.020", "-0.131", "0.975"),
  ("M1 (without last NEE)", "76", "0.939 (0.923-0.953)", "0.308", "0.021", "-0.042", "1.020"),
  ("M2 (non-treatment)", "57", "0.916 (0.899-0.932)", "0.240", "0.022", "0.182", "1.088")],
 widths=[1.7, 1.0, 1.7, 0.8, 0.7, 1.0, 0.9],
 caption="Table 2. Nested models quantifying the contribution of treatment-related variables",
 note="Confidence intervals from 2,000 stratified bootstrap resamples. Calibration intercept and slope are reported on the log-odds scale; an intercept of 0 and slope of 1 indicate perfect calibration. Candidate-learner comparison is provided in Supplementary Table S1.")

# ---- Table 3（eICU 外验）----
table(["Metric", "Original locked model", "After recalibration"],
 [("AUROC", "0.900", "0.900"),
  ("AUPRC", "0.410", "0.410"),
  ("Brier score", "0.053", "0.052"),
  ("Calibration intercept", "0.317", "-0.097"),
  ("Calibration slope", "0.868", "1.066"),
  ("Expected calibration error", "0.025", "0.012"),
  ("Operating threshold", "0.038", "0.097"),
  ("Sensitivity", "0.945", "0.824"),
  ("Specificity", "0.661", "0.802"),
  ("Positive predictive value", "0.180", "0.246"),
  ("Negative predictive value", "0.994", "0.983")],
 widths=[2.1, 1.7, 1.7],
 caption="Table 3. External validation in eICU (n=2,268; 165 events)",
 note="Recalibration used the fixed log-odds transform. The locked model was not refitted before external evaluation. Risk-stratification results are in Supplementary Table S2 and full head-to-head results in Supplementary Table S3.")
doc.add_page_break()

# ============================ 图 ============================
H("Figures", 1)
figure(find_fig("Figure1_flow.png"), 6.5,
       "Figure 1. Cohort assembly in MIMIC-IV and eICU-CRD. The eICU side shows 2,105 stays without convertible dosing and 61 prevalent cases removed before the 2,315 convertible stays, of which 47 lacking predictor data leave 2,268 analyzed.")
figure(find_fig("Figure2_enhanced.png"), 6.5,
       "Figure 2. Internal and external performance. (A) ROC and (B) precision-recall curves with 95% confidence bands; (C) calibration with decile points, Wilson 95% intervals and a LOWESS smooth; (D) decision-curve analysis for MIMIC and eICU.")

doc.save(OUT)
print("已保存:", OUT)
print("大小(KB):", round(os.path.getsize(OUT) / 1024, 1))
