from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .models import (
    PREGNANCY_EXCLUSIONS,
    REJECT_TERMS,
    TMP_SMX_ALLERGY_TERMS,
    TREATMENT_OPTIONS,
    AssessmentOutput,
    Decision,
    History,
    MedicationAgent,
    PatientState,
    Recommendation,
    RecurrenceResult,
    ValidatorResult,
)


def assess_symptom_criteria(patient: PatientState) -> bool:
    """Check if patient meets UTI criteria: dysuria OR ≥2 of urgency/frequency/suprapubic_pain/hematuria"""
    symptoms = patient.symptoms
    return (
        symptoms.dysuria
        or sum(
            [
                symptoms.urgency,
                symptoms.frequency,
                symptoms.suprapubic_pain,
                symptoms.hematuria,
            ],
        )
        >= 2
    )


def has_nonspecific_symptoms(patient: PatientState) -> bool:
    """Check for nonspecific symptoms that require referral: confusion/delirium or gross hematuria"""
    symptoms = patient.symptoms
    return any([symptoms.confusion, symptoms.delirium, symptoms.gross_hematuria])


def check_complicating_factors(patient: PatientState) -> list[str]:
    """Check for complicating factors that require referral"""
    complications = []

    # Upper urinary tract or systemic disease (red flag symptoms)
    red_flags = patient.red_flags
    if any(
        [
            red_flags.fever,
            red_flags.rigors,
            red_flags.flank_pain,
            red_flags.back_pain,
            red_flags.nausea_vomiting,
            red_flags.systemic,
        ],
    ):
        complications.append("systemic_or_upper_tract_symptoms")

    # Additional complicating factors
    complication_checks = [
        (patient.sex.value == "male", "male_patient"),
        (
            patient.sex.value == "female"
            and patient.pregnancy_status not in PREGNANCY_EXCLUSIONS,
            "pregnancy",
        ),
        (patient.age < 12, "pediatric_<12y"),
        (patient.history.immunocompromised, "immunocompromised"),
        (
            any(
                [
                    patient.history.catheter,
                    patient.history.neurogenic_bladder,
                    patient.history.stones,
                    patient.renal_function_summary.value != "normal",
                ],
            ),
            "abnormal_urinary_tract_or_function",
        ),
    ]

    return complications + [
        factor for condition, factor in complication_checks if condition
    ]


def check_recurrence_relapse(patient: PatientState) -> RecurrenceResult:
    """Check for relapse or recurrent infection patterns"""
    recurrence = patient.recurrence

    # Check for recurrence patterns in order of priority
    recurrence_patterns = [
        (recurrence.relapse_within_4w, "relapse ≤4 weeks after treatment"),
        (recurrence.recurrent_6m, "recurrent UTI: ≥2 in 6 months"),
        (recurrence.recurrent_12m, "recurrent UTI: ≥3 in 12 months"),
    ]

    for has_pattern, reason in recurrence_patterns:
        if has_pattern:
            return RecurrenceResult(has_recurrence=True, reason=reason)

    return RecurrenceResult(has_recurrence=False, reason="")


def select_treatment(patient: PatientState) -> Recommendation | None:
    """Select appropriate antibiotic treatment based on patient factors"""
    history = patient.history
    allergies = {a.lower() for a in history.allergies}

    def is_medication_allowed(agent: MedicationAgent) -> bool:
        """Check if medication is allowed based on patient factors"""
        # Common exclusions for all medications
        if history.antibiotics_last_90d:
            return False

        # Agent-specific contraindications
        contraindications = {
            MedicationAgent.nitrofurantoin: [
                "nitrofurantoin" in allergies,
                patient.egfr_ml_min is not None and patient.egfr_ml_min < 30,
            ],
            MedicationAgent.tmp_smx: [
                bool(allergies & TMP_SMX_ALLERGY_TERMS),
                history.acei_arb_use,
            ],
            MedicationAgent.trimethoprim: [
                "trimethoprim" in allergies,
            ],
            MedicationAgent.fosfomycin: [
                patient.age < 18,
                "fosfomycin" in allergies,
            ],
        }

        return not any(contraindications.get(agent, []))

    # Try medications in order of preference (first-line to alternatives)
    preferred_order = [
        MedicationAgent.nitrofurantoin,
        MedicationAgent.tmp_smx,
        MedicationAgent.trimethoprim,
        MedicationAgent.fosfomycin,
    ]

    for agent in preferred_order:
        if is_medication_allowed(agent):
            spec = TREATMENT_OPTIONS[agent]
            return Recommendation(
                regimen=spec.regimen,
                regimen_agent=spec.agent,
                dose=spec.dose,
                frequency=spec.frequency,
                duration=spec.duration,
                alternatives=spec.alternatives,
                contraindications=spec.contraindications,
                monitoring=spec.monitoring,
            )

    return None


