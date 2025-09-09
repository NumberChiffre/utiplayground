from __future__ import annotations

from datetime import datetime

from src.models import (
    Decision,
    MedicationAgent,
    RenalFunction,
)
from src.uti_algo import (
    _create_audit,
    assess_symptom_criteria,
    assess_uti_patient,
    check_complicating_factors,
    check_recurrence_relapse,
    get_contraindications_from_assessment,
    get_enhanced_follow_up_plan,
    get_follow_up_plan,
    has_nonspecific_symptoms,
    select_treatment,
    state_validator,
)
from tests.factories import (
    AsymptomaticBacteruriaPatientFactory,
    ComplicatedUTIPatientFactory,
    ElderlyUTIPatientFactory,
    InsufficientSymptomsPatientFactory,
    MaleUTIPatientFactory,
    PatientWithAllergiesFactory,
    PediatricPatientFactory,
    PregnantPatientFactory,
    RecurrentUTIPatientFactory,
    SimpleUTIPatientFactory,
)


class TestAssessSymptomCriteria:
    def test_dysuria_only_meets_criteria(self):
        patient = SimpleUTIPatientFactory()
        patient.symptoms.dysuria = True
        patient.symptoms.urgency = False
        patient.symptoms.frequency = False
        patient.symptoms.suprapubic_pain = False
        patient.symptoms.hematuria = False

        assert assess_symptom_criteria(patient) is True

    def test_two_symptoms_without_dysuria_meets_criteria(self):
        patient = SimpleUTIPatientFactory()
        patient.symptoms.dysuria = False
        patient.symptoms.urgency = True
        patient.symptoms.frequency = True
        patient.symptoms.suprapubic_pain = False
        patient.symptoms.hematuria = False

        assert assess_symptom_criteria(patient) is True

    def test_three_symptoms_without_dysuria_meets_criteria(self):
        patient = SimpleUTIPatientFactory()
        patient.symptoms.dysuria = False
        patient.symptoms.urgency = True
        patient.symptoms.frequency = True
        patient.symptoms.suprapubic_pain = True
        patient.symptoms.hematuria = False

        assert assess_symptom_criteria(patient) is True

    def test_one_symptom_without_dysuria_fails_criteria(self):
        patient = SimpleUTIPatientFactory()
        patient.symptoms.dysuria = False
        patient.symptoms.urgency = True
        patient.symptoms.frequency = False
        patient.symptoms.suprapubic_pain = False
        patient.symptoms.hematuria = False

        assert assess_symptom_criteria(patient) is False

    def test_no_symptoms_fails_criteria(self):
        patient = SimpleUTIPatientFactory()
        patient.symptoms.dysuria = False
        patient.symptoms.urgency = False
        patient.symptoms.frequency = False
        patient.symptoms.suprapubic_pain = False
        patient.symptoms.hematuria = False

        assert assess_symptom_criteria(patient) is False


class TestHasNonspecificSymptoms:
    def test_confusion_is_nonspecific(self):
        patient = SimpleUTIPatientFactory()
        patient.symptoms.confusion = True
        patient.symptoms.delirium = False
        patient.symptoms.gross_hematuria = False

        assert has_nonspecific_symptoms(patient) is True

    def test_delirium_is_nonspecific(self):
        patient = SimpleUTIPatientFactory()
        patient.symptoms.confusion = False
        patient.symptoms.delirium = True
        patient.symptoms.gross_hematuria = False

        assert has_nonspecific_symptoms(patient) is True

    def test_gross_hematuria_is_nonspecific(self):
        patient = SimpleUTIPatientFactory()
        patient.symptoms.confusion = False
        patient.symptoms.delirium = False
        patient.symptoms.gross_hematuria = True

        assert has_nonspecific_symptoms(patient) is True

    def test_no_nonspecific_symptoms(self):
        patient = SimpleUTIPatientFactory()
        patient.symptoms.confusion = False
        patient.symptoms.delirium = False
        patient.symptoms.gross_hematuria = False

        assert has_nonspecific_symptoms(patient) is False


