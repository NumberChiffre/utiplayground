from __future__ import annotations

import base64
import json
import logging
import os
from io import BytesIO
from typing import Annotated

from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import Field

from .services import (
    assess_and_plan as _assess_and_plan,
)
from .services import (
    clinical_reasoning as _clinical_reasoning,
)
from .services import (
    deep_research_diagnosis as _deep_research_diagnosis,
)
from .services import (
    follow_up_plan as _follow_up_plan,
)
from .services import (
    prescribing_considerations as _prescribing_considerations,
)
from .services import (
    safety_validation as _safety_validation,
)
from .services import (
    uti_complete_patient_assessment as _uti_complete_patient_assessment,
)
from .services import (
    web_research as _web_research,
)

load_dotenv()
logger = logging.getLogger(__name__)
mcp = FastMCP("uti-assessment-agents")


def _build_patient(
    *,
    age: int,
    sex: str,
    pregnancy_status: str,
    renal_function_summary: str,
    egfr_mL_min: float | None,
    symptoms_dysuria: bool,
    symptoms_urgency: bool,
    symptoms_frequency: bool,
    symptoms_suprapubic_pain: bool,
    symptoms_hematuria: bool,
    symptoms_confusion: bool | None = None,
    symptoms_delirium: bool | None = None,
    symptoms_gross_hematuria: bool | None = None,
    red_flags_fever: bool,
    red_flags_rigors: bool,
    red_flags_flank_pain: bool,
    red_flags_back_pain: bool | None = None,
    red_flags_nausea_vomiting: bool,
    red_flags_systemic: bool,
    history_antibiotics_last_90d: bool,
    history_allergies: list[str] | None,
    history_meds: list[str] | None,
    history_ACEI_ARB_use: bool,
    history_catheter: bool,
    history_neurogenic_bladder: bool | None,
    history_stones: bool,
    history_immunocompromised: bool,
    recurrence_relapse_within_4w: bool,
    recurrence_recurrent_6m: bool,
    recurrence_recurrent_12m: bool,
    locale_code: str,
    asymptomatic_bacteriuria: bool | None = None,
) -> dict:
    return {
        "age": age,
        "sex": sex,
        "pregnancy_status": pregnancy_status,
        "renal_function_summary": renal_function_summary,
        "egfr_mL_min": egfr_mL_min,
        "symptoms": {
            "dysuria": symptoms_dysuria,
            "urgency": symptoms_urgency,
            "frequency": symptoms_frequency,
            "suprapubic_pain": symptoms_suprapubic_pain,
            "hematuria": symptoms_hematuria,
            **(
                {"confusion": symptoms_confusion}
                if symptoms_confusion is not None
                else {}
            ),
            **(
                {"delirium": symptoms_delirium} if symptoms_delirium is not None else {}
            ),
            **(
                {"gross_hematuria": symptoms_gross_hematuria}
                if symptoms_gross_hematuria is not None
                else {}
            ),
        },
        "red_flags": {
            "fever": red_flags_fever,
            "rigors": red_flags_rigors,
            "flank_pain": red_flags_flank_pain,
            **(
                {"back_pain": red_flags_back_pain}
                if red_flags_back_pain is not None
                else {}
            ),
            "nausea_vomiting": red_flags_nausea_vomiting,
            "systemic": red_flags_systemic,
        },
        "history": {
            "antibiotics_last_90d": history_antibiotics_last_90d,
            "allergies": history_allergies or [],
            "meds": history_meds or [],
            "ACEI_ARB_use": history_ACEI_ARB_use,
            "catheter": history_catheter,
            **(
                {"neurogenic_bladder": history_neurogenic_bladder}
                if history_neurogenic_bladder is not None
                else {}
            ),
            "stones": history_stones,
            "immunocompromised": history_immunocompromised,
        },
        "recurrence": {
            "relapse_within_4w": recurrence_relapse_within_4w,
            "recurrent_6m": recurrence_recurrent_6m,
            "recurrent_12m": recurrence_recurrent_12m,
        },
        "locale_code": locale_code,
        **(
            {"asymptomatic_bacteriuria": asymptomatic_bacteriuria}
            if asymptomatic_bacteriuria is not None
            else {}
        ),
    }


def _build_recommendation(
    *,
    recommendation_regimen: str | None,
    recommendation_dose: str | None,
    recommendation_frequency: str | None,
    recommendation_duration: str | None,
    recommendation_alternatives: list[str] | None,
    recommendation_contraindications: list[str] | None,
    recommendation_monitoring: list[str] | None,
) -> dict | None:
    if not all(
        [
            recommendation_regimen,
            recommendation_dose,
            recommendation_frequency,
            recommendation_duration,
        ]
    ):
        return None
    return {
        "regimen": recommendation_regimen,
        "dose": recommendation_dose,
        "frequency": recommendation_frequency,
        "duration": recommendation_duration,
        "alternatives": recommendation_alternatives or [],
        "contraindications": recommendation_contraindications or [],
        "monitoring": recommendation_monitoring or [],
    }