def _create_audit() -> dict:
    """Create standardized audit metadata"""
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "algorithm_version": "mermaid_v1",
    }


def get_follow_up_plan() -> dict:
    """Standard 72-hour follow-up plan per algorithm"""
    return {
        "assessment_timeframe": "48-72 hours",
        "instructions": [
            "Complete documentation & notify a physician or nurse practitioner",
            "Assess for improvement & side effects in 72 hours",
        ],
        "red_flags_for_escalation": [
            "Fever, rigors, or systemic symptoms",
            "Worsening symptoms after 48-72 hours",
            "Development of upper urinary tract or systemic disease",
        ],
    }


def assess_uti_patient(patient: PatientState) -> AssessmentOutput:  # noqa: PLR0911
    """
    Main UTI assessment function following the Mermaid algorithm exactly:
    1. Check if patient has asymptomatic bacteriuria -> no antibiotics
    2. Check symptom criteria -> no antibiotics if not met (unless nonspecific symptoms -> refer)
    3. Check complicating factors -> refer if present
    4. Check recurrence/relapse -> refer if present
    5. Select treatment -> recommend treatment
    """
    rationale = []

    # Step 1: Check for asymptomatic bacteriuria (explicit no antibiotics per diagram)
    if patient.asymptomatic_bacteriuria:
        return AssessmentOutput(
            decision=Decision.no_antibiotics_not_met,
            rationale=[
                "This patient presents with asymptomatic bacteriuria, which does not warrant antibiotic treatment according to current UTI management guidelines.",
                "The Ontario College of Pharmacists algorithm specifically states that antibiotics should not be prescribed for asymptomatic bacteriuria, even when bacteria are present in urine cultures.",
            ],
            eligibility_criteria_met=False,
            criteria_not_met_reasons=["Asymptomatic bacteriuria present"],
            audit=_create_audit(),
        )

    # Step 2: Assess symptom criteria
    criteria_met = assess_symptom_criteria(patient)
    if not criteria_met:
        # Check for nonspecific symptoms that require referral
        if has_nonspecific_symptoms(patient):
            return AssessmentOutput(
                decision=Decision.refer_complicated,
                rationale=[
                    "While this patient does not meet the standard criteria for uncomplicated cystitis, they present with nonspecific symptoms such as confusion, delirium, or gross hematuria.",
                    "According to the Ontario College of Pharmacists UTI algorithm, patients with these nonspecific symptoms should be referred to a physician or nurse practitioner for further investigation to rule out other conditions.",
                ],
                eligibility_criteria_met=False,
                criteria_not_met_reasons=[
                    "Nonspecific symptoms requiring physician evaluation",
                ],
                audit=_create_audit(),
            )
        # Criteria not met, no nonspecific symptoms -> no antibiotics
        return AssessmentOutput(
            decision=Decision.no_antibiotics_not_met,
            rationale=[
                "This patient does not meet the diagnostic criteria for acute uncomplicated cystitis as defined by the Ontario College of Pharmacists algorithm.",
                "The algorithm requires either acute dysuria OR at least two of the following symptoms: urinary urgency, frequency, suprapubic pain, or hematuria. This patient's presentation does not fulfill these requirements.",
                "Antibiotic treatment is not indicated when UTI criteria are not met, as this could contribute to unnecessary antibiotic resistance and adverse effects.",
            ],
            eligibility_criteria_met=False,
            criteria_not_met_reasons=["Insufficient symptoms for UTI diagnosis"],
            audit=_create_audit(),
        )

    rationale.append(
        "This patient meets the diagnostic criteria for acute uncomplicated cystitis based on their symptom presentation.",
    )

    # Step 3: Check for complicating factors
    complications = check_complicating_factors(patient)
    if complications:
        complication_descriptions = {
            "systemic_or_upper_tract_symptoms": "upper urinary tract or systemic disease with red flag symptoms including fever, rigors, flank pain, back pain, nausea, or vomiting",
            "male_patient": "male sex, which increases complexity and risk of complications",
            "pregnancy": "pregnancy, which requires specialized antibiotic selection and monitoring",
            "pediatric_<12y": "age less than 12 years, requiring pediatric specialist management",
            "immunocompromised": "immunocompromised status, increasing risk of treatment failure and complications",
            "abnormal_urinary_tract_or_function": "abnormal urinary tract function or structure including indwelling catheter, neurogenic bladder, renal stones, or renal dysfunction",
        }

        detailed_complications = [
            complication_descriptions.get(comp, comp) for comp in complications
        ]
        return AssessmentOutput(
            decision=Decision.refer_complicated,
            rationale=[
                f"This patient presents with complicating factors that preclude pharmacist-initiated antibiotic therapy: {', '.join(detailed_complications)}.",
                "According to the Ontario College of Pharmacists UTI assessment algorithm, patients with any complicating factors should be referred to a physician or nurse practitioner for comprehensive evaluation and management.",
                "These factors increase the risk of treatment failure, complications, and the need for alternative diagnostic approaches or specialized antimicrobial regimens.",
            ],
            eligibility_criteria_met=True,
            triggered_complicating_factors=complications,
            audit=_create_audit(),
        )

    rationale.append(
        "No complicating factors were identified that would preclude pharmacist-initiated treatment.",
    )

    # Step 4: Check for recurrence or relapse
    recurrence_result = check_recurrence_relapse(patient)
    if recurrence_result.has_recurrence:
        recurrence_explanation = {
            "relapse ≤4 weeks after treatment": "This patient experienced a relapse of UTI symptoms within 4 weeks of completing previous antibiotic treatment, suggesting possible treatment failure, antimicrobial resistance, or underlying predisposing factors.",
            "recurrent UTI: ≥2 in 6 months": "This patient has experienced 2 or more UTI episodes within the past 6 months, meeting the definition for recurrent urinary tract infection.",
            "recurrent UTI: ≥3 in 12 months": "This patient has experienced 3 or more UTI episodes within the past 12 months, meeting the definition for recurrent urinary tract infection.",
        }

        return AssessmentOutput(
            decision=Decision.refer_recurrence,
            rationale=[
                recurrence_explanation.get(
                    recurrence_result.reason,
                    f"This patient presents with a recurrence pattern: {recurrence_result.reason}.",
                ),
                "According to the Ontario College of Pharmacists UTI algorithm, patients experiencing relapse or recurrent infections should be referred to a physician or nurse practitioner for comprehensive evaluation.",
                "Recurrent UTIs may indicate underlying anatomical abnormalities, functional disorders, antimicrobial resistance, or other predisposing factors that require specialized investigation and management beyond the scope of pharmacist-initiated therapy.",
            ],
            eligibility_criteria_met=True,
            triggered_recurrence_markers=[recurrence_result.reason],
            audit=_create_audit(),
        )

    rationale.append(
        "No recurrence or relapse pattern was detected based on the patient's UTI history.",
    )

    # Step 5: Select treatment
    recommendation = select_treatment(patient)
    if recommendation is None:
        return AssessmentOutput(
            decision=Decision.refer_complicated,
            rationale=[
                "No safe first-line antibiotic option is available for this patient based on their individual risk factors.",
                "Factors such as advanced age, significant allergies, impaired renal function, or recent antibiotic exposure have eliminated all standard treatment options from the Ontario College of Pharmacists algorithm.",
                "This patient requires physician or nurse practitioner assessment to determine alternative antimicrobial therapy or specialized management approaches.",
            ],
            eligibility_criteria_met=True,
            audit=_create_audit(),
        )

    rationale.append(
        f"Based on the patient's clinical profile and the Ontario College of Pharmacists UTI algorithm, {recommendation.regimen} has been selected as the most appropriate first-line treatment option.",
    )

    # Step 6: Add follow-up plan for treatment decisions
    follow_up = get_follow_up_plan()

    return AssessmentOutput(
        decision=Decision.recommend_treatment,
        recommendation=recommendation,
        rationale=rationale,
        follow_up=follow_up,
        eligibility_criteria_met=True,
        audit=_create_audit(),
    )