class TestCheckComplicatingFactors:
    def test_fever_is_complicating(self):
        patient = SimpleUTIPatientFactory()
        patient.red_flags.fever = True

        factors = check_complicating_factors(patient)
        assert "systemic_or_upper_tract_symptoms" in factors

    def test_rigors_is_complicating(self):
        patient = SimpleUTIPatientFactory()
        patient.red_flags.rigors = True

        factors = check_complicating_factors(patient)
        assert "systemic_or_upper_tract_symptoms" in factors

    def test_flank_pain_is_complicating(self):
        patient = SimpleUTIPatientFactory()
        patient.red_flags.flank_pain = True

        factors = check_complicating_factors(patient)
        assert "systemic_or_upper_tract_symptoms" in factors

    def test_back_pain_is_complicating(self):
        patient = SimpleUTIPatientFactory()
        patient.red_flags.back_pain = True

        factors = check_complicating_factors(patient)
        assert "systemic_or_upper_tract_symptoms" in factors

    def test_nausea_vomiting_is_complicating(self):
        patient = SimpleUTIPatientFactory()
        patient.red_flags.nausea_vomiting = True

        factors = check_complicating_factors(patient)
        assert "systemic_or_upper_tract_symptoms" in factors

    def test_systemic_symptoms_is_complicating(self):
        patient = SimpleUTIPatientFactory()
        patient.red_flags.systemic = True

        factors = check_complicating_factors(patient)
        assert "systemic_or_upper_tract_symptoms" in factors

    def test_male_patient_is_complicating(self):
        patient = MaleUTIPatientFactory()

        factors = check_complicating_factors(patient)
        assert "male_patient" in factors

    def test_pregnancy_is_complicating(self):
        patient = PregnantPatientFactory()

        factors = check_complicating_factors(patient)
        assert "pregnancy" in factors

    def test_pediatric_under_12_is_complicating(self):
        patient = PediatricPatientFactory()

        factors = check_complicating_factors(patient)
        assert "pediatric_<12y" in factors

    def test_immunocompromised_is_complicating(self):
        patient = SimpleUTIPatientFactory()
        patient.history.immunocompromised = True

        factors = check_complicating_factors(patient)
        assert "immunocompromised" in factors

    def test_catheter_is_complicating(self):
        patient = SimpleUTIPatientFactory()
        patient.history.catheter = True

        factors = check_complicating_factors(patient)
        assert "abnormal_urinary_tract_or_function" in factors

    def test_neurogenic_bladder_is_complicating(self):
        patient = SimpleUTIPatientFactory()
        patient.history.neurogenic_bladder = True

        factors = check_complicating_factors(patient)
        assert "abnormal_urinary_tract_or_function" in factors

    def test_stones_is_complicating(self):
        patient = SimpleUTIPatientFactory()
        patient.history.stones = True

        factors = check_complicating_factors(patient)
        assert "abnormal_urinary_tract_or_function" in factors

    def test_renal_dysfunction_is_complicating(self):
        patient = SimpleUTIPatientFactory()
        patient.renal_function_summary = RenalFunction.impaired

        factors = check_complicating_factors(patient)
        assert "abnormal_urinary_tract_or_function" in factors

    def test_no_complicating_factors(self):
        patient = SimpleUTIPatientFactory()

        factors = check_complicating_factors(patient)
        assert len(factors) == 0


class TestCheckRecurrenceRelapse:
    def test_relapse_within_4w_detected(self):
        patient = SimpleUTIPatientFactory()
        patient.recurrence.relapse_within_4w = True

        result = check_recurrence_relapse(patient)
        assert result.has_recurrence is True
        assert result.reason == "relapse ≤4 weeks after treatment"

    def test_recurrent_6m_detected(self):
        patient = SimpleUTIPatientFactory()
        patient.recurrence.recurrent_6m = True

        result = check_recurrence_relapse(patient)
        assert result.has_recurrence is True
        assert result.reason == "recurrent UTI: ≥2 in 6 months"

    def test_recurrent_12m_detected(self):
        patient = SimpleUTIPatientFactory()
        patient.recurrence.recurrent_12m = True

        result = check_recurrence_relapse(patient)
        assert result.has_recurrence is True
        assert result.reason == "recurrent UTI: ≥3 in 12 months"

    def test_relapse_takes_priority_over_recurrence(self):
        patient = SimpleUTIPatientFactory()
        patient.recurrence.relapse_within_4w = True
        patient.recurrence.recurrent_6m = True
        patient.recurrence.recurrent_12m = True

        result = check_recurrence_relapse(patient)
        assert result.has_recurrence is True
        assert result.reason == "relapse ≤4 weeks after treatment"

    def test_6m_recurrence_takes_priority_over_12m(self):
        patient = SimpleUTIPatientFactory()
        patient.recurrence.relapse_within_4w = False
        patient.recurrence.recurrent_6m = True
        patient.recurrence.recurrent_12m = True

        result = check_recurrence_relapse(patient)
        assert result.has_recurrence is True
        assert result.reason == "recurrent UTI: ≥2 in 6 months"

    def test_no_recurrence(self):
        patient = SimpleUTIPatientFactory()

        result = check_recurrence_relapse(patient)
        assert result.has_recurrence is False
        assert result.reason == ""