@mcp.tool(
    name="clinical_reasoning",
    title="UTI Clinical Reasoning",
    description=(
        "Analyze a suspected UTI presentation and return structured clinical reasoning. "
        "Consumes flattened patient context (age, sex, renal function, symptoms, red flags, history, recurrence, locale). "
        "Produces reasoning bullets, differential diagnoses, risk factors, recommendations, stewardship notes, citations, and a confidence score. "
        "Intended for use after or alongside deterministic assessment to provide explainability and narrative for the plan. "
        "Response is a JSON string suitable for direct rendering in clients."
    ),
    tags={"uti", "reasoning", "assessment"},
    meta={
        "product": "uti-cli",
        "category": "uti",
        "version": "v1",
        "args": "flattened",
        "returns": "json_string",
    },
    enabled=True,
)
async def clinical_reasoning(
    age: Annotated[int, Field(description="Patient age in years.")],
    sex: Annotated[str, Field(description="Administrative sex for safety rules.")],
    pregnancy_status: Annotated[
        str, Field(description="Pregnancy status at time of assessment.")
    ],
    renal_function_summary: Annotated[
        str, Field(description="Clinically summarized renal function.")
    ],
    symptoms_dysuria: Annotated[
        bool, Field(description="Painful urination reported within current episode.")
    ],
    symptoms_urgency: Annotated[
        bool, Field(description="Sudden compelling need to urinate.")
    ],
    symptoms_frequency: Annotated[
        bool, Field(description="Urination frequency above normal for patient.")
    ],
    symptoms_suprapubic_pain: Annotated[
        bool, Field(description="Pain or discomfort in suprapubic area.")
    ],
    symptoms_hematuria: Annotated[
        bool, Field(description="Visible blood in urine or positive dipstick.")
    ],
    red_flags_fever: Annotated[
        bool, Field(description="Temperature ≥38°C within past 24–48h.")
    ],
    red_flags_rigors: Annotated[
        bool, Field(description="Shaking chills suggesting bacteremia.")
    ],
    red_flags_flank_pain: Annotated[
        bool, Field(description="Unilateral/bilateral flank or CVA tenderness.")
    ],
    red_flags_nausea_vomiting: Annotated[
        bool, Field(description="Nausea and/or vomiting present.")
    ],
    red_flags_systemic: Annotated[
        bool, Field(description="Signs of systemic illness or sepsis concern.")
    ],
    history_antibiotics_last_90d: Annotated[
        bool, Field(description="Any systemic antibiotic exposure within last 90 days.")
    ],
    history_ACEI_ARB_use: Annotated[
        bool,
        Field(
            description="True if ACE inhibitor or ARB used (hyperkalemia risk with TMP/SMX)."
        ),
    ],
    history_catheter: Annotated[
        bool, Field(description="Indwelling urinary catheter present.")
    ],
    history_stones: Annotated[
        bool, Field(description="Known urinary tract stones history.")
    ],
    history_immunocompromised: Annotated[
        bool, Field(description="Any condition or therapy causing immunosuppression.")
    ],
    recurrence_relapse_within_4w: Annotated[
        bool, Field(description="Return of symptoms within 4 weeks post-therapy.")
    ],
    recurrence_recurrent_6m: Annotated[
        bool, Field(description="≥2 UTIs within 6 months.")
    ],
    recurrence_recurrent_12m: Annotated[
        bool, Field(description="≥3 UTIs within 12 months.")
    ],
    locale_code: Annotated[
        str,
        Field(
            min_length=2,
            max_length=10,
            description="Region code (e.g., CA-ON) for resistance data.",
        ),
    ],
    history_allergies: Annotated[
        list[str] | None, Field(description="All reported allergies (free-text).")
    ] = None,
    history_meds: Annotated[
        list[str] | None, Field(description="Active medication list.")
    ] = None,
    egfr_mL_min: Annotated[
        float | None,
        Field(description="Optional numeric eGFR in mL/min for renal checks."),
    ] = None,
    symptoms_confusion: Annotated[
        bool,
        Field(
            description="Confusion; nonspecific symptom for referral when criteria not met."
        ),
    ] = False,
    symptoms_delirium: Annotated[
        bool,
        Field(
            description="Delirium; nonspecific symptom for referral when criteria not met."
        ),
    ] = False,
    symptoms_gross_hematuria: Annotated[
        bool,
        Field(
            description="Gross hematuria; nonspecific symptom for referral when criteria not met."
        ),
    ] = False,
    red_flags_back_pain: Annotated[
        bool, Field(description="Back pain (modifier).")
    ] = False,
    history_neurogenic_bladder: Annotated[
        bool, Field(description="Neurogenic bladder or abnormal urinary function.")
    ] = False,
    asymptomatic_bacteriuria: Annotated[
        bool,
        Field(description="Asymptomatic bacteriuria; no antibiotics per algorithm."),
    ] = False,
    model: Annotated[
        str,
        Field(description="LLM identifier used by the agents SDK (e.g., 'gpt-4.1')."),
    ] = "gpt-4.1",
) -> str:
    try:
        patient = _build_patient(
            age=age,
            sex=sex,
            pregnancy_status=pregnancy_status,
            renal_function_summary=renal_function_summary,
            egfr_mL_min=egfr_mL_min,
            symptoms_dysuria=symptoms_dysuria,
            symptoms_urgency=symptoms_urgency,
            symptoms_frequency=symptoms_frequency,
            symptoms_suprapubic_pain=symptoms_suprapubic_pain,
            symptoms_hematuria=symptoms_hematuria,
            symptoms_confusion=symptoms_confusion,
            symptoms_delirium=symptoms_delirium,
            symptoms_gross_hematuria=symptoms_gross_hematuria,
            red_flags_fever=red_flags_fever,
            red_flags_rigors=red_flags_rigors,
            red_flags_flank_pain=red_flags_flank_pain,
            red_flags_back_pain=red_flags_back_pain,
            red_flags_nausea_vomiting=red_flags_nausea_vomiting,
            red_flags_systemic=red_flags_systemic,
            history_antibiotics_last_90d=history_antibiotics_last_90d,
            history_allergies=history_allergies,
            history_meds=history_meds,
            history_ACEI_ARB_use=history_ACEI_ARB_use,
            history_catheter=history_catheter,
            history_neurogenic_bladder=history_neurogenic_bladder,
            history_stones=history_stones,
            history_immunocompromised=history_immunocompromised,
            recurrence_relapse_within_4w=recurrence_relapse_within_4w,
            recurrence_recurrent_6m=recurrence_recurrent_6m,
            recurrence_recurrent_12m=recurrence_recurrent_12m,
            locale_code=locale_code,
            asymptomatic_bacteriuria=asymptomatic_bacteriuria,
        )
        result = await _clinical_reasoning(patient, model)
        return json.dumps(result)
    except Exception as e:
        logger.error("clinical_reasoning tool failed: %s", e)
        return json.dumps({"error": "clinical_reasoning_failed", "details": str(e)})


