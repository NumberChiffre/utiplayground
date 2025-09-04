from __future__ import annotations

import json

from .models import AssessmentOutput, PatientState

SYSTEM_ROLE_CLINICAL_REASONING = """You are an expert clinical pharmacist and infectious disease specialist providing clinical decision support for UTI assessment and treatment planning."""

SYSTEM_ROLE_SAFETY = """You are a clinical medication safety specialist responsible for identifying contraindications, drug interactions, and safety considerations for antimicrobial therapy."""

SYSTEM_ROLE_WEB_RESEARCH = """You are a clinical research assistant providing evidence-based medical information with focus on current antimicrobial resistance patterns and treatment guidelines. Prioritize Canadian (Canada-wide) and Ontario (CA-ON) sources, guidelines, and surveillance where applicable."""


def make_clinical_reasoning_prompt(
    patient: PatientState, assessment_details: dict | None = None
) -> str:
    assessment_block = ""
    if isinstance(assessment_details, dict) and assessment_details:
        try:
            assessment_json = json.dumps(assessment_details, ensure_ascii=False)
        except Exception:
            assessment_json = str(assessment_details)
        assessment_block = f"""
<ASSESSMENT_FULL>
{assessment_json}
</ASSESSMENT_FULL>
"""
    return f"""
<CLINICAL_REASONING_ASSESSMENT>
<INSTRUCTIONS>
- Output strictly valid JSON only with keys: reasoning[], confidence, differential_dx[], risk_factors[], recommendations[], clinical_rationale[], stewardship_considerations[], citations[], proposed_regimen_text.
- For reasoning[], provide comprehensive clinical analysis with each element being a complete, well-structured sentence that demonstrates expert-level clinical thinking and ties specific patient data to established algorithm criteria.
- For differential_dx[], include 4-6 relevant diagnostic possibilities with brief but thorough justifications for inclusion or exclusion based on patient presentation and clinical probability.
- For risk_factors[], provide detailed analysis of patient-specific modifiers that impact treatment selection, prognosis, or monitoring requirements.
- For recommendations[], generate specific, actionable clinical directives that address diagnostics, therapeutics, monitoring, counseling, and follow-up with explicit rationale.
- For clinical_rationale[], write 3-5 comprehensive paragraphs (as separate array elements) that read like a senior clinician's detailed assessment note, integrating pathophysiology, patient factors, and evidence-based decision making.
- For stewardship_considerations[], address spectrum optimization, duration minimization, resistance prevention, and cost-effectiveness while maintaining clinical efficacy.
- confidence must be a float in [0.0, 1.0] representing your assessment certainty based on evidence quality, clinical complexity, and diagnostic clarity.
- Each reasoning element should comprehensively address the clinical significance of findings and their impact on management decisions.
- Explicitly evaluate all red flags with detailed consideration of escalation triggers, referral indications, and safety concerns.
- No chain-of-thought or explanatory text outside the JSON structure; provide polished final results only.
- Include comprehensive citations[] with objects containing title, url, and detailed relevance explanations (2-3 sentences) demonstrating clear connection to clinical decisions.
- Do NOT embed citation URLs within reasoning or clinical_rationale content; maintain separation between content and references.
</INSTRUCTIONS>
<DECISION_RULES>
- If ASSESSMENT_FULL.decision == "recommend_treatment":
  - Set proposed_regimen_text to the single best regimen string you propose, including agent, dose, route, frequency, and duration (e.g., "Nitrofurantoin 100 mg PO BID x 5 days").
- Else:
  - Set proposed_regimen_text to an empty string.
</INSTRUCTIONS>
<DESCRIPTION>
Perform comprehensive, expert-level clinical reasoning for this urinary tract infection case using systematic evaluation methodology employed by senior infectious disease specialists. 

Your assessment must provide thorough analysis that evaluates diagnostic appropriateness through evidence-based criteria, identifies and systematically addresses all potential red flag symptoms, analyzes patient-specific clinical factors that impact treatment selection and prognosis, and provides robust support for the proposed management plan.

COMPREHENSIVE ANALYSIS REQUIREMENTS:
- Map all key clinical findings to specific algorithm criteria with detailed explanation of how each criterion is met or not met, including borderline cases and clinical judgment factors
- Systematically evaluate red flags with explicit consideration and acceptance/rejection rationale; provide detailed escalation triggers with specific clinical thresholds and timeframes
- Generate comprehensive differential diagnosis with detailed justifications for each possibility, including explicit ruled-in/ruled-out reasoning based on clinical probability, symptom patterns, and risk factor analysis
- Analyze patient-specific risk factors including recent antimicrobial exposure, pregnancy status and trimester, immunocompromised state, renal function, age-related considerations, and comorbidity impact on treatment selection
- Provide detailed antimicrobial stewardship analysis addressing spectrum optimization, duration minimization, resistance prevention, cost-effectiveness, and ecological impact considerations
- Generate clear, specific, actionable clinical recommendations with explicit treatment versus referral justification based on evidence hierarchy and clinical guidelines
- Include precise numeric confidence assessment with comprehensive rationale addressing evidence quality, clinical complexity, diagnostic certainty, and treatment appropriateness
</DESCRIPTION>

<PATIENT_DATA>
Age: {patient.age} years
Sex: {patient.sex.value}
Pregnancy: {patient.pregnancy_status}
Renal function: {patient.renal_function_summary.value}

Symptoms:
- Dysuria: {patient.symptoms.dysuria}
- Urgency: {patient.symptoms.urgency}
- Frequency: {patient.symptoms.frequency}
- Suprapubic pain: {patient.symptoms.suprapubic_pain}
- Hematuria: {patient.symptoms.hematuria}

Red flags:
- Fever: {patient.red_flags.fever}
- Rigors: {patient.red_flags.rigors}
- Flank pain: {patient.red_flags.flank_pain}
- Nausea/vomiting: {patient.red_flags.nausea_vomiting}
- Systemic symptoms: {patient.red_flags.systemic}

History:
- Recent antibiotics (90d): {patient.history.antibiotics_last_90d}
- Allergies: {", ".join(patient.history.allergies) if patient.history.allergies else "None"}
- Current medications: {", ".join(patient.history.meds) if patient.history.meds else "None"}
- ACEI/ARB use: {patient.history.ACEI_ARB_use}
- Catheter: {patient.history.catheter}
- Kidney stones: {patient.history.stones}
- Immunocompromised: {patient.history.immunocompromised}

Recurrence:
- Relapse within 4 weeks: {patient.recurrence.relapse_within_4w}
- ≥2 UTIs in 6 months: {patient.recurrence.recurrent_6m}
- ≥3 UTIs in 12 months: {patient.recurrence.recurrent_12m}
</PATIENT_DATA>

<TASK>
Provide an expert clinical reasoning assessment as JSON using the specified keys. Ensure clinical_rationale bullets read as a cohesive narrative.
Do not include any text outside the JSON object.
</TASK>
{assessment_block}
</CLINICAL_REASONING_ASSESSMENT>
"""