class TestSelectTreatment:
    def test_nitrofurantoin_first_choice(self):
        patient = SimpleUTIPatientFactory()

        rec = select_treatment(patient)
        assert rec is not None
        assert rec.regimen_agent == MedicationAgent.nitrofurantoin
        assert rec.regimen == "Nitrofurantoin macrocrystals"

    def test_nitrofurantoin_contraindicated_low_egfr(self):
        patient = ElderlyUTIPatientFactory()
        patient.egfr_ml_min = 25.0  # < 30

        rec = select_treatment(patient)
        # Should select alternative (TMP/SMX in this case, but ACEI use contraindicated)
        # Should eventually get trimethoprim or fosfomycin
        assert rec is not None
        assert rec.regimen_agent != MedicationAgent.nitrofurantoin

    def test_nitrofurantoin_contraindicated_allergy(self):
        patient = PatientWithAllergiesFactory()
        # This factory has nitrofurantoin allergy

        rec = select_treatment(patient)
        # Should select alternative since nitrofurantoin and trimethoprim are in allergies
        assert rec is not None
        assert rec.regimen_agent != MedicationAgent.nitrofurantoin
        assert rec.regimen_agent != MedicationAgent.trimethoprim

    def test_tmp_smx_contraindicated_acei_use(self):
        patient = ElderlyUTIPatientFactory()  # Has ACEI use
        patient.history.allergies = ["nitrofurantoin"]  # Block nitrofurantoin

        rec = select_treatment(patient)
        # Should not select TMP/SMX due to ACEI use
        assert rec is not None
        assert rec.regimen_agent != MedicationAgent.tmp_smx
        assert rec.regimen_agent != MedicationAgent.nitrofurantoin

    def test_tmp_smx_contraindicated_allergy(self):
        patient = SimpleUTIPatientFactory()
        patient.history.allergies = [
            "nitrofurantoin",
            "trimethoprim",
            "sulfamethoxazole",
        ]

        rec = select_treatment(patient)
        # Should select fosfomycin as only remaining option
        assert rec is not None
        assert rec.regimen_agent == MedicationAgent.fosfomycin

    def test_fosfomycin_contraindicated_age(self):
        patient = PediatricPatientFactory()  # Age < 18
        patient.age = 16

        rec = select_treatment(patient)
        # Should not select fosfomycin for under 18
        if rec is not None:  # May be None if no options available
            assert rec.regimen_agent != MedicationAgent.fosfomycin

    def test_recent_antibiotics_blocks_all(self):
        patient = SimpleUTIPatientFactory()
        patient.history.antibiotics_last_90d = True

        rec = select_treatment(patient)
        assert rec is None

    def test_all_options_contraindicated(self):
        patient = SimpleUTIPatientFactory()
        patient.history.antibiotics_last_90d = True

        rec = select_treatment(patient)
        assert rec is None