@mcp.tool(
    name="safety_validation",
    title="UTI Safety Validation",
    description=(
        "Screen a proposed clinical decision and regimen for patient-specific safety risks. "
        "Accepts flattened patient context plus: decision (e.g., 'recommend_treatment') and optional regimen parts "
        "(regimen, dose, frequency, duration, alternatives, contraindications, monitoring). "
        "Returns contraindications, drug–drug interactions, monitoring requirements, an overall risk level, and an approval recommendation "
        "(approve/modify/reject), with concise rationale and citations when available. "
        "Response is a JSON string for downstream gating or UI display."
    ),
    tags={"uti", "safety", "pharmacology"},
    meta={
        "product": "uti-cli",
        "category": "uti",
        "version": "v1",
        "args": "flattened",
        "returns": "json_string",
    },
    enabled=True,
)
async def safety_validation(
    age: Annotated[int, Field(description="Patient age in years.")],
    sex: Annotated[str, Field(description="Administrative sex for safety rules.")],
    pregnancy_status: Annotated[
        str, Field(description="Pregnancy status at time of assessment.")
    ],
    renal_function_summary: Annotated[
        str, Field(description="Clinically summarized renal function.")
    ],
    symptoms_dysuria: Annotated[
        bool, Field(description="Painful urination reported within current episode.")
    ],
    symptoms_urgency: Annotated[
        bool, Field(description="Sudden compelling need to urinate.")
    ],
    symptoms_frequency: Annotated[
        bool, Field(description="Urination frequency above normal for patient.")
    ],
    symptoms_suprapubic_pain: Annotated[
        bool, Field(description="Pain or discomfort in suprapubic area.")
    ],
    symptoms_hematuria: Annotated[
        bool, Field(description="Visible blood in urine or positive dipstick.")
    ],
    red_flags_fever: Annotated[
        bool, Field(description="Temperature ≥38°C within past 24–48h.")
    ],
    red_flags_rigors: Annotated[
        bool, Field(description="Shaking chills suggesting bacteremia.")
    ],
    red_flags_flank_pain: Annotated[
        bool, Field(description="Unilateral/bilateral flank or CVA tenderness.")
    ],
    red_flags_nausea_vomiting: Annotated[
        bool, Field(description="Nausea and/or vomiting present.")
    ],
    red_flags_systemic: Annotated[
        bool, Field(description="Signs of systemic illness or sepsis concern.")
    ],
    history_antibiotics_last_90d: Annotated[
        bool, Field(description="Any systemic antibiotic exposure within last 90 days.")
    ],
    history_ACEI_ARB_use: Annotated[
        bool,
        Field(
            description="True if ACE inhibitor or ARB used (hyperkalemia risk with TMP/SMX)."
        ),
    ],
    history_catheter: Annotated[
        bool, Field(description="Indwelling urinary catheter present.")
    ],
    history_stones: Annotated[
        bool, Field(description="Known urinary tract stones history.")
    ],
    history_immunocompromised: Annotated[
        bool, Field(description="Any condition or therapy causing immunosuppression.")
    ],
    recurrence_relapse_within_4w: Annotated[
        bool, Field(description="Return of symptoms within 4 weeks post-therapy.")
    ],
    recurrence_recurrent_6m: Annotated[
        bool, Field(description="≥2 UTIs within 6 months.")
    ],
    recurrence_recurrent_12m: Annotated[
        bool, Field(description="≥3 UTIs within 12 months.")
    ],
    locale_code: Annotated[
        str,
        Field(
            min_length=2,
            max_length=10,
            description="Region code (e.g., CA-ON) for resistance data.",
        ),
    ],
    decision: Annotated[
        str,
        Field(
            description="Clinical decision from the assessment algorithm. Must be one of: no_antibiotics_not_met, refer_complicated, refer_recurrence, recommend_treatment."
        ),
    ],
    history_allergies: Annotated[
        list[str] | None, Field(description="All reported allergies (free-text).")
    ] = None,
    history_meds: Annotated[
        list[str] | None, Field(description="Active medication list.")
    ] = None,
    recommendation_regimen: Annotated[
        str | None,
        Field(description="Chosen agent name (e.g., 'Nitrofurantoin macrocrystals')."),
    ] = None,
    recommendation_dose: Annotated[
        str | None, Field(description="Dose string (e.g., '100 mg').")
    ] = None,
    recommendation_frequency: Annotated[
        str | None, Field(description="Dosing frequency (e.g., 'PO BID').")
    ] = None,
    recommendation_duration: Annotated[
        str | None, Field(description="Course length (e.g., '5 days').")
    ] = None,
    recommendation_alternatives: Annotated[
        list[str] | None, Field(description="Acceptable alternative regimens.")
    ] = None,
    recommendation_contraindications: Annotated[
        list[str] | None, Field(description="Notable reasons to avoid certain agents.")
    ] = None,
    recommendation_monitoring: Annotated[
        list[str] | None, Field(description="Monitoring and counseling bullets.")
    ] = None,
    egfr_mL_min: Annotated[
        float | None,
        Field(description="Optional numeric eGFR in mL/min for renal checks."),
    ] = None,
    symptoms_confusion: Annotated[
        bool,
        Field(
            description="Confusion; nonspecific symptom for referral when criteria not met."
        ),
    ] = False,
    symptoms_delirium: Annotated[
        bool,
        Field(
            description="Delirium; nonspecific symptom for referral when criteria not met."
        ),
    ] = False,
    symptoms_gross_hematuria: Annotated[
        bool,
        Field(
            description="Gross hematuria; nonspecific symptom for referral when criteria not met."
        ),
    ] = False,
    red_flags_back_pain: Annotated[
        bool, Field(description="Back pain (modifier).")
    ] = False,
    history_neurogenic_bladder: Annotated[
        bool, Field(description="Neurogenic bladder or abnormal urinary function.")
    ] = False,
    asymptomatic_bacteriuria: Annotated[
        bool,
        Field(description="Asymptomatic bacteriuria; no antibiotics per algorithm."),
    ] = False,
    model: Annotated[
        str,
        Field(description="LLM identifier used by the agents SDK (e.g., 'gpt-4.1')."),
    ] = "gpt-4.1",
) -> str:
    try:
        patient = _build_patient(
            age=age,
            sex=sex,
            pregnancy_status=pregnancy_status,
            renal_function_summary=renal_function_summary,
            egfr_mL_min=egfr_mL_min,
            symptoms_dysuria=symptoms_dysuria,
            symptoms_urgency=symptoms_urgency,
            symptoms_frequency=symptoms_frequency,
            symptoms_suprapubic_pain=symptoms_suprapubic_pain,
            symptoms_hematuria=symptoms_hematuria,
            symptoms_confusion=symptoms_confusion,
            symptoms_delirium=symptoms_delirium,
            symptoms_gross_hematuria=symptoms_gross_hematuria,
            red_flags_fever=red_flags_fever,
            red_flags_rigors=red_flags_rigors,
            red_flags_flank_pain=red_flags_flank_pain,
            red_flags_back_pain=red_flags_back_pain,
            red_flags_nausea_vomiting=red_flags_nausea_vomiting,
            red_flags_systemic=red_flags_systemic,
            history_antibiotics_last_90d=history_antibiotics_last_90d,
            history_allergies=history_allergies,
            history_meds=history_meds,
            history_ACEI_ARB_use=history_ACEI_ARB_use,
            history_catheter=history_catheter,
            history_neurogenic_bladder=history_neurogenic_bladder,
            history_stones=history_stones,
            history_immunocompromised=history_immunocompromised,
            recurrence_relapse_within_4w=recurrence_relapse_within_4w,
            recurrence_recurrent_6m=recurrence_recurrent_6m,
            recurrence_recurrent_12m=recurrence_recurrent_12m,
            locale_code=locale_code,
            asymptomatic_bacteriuria=asymptomatic_bacteriuria,
        )
        recommendation = _build_recommendation(
            recommendation_regimen=recommendation_regimen,
            recommendation_dose=recommendation_dose,
            recommendation_frequency=recommendation_frequency,
            recommendation_duration=recommendation_duration,
            recommendation_alternatives=recommendation_alternatives,
            recommendation_contraindications=recommendation_contraindications,
            recommendation_monitoring=recommendation_monitoring,
        )
        result = await _safety_validation(patient, decision, recommendation, model)
        return json.dumps(result)
    except Exception as e:
        logger.error("safety_validation tool failed: %s", e)
        return json.dumps({"error": "safety_validation_failed", "details": str(e)})