def make_safety_validation_prompt(
    patient: PatientState,
    decision: str,
    recommendation_text: str,
    clinical_reasoning: dict | None = None,
) -> str:
    doctor_block = ""
    if isinstance(clinical_reasoning, dict) and clinical_reasoning:
        try:
            cr_json = json.dumps(clinical_reasoning, ensure_ascii=False)
        except Exception:
            cr_json = str(clinical_reasoning)
        doctor_block = f"""
<DOCTOR_REASONING>
{cr_json}
</DOCTOR_REASONING>
"""
    return f"""
<SAFETY_VALIDATION_ASSESSMENT>
<INSTRUCTIONS>
- Output strictly valid JSON only with keys: safety_flags[], contraindications[], drug_interactions[], monitoring_requirements[], risk_level, approval_recommendation, rationale, citations[].
- For safety_flags[], provide comprehensive safety alerts that explain clinical significance, mechanism of concern, and specific monitoring or avoidance strategies required.
- For contraindications[], detail both absolute and relative contraindications with thorough explanations of the underlying pathophysiology and clinical consequences.
- For drug_interactions[], specify interacting agents/classes, interaction mechanism (pharmacokinetic vs pharmacodynamic), clinical consequences, and management strategies.
- For monitoring_requirements[], provide detailed monitoring protocols including specific laboratory parameters, timing intervals, clinical signs to assess, and patient counseling points.
- Write rationale as a comprehensive, multi-paragraph clinical assessment that explains your safety evaluation methodology, risk-benefit analysis, and final recommendation with detailed justification.
- Conduct thorough evaluation of absolute/relative contraindications, major drug interactions, pregnancy and lactation considerations, renal/hepatic function impacts, age-specific dosing requirements, and comprehensive monitoring needs.
- If clinical decision indicates referral or non-antibiotic management, explicitly state that antibiotic initiation is not recommended and provide detailed rationale.
- Be highly specific in identifying interacting agents/drug classes and provide detailed explanations of clinical consequences including mechanism, onset, severity, and management strategies.
- Address common UTI antimicrobial agents (nitrofurantoin, TMP/SMX, fosfomycin, trimethoprim) and their specific safety considerations including well-documented pitfalls such as hyperkalemia risk with TMP/SMX in patients taking ACEI/ARB, nitrofurantoin contraindications in late pregnancy and severe renal impairment, and age restrictions for fosfomycin.
- No explanatory text outside the JSON object structure.
- risk_level must be precisely classified as one of: low, moderate, high based on comprehensive safety assessment.
- approval_recommendation must be one of: approve, conditional, modify, reject, do not start, refer_no_antibiotics with detailed supporting rationale.
- Include comprehensive citations[] with objects containing title, url, and detailed relevance explanations (2-3 sentences) with no duplicate sources.
</INSTRUCTIONS>
<DESCRIPTION>
Perform comprehensive medication safety screening for the proposed UTI treatment plan.
</DESCRIPTION>

<PATIENT_SAFETY_PROFILE>
Age: {patient.age} years
Sex: {patient.sex.value}
Pregnancy: {patient.pregnancy_status}
Renal function: {patient.renal_function_summary.value}
Known allergies: {", ".join(patient.history.allergies) if patient.history.allergies else "None"}
Current medications: {", ".join(patient.history.meds) if patient.history.meds else "None"}
ACEI/ARB use: {patient.history.ACEI_ARB_use}
Immunocompromised: {patient.history.immunocompromised}
</PATIENT_SAFETY_PROFILE>

<PROPOSED_TREATMENT>
Clinical decision: {decision}
Recommended regimen to screen: {recommendation_text}
Notes:
- If DOCTOR_REASONING.proposed_regimen_text is present, that reflects the clinician-proposed regimen to screen.
- The assessment's recommendation provides algorithmic context only.
</PROPOSED_TREATMENT>
{doctor_block}

<SAFETY_SCREENING_TASKS>
1. Contraindication screening (absolute and relative)
2. Drug-drug interaction assessment
3. Pregnancy and renal function appropriateness
4. Age-related dosing considerations
5. Monitoring requirements identification
6. Overall risk stratification
If the clinical decision indicates referral (e.g., contains "refer"), do not recommend initiating antibiotics.
Return JSON only with keys: safety_flags[], contraindications[], drug_interactions[], monitoring_requirements[], risk_level, approval_recommendation, rationale
Additional checks to consider:
- TMP/SMX and ACEI/ARB (hyperkalemia risk)
- Nitrofurantoin in late pregnancy or severe renal impairment
- Fosfomycin use in pediatric patients
- Significant CYP-mediated interactions with concurrent medications
</SAFETY_SCREENING_TASKS>
</SAFETY_VALIDATION_ASSESSMENT>
"""