class TestAssessUTIPatient:
    def test_simple_uti_patient_gets_treatment(self):
        patient = SimpleUTIPatientFactory()

        result = assess_uti_patient(patient)

        assert result.decision == Decision.recommend_treatment
        assert result.recommendation is not None
        assert result.eligibility_criteria_met is True
        assert len(result.triggered_complicating_factors) == 0
        assert len(result.triggered_recurrence_markers) == 0

    def test_asymptomatic_bacteriuria_no_antibiotics(self):
        patient = AsymptomaticBacteruriaPatientFactory()

        result = assess_uti_patient(patient)

        assert result.decision == Decision.no_antibiotics_not_met
        assert result.recommendation is None
        assert result.eligibility_criteria_met is False
        assert "Asymptomatic bacteriuria present" in result.criteria_not_met_reasons
        assert "asymptomatic bacteriuria" in " ".join(result.rationale).lower()

    def test_insufficient_symptoms_no_antibiotics(self):
        patient = InsufficientSymptomsPatientFactory()

        result = assess_uti_patient(patient)

        assert result.decision == Decision.no_antibiotics_not_met
        assert result.recommendation is None
        assert result.eligibility_criteria_met is False
        assert (
            "Insufficient symptoms for UTI diagnosis" in result.criteria_not_met_reasons
        )

    def test_nonspecific_symptoms_refer(self):
        patient = SimpleUTIPatientFactory()
        patient.symptoms.dysuria = False
        patient.symptoms.urgency = False
        patient.symptoms.frequency = False
        patient.symptoms.suprapubic_pain = False
        patient.symptoms.hematuria = False
        patient.symptoms.confusion = True  # nonspecific

        result = assess_uti_patient(patient)

        assert result.decision == Decision.refer_complicated
        assert result.recommendation is None
        assert result.eligibility_criteria_met is False
        assert (
            "Nonspecific symptoms requiring physician evaluation"
            in result.criteria_not_met_reasons
        )

    def test_complicated_patient_referred(self):
        patient = ComplicatedUTIPatientFactory()

        result = assess_uti_patient(patient)

        assert result.decision == Decision.refer_complicated
        assert result.recommendation is None
        assert result.eligibility_criteria_met is True
        assert len(result.triggered_complicating_factors) > 0
        assert (
            "systemic_or_upper_tract_symptoms" in result.triggered_complicating_factors
        )

    def test_male_patient_referred(self):
        patient = MaleUTIPatientFactory()

        result = assess_uti_patient(patient)

        assert result.decision == Decision.refer_complicated
        assert result.recommendation is None
        assert result.eligibility_criteria_met is True
        assert "male_patient" in result.triggered_complicating_factors

    def test_recurrent_patient_referred(self):
        patient = RecurrentUTIPatientFactory()

        result = assess_uti_patient(patient)

        assert result.decision == Decision.refer_recurrence
        assert result.recommendation is None
        assert result.eligibility_criteria_met is True
        assert len(result.triggered_recurrence_markers) > 0
        assert "recurrent UTI: ≥2 in 6 months" in result.triggered_recurrence_markers

    def test_no_treatment_options_referred(self):
        patient = SimpleUTIPatientFactory()
        patient.history.antibiotics_last_90d = True  # Blocks all options

        result = assess_uti_patient(patient)

        assert result.decision == Decision.refer_complicated
        assert result.recommendation is None
        assert result.eligibility_criteria_met is True
        assert "No safe first-line antibiotic option" in " ".join(result.rationale)

    def test_audit_included(self):
        patient = SimpleUTIPatientFactory()

        result = assess_uti_patient(patient)

        assert "audit" in result.model_dump()
        assert "timestamp" in result.audit
        assert "algorithm_version" in result.audit


class TestFollowUpPlan:
    def test_get_follow_up_plan(self):
        plan = get_follow_up_plan()

        assert "assessment_timeframe" in plan
        assert plan["assessment_timeframe"] == "48-72 hours"
        assert "instructions" in plan
        assert len(plan["instructions"]) > 0
        assert "red_flags_for_escalation" in plan
        assert len(plan["red_flags_for_escalation"]) > 0

    def test_get_enhanced_follow_up_plan(self):
        patient = SimpleUTIPatientFactory()

        plan = get_enhanced_follow_up_plan(patient)

        assert "follow_up_plan" in plan
        assert "monitoring_checklist" in plan
        assert "special_instructions" in plan
        assert "provider_actions" in plan

        # Check provider actions
        assert len(plan["provider_actions"]) > 0
        assert any(
            "documentation" in action.lower() for action in plan["provider_actions"]
        )

    def test_enhanced_follow_up_elderly_patient(self):
        patient = ElderlyUTIPatientFactory()

        plan = get_enhanced_follow_up_plan(patient)

        # Should have special instructions for elderly
        special_instructions = plan["special_instructions"]
        assert any(
            "elderly" in instruction.lower() for instruction in special_instructions
        )

    def test_enhanced_follow_up_acei_arb_patient(self):
        patient = ElderlyUTIPatientFactory()  # Has ACEI use

        plan = get_enhanced_follow_up_plan(patient)

        # Should have hyperkalemia monitoring
        special_instructions = plan["special_instructions"]
        assert any(
            "hyperkalemia" in instruction.lower()
            for instruction in special_instructions
        )

    def test_enhanced_follow_up_renal_impairment(self):
        patient = ElderlyUTIPatientFactory()  # Has impaired renal function

        plan = get_enhanced_follow_up_plan(patient)

        # Should have renal dosing considerations
        special_instructions = plan["special_instructions"]
        assert any(
            "renal" in instruction.lower() for instruction in special_instructions
        )