@mcp.tool(
    name="prescribing_considerations",
    title="UTI Prescribing Considerations",
    description=(
        "Provide concise, region-aware prescribing guidance to complement the assessment. "
        "Consumes flattened patient context plus region code. Returns a curated list of considerations: resistance patterns, "
        "stewardship notes, dosing caveats (e.g., renal impairment, age thresholds), and optional citations when the LLM is available. "
        "Designed for quick UI surfaces and clinician review. Response is a JSON string."
    ),
    tags={"uti", "prescribing", "resistance"},
    meta={
        "product": "uti-cli",
        "category": "uti",
        "version": "v1",
        "args": "flattened",
        "returns": "json_string",
    },
    enabled=True,
)
async def prescribing_considerations(
    age: Annotated[int, Field(description="Patient age in years.")],
    sex: Annotated[str, Field(description="Administrative sex for safety rules.")],
    pregnancy_status: Annotated[
        str, Field(description="Pregnancy status at time of assessment.")
    ],
    renal_function_summary: Annotated[
        str, Field(description="Clinically summarized renal function.")
    ],
    symptoms_dysuria: Annotated[
        bool, Field(description="Painful urination reported within current episode.")
    ],
    symptoms_urgency: Annotated[
        bool, Field(description="Sudden compelling need to urinate.")
    ],
    symptoms_frequency: Annotated[
        bool, Field(description="Urination frequency above normal for patient.")
    ],
    symptoms_suprapubic_pain: Annotated[
        bool, Field(description="Pain or discomfort in suprapubic area.")
    ],
    symptoms_hematuria: Annotated[
        bool, Field(description="Visible blood in urine or positive dipstick.")
    ],
    red_flags_fever: Annotated[
        bool, Field(description="Temperature ≥38°C within past 24–48h.")
    ],
    red_flags_rigors: Annotated[
        bool, Field(description="Shaking chills suggesting bacteremia.")
    ],
    red_flags_flank_pain: Annotated[
        bool, Field(description="Unilateral/bilateral flank or CVA tenderness.")
    ],
    red_flags_nausea_vomiting: Annotated[
        bool, Field(description="Nausea and/or vomiting present.")
    ],
    red_flags_systemic: Annotated[
        bool, Field(description="Signs of systemic illness or sepsis concern.")
    ],
    history_antibiotics_last_90d: Annotated[
        bool, Field(description="Any systemic antibiotic exposure within last 90 days.")
    ],
    history_ACEI_ARB_use: Annotated[
        bool,
        Field(
            description="True if ACE inhibitor or ARB used (hyperkalemia risk with TMP/SMX)."
        ),
    ],
    history_catheter: Annotated[
        bool, Field(description="Indwelling urinary catheter present.")
    ],
    history_stones: Annotated[
        bool, Field(description="Known urinary tract stones history.")
    ],
    history_immunocompromised: Annotated[
        bool, Field(description="Any condition or therapy causing immunosuppression.")
    ],
    recurrence_relapse_within_4w: Annotated[
        bool, Field(description="Return of symptoms within 4 weeks post-therapy.")
    ],
    recurrence_recurrent_6m: Annotated[
        bool, Field(description="≥2 UTIs within 6 months.")
    ],
    recurrence_recurrent_12m: Annotated[
        bool, Field(description="≥3 UTIs within 12 months.")
    ],
    locale_code: Annotated[
        str,
        Field(
            min_length=2,
            max_length=10,
            description="Region code (e.g., CA-ON) for resistance data.",
        ),
    ],
    region: Annotated[
        str, Field(description="Region code for resistance context (e.g., 'CA-ON').")
    ],
    history_allergies: Annotated[
        list[str] | None, Field(description="All reported allergies (free-text).")
    ] = None,
    history_meds: Annotated[
        list[str] | None, Field(description="Active medication list.")
    ] = None,
    egfr_mL_min: Annotated[
        float | None,
        Field(description="Optional numeric eGFR in mL/min for renal checks."),
    ] = None,
    symptoms_confusion: Annotated[
        bool,
        Field(
            description="Confusion; nonspecific symptom for referral when criteria not met."
        ),
    ] = False,
    symptoms_delirium: Annotated[
        bool,
        Field(
            description="Delirium; nonspecific symptom for referral when criteria not met."
        ),
    ] = False,
    symptoms_gross_hematuria: Annotated[
        bool,
        Field(
            description="Gross hematuria; nonspecific symptom for referral when criteria not met."
        ),
    ] = False,
    red_flags_back_pain: Annotated[
        bool, Field(description="Back pain (modifier).")
    ] = False,
    history_neurogenic_bladder: Annotated[
        bool, Field(description="Neurogenic bladder or abnormal urinary function.")
    ] = False,
    asymptomatic_bacteriuria: Annotated[
        bool,
        Field(description="Asymptomatic bacteriuria; no antibiotics per algorithm."),
    ] = False,
    model: Annotated[
        str,
        Field(description="LLM identifier used by the agents SDK (e.g., 'gpt-4.1')."),
    ] = "gpt-4.1",
) -> str:
    try:
        patient = _build_patient(
            age=age,
            sex=sex,
            pregnancy_status=pregnancy_status,
            renal_function_summary=renal_function_summary,
            egfr_mL_min=egfr_mL_min,
            symptoms_dysuria=symptoms_dysuria,
            symptoms_urgency=symptoms_urgency,
            symptoms_frequency=symptoms_frequency,
            symptoms_suprapubic_pain=symptoms_suprapubic_pain,
            symptoms_hematuria=symptoms_hematuria,
            symptoms_confusion=symptoms_confusion,
            symptoms_delirium=symptoms_delirium,
            symptoms_gross_hematuria=symptoms_gross_hematuria,
            red_flags_fever=red_flags_fever,
            red_flags_rigors=red_flags_rigors,
            red_flags_flank_pain=red_flags_flank_pain,
            red_flags_back_pain=red_flags_back_pain,
            red_flags_nausea_vomiting=red_flags_nausea_vomiting,
            red_flags_systemic=red_flags_systemic,
            history_antibiotics_last_90d=history_antibiotics_last_90d,
            history_allergies=history_allergies,
            history_meds=history_meds,
            history_ACEI_ARB_use=history_ACEI_ARB_use,
            history_catheter=history_catheter,
            history_neurogenic_bladder=history_neurogenic_bladder,
            history_stones=history_stones,
            history_immunocompromised=history_immunocompromised,
            recurrence_relapse_within_4w=recurrence_relapse_within_4w,
            recurrence_recurrent_6m=recurrence_recurrent_6m,
            recurrence_recurrent_12m=recurrence_recurrent_12m,
            locale_code=locale_code,
            asymptomatic_bacteriuria=asymptomatic_bacteriuria,
        )
        result = await _prescribing_considerations(patient, region, model)
        return json.dumps(result)
    except Exception as e:
        logger.error("prescribing_considerations tool failed: %s", e)
        return json.dumps(
            {"error": "prescribing_considerations_failed", "details": str(e)}
        )


@mcp.tool(
    name="research_summary",
    title="UTI Research Summary",
    description=(
        "Summarize current evidence, guidelines, and resistance context for a focused query and region. "
        "Accepts a natural-language query and a region code. Returns a concise narrative with citations suitable for side panels or notes. "
        "Intended for just-in-time evidence lookup during assessment or counseling. Response is a JSON string."
    ),
    tags={"uti", "research", "guidelines"},
    meta={
        "product": "uti-cli",
        "category": "uti",
        "version": "v1",
        "args": "flattened",
        "returns": "json_string",
    },
    enabled=True,
)
async def research_summary(
    query: Annotated[
        str, Field(description="Focused clinical question for evidence lookup.")
    ],
    region: Annotated[
        str,
        Field(
            description="Region code for resistance and guidelines context (e.g., 'CA-ON')."
        ),
    ],
    model: Annotated[
        str,
        Field(description="LLM identifier used by the agents SDK (e.g., 'gpt-4.1')."),
    ] = "gpt-4.1",
) -> str:
    """Run focused research to summarize current guidelines and resistance for a query and region.

    Inputs
    - query: Focused clinical question.
    - region: Region code for resistance and guideline context.
    - model: LLM identifier used by the underlying agents SDK.

    Returns
    - JSON string with keys: summary, region, citations[], model
    """
    try:
        result = await _web_research(query, region, model)
        return json.dumps(result)
    except Exception as e:
        logger.error("research_summary tool failed: %s", e)
        return json.dumps({"error": "research_summary_failed", "details": str(e)})


