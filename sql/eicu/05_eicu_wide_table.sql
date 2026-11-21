-- Step29 eICU 77特征
WITH t0 AS (
    SELECT patientunitstayid, t0 FROM eicu.e_t0
),
eligible AS (
    SELECT patientunitstayid, label
    FROM eicu.e_label
    WHERE label_type IN ('incident','negative')
),
demog AS (
    SELECT c.patientunitstayid,
        c.age_num::float AS age,
        c.admissionweight::float AS weight_kg
    FROM eicu.e_cohort c
    JOIN eligible e ON c.patientunitstayid = e.patientunitstayid
),
vp AS (
    SELECT patientunitstayid, observationoffset AS off,
        heartrate AS hr, systemicsystolic AS sbp,
        systemicdiastolic AS dbp, systemicmean AS map,
        respiration AS rr, sao2 AS spo2, temperature AS temp
    FROM eicu.vitalperiodic
    WHERE patientunitstayid IN (SELECT patientunitstayid FROM eligible)
),
va AS (
    SELECT patientunitstayid, observationoffset AS off,
        noninvasivesystolic AS sbp, noninvasivediastolic AS dbp,
        noninvasivemean AS map
    FROM eicu.vitalaperiodic
    WHERE patientunitstayid IN (SELECT patientunitstayid FROM eligible)
),
vitals_win AS (
    SELECT
        COALESCE(vp.patientunitstayid, va.patientunitstayid) AS patientunitstayid,
        COALESCE(vp.off, va.off) AS off,
        vp.hr,
        COALESCE(vp.sbp, va.sbp) AS sbp,
        COALESCE(vp.dbp, va.dbp) AS dbp,
        COALESCE(vp.map, va.map) AS map,
        vp.rr, vp.spo2,
        CASE WHEN vp.temp BETWEEN 25 AND 45 THEN vp.temp ELSE NULL END AS temp
    FROM vp
    FULL OUTER JOIN va
      ON vp.patientunitstayid = va.patientunitstayid AND vp.off = va.off
),
vitals_f AS (
    SELECT v.*
    FROM vitals_win v
    JOIN t0 ON v.patientunitstayid = t0.patientunitstayid
    WHERE v.off >= t0.t0 AND v.off < t0.t0 + 360
),
vitals_agg AS (
    SELECT patientunitstayid,
        (array_agg(hr ORDER BY off))[cardinality(array_agg(hr ORDER BY off))] AS hr_last,
        MIN(hr) AS hr_min, MAX(hr) AS hr_max, AVG(hr) AS hr_mean,
        (array_agg(sbp ORDER BY off))[cardinality(array_agg(sbp ORDER BY off))] AS sbp_last,
        MIN(sbp) AS sbp_min, AVG(sbp) AS sbp_mean,
        (array_agg(dbp ORDER BY off))[cardinality(array_agg(dbp ORDER BY off))] AS dbp_last,
        (array_agg(map ORDER BY off))[1] AS map_first,
        (array_agg(map ORDER BY off))[cardinality(array_agg(map ORDER BY off))] AS map_last,
        MIN(map) AS map_min, MAX(map) AS map_max, AVG(map) AS map_mean,
        stddev_samp(map) AS map_sd,
        AVG(CASE WHEN "map" < 65 THEN 1.0 ELSE 0.0 END) AS map_below65_frac,
        (array_agg(rr ORDER BY off))[cardinality(array_agg(rr ORDER BY off))] AS rr_last,
        AVG(rr) AS rr_mean,
        (array_agg(spo2 ORDER BY off))[cardinality(array_agg(spo2 ORDER BY off))] AS spo2_last,
        MIN(spo2) AS spo2_min, AVG(spo2) AS spo2_mean,
        (array_agg(temp ORDER BY off))[cardinality(array_agg(temp ORDER BY off))] AS temp_last
    FROM vitals_f
    GROUP BY patientunitstayid
),
lab_f AS (
    SELECT l.patientunitstayid, l.labname, l.labresult::float AS val,
        l.labresultoffset AS off
    FROM eicu.lab l
    JOIN t0 ON l.patientunitstayid = t0.patientunitstayid
    WHERE l.labresult IS NOT NULL
      AND l.labresultoffset >= t0.t0
      AND l.labresultoffset < t0.t0 + 360
      AND l.labname IN (
        'lactate','creatinine','WBC x 1000','Hgb','Hct','platelets x 1000',
        'sodium','potassium','chloride','bicarbonate','glucose','calcium',
        'magnesium','phosphate','total bilirubin','albumin','BUN','anion gap')
),
lab_last AS (
    SELECT DISTINCT ON (patientunitstayid, labname)
        patientunitstayid, labname, val
    FROM lab_f
    ORDER BY patientunitstayid, labname, off DESC
),
lab_pivot AS (
    SELECT patientunitstayid,
        MAX(CASE WHEN labname='lactate' THEN val END) AS lactate_last,
        MAX(CASE WHEN labname='creatinine' THEN val END) AS creat_last,
        MAX(CASE WHEN labname='WBC x 1000' THEN val END) AS wbc_last,
        MAX(CASE WHEN labname='Hgb' THEN val END) AS hgb_last,
        MAX(CASE WHEN labname='Hct' THEN val END) AS hct_last,
        MAX(CASE WHEN labname='platelets x 1000' THEN val END) AS plt_last,
        MAX(CASE WHEN labname='sodium' THEN val END) AS na_last,
        MAX(CASE WHEN labname='potassium' THEN val END) AS k_last,
        MAX(CASE WHEN labname='chloride' THEN val END) AS cl_last,
        MAX(CASE WHEN labname='bicarbonate' THEN val END) AS hco3_last,
        MAX(CASE WHEN labname='glucose' THEN val END) AS glucose_last,
        MAX(CASE WHEN labname='calcium' THEN val END) AS ca_last,
        MAX(CASE WHEN labname='magnesium' THEN val END) AS mg_last,
        MAX(CASE WHEN labname='phosphate' THEN val END) AS phos_last,
        MAX(CASE WHEN labname='total bilirubin' THEN val END) AS bili_last,
        MAX(CASE WHEN labname='albumin' THEN val END) AS albumin_last,
        MAX(CASE WHEN labname='BUN' THEN val END) AS bun_last,
        MAX(CASE WHEN labname='anion gap' THEN val END) AS aniongap_last
    FROM lab_last
    GROUP BY patientunitstayid
),
lactate_max_agg AS (
    SELECT patientunitstayid, MAX(val) AS lactate_max
    FROM lab_f WHERE labname='lactate' GROUP BY patientunitstayid
),
nee_ord AS (
    SELECT vd.patientunitstayid, vd.infusionoffset AS off, vd.nee::float AS nee,
        LEAD(vd.infusionoffset) OVER (PARTITION BY vd.patientunitstayid
            ORDER BY vd.infusionoffset) AS next_off
    FROM eicu.e_vaso_dose vd
    JOIN t0 ON vd.patientunitstayid = t0.patientunitstayid
    WHERE vd.infusionoffset >= t0.t0
),
nee_seg AS (
    SELECT n.patientunitstayid, n.nee,
        LEAST(n.next_off, t0.t0 + 360) - n.off AS dur
    FROM nee_ord n
    JOIN t0 ON n.patientunitstayid = t0.patientunitstayid
    WHERE n.off < t0.t0 + 360 AND n.nee IS NOT NULL
),
nee_timeagg AS (
    SELECT patientunitstayid,
        SUM(nee*dur)/NULLIF(SUM(dur),0) AS nee_mean,
        SUM(CASE WHEN nee >= 0.5 THEN dur ELSE 0 END)
            /NULLIF(SUM(dur),0) AS nee_high_frac
    FROM nee_seg
    GROUP BY patientunitstayid
),
nee_simple_f AS (
    SELECT vd.patientunitstayid, vd.infusionoffset AS off, vd.nee::float AS nee
    FROM eicu.e_vaso_dose vd
    JOIN t0 ON vd.patientunitstayid = t0.patientunitstayid
    WHERE vd.infusionoffset >= t0.t0
      AND vd.infusionoffset < t0.t0 + 360
      AND vd.nee IS NOT NULL
),
nee_simple AS (
    SELECT patientunitstayid,
        (array_agg(nee ORDER BY off))[1] AS nee_first,
        (array_agg(nee ORDER BY off))[cardinality(array_agg(nee ORDER BY off))] AS nee_last,
        MIN(nee) AS nee_min, MAX(nee) AS nee_max
    FROM nee_simple_f
    GROUP BY patientunitstayid
),
vaso_agg AS (
    SELECT vd.patientunitstayid,
        (MAX(CASE WHEN vd.ne>0 THEN 1 ELSE 0 END)
        +MAX(CASE WHEN vd.epi>0 THEN 1 ELSE 0 END)
        +MAX(CASE WHEN vd.dopa>0 THEN 1 ELSE 0 END)
        +MAX(CASE WHEN vd.pe>0 THEN 1 ELSE 0 END)
        +MAX(CASE WHEN vd.vaso>0 THEN 1 ELSE 0 END)) AS n_drug,
        MAX(CASE WHEN vd.ne>0 THEN 1 ELSE 0 END) AS ne_used,
        MAX(CASE WHEN vd.pe>0 THEN 1 ELSE 0 END) AS pe_used,
        MAX(CASE WHEN vd.vaso>0 THEN 1 ELSE 0 END) AS vaso_used,
        MAX(CASE WHEN vd.epi>0 THEN 1 ELSE 0 END) AS epi_used,
        MAX(CASE WHEN vd.dopa>0 THEN 1 ELSE 0 END) AS dopa_used,
        0 AS ang2_used,
        MAX(vd.ne)::float AS ne_maxrate,
        MAX(vd.pe)::float AS pe_maxrate,
        MAX(vd.vaso)::float AS vaso_maxrate,
        MAX(vd.epi)::float AS epi_maxrate,
        MAX(vd.dopa)::float AS dopa_maxrate
    FROM eicu.e_vaso_dose vd
    JOIN t0 ON vd.patientunitstayid = t0.patientunitstayid
    WHERE vd.infusionoffset >= t0.t0
      AND vd.infusionoffset < t0.t0 + 360
    GROUP BY vd.patientunitstayid
),
fluid_agg AS (
    SELECT patientunitstayid,
        SUM(CASE WHEN cellpath LIKE '%Intake (ml)%'
                 THEN cellvaluenumeric ELSE 0 END) AS fluid_ml,
        COUNT(DISTINCT CAST(intakeoutputoffset AS varchar)
              ||'_'||CAST(cellvaluenumeric AS varchar))
            FILTER (WHERE celllabel ILIKE '%bolus%') AS n_bolus
    FROM eicu.intakeoutput
    JOIN t0 USING(patientunitstayid)
    WHERE intakeoutputoffset >= t0.t0
      AND intakeoutputoffset < t0.t0 + 360
      AND cellvaluenumeric > 0
    GROUP BY patientunitstayid
),
-- 合并症来源1: pasthistory 既往史
ph_comorb AS (
    SELECT patientunitstayid,
        MAX(CASE WHEN pasthistorypath LIKE '%Diabetes%' THEN 1 ELSE 0 END) AS diabetes,
        MAX(CASE WHEN pasthistorypath LIKE '%Hypertension Requiring Treatment%' THEN 1 ELSE 0 END) AS hypertension,
        MAX(CASE WHEN pasthistorypath LIKE '%Congestive Heart Failure%' THEN 1 ELSE 0 END) AS chf,
        MAX(CASE WHEN pasthistorypath LIKE '%Pulmonary/COPD%' THEN 1 ELSE 0 END) AS chronic_pulmonary,
        MAX(CASE WHEN pasthistorypath LIKE '%Cirrhosis%' THEN 1 ELSE 0 END) AS chronic_liver,
        MAX(CASE WHEN pasthistorypath LIKE '%Renal Failure%'
                   OR pasthistorypath LIKE '%Renal Insufficiency%' THEN 1 ELSE 0 END) AS ckd,
        MAX(CASE WHEN pasthistorypath LIKE '%Cancer/Metastases%' THEN 1 ELSE 0 END) AS metastatic_cancer,
        MAX(CASE WHEN pasthistorypath LIKE '%Arrhythmias%' THEN 1 ELSE 0 END) AS arrhythmia
    FROM eicu.pasthistory GROUP BY patientunitstayid
),
-- 合并症来源2: diagnosis 诊断
dx_comorb AS (
    SELECT patientunitstayid,
        MAX(CASE WHEN diagnosisstring LIKE '%diabetes mellitus%' THEN 1 ELSE 0 END) AS diabetes,
        MAX(CASE WHEN diagnosisstring LIKE '%vascular disorders|hypertension%' THEN 1 ELSE 0 END) AS hypertension,
        MAX(CASE WHEN diagnosisstring LIKE '%heart failure%' THEN 1 ELSE 0 END) AS chf,
        MAX(CASE WHEN diagnosisstring LIKE '%cardiovascular|arrhythmias%' THEN 1 ELSE 0 END) AS arrhythmia,
        MAX(CASE WHEN diagnosisstring LIKE '%copd%' THEN 1 ELSE 0 END) AS chronic_pulmonary,
        MAX(CASE WHEN diagnosisstring LIKE '%cirrhosis%' THEN 1 ELSE 0 END) AS chronic_liver,
        MAX(CASE WHEN diagnosisstring LIKE '%chronic kidney%' THEN 1 ELSE 0 END) AS ckd,
        MAX(CASE WHEN diagnosisstring LIKE '%metastatic%' THEN 1 ELSE 0 END) AS metastatic_cancer
    FROM eicu.diagnosis GROUP BY patientunitstayid
),
-- 合并症来源3: APACHE
ap_comorb AS (
    SELECT patientunitstayid,
        CASE WHEN diabetes=1 THEN 1 ELSE 0 END AS diabetes,
        CASE WHEN metastaticcancer=1 THEN 1 ELSE 0 END AS metastatic_cancer
    FROM eicu.apachepredvar
),
-- 三来源并集（任一来源阳性即阳性）
comorb AS (
    SELECT e.patientunitstayid,
        GREATEST(COALESCE(ph.diabetes,0),COALESCE(dx.diabetes,0),COALESCE(ap.diabetes,0)) AS diabetes,
        GREATEST(COALESCE(ph.hypertension,0),COALESCE(dx.hypertension,0)) AS hypertension,
        GREATEST(COALESCE(ph.chf,0),COALESCE(dx.chf,0)) AS chf,
        GREATEST(COALESCE(ph.chronic_pulmonary,0),COALESCE(dx.chronic_pulmonary,0)) AS chronic_pulmonary,
        GREATEST(COALESCE(ph.chronic_liver,0),COALESCE(dx.chronic_liver,0)) AS chronic_liver,
        GREATEST(COALESCE(ph.ckd,0),COALESCE(dx.ckd,0)) AS ckd,
        GREATEST(COALESCE(ph.metastatic_cancer,0),COALESCE(ap.metastatic_cancer,0),COALESCE(dx.metastatic_cancer,0)) AS metastatic_cancer,
        GREATEST(COALESCE(ph.arrhythmia,0),COALESCE(dx.arrhythmia,0)) AS arrhythmia
    FROM eligible e
    LEFT JOIN ph_comorb ph USING(patientunitstayid)
    LEFT JOIN dx_comorb dx USING(patientunitstayid)
    LEFT JOIN ap_comorb ap USING(patientunitstayid)
),
race_cu AS (
    SELECT c.patientunitstayid,
        CASE WHEN c.ethnicity ILIKE '%hispanic%' THEN 1 ELSE 0 END AS race_grp_hispanic,
        CASE WHEN c.ethnicity ILIKE '%white%'
               OR c.ethnicity ILIKE '%caucasian%' THEN 1 ELSE 0 END AS race_grp_white,
        CASE WHEN c.ethnicity NOT ILIKE '%white%'
               AND c.ethnicity NOT ILIKE '%caucasian%'
               AND c.ethnicity NOT ILIKE '%hispanic%'
               AND c.ethnicity NOT ILIKE '%african%'
               AND c.ethnicity NOT ILIKE '%black%' THEN 1 ELSE 0 END AS race_grp_other,
        CASE WHEN c.unittype IN ('MICU','Med-Surg ICU') THEN 1 ELSE 0 END AS cu_grp_micu,
        CASE WHEN c.unittype = 'SICU' THEN 1 ELSE 0 END AS cu_grp_sicu,
        CASE WHEN c.unittype = 'Neuro ICU' THEN 1 ELSE 0 END AS cu_grp_other
    FROM eicu.e_cohort c
    JOIN eligible e ON c.patientunitstayid = e.patientunitstayid
)
SELECT
    e.patientunitstayid,
    d.age, d.weight_kg,
    v.map_first, v.map_last, v.map_min, v.map_max, v.map_mean,
    v.map_sd, v.map_below65_frac,
    ns.nee_first, ns.nee_last, ns.nee_min, ns.nee_max,
    nt.nee_mean, nt.nee_high_frac,
    va.n_drug, va.ne_maxrate, va.pe_maxrate, va.vaso_maxrate,
    va.epi_maxrate, va.dopa_maxrate,
    v.hr_last, v.hr_min, v.hr_max, v.hr_mean,
    v.sbp_last, v.sbp_min, v.sbp_mean, v.dbp_last,
    v.rr_last, v.rr_mean,
    v.spo2_last, v.spo2_min, v.spo2_mean,
    v.temp_last,
    lp.lactate_last, lm.lactate_max, lp.creat_last, lp.wbc_last,
    lp.hgb_last, lp.hct_last, lp.plt_last, lp.na_last, lp.k_last,
    lp.cl_last, lp.hco3_last, lp.glucose_last, lp.ca_last, lp.mg_last,
    lp.phos_last, lp.bili_last, lp.albumin_last, lp.bun_last,
    lp.aniongap_last,
    f.n_bolus, f.fluid_ml,
    (CASE WHEN c2.gender='Male' THEN 1 ELSE 0 END) AS male,
    co.diabetes, co.hypertension, co.chf, co.chronic_pulmonary,
    co.chronic_liver, co.ckd, co.metastatic_cancer, co.arrhythmia,
    va.ne_used, va.pe_used, va.vaso_used, va.epi_used, va.dopa_used,
    va.ang2_used,
    rc.race_grp_hispanic, rc.race_grp_other, rc.race_grp_white,
    rc.cu_grp_micu, rc.cu_grp_other, rc.cu_grp_sicu
FROM eligible e
LEFT JOIN demog d        ON e.patientunitstayid = d.patientunitstayid
LEFT JOIN vitals_agg v   ON e.patientunitstayid = v.patientunitstayid
LEFT JOIN lab_pivot lp   ON e.patientunitstayid = lp.patientunitstayid
LEFT JOIN lactate_max_agg lm ON e.patientunitstayid = lm.patientunitstayid
LEFT JOIN nee_simple ns  ON e.patientunitstayid = ns.patientunitstayid
LEFT JOIN nee_timeagg nt ON e.patientunitstayid = nt.patientunitstayid
LEFT JOIN vaso_agg va    ON e.patientunitstayid = va.patientunitstayid
LEFT JOIN fluid_agg f    ON e.patientunitstayid = f.patientunitstayid
LEFT JOIN comorb co      ON e.patientunitstayid = co.patientunitstayid
LEFT JOIN race_cu rc     ON e.patientunitstayid = rc.patientunitstayid
LEFT JOIN eicu.e_cohort c2 ON e.patientunitstayid = c2.patientunitstayid
ORDER BY e.patientunitstayid;