def make_web_research_prompt(query: str, region: str) -> str:
    return f"""
<CLINICAL_RESEARCH_REQUEST>
<INSTRUCTIONS>
- Conduct comprehensive evidence synthesis on UTI-related clinical guidelines, antimicrobial resistance patterns, and treatment recommendations relevant to the specified query.
- Generate well-structured, cohesive paragraphs with clear topic sentences that demonstrate expert-level understanding of clinical evidence hierarchy and guideline development methodology.
- Include comprehensive guideline identification with specific names, publishing organizations, publication years, and version numbers when available.
- Provide detailed regional anchoring to the specified geographic area; when extrapolating data from other jurisdictions, explicitly state limitations, applicability concerns, and confidence intervals in complete, well-reasoned sentences.
- Maintain strict factual accuracy; avoid speculation, unsupported recommendations, or extrapolation beyond available evidence while clearly identifying areas where evidence is limited or conflicting.
- Include comprehensive explanations of how each piece of evidence supports your overall synthesis, including discussion of study methodology, sample sizes, confidence intervals, and clinical significance.
- Focus exclusively on evidence synthesis and guideline interpretation; avoid patient-specific prescribing recommendations or individualized treatment advice.
- Integrate multiple evidence sources to provide balanced perspectives and identify areas of consensus versus controversy in current clinical practice.
- Address both efficacy and safety data when available, including comparative effectiveness research and real-world clinical outcomes data.
</INSTRUCTIONS>
<DESCRIPTION>
Conduct focused research on UTI-related clinical evidence with emphasis on current guidelines and resistance patterns.
</DESCRIPTION>

<RESEARCH_PARAMETERS>
Query: {query}
Region: {region} (assume Canada/Ontario; prefer CA-ON sources and Canadian guidelines)
Focus: Clinical evidence, treatment guidelines, resistance patterns
</RESEARCH_PARAMETERS>

<RESEARCH_GUIDELINES>
- Prioritize recent, high-quality clinical evidence
- Include specific resistance percentages when available
- Reference official treatment guidelines (e.g., Public Health Ontario, Canadian Urological Association, Health Canada, IDSA/NICE only for secondary context)
- Provide regional context for resistance patterns
- Limit response to 1000 words maximum
- Include publication dates when citing sources
 - Use crisp bullet points, no long paragraphs
 - Name guideline publishers (e.g., IDSA, NICE, local public health) when cited
- Avoid duplicate citations; if duplicates occur, list once and aggregate relevance.
</RESEARCH_GUIDELINES>

<OUTPUT_FORMAT>
Provide a brief, factual, sectioned bullet summary:
- Guidelines (name, year, key point, relevance)
- Resistance (agent %, geography, year, source, relevance)
- Comparative efficacy (high-level findings, relevance)
- Limitations (scope/data gaps)
Include source attribution inline and ensure citations emitted in stream are deduplicated.
</OUTPUT_FORMAT>
</CLINICAL_RESEARCH_REQUEST>
"""