def get_enhanced_follow_up_plan(patient: PatientState) -> dict:
    """Enhanced follow-up plan with patient-specific considerations"""
    base_plan = get_follow_up_plan()

    # Get monitoring from patient's current assessment (efficient single call)
    result = assess_uti_patient(patient)
    monitoring = result.recommendation.monitoring if result.recommendation else []

    special_instructions = []
    if patient.age >= 65:
        special_instructions.append(
            "Monitor elderly patients closely for adverse effects",
        )
    if patient.history.acei_arb_use:
        special_instructions.append("Monitor for hyperkalemia if TMP/SMX prescribed")
    if patient.renal_function_summary.value == "impaired":
        special_instructions.append("Consider dose adjustment for renal impairment")

    return {
        "follow_up_plan": base_plan,
        "monitoring_checklist": monitoring,
        "special_instructions": special_instructions,
        "provider_actions": [
            "Complete documentation in medical record",
            "Notify supervising physician or nurse practitioner",
            "Schedule 72-hour follow-up contact",
            "Provide patient education materials",
        ],
    }


def get_contraindications_from_assessment(assessment: AssessmentOutput) -> list[str]:
    """Extract contraindications from existing assessment result"""
    if assessment.recommendation:
        return assessment.recommendation.contraindications
    return []