@mcp.tool(
    name="deep_research_diagnosis",
    title="UTI Research Diagnosis",
    description=(
        "Generate a provider-ready clinical diagnosis and treatment brief using multi-agent research. "
        "Consumes flattened patient context and returns a Markdown diagnosis with citations, plus the structured assessment context. "
        "Best used for complex or educational cases where an expanded rationale and evidence trail are desired. "
        "Response is a JSON string containing the diagnosis, citations, and related metadata."
    ),
    tags={"uti", "diagnosis", "research"},
    meta={
        "product": "uti-cli",
        "category": "uti",
        "version": "v1",
        "args": "flattened",
        "returns": "json_string",
    },
    enabled=True,
)
async def deep_research_diagnosis(
    age: Annotated[int, Field(description="Patient age in years.")],
    sex: Annotated[str, Field(description="Administrative sex for safety rules.")],
    pregnancy_status: Annotated[
        str, Field(description="Pregnancy status at time of assessment.")
    ],
    renal_function_summary: Annotated[
        str, Field(description="Clinically summarized renal function.")
    ],
    symptoms_dysuria: Annotated[
        bool, Field(description="Painful urination reported within current episode.")
    ],
    symptoms_urgency: Annotated[
        bool, Field(description="Sudden compelling need to urinate.")
    ],
    symptoms_frequency: Annotated[
        bool, Field(description="Urination frequency above normal for patient.")
    ],
    symptoms_suprapubic_pain: Annotated[
        bool, Field(description="Pain or discomfort in suprapubic area.")
    ],
    symptoms_hematuria: Annotated[
        bool, Field(description="Visible blood in urine or positive dipstick.")
    ],
    red_flags_fever: Annotated[
        bool, Field(description="Temperature ≥38°C within past 24–48h.")
    ],
    red_flags_rigors: Annotated[
        bool, Field(description="Shaking chills suggesting bacteremia.")
    ],
    red_flags_flank_pain: Annotated[
        bool, Field(description="Unilateral/bilateral flank or CVA tenderness.")
    ],
    red_flags_nausea_vomiting: Annotated[
        bool, Field(description="Nausea and/or vomiting present.")
    ],
    red_flags_systemic: Annotated[
        bool, Field(description="Signs of systemic illness or sepsis concern.")
    ],
    history_antibiotics_last_90d: Annotated[
        bool, Field(description="Any systemic antibiotic exposure within last 90 days.")
    ],
    history_ACEI_ARB_use: Annotated[
        bool,
        Field(
            description="True if ACE inhibitor or ARB used (hyperkalemia risk with TMP/SMX)."
        ),
    ],
    history_catheter: Annotated[
        bool, Field(description="Indwelling urinary catheter present.")
    ],
    history_stones: Annotated[
        bool, Field(description="Known urinary tract stones history.")
    ],
    history_immunocompromised: Annotated[
        bool, Field(description="Any condition or therapy causing immunosuppression.")
    ],
    recurrence_relapse_within_4w: Annotated[
        bool, Field(description="Return of symptoms within 4 weeks post-therapy.")
    ],
    recurrence_recurrent_6m: Annotated[
        bool, Field(description="≥2 UTIs within 6 months.")
    ],
    recurrence_recurrent_12m: Annotated[
        bool, Field(description="≥3 UTIs within 12 months.")
    ],
    locale_code: Annotated[
        str,
        Field(
            min_length=2,
            max_length=10,
            description="Region code (e.g., CA-ON) for resistance data.",
        ),
    ],
    history_allergies: Annotated[
        list[str] | None, Field(description="All reported allergies (free-text).")
    ] = None,
    history_meds: Annotated[
        list[str] | None, Field(description="Active medication list.")
    ] = None,
    egfr_mL_min: Annotated[
        float | None,
        Field(description="Optional numeric eGFR in mL/min for renal checks."),
    ] = None,
    symptoms_confusion: Annotated[
        bool,
        Field(
            description="Confusion; nonspecific symptom for referral when criteria not met."
        ),
    ] = False,
    symptoms_delirium: Annotated[
        bool,
        Field(
            description="Delirium; nonspecific symptom for referral when criteria not met."
        ),
    ] = False,
    symptoms_gross_hematuria: Annotated[
        bool,
        Field(
            description="Gross hematuria; nonspecific symptom for referral when criteria not met."
        ),
    ] = False,
    red_flags_back_pain: Annotated[
        bool, Field(description="Back pain (modifier).")
    ] = False,
    history_neurogenic_bladder: Annotated[
        bool, Field(description="Neurogenic bladder or abnormal urinary function.")
    ] = False,
    asymptomatic_bacteriuria: Annotated[
        bool,
        Field(description="Asymptomatic bacteriuria; no antibiotics per algorithm."),
    ] = False,
    model: Annotated[
        str,
        Field(description="LLM identifier used by the agents SDK (e.g., 'gpt-4.1')."),
    ] = "gpt-4.1",
) -> str:
    """Generate a provider-ready diagnosis and treatment brief using multi-agent research.

    Inputs
    - patient: Complete `PatientState`.
    - model: LLM identifier used by the underlying agents SDK.

    Returns
    - JSON string with keys: diagnosis (Markdown), citations[], model, assessment
    """
    try:
        patient = _build_patient(
            age=age,
            sex=sex,
            pregnancy_status=pregnancy_status,
            renal_function_summary=renal_function_summary,
            egfr_mL_min=egfr_mL_min,
            symptoms_dysuria=symptoms_dysuria,
            symptoms_urgency=symptoms_urgency,
            symptoms_frequency=symptoms_frequency,
            symptoms_suprapubic_pain=symptoms_suprapubic_pain,
            symptoms_hematuria=symptoms_hematuria,
            symptoms_confusion=symptoms_confusion,
            symptoms_delirium=symptoms_delirium,
            symptoms_gross_hematuria=symptoms_gross_hematuria,
            red_flags_fever=red_flags_fever,
            red_flags_rigors=red_flags_rigors,
            red_flags_flank_pain=red_flags_flank_pain,
            red_flags_back_pain=red_flags_back_pain,
            red_flags_nausea_vomiting=red_flags_nausea_vomiting,
            red_flags_systemic=red_flags_systemic,
            history_antibiotics_last_90d=history_antibiotics_last_90d,
            history_allergies=history_allergies,
            history_meds=history_meds,
            history_ACEI_ARB_use=history_ACEI_ARB_use,
            history_catheter=history_catheter,
            history_neurogenic_bladder=history_neurogenic_bladder,
            history_stones=history_stones,
            history_immunocompromised=history_immunocompromised,
            recurrence_relapse_within_4w=recurrence_relapse_within_4w,
            recurrence_recurrent_6m=recurrence_recurrent_6m,
            recurrence_recurrent_12m=recurrence_recurrent_12m,
            locale_code=locale_code,
            asymptomatic_bacteriuria=asymptomatic_bacteriuria,
        )
        result = await _deep_research_diagnosis(patient, model)
        return json.dumps(result)
    except Exception as e:
        logger.error("deep_research_diagnosis tool failed: %s", e)
        return json.dumps(
            {"error": "deep_research_diagnosis_failed", "details": str(e)}
        )