def make_diagnosis_xml_prompt(
    patient: PatientState,
    assessment: AssessmentOutput,
    doctor_reasoning: dict | None = None,
    safety_validation_context: dict | None = None,
) -> str:
    rec = assessment.recommendation
    rec_text = (
        f"{rec.regimen} {rec.dose} {rec.frequency} x {rec.duration}" if rec else "None"
    )
    doctor_block = ""
    if isinstance(doctor_reasoning, dict) and doctor_reasoning:
        try:
            dr_json = json.dumps(doctor_reasoning, ensure_ascii=False)
        except Exception:
            dr_json = str(doctor_reasoning)
        doctor_block = f"""
<DOCTOR_REASONING>
{dr_json}
</DOCTOR_REASONING>
"""

    safety_block = ""
    if isinstance(safety_validation_context, dict) and safety_validation_context:
        try:
            sv_json = json.dumps(safety_validation_context, ensure_ascii=False)
        except Exception:
            sv_json = str(safety_validation_context)
        safety_block = f"""
<PHARMACIST_SAFETY>
{sv_json}
</PHARMACIST_SAFETY>
"""

    return f"""
<CLINICAL_DIAGNOSIS_TASK>
<INSTRUCTIONS>
- Produce a comprehensive, provider-ready clinical diagnosis and treatment brief in professional Markdown format suitable for attending physician review and clinical documentation.
- Use clear, structured headings with professional medical terminology and generate detailed bullet lists supplemented by clinically meaningful narrative paragraphs where appropriate for complex concepts.
- Required sections and comprehensive content requirements:
  - Executive Summary: Generate a detailed 2-3 paragraph synthesis of the case including patient demographics, presenting symptoms, key clinical findings, most likely diagnosis with confidence assessment, and high-level management plan with rationale.
  - Algorithm Alignment: Systematically map each patient finding to specific algorithm criteria with detailed explanation of how criteria are met or not met; state the resulting clinical decision (treat vs refer) with comprehensive justification including evidence hierarchy and guideline support.
  - Differential Diagnosis: Include 4-6 key diagnostic possibilities with detailed ruled-in/ruled-out reasoning based on clinical probability, symptom patterns, epidemiologic factors, and patient risk profile.
  - Therapeutic Plan & Justification: Provide comprehensive regimen selection rationale (or detailed referral decision justification) with specific clinical reasoning addressing safety profile, documented allergies, renal function impact, recurrence pattern analysis, regional resistance context, patient adherence factors; include detailed discussion of alternatives considered with explicit reasoning for selection or rejection.
  - Safety Review Summary: Generate detailed summary of pharmacist safety screening including risk level assessment, identification of key safety flags, contraindication analysis, drug interaction review, and comprehensive explanation of how safety considerations impacted the final treatment plan.
  - Monitoring & Follow-up: Specify detailed monitoring actions with precise timeframes, include relevant laboratory parameters or clinical assessments if applicable, provide escalation triggers with specific clinical thresholds.
  - Patient Counseling: Generate 6-10 comprehensive counseling points covering treatment expectations, anticipated symptom resolution timeline, potential side effects with management strategies, medication administration instructions, and detailed guidance on when to seek urgent care or escalate concerns.
  - Evidence Pointers: Provide detailed list of named clinical guidelines, research studies, and surveillance reports with publication years, publishing organizations, and comprehensive one-sentence relevance explanations demonstrating connection to clinical decisions.
- Do NOT embed citation URLs within clinical content; maintain separation by placing URLs only in Evidence Pointers section; the system captures citations separately through streaming analysis.
</INSTRUCTIONS>
<DESCRIPTION>
Generate an extensive, detailed Clinical Diagnosis & Treatment Brief for acute UTI assessment suitable for provider review and clinical decision-making.
</DESCRIPTION>

<PATIENT_CONTEXT>
<DEMOGRAPHICS>
Age: {patient.age} years
Sex: {patient.sex.value}
Pregnancy: {patient.pregnancy_status}
Region: {patient.locale_code}
Renal function: {patient.renal_function_summary.value}
</DEMOGRAPHICS>

<CLINICAL_PRESENTATION>
Symptoms: Dysuria={patient.symptoms.dysuria}, Urgency={patient.symptoms.urgency}, Frequency={patient.symptoms.frequency}, Suprapubic pain={patient.symptoms.suprapubic_pain}, Hematuria={patient.symptoms.hematuria}

Red flags: Fever={patient.red_flags.fever}, Rigors={patient.red_flags.rigors}, Flank pain={patient.red_flags.flank_pain}, Nausea/vomiting={patient.red_flags.nausea_vomiting}, Systemic={patient.red_flags.systemic}

History: Recent antibiotics={patient.history.antibiotics_last_90d}, Allergies={", ".join(patient.history.allergies) if patient.history.allergies else "None"}, Current meds={", ".join(patient.history.meds) if patient.history.meds else "None"}, ACEI/ARB={patient.history.ACEI_ARB_use}, Catheter={patient.history.catheter}, Stones={patient.history.stones}, Immunocompromised={patient.history.immunocompromised}

Recurrence: Relapse 4w={patient.recurrence.relapse_within_4w}, Recurrent 6m={patient.recurrence.recurrent_6m}, Recurrent 12m={patient.recurrence.recurrent_12m}
</CLINICAL_PRESENTATION>

<ASSESSMENT_RESULTS>
Decision: {assessment.decision.value}
Recommendation: {rec_text}
Clinical rationale: {" | ".join(assessment.rationale)}
Follow-up plan: {assessment.follow_up if assessment.follow_up else "Standard UTI follow-up"}
</ASSESSMENT_RESULTS>
{doctor_block}
{safety_block}
</PATIENT_CONTEXT>
"""