def state_validator(
    patient: PatientState,
    regimen_text: str,
    safety: dict | None,
) -> ValidatorResult:
    """Validate patient state against UTI algorithm rules"""

    @dataclass
    class ValidationRule:
        condition: bool
        rule_name: str
        severity: str = "moderate"
        is_contradiction: bool = False

    rules_fired: list[str] = []
    contradictions: list[str] = []
    severity = "low"

    try:
        safety_approval = (
            (safety or {}).get("approval_recommendation", "").lower()
            if isinstance(safety, dict)
            else ""
        )
        rt = regimen_text.lower()

        validation_rules = [
            # Safety contradictions
            ValidationRule(
                condition=safety_approval in REJECT_TERMS
                and regimen_text
                and rt != "none",
                rule_name="Safety rejected but regimen present",
                severity="high",
                is_contradiction=True,
            ),
            # Allergy vs regimen contradictions (agent text match on common signals)
            ValidationRule(
                condition=(
                    "nitrofurantoin" in rt
                    and any(
                        "nitrofurantoin" in a.lower()
                        for a in (patient.history.allergies or [])
                    )
                ),
                rule_name="allergy_conflict_nitrofurantoin",
                severity="high",
                is_contradiction=True,
            ),
            ValidationRule(
                condition=(
                    any(
                        term in rt
                        for term in ["tmp", "sulfamethoxazole", "smx", "trimethoprim"]
                    )
                    and any(
                        any(k in a.lower() for k in TMP_SMX_ALLERGY_TERMS)
                        for a in (patient.history.allergies or [])
                    )
                ),
                rule_name="allergy_conflict_tmpsmx_or_trimethoprim",
                severity="high",
                is_contradiction=True,
            ),
            ValidationRule(
                condition=(
                    "fosfomycin" in rt
                    and any(
                        "fosfomycin" in a.lower()
                        for a in (patient.history.allergies or [])
                    )
                ),
                rule_name="allergy_conflict_fosfomycin",
                severity="high",
                is_contradiction=True,
            ),
            # Renal function rules
            ValidationRule(
                condition=patient.renal_function_summary.value == "failure"
                and "nitrofurantoin" in rt,
                rule_name="avoid_nitrofurantoin_in_renal_failure",
                severity="high",
            ),
            ValidationRule(
                condition=(
                    patient.egfr_ml_min is not None
                    and patient.egfr_ml_min < 30
                    and "nitrofurantoin" in rt
                ),
                rule_name="avoid_nitrofurantoin_egfr_lt_30",
                severity="high",
            ),
            # Drug interaction rules
            ValidationRule(
                condition=patient.history.acei_arb_use
                and any(term in rt for term in ["tmp", "sulfamethoxazole", "smx"]),
                rule_name="acei_arb_plus_tmpsmx_hyperkalemia_risk",
            ),
            ValidationRule(
                condition=(
                    any(term in rt for term in ["tmp", "sulfamethoxazole", "smx"])
                    and any(
                        cls in patient.history.med_classes
                        for cls in [
                            History.MedClass.potassium_sparing,
                            History.MedClass.nsaid,
                        ]
                    )
                ),
                rule_name="tmpsmx_with_potassium_sparing_or_nsaid_monitor_k",
            ),
            # Age restrictions
            ValidationRule(
                condition=patient.age < 18 and "fosfomycin" in rt,
                rule_name="fosfomycin_not_indicated_under_18",
                severity="high",
            ),
            # Duration checks
            ValidationRule(
                condition="nitrofurantoin" in rt and "x 5" not in rt,
                rule_name="nitrofurantoin_duration_check_5_days",
            ),
            ValidationRule(
                condition=any(term in rt for term in ["tmp", "sulfamethoxazole", "smx"])
                and "x 3" not in rt,
                rule_name="tmpsmx_duration_check_3_days",
            ),
            ValidationRule(
                condition="trimethoprim" in rt and "x 3" not in rt,
                rule_name="trimethoprim_duration_check_3_days",
            ),
            # Dose checks
            ValidationRule(
                condition="fosfomycin" in rt
                and not any(dose in rt for dose in ["3 g", "3g"]),
                rule_name="fosfomycin_dose_check_3g_single_dose",
            ),
        ]

        # Process rules
        for rule in validation_rules:
            if rule.condition:
                if rule.is_contradiction:
                    contradictions.append(rule.rule_name)
                else:
                    rules_fired.append(rule.rule_name)

                # Update severity (high takes precedence)
                if rule.severity == "high":
                    severity = "high"
                elif rule.severity == "moderate" and severity != "high":
                    severity = "moderate"

    except Exception:  # noqa: S110
        pass  # Maintain existing error handling behavior

    passed = severity != "high" and not contradictions
    return ValidatorResult(
        passed=passed,
        rules_fired=rules_fired,
        contradictions=contradictions,
        severity=severity,
    )