@mcp.tool(
    name="uti_complete_patient_assessment",
    title="UTI Complete Patient Assessment",
    description=(
        "Run the full orchestrated UTI assessment with safety gates, reasoning, validation, evidence, and diagnosis. "
        "Consumes flattened patient context and returns a consolidated output with assessment, clinical reasoning, safety validation, "
        "validator snapshot, prescribing considerations, research summary, diagnosis, follow-up (if applicable), and an audit bundle. "
        "Response is a JSON string."
    ),
    tags={"uti", "orchestration", "assessment"},
    meta={
        "product": "uti-cli",
        "category": "uti",
        "version": "v1",
        "args": "flattened",
        "returns": "json_string",
    },
    enabled=True,
)
async def uti_complete_patient_assessment(
    age: Annotated[int, Field(description="Patient age in years.")],
    sex: Annotated[str, Field(description="Administrative sex for safety rules.")],
    pregnancy_status: Annotated[
        str, Field(description="Pregnancy status at time of assessment.")
    ],
    renal_function_summary: Annotated[
        str, Field(description="Clinically summarized renal function.")
    ],
    locale_code: Annotated[
        str,
        Field(
            min_length=2,
            max_length=10,
            description="Region code (e.g., CA-ON) for resistance data.",
        ),
    ],
    symptoms_dysuria: Annotated[
        bool, Field(description="Painful urination reported within current episode.")
    ],
    symptoms_urgency: Annotated[
        bool, Field(description="Sudden compelling need to urinate.")
    ],
    symptoms_frequency: Annotated[
        bool, Field(description="Urination frequency above normal for patient.")
    ],
    symptoms_suprapubic_pain: Annotated[
        bool, Field(description="Pain or discomfort in suprapubic area.")
    ],
    symptoms_hematuria: Annotated[
        bool, Field(description="Visible blood in urine or positive dipstick.")
    ],
    red_flags_fever: Annotated[
        bool, Field(description="Temperature ≥38°C within past 24–48h.")
    ],
    red_flags_rigors: Annotated[
        bool, Field(description="Shaking chills suggesting bacteremia.")
    ],
    red_flags_flank_pain: Annotated[
        bool, Field(description="Unilateral/bilateral flank or CVA tenderness.")
    ],
    red_flags_nausea_vomiting: Annotated[
        bool, Field(description="Nausea and/or vomiting present.")
    ],
    red_flags_systemic: Annotated[
        bool, Field(description="Signs of systemic illness or sepsis concern.")
    ],
    history_antibiotics_last_90d: Annotated[
        bool, Field(description="Any systemic antibiotic exposure within last 90 days.")
    ],
    history_ACEI_ARB_use: Annotated[
        bool,
        Field(
            description="True if ACE inhibitor or ARB used (hyperkalemia risk with TMP/SMX)."
        ),
    ],
    history_catheter: Annotated[
        bool, Field(description="Indwelling urinary catheter present.")
    ],
    history_stones: Annotated[
        bool, Field(description="Known urinary tract stones history.")
    ],
    history_immunocompromised: Annotated[
        bool, Field(description="Any condition or therapy causing immunosuppression.")
    ],
    recurrence_relapse_within_4w: Annotated[
        bool, Field(description="Return of symptoms within 4 weeks post-therapy.")
    ],
    recurrence_recurrent_6m: Annotated[
        bool, Field(description="≥2 UTIs within 6 months.")
    ],
    recurrence_recurrent_12m: Annotated[
        bool, Field(description="≥3 UTIs within 12 months.")
    ],
    egfr_mL_min: Annotated[
        float | None,
        Field(description="Optional numeric eGFR in mL/min for renal checks."),
    ] = None,
    symptoms_confusion: Annotated[
        bool,
        Field(
            description="Confusion; nonspecific symptom for referral when criteria not met."
        ),
    ] = False,
    symptoms_delirium: Annotated[
        bool,
        Field(
            description="Delirium; nonspecific symptom for referral when criteria not met."
        ),
    ] = False,
    symptoms_gross_hematuria: Annotated[
        bool,
        Field(
            description="Gross hematuria; nonspecific symptom for referral when criteria not met."
        ),
    ] = False,
    red_flags_back_pain: Annotated[
        bool, Field(description="Back pain (modifier).")
    ] = False,
    history_neurogenic_bladder: Annotated[
        bool, Field(description="Neurogenic bladder or abnormal urinary function.")
    ] = False,
    asymptomatic_bacteriuria: Annotated[
        bool,
        Field(description="Asymptomatic bacteriuria; no antibiotics per algorithm."),
    ] = False,
    history_allergies: Annotated[
        list[str] | None, Field(description="All reported allergies (free-text).")
    ] = None,
    history_meds: Annotated[
        list[str] | None, Field(description="Active medication list.")
    ] = None,
    model: Annotated[
        str,
        Field(description="LLM identifier used by the agents SDK (e.g., 'gpt-4.1')."),
    ] = "gpt-4.1",
) -> str:
    try:
        patient = _build_patient(
            age=age,
            sex=sex,
            pregnancy_status=pregnancy_status,
            renal_function_summary=renal_function_summary,
            egfr_mL_min=egfr_mL_min,
            symptoms_dysuria=symptoms_dysuria,
            symptoms_urgency=symptoms_urgency,
            symptoms_frequency=symptoms_frequency,
            symptoms_suprapubic_pain=symptoms_suprapubic_pain,
            symptoms_hematuria=symptoms_hematuria,
            symptoms_confusion=symptoms_confusion,
            symptoms_delirium=symptoms_delirium,
            symptoms_gross_hematuria=symptoms_gross_hematuria,
            red_flags_fever=red_flags_fever,
            red_flags_rigors=red_flags_rigors,
            red_flags_flank_pain=red_flags_flank_pain,
            red_flags_back_pain=red_flags_back_pain,
            red_flags_nausea_vomiting=red_flags_nausea_vomiting,
            red_flags_systemic=red_flags_systemic,
            history_antibiotics_last_90d=history_antibiotics_last_90d,
            history_allergies=history_allergies,
            history_meds=history_meds,
            history_ACEI_ARB_use=history_ACEI_ARB_use,
            history_catheter=history_catheter,
            history_neurogenic_bladder=history_neurogenic_bladder,
            history_stones=history_stones,
            history_immunocompromised=history_immunocompromised,
            recurrence_relapse_within_4w=recurrence_relapse_within_4w,
            recurrence_recurrent_6m=recurrence_recurrent_6m,
            recurrence_recurrent_12m=recurrence_recurrent_12m,
            locale_code=locale_code,
            asymptomatic_bacteriuria=asymptomatic_bacteriuria,
        )
        result = await _uti_complete_patient_assessment(patient, model)
        return json.dumps(result)
    except Exception as e:
        logger.error("uti_complete_patient_assessment tool failed: %s", e)
        return json.dumps(
            {"error": "uti_complete_patient_assessment_failed", "details": str(e)}
        )