def make_verifier_prompt(final_snapshot: dict) -> str:
    try:
        ctx = json.dumps(final_snapshot, ensure_ascii=False)
    except Exception:
        ctx = str(final_snapshot)
    return f"""
<PLAN_VERIFICATION>
<INSTRUCTIONS>
- Output strictly valid JSON with keys: contradictions[], unsupported_claims[], alignment_notes[], verdict.
- verdict must be one of: pass, needs_review, fail.
- Focus on alignment between deterministic assessment, safety approval, clinical reasoning, diagnosis recommendations.
- Flag any recommendation that contradicts safety gating or algorithmic decision.
- Identify claims without clear evidence support or citations.
</INSTRUCTIONS>
<CONTEXT>
{ctx}
</CONTEXT>
</PLAN_VERIFICATION>
"""


def make_claim_extractor_prompt(final_snapshot: dict) -> str:
    try:
        ctx = json.dumps(final_snapshot, ensure_ascii=False)
    except Exception:
        ctx = str(final_snapshot)
    return f"""
<CLAIMS_AND_CITATIONS>
<INSTRUCTIONS>
- Extract concise claims from assessment.rationale, clinical_reasoning.reasoning/clinical_rationale, and diagnosis.
- For each claim, map citation URLs from any captured citations; include a one-line relevance.
- Deduplicate URLs across claims; if the same URL supports multiple claims, include it in each relevant claim.
- Output strictly valid JSON with key 'claims': Claim[] as defined by ClaimExtractionOutput.
</INSTRUCTIONS>
<CONTEXT>
{ctx}
</CONTEXT>
</CLAIMS_AND_CITATIONS>
"""