class TestContraindications:
    def test_get_contraindications_from_assessment_with_recommendation(self):
        patient = SimpleUTIPatientFactory()
        assessment = assess_uti_patient(patient)

        contraindications = get_contraindications_from_assessment(assessment)

        if assessment.recommendation:
            assert isinstance(contraindications, list)
        else:
            assert contraindications == []

    def test_get_contraindications_from_assessment_no_recommendation(self):
        patient = MaleUTIPatientFactory()  # Will be referred
        assessment = assess_uti_patient(patient)

        contraindications = get_contraindications_from_assessment(assessment)

        assert contraindications == []


class TestStateValidator:
    def test_validator_no_issues(self):
        patient = SimpleUTIPatientFactory()
        regimen_text = "nitrofurantoin 100 mg PO BID x 5 days"
        safety = {"approval_recommendation": "approve"}

        result = state_validator(patient, regimen_text, safety)

        assert result.passed is True
        assert len(result.rules_fired) == 0
        assert len(result.contradictions) == 0
        assert result.severity == "low"

    def test_validator_safety_rejection_contradiction(self):
        patient = SimpleUTIPatientFactory()
        regimen_text = "nitrofurantoin 100 mg PO BID x 5 days"
        safety = {"approval_recommendation": "reject"}

        result = state_validator(patient, regimen_text, safety)

        assert result.passed is False
        assert "Safety rejected but regimen present" in result.contradictions
        assert result.severity == "high"

    def test_validator_nitrofurantoin_renal_failure(self):
        patient = SimpleUTIPatientFactory()
        patient.renal_function_summary = RenalFunction.failure
        regimen_text = "nitrofurantoin 100 mg PO BID x 5 days"
        safety = {"approval_recommendation": "approve"}

        result = state_validator(patient, regimen_text, safety)

        assert result.passed is False
        assert "avoid_nitrofurantoin_in_renal_failure" in result.rules_fired
        assert result.severity == "high"

    def test_validator_nitrofurantoin_low_egfr(self):
        patient = ElderlyUTIPatientFactory()  # Has egfr_ml_min = 25.0
        regimen_text = "nitrofurantoin 100 mg PO BID x 5 days"
        safety = {"approval_recommendation": "approve"}

        result = state_validator(patient, regimen_text, safety)

        assert result.passed is False
        assert "avoid_nitrofurantoin_egfr_lt_30" in result.rules_fired
        assert result.severity == "high"

    def test_validator_tmp_smx_acei_interaction(self):
        patient = ElderlyUTIPatientFactory()  # Has ACEI use
        regimen_text = "TMP/SMX 160/800 mg PO BID x 3 days"
        safety = {"approval_recommendation": "approve"}

        result = state_validator(patient, regimen_text, safety)

        assert "acei_arb_plus_tmpsmx_hyperkalemia_risk" in result.rules_fired
        assert result.severity in ["moderate", "high"]

    def test_validator_fosfomycin_age_restriction(self):
        patient = PediatricPatientFactory()
        patient.age = 16
        regimen_text = "fosfomycin 3g PO single dose"
        safety = {"approval_recommendation": "approve"}

        result = state_validator(patient, regimen_text, safety)

        assert result.passed is False
        assert "fosfomycin_not_indicated_under_18" in result.rules_fired
        assert result.severity == "high"

    def test_validator_duration_checks(self):
        patient = SimpleUTIPatientFactory()
        regimen_text = "nitrofurantoin 100 mg PO BID x 3 days"  # Wrong duration
        safety = {"approval_recommendation": "approve"}

        result = state_validator(patient, regimen_text, safety)

        assert "nitrofurantoin_duration_check_5_days" in result.rules_fired

    def test_validator_dose_checks(self):
        patient = SimpleUTIPatientFactory()
        regimen_text = "fosfomycin 1g PO single dose"  # Wrong dose
        safety = {"approval_recommendation": "approve"}

        result = state_validator(patient, regimen_text, safety)

        assert "fosfomycin_dose_check_3g_single_dose" in result.rules_fired


class TestCreateAudit:
    def test_create_audit_structure(self):
        audit = _create_audit()

        assert "timestamp" in audit
        assert "algorithm_version" in audit
        assert audit["algorithm_version"] == "mermaid_v1"

        # Verify timestamp is valid ISO format
        datetime.fromisoformat(audit["timestamp"])