@mcp.tool(
    name="assess_and_plan",
    title="UTI Assess & Plan",
    description=(
        "Execute the deterministic UTI assessment algorithm and return the plan of care. "
        "Consumes flattened patient context and returns: decision (route), recommendation (if applicable), rationale bullets, "
        "follow-up (when indicated), and an audit snapshot. This is non-LLM logic that encodes the prescribing algorithm. "
        "Response is a JSON string aligned with the AssessmentOutput contract."
    ),
    tags={"uti", "algorithm", "assessment"},
    meta={
        "product": "uti-cli",
        "category": "uti",
        "version": "v1",
        "args": "flattened",
        "returns": "json_string",
    },
    enabled=True,
)
async def assess_and_plan(
    age: Annotated[int, Field(description="Patient age in years.")],
    sex: Annotated[str, Field(description="Administrative sex for safety rules.")],
    pregnancy_status: Annotated[
        str, Field(description="Pregnancy status at time of assessment.")
    ],
    renal_function_summary: Annotated[
        str, Field(description="Clinically summarized renal function.")
    ],
    locale_code: Annotated[
        str,
        Field(
            min_length=2,
            max_length=10,
            description="Region code (e.g., CA-ON) for resistance data.",
        ),
    ],
    symptoms_dysuria: Annotated[
        bool, Field(description="Painful urination reported within current episode.")
    ],
    symptoms_urgency: Annotated[
        bool, Field(description="Sudden compelling need to urinate.")
    ],
    symptoms_frequency: Annotated[
        bool, Field(description="Urination frequency above normal for patient.")
    ],
    symptoms_suprapubic_pain: Annotated[
        bool, Field(description="Pain or discomfort in suprapubic area.")
    ],
    symptoms_hematuria: Annotated[
        bool, Field(description="Visible blood in urine or positive dipstick.")
    ],
    red_flags_fever: Annotated[
        bool, Field(description="Temperature ≥38°C within past 24–48h.")
    ],
    red_flags_rigors: Annotated[
        bool, Field(description="Shaking chills suggesting bacteremia.")
    ],
    red_flags_flank_pain: Annotated[
        bool, Field(description="Unilateral/bilateral flank or CVA tenderness.")
    ],
    red_flags_nausea_vomiting: Annotated[
        bool, Field(description="Nausea and/or vomiting present.")
    ],
    red_flags_systemic: Annotated[
        bool, Field(description="Signs of systemic illness or sepsis concern.")
    ],
    history_antibiotics_last_90d: Annotated[
        bool, Field(description="Any systemic antibiotic exposure within last 90 days.")
    ],
    history_ACEI_ARB_use: Annotated[
        bool,
        Field(
            description="True if ACE inhibitor or ARB used (hyperkalemia risk with TMP/SMX)."
        ),
    ],
    history_catheter: Annotated[
        bool, Field(description="Indwelling urinary catheter present.")
    ],
    history_stones: Annotated[
        bool, Field(description="Known urinary tract stones history.")
    ],
    history_immunocompromised: Annotated[
        bool, Field(description="Any condition or therapy causing immunosuppression.")
    ],
    recurrence_relapse_within_4w: Annotated[
        bool, Field(description="Return of symptoms within 4 weeks post-therapy.")
    ],
    recurrence_recurrent_6m: Annotated[
        bool, Field(description="≥2 UTIs within 6 months.")
    ],
    recurrence_recurrent_12m: Annotated[
        bool, Field(description="≥3 UTIs within 12 months.")
    ],
    egfr_mL_min: Annotated[
        float | None,
        Field(description="Optional numeric eGFR in mL/min for renal checks."),
    ] = None,
    symptoms_confusion: Annotated[
        bool,
        Field(
            description="Confusion; nonspecific symptom for referral when criteria not met."
        ),
    ] = False,
    symptoms_delirium: Annotated[
        bool,
        Field(
            description="Delirium; nonspecific symptom for referral when criteria not met."
        ),
    ] = False,
    symptoms_gross_hematuria: Annotated[
        bool,
        Field(
            description="Gross hematuria; nonspecific symptom for referral when criteria not met."
        ),
    ] = False,
    red_flags_back_pain: Annotated[
        bool, Field(description="Back pain (modifier).")
    ] = False,
    history_neurogenic_bladder: Annotated[
        bool, Field(description="Neurogenic bladder or abnormal urinary function.")
    ] = False,
    asymptomatic_bacteriuria: Annotated[
        bool,
        Field(description="Asymptomatic bacteriuria; no antibiotics per algorithm."),
    ] = False,
) -> str:
    """Execute the deterministic UTI assessment algorithm to produce a plan.

    Inputs
    - patient: Complete `PatientState`.

    Returns
    - JSON string matching `AssessmentOutput`: decision, recommendation?, rationale[], follow_up?, audit, version
    """
    try:
        patient = _build_patient(
            age=age,
            sex=sex,
            pregnancy_status=pregnancy_status,
            renal_function_summary=renal_function_summary,
            egfr_mL_min=egfr_mL_min,
            symptoms_dysuria=symptoms_dysuria,
            symptoms_urgency=symptoms_urgency,
            symptoms_frequency=symptoms_frequency,
            symptoms_suprapubic_pain=symptoms_suprapubic_pain,
            symptoms_hematuria=symptoms_hematuria,
            symptoms_confusion=symptoms_confusion,
            symptoms_delirium=symptoms_delirium,
            symptoms_gross_hematuria=symptoms_gross_hematuria,
            red_flags_fever=red_flags_fever,
            red_flags_rigors=red_flags_rigors,
            red_flags_flank_pain=red_flags_flank_pain,
            red_flags_back_pain=red_flags_back_pain,
            red_flags_nausea_vomiting=red_flags_nausea_vomiting,
            red_flags_systemic=red_flags_systemic,
            history_antibiotics_last_90d=history_antibiotics_last_90d,
            history_allergies=None,
            history_meds=None,
            history_ACEI_ARB_use=history_ACEI_ARB_use,
            history_catheter=history_catheter,
            history_neurogenic_bladder=history_neurogenic_bladder,
            history_stones=history_stones,
            history_immunocompromised=history_immunocompromised,
            recurrence_relapse_within_4w=recurrence_relapse_within_4w,
            recurrence_recurrent_6m=recurrence_recurrent_6m,
            recurrence_recurrent_12m=recurrence_recurrent_12m,
            locale_code=locale_code,
            asymptomatic_bacteriuria=asymptomatic_bacteriuria,
        )
        result = await _assess_and_plan(patient)
        return json.dumps(result)
    except Exception as e:
        logger.error("assess_and_plan tool failed: %s", e)
        return json.dumps({"error": "assess_and_plan_failed", "details": str(e)})


@mcp.tool(
    name="follow_up_plan",
    title="UTI 72-hour Follow-up Plan",
    description=(
        "Return a standardized 72-hour follow-up plan tailored to the patient's risk profile. "
        "Consumes flattened patient context and produces a monitoring checklist, special instructions (e.g., age ≥65, ACEI/ARB use, renal impairment), "
        "and provider action items. Designed for discharge instructions and safety callbacks. Response is a JSON string."
    ),
    tags={"uti", "follow_up", "plan"},
    meta={
        "product": "uti-cli",
        "category": "uti",
        "version": "v1",
        "args": "flattened",
        "returns": "json_string",
    },
    enabled=True,
)
async def follow_up_plan(
    age: Annotated[int, Field(description="Patient age in years.")],
    sex: Annotated[str, Field(description="Administrative sex for safety rules.")],
    pregnancy_status: Annotated[
        str, Field(description="Pregnancy status at time of assessment.")
    ],
    renal_function_summary: Annotated[
        str, Field(description="Clinically summarized renal function.")
    ],
    locale_code: Annotated[
        str,
        Field(
            min_length=2,
            max_length=10,
            description="Region code (e.g., CA-ON) for resistance data.",
        ),
    ],
    symptoms_dysuria: Annotated[
        bool, Field(description="Painful urination reported within current episode.")
    ],
    symptoms_urgency: Annotated[
        bool, Field(description="Sudden compelling need to urinate.")
    ],
    symptoms_frequency: Annotated[
        bool, Field(description="Urination frequency above normal for patient.")
    ],
    symptoms_suprapubic_pain: Annotated[
        bool, Field(description="Pain or discomfort in suprapubic area.")
    ],
    symptoms_hematuria: Annotated[
        bool, Field(description="Visible blood in urine or positive dipstick.")
    ],
    red_flags_fever: Annotated[
        bool, Field(description="Temperature ≥38°C within past 24–48h.")
    ],
    red_flags_rigors: Annotated[
        bool, Field(description="Shaking chills suggesting bacteremia.")
    ],
    red_flags_flank_pain: Annotated[
        bool, Field(description="Unilateral/bilateral flank or CVA tenderness.")
    ],
    red_flags_nausea_vomiting: Annotated[
        bool, Field(description="Nausea and/or vomiting present.")
    ],
    red_flags_systemic: Annotated[
        bool, Field(description="Signs of systemic illness or sepsis concern.")
    ],
    history_antibiotics_last_90d: Annotated[
        bool, Field(description="Any systemic antibiotic exposure within last 90 days.")
    ],
    history_ACEI_ARB_use: Annotated[
        bool,
        Field(
            description="True if ACE inhibitor or ARB used (hyperkalemia risk with TMP/SMX)."
        ),
    ],
    history_catheter: Annotated[
        bool, Field(description="Indwelling urinary catheter present.")
    ],
    history_stones: Annotated[
        bool, Field(description="Known urinary tract stones history.")
    ],
    history_immunocompromised: Annotated[
        bool, Field(description="Any condition or therapy causing immunosuppression.")
    ],
    recurrence_relapse_within_4w: Annotated[
        bool, Field(description="Return of symptoms within 4 weeks post-therapy.")
    ],
    recurrence_recurrent_6m: Annotated[
        bool, Field(description="≥2 UTIs within 6 months.")
    ],
    recurrence_recurrent_12m: Annotated[
        bool, Field(description="≥3 UTIs within 12 months.")
    ],
) -> str:
    """Return the standardized 72-hour follow-up plan tailored to the patient.

    Inputs
    - patient: Complete `PatientState`.

    Returns
    - JSON string with follow_up_plan, monitoring_checklist, special_instructions[], provider_actions[]
    """
    try:
        patient = _build_patient(
            age=age,
            sex=sex,
            pregnancy_status=pregnancy_status,
            renal_function_summary=renal_function_summary,
            symptoms_dysuria=symptoms_dysuria,
            symptoms_urgency=symptoms_urgency,
            symptoms_frequency=symptoms_frequency,
            symptoms_suprapubic_pain=symptoms_suprapubic_pain,
            symptoms_hematuria=symptoms_hematuria,
            red_flags_fever=red_flags_fever,
            red_flags_rigors=red_flags_rigors,
            red_flags_flank_pain=red_flags_flank_pain,
            red_flags_nausea_vomiting=red_flags_nausea_vomiting,
            red_flags_systemic=red_flags_systemic,
            history_antibiotics_last_90d=history_antibiotics_last_90d,
            history_allergies=None,
            history_meds=None,
            history_ACEI_ARB_use=history_ACEI_ARB_use,
            history_catheter=history_catheter,
            history_stones=history_stones,
            history_immunocompromised=history_immunocompromised,
            recurrence_relapse_within_4w=recurrence_relapse_within_4w,
            recurrence_recurrent_6m=recurrence_recurrent_6m,
            recurrence_recurrent_12m=recurrence_recurrent_12m,
            locale_code=locale_code,
        )
        result = await _follow_up_plan(patient)
        return json.dumps(result)
    except Exception as e:
        logger.error("follow_up_plan tool failed: %s", e)
        return json.dumps({"error": "follow_up_plan_failed", "details": str(e)})