def make_reasoning_refinement_prompt(
    patient: PatientState,
    initial_reasoning: dict,
    pharmacist_feedback: dict,
) -> str:
    try:
        init_json = json.dumps(initial_reasoning, ensure_ascii=False)
    except Exception:
        init_json = str(initial_reasoning)
    try:
        pharm_json = json.dumps(pharmacist_feedback, ensure_ascii=False)
    except Exception:
        pharm_json = str(pharmacist_feedback)
    return f"""
<CLINICAL_REASONING_REFINEMENT>
<INSTRUCTIONS>
- You previously produced a Clinical Reasoning JSON object. A pharmacist safety review has provided critique.
- Revise and improve your reasoning by incorporating the pharmacist feedback and any safety concerns.
- Output strictly valid JSON only with the SAME keys as before: reasoning[], confidence, differential_dx[], risk_factors[], recommendations[], clinical_rationale[], stewardship_considerations[], citations[].
- Keep bullets short and precise; avoid prose paragraphs. Update recommendations and stewardship to reflect safety concerns.
- No chain-of-thought; no text outside the JSON object.
</INSTRUCTIONS>

<PATIENT_DATA>
Age: {patient.age} years
Sex: {patient.sex.value}
Pregnancy: {patient.pregnancy_status}
Renal function: {patient.renal_function_summary.value}
</PATIENT_DATA>

<INITIAL_DOCTOR_REASONING>
{init_json}
</INITIAL_DOCTOR_REASONING>

<PHARMACIST_FEEDBACK>
{pharm_json}
</PHARMACIST_FEEDBACK>

<TASK>
Return ONLY the revised JSON object. If pharmacist indicates modify/conditional/reject, ensure your recommendations reflect that.
</TASK>
</CLINICAL_REASONING_REFINEMENT>
"""