@mcp.tool(
    name="ocr_extract_pdf",
    title="OCR Extract PDF Text",
    description=(
        "Extract full text from PDF documents. Provide a file path, a base64-encoded PDF, "
        "or leave blank to read all PDFs under uti-cli/data. Returns a JSON string with text per file."
    ),
    tags={"ocr", "pdf", "ingestion"},
    meta={
        "product": "uti-cli",
        "category": "utilities",
        "version": "v1",
        "args": "path|base64|none",
        "returns": "json_string",
    },
    enabled=True,
)
async def ocr_extract_pdf(
    file_path: Annotated[
        str | None,
        Field(description="Absolute or workspace-relative path to a PDF file."),
    ] = None,
    file_base64: Annotated[
        str | None, Field(description="Base64-encoded PDF content.")
    ] = None,
    ocr: Annotated[
        bool,
        Field(description="If true, OCR is attempted when little or no text is found."),
    ] = True,
) -> str:
    try:
        result = await _ocr_extract_pdf_impl(
            file_path=file_path, file_base64=file_base64, force_ocr=ocr
        )
        return json.dumps(result)
    except Exception as e:
        logger.error("ocr_extract_pdf tool failed: %s", e)
        return json.dumps({"error": "ocr_extract_pdf_failed", "details": str(e)})


async def _ocr_extract_pdf_impl(
    *, file_path: str | None, file_base64: str | None, force_ocr: bool
) -> dict:
    try:
        from pypdf import PdfReader  # Lazy import
    except Exception as e:
        return {"error": "dependency_missing", "details": f"pypdf not available: {e}"}

    results: dict[str, str] = {}
    warnings: list[str] = []

    if file_base64:
        try:
            pdf_bytes = base64.b64decode(file_base64)
            reader = PdfReader(BytesIO(pdf_bytes))
            extracted: list[str] = []
            page_texts: list[str] = []
            for page in reader.pages:
                try:
                    txt = page.extract_text() or ""
                except Exception:
                    txt = ""
                page_texts.append(txt)
            extracted_text = "\n".join(page_texts).strip()
            if (force_ocr and len(extracted_text) < 16) or (
                not extracted_text and force_ocr
            ):
                ocr_text = await _ocr_pdf_bytes(pdf_bytes, warnings)
                extracted_text = ocr_text if ocr_text is not None else extracted_text
            results["uploaded.pdf"] = extracted_text
        except Exception as e:
            return {"error": "invalid_base64", "details": str(e)}

    paths_to_read: list[str] = []

    if file_path:
        abs_path = file_path
        if not os.path.isabs(abs_path):
            abs_path = os.path.abspath(abs_path)
        paths_to_read.append(abs_path)
    elif not file_base64:
        data_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "data")
        )
        if os.path.isdir(data_dir):
            for name in os.listdir(data_dir):
                if name.lower().endswith(".pdf"):
                    paths_to_read.append(os.path.join(data_dir, name))

    for path in paths_to_read:
        try:
            if not os.path.isfile(path):
                results[path] = ""
                continue
            with open(path, "rb") as f:
                reader = PdfReader(f)
                page_texts: list[str] = []
                for page in reader.pages:
                    try:
                        txt = page.extract_text() or ""
                    except Exception:
                        txt = ""
                    page_texts.append(txt)
            combined = "\n".join(page_texts).strip()
            if (force_ocr and len(combined) < 16) or (not combined and force_ocr):
                try:
                    with open(path, "rb") as fb:
                        pdf_bytes = fb.read()
                    ocr_text = await _ocr_pdf_bytes(pdf_bytes, warnings)
                    combined = ocr_text if ocr_text is not None else combined
                except Exception as e:
                    logger.error("OCR fallback failed for %s: %s", path, e)
            results[path] = combined
        except Exception as e:
            results[path] = ""
            logger.error("Failed to read PDF %s: %s", path, e)

    out: dict = {"files": results}
    if warnings:
        out["warnings"] = warnings
    return out


async def _ocr_pdf_bytes(pdf_bytes: bytes, warnings: list[str]) -> str | None:
    try:
        import pypdfium2 as pdfium  # type: ignore
    except Exception as e:
        warnings.append(f"pypdfium2 unavailable: {e}")
        return None
    try:
        import pytesseract  # type: ignore
    except Exception as e:
        warnings.append(f"pytesseract/Pillow unavailable: {e}")
        return None

    try:
        pdf = pdfium.PdfDocument(BytesIO(pdf_bytes))
        ocr_texts: list[str] = []
        for i in range(len(pdf)):
            try:
                page = pdf[i]
                bitmap = page.render(scale=2.0).to_pil()
                text = pytesseract.image_to_string(bitmap)
                ocr_texts.append(text.strip())
            except Exception as e:
                warnings.append(f"OCR failed on page {i + 1}: {e}")
                ocr_texts.append("")
        return "\n".join(ocr_texts).strip()
    except Exception as e:
        warnings.append(f"OCR pipeline error: {e}")
        return None


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
