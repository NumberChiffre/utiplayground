from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models import (
    PREGNANCY_EXCLUSIONS,
    REJECT_TERMS,
    TMP_SMX_ALLERGY_TERMS,
    TREATMENT_OPTIONS,
    ApprovalDecision,
    AssessmentOutput,
    ClinicalReasoningOutput,
    Decision,
    History,
    MedicationAgent,
    MedicationSpec,
    PatientState,
    PregnancyStatus,
    Recommendation,
    Recurrence,
    RecurrenceResult,
    RedFlags,
    RenalFunction,
    RiskLevel,
    SafetyValidationOutput,
    Sex,
    Symptoms,
)
from tests.factories import (
    PatientStateFactory,
    SimpleUTIPatientFactory,
)


class TestEnums:
    def test_sex_enum_values(self):
        assert Sex.female == "female"
        assert Sex.male == "male"
        assert Sex.other == "other"
        assert Sex.unknown == "unknown"

    def test_renal_function_enum_values(self):
        assert RenalFunction.normal == "normal"
        assert RenalFunction.impaired == "impaired"
        assert RenalFunction.failure == "failure"
        assert RenalFunction.unknown == "unknown"

    def test_medication_agent_enum_values(self):
        assert MedicationAgent.nitrofurantoin == "nitrofurantoin"
        assert MedicationAgent.tmp_smx == "tmp_smx"
        assert MedicationAgent.trimethoprim == "trimethoprim"
        assert MedicationAgent.fosfomycin == "fosfomycin"

    def test_pregnancy_status_enum_values(self):
        assert PregnancyStatus.pregnant == "pregnant"
        assert PregnancyStatus.not_pregnant == "not_pregnant"
        assert PregnancyStatus.not_applicable == "not_applicable"
        assert PregnancyStatus.unknown == "unknown"
        assert PregnancyStatus.no == "no"

    def test_decision_enum_values(self):
        assert Decision.no_antibiotics_not_met == "no_antibiotics_not_met"
        assert Decision.refer_complicated == "refer_complicated"
        assert Decision.refer_recurrence == "refer_recurrence"
        assert Decision.recommend_treatment == "recommend_treatment"

    def test_approval_decision_enum_values(self):
        assert ApprovalDecision.approve == "approve"
        assert ApprovalDecision.conditional == "conditional"
        assert ApprovalDecision.modify == "modify"
        assert ApprovalDecision.reject == "reject"


class TestConstants:
    def test_pregnancy_exclusions(self):
        expected = {
            PregnancyStatus.no,
            PregnancyStatus.not_pregnant,
            PregnancyStatus.not_applicable,
            PregnancyStatus.unknown,
        }
        assert expected == PREGNANCY_EXCLUSIONS

    def test_tmp_smx_allergy_terms(self):
        expected = {"tmp/smx", "trimethoprim", "sulfamethoxazole", "sulfonamides"}
        assert expected == TMP_SMX_ALLERGY_TERMS

    def test_reject_terms(self):
        expected = {"reject", "do not start", "refer_no_antibiotics"}
        assert expected == REJECT_TERMS

    def test_treatment_options_structure(self):
        assert MedicationAgent.nitrofurantoin in TREATMENT_OPTIONS
        assert MedicationAgent.tmp_smx in TREATMENT_OPTIONS
        assert MedicationAgent.trimethoprim in TREATMENT_OPTIONS
        assert MedicationAgent.fosfomycin in TREATMENT_OPTIONS

        nitro_spec = TREATMENT_OPTIONS[MedicationAgent.nitrofurantoin]
        assert isinstance(nitro_spec, MedicationSpec)
        assert nitro_spec.regimen == "Nitrofurantoin macrocrystals"
        assert nitro_spec.agent == MedicationAgent.nitrofurantoin
        assert nitro_spec.dose == "100 mg"
        assert nitro_spec.frequency == "PO BID"
        assert nitro_spec.duration == "5 days"


class TestMedicationSpec:
    def test_medication_spec_creation(self):
        spec = MedicationSpec(
            regimen="Test Regimen",
            agent=MedicationAgent.nitrofurantoin,
            dose="100 mg",
            frequency="PO BID",
            duration="5 days",
            alternatives=["Alternative 1"],
            contraindications=["Allergy"],
            monitoring=["Monitor for side effects"],
        )

        assert spec.regimen == "Test Regimen"
        assert spec.agent == MedicationAgent.nitrofurantoin
        assert spec.dose == "100 mg"
        assert spec.frequency == "PO BID"
        assert spec.duration == "5 days"
        assert spec.alternatives == ["Alternative 1"]
        assert spec.contraindications == ["Allergy"]
        assert spec.monitoring == ["Monitor for side effects"]

    def test_medication_spec_immutable(self):
        spec = MedicationSpec(
            regimen="Test",
            agent=MedicationAgent.nitrofurantoin,
            dose="100 mg",
            frequency="PO BID",
            duration="5 days",
            alternatives=[],
            contraindications=[],
            monitoring=[],
        )

        # Test that it's frozen (immutable)
        with pytest.raises(Exception):  # dataclass frozen raises FrozenInstanceError
            spec.regimen = "Modified"


class TestRecurrenceResult:
    def test_recurrence_result_creation(self):
        result = RecurrenceResult(True, "Test reason")
        assert result.has_recurrence is True
        assert result.reason == "Test reason"

        result = RecurrenceResult(False, "")
        assert result.has_recurrence is False
        assert result.reason == ""


class TestSymptoms:
    def test_symptoms_valid_creation(self):
        symptoms = Symptoms(
            dysuria=True,
            urgency=True,
            frequency=False,
            suprapubic_pain=False,
            hematuria=False,
        )

        assert symptoms.dysuria is True
        assert symptoms.urgency is True
        assert symptoms.frequency is False
        assert symptoms.suprapubic_pain is False
        assert symptoms.hematuria is False
        assert symptoms.gross_hematuria is False  # default
        assert symptoms.confusion is False  # default
        assert symptoms.delirium is False  # default

    def test_symptoms_all_fields(self):
        symptoms = Symptoms(
            dysuria=True,
            urgency=False,
            frequency=True,
            suprapubic_pain=True,
            hematuria=True,
            gross_hematuria=True,
            confusion=True,
            delirium=True,
        )

        assert symptoms.dysuria is True
        assert symptoms.urgency is False
        assert symptoms.frequency is True
        assert symptoms.suprapubic_pain is True
        assert symptoms.hematuria is True
        assert symptoms.gross_hematuria is True
        assert symptoms.confusion is True
        assert symptoms.delirium is True

    def test_symptoms_validation_error(self):
        with pytest.raises(ValidationError):
            Symptoms(
                # Missing required fields
                dysuria=True,
            )


class TestRedFlags:
    def test_red_flags_valid_creation(self):
        red_flags = RedFlags(
            fever=True,
            rigors=False,
            flank_pain=True,
            nausea_vomiting=False,
            systemic=False,
        )

        assert red_flags.fever is True
        assert red_flags.rigors is False
        assert red_flags.flank_pain is True
        assert red_flags.back_pain is False  # default
        assert red_flags.nausea_vomiting is False
        assert red_flags.systemic is False

    def test_red_flags_all_fields(self):
        red_flags = RedFlags(
            fever=True,
            rigors=True,
            flank_pain=True,
            back_pain=True,
            nausea_vomiting=True,
            systemic=True,
        )

        assert all(
            [
                red_flags.fever,
                red_flags.rigors,
                red_flags.flank_pain,
                red_flags.back_pain,
                red_flags.nausea_vomiting,
                red_flags.systemic,
            ]
        )


class TestHistory:
    def test_history_basic_creation(self):
        history = History(
            antibiotics_last_90d=False,
            ACEI_ARB_use=False,
            catheter=False,
            stones=False,
            immunocompromised=False,
        )

        assert history.antibiotics_last_90d is False
        assert history.allergies == []  # default
        assert history.meds == []  # default
        assert history.ACEI_ARB_use is False
        assert history.catheter is False
        assert history.stones is False
        assert history.immunocompromised is False
        assert history.neurogenic_bladder is False  # default
        assert history.med_classes == set()  # default

    def test_history_with_medications(self):
        history = History(
            antibiotics_last_90d=False,
            allergies=["penicillin", "sulfa"],
            meds=["lisinopril", "ibuprofen", "spironolactone"],
            ACEI_ARB_use=True,
            catheter=False,
            stones=False,
            immunocompromised=False,
        )

        assert history.allergies == ["penicillin", "sulfa"]
        assert history.meds == ["lisinopril", "ibuprofen", "spironolactone"]
        # Test medication class inference
        assert History.MedClass.acei in history.med_classes
        assert History.MedClass.nsaid in history.med_classes
        assert History.MedClass.potassium_sparing in history.med_classes

    def test_medication_class_inference_acei(self):
        history = History(
            antibiotics_last_90d=False,
            meds=["lisinopril", "enalapril", "ramipril"],
            ACEI_ARB_use=False,
            catheter=False,
            stones=False,
            immunocompromised=False,
        )

        assert History.MedClass.acei in history.med_classes

    def test_medication_class_inference_arb(self):
        history = History(
            antibiotics_last_90d=False,
            meds=["losartan", "valsartan"],
            ACEI_ARB_use=False,
            catheter=False,
            stones=False,
            immunocompromised=False,
        )

        assert History.MedClass.arb in history.med_classes

    def test_medication_class_inference_nsaid(self):
        history = History(
            antibiotics_last_90d=False,
            meds=["ibuprofen", "naproxen", "diclofenac"],
            ACEI_ARB_use=False,
            catheter=False,
            stones=False,
            immunocompromised=False,
        )

        assert History.MedClass.nsaid in history.med_classes

    def test_medication_class_inference_potassium_sparing(self):
        history = History(
            antibiotics_last_90d=False,
            meds=["spironolactone", "amiloride"],
            ACEI_ARB_use=False,
            catheter=False,
            stones=False,
            immunocompromised=False,
        )

        assert History.MedClass.potassium_sparing in history.med_classes


class TestRecurrence:
    def test_recurrence_creation(self):
        recurrence = Recurrence(
            relapse_within_4w=False,
            recurrent_6m=True,
            recurrent_12m=False,
        )

        assert recurrence.relapse_within_4w is False
        assert recurrence.recurrent_6m is True
        assert recurrence.recurrent_12m is False


class TestPatientState:
    def test_patient_state_valid_creation(self):
        patient_data = {
            "age": 25,
            "sex": Sex.female,
            "pregnancy_status": PregnancyStatus.not_pregnant,
            "renal_function_summary": RenalFunction.normal,
            "symptoms": Symptoms(
                dysuria=True,
                urgency=True,
                frequency=False,
                suprapubic_pain=False,
                hematuria=False,
            ),
            "red_flags": RedFlags(
                fever=False,
                rigors=False,
                flank_pain=False,
                nausea_vomiting=False,
                systemic=False,
            ),
            "history": History(
                antibiotics_last_90d=False,
                ACEI_ARB_use=False,
                catheter=False,
                stones=False,
                immunocompromised=False,
            ),
            "recurrence": Recurrence(
                relapse_within_4w=False,
                recurrent_6m=False,
                recurrent_12m=False,
            ),
            "locale_code": "CA-ON",
        }

        patient = PatientState(**patient_data)

        assert patient.age == 25
        assert patient.sex == Sex.female
        assert patient.pregnancy_status == PregnancyStatus.not_pregnant
        assert patient.renal_function_summary == RenalFunction.normal
        assert patient.locale_code == "CA-ON"
        assert patient.asymptomatic_bacteriuria is False  # default

    def test_patient_state_age_validation(self):
        with pytest.raises(ValidationError):
            PatientStateFactory(age=-1)

        with pytest.raises(ValidationError):
            PatientStateFactory(age=150)

    def test_patient_state_pregnancy_validation_male(self):
        # Male patient with pregnancy status should auto-correct
        patient = PatientStateFactory(
            sex=Sex.male,
            pregnancy_status=PregnancyStatus.pregnant,
        )

        assert patient.sex == Sex.male
        assert patient.pregnancy_status == PregnancyStatus.not_applicable

    def test_patient_state_with_egfr(self):
        patient = PatientStateFactory(
            renal_function_summary=RenalFunction.impaired,
            egfr_mL_min=25.0,
        )

        assert patient.egfr_mL_min == 25.0

    def test_patient_state_locale_code_validation(self):
        with pytest.raises(ValidationError):
            PatientStateFactory(locale_code="X")  # too short

        with pytest.raises(ValidationError):
            PatientStateFactory(locale_code="X" * 20)  # too long


class TestRecommendation:
    def test_recommendation_creation(self):
        rec = Recommendation(
            regimen="Nitrofurantoin macrocrystals",
            regimen_agent=MedicationAgent.nitrofurantoin,
            dose="100 mg",
            frequency="PO BID",
            duration="5 days",
            alternatives=["TMP/SMX"],
            contraindications=["eGFR <30"],
            monitoring=["Take with food"],
        )

        assert rec.regimen == "Nitrofurantoin macrocrystals"
        assert rec.regimen_agent == MedicationAgent.nitrofurantoin
        assert rec.dose == "100 mg"
        assert rec.frequency == "PO BID"
        assert rec.duration == "5 days"
        assert rec.alternatives == ["TMP/SMX"]
        assert rec.contraindications == ["eGFR <30"]
        assert rec.monitoring == ["Take with food"]

    def test_recommendation_as_text(self):
        rec = Recommendation(
            regimen="Nitrofurantoin",
            dose="100 mg",
            frequency="PO BID",
            duration="5 days",
        )

        expected = "Nitrofurantoin 100 mg PO BID x 5 days"
        assert rec.as_text() == expected

    def test_recommendation_as_text_no_duration(self):
        rec = Recommendation(
            regimen="Nitrofurantoin",
            dose="100 mg",
            frequency="PO BID",
            duration="",
        )

        expected = "Nitrofurantoin 100 mg PO BID"
        assert rec.as_text() == expected


class TestAssessmentOutput:
    def test_assessment_output_creation(self):
        assessment = AssessmentOutput(
            decision=Decision.recommend_treatment,
            recommendation=Recommendation(
                regimen="Nitrofurantoin",
                dose="100 mg",
                frequency="PO BID",
                duration="5 days",
            ),
            rationale=["Patient meets criteria"],
            audit={"timestamp": "2024-01-01"},
            version="v1",
        )

        assert assessment.decision == Decision.recommend_treatment
        assert assessment.recommendation is not None
        assert assessment.rationale == ["Patient meets criteria"]
        assert assessment.audit == {"timestamp": "2024-01-01"}
        assert assessment.version == "v1"
        assert assessment.eligibility_criteria_met is False  # default
        assert assessment.triggered_complicating_factors == []  # default
        assert assessment.triggered_recurrence_markers == []  # default


class TestClinicalReasoningOutput:
    def test_clinical_reasoning_creation(self):
        output = ClinicalReasoningOutput(
            reasoning=["Symptom analysis", "Treatment rationale"],
            confidence=0.85,
            differential_dx=["Cystitis", "Urethritis"],
            risk_factors=["Age", "Gender"],
            recommendations=["Start antibiotics"],
            clinical_rationale=["Based on symptoms"],
            stewardship_considerations=["Short course"],
            citations=[
                {
                    "title": "UTI Guidelines",
                    "url": "http://example.com",
                    "relevance": "high",
                }
            ],
            proposed_regimen_text="Nitrofurantoin 100 mg PO BID x 5 days",
        )

        assert output.reasoning == ["Symptom analysis", "Treatment rationale"]
        assert output.confidence == 0.85
        assert output.differential_dx == ["Cystitis", "Urethritis"]
        assert output.proposed_regimen_text == "Nitrofurantoin 100 mg PO BID x 5 days"

    def test_clinical_reasoning_confidence_validation(self):
        with pytest.raises(ValidationError):
            ClinicalReasoningOutput(confidence=-0.1)

        with pytest.raises(ValidationError):
            ClinicalReasoningOutput(confidence=1.1)

    def test_clinical_reasoning_as_narrative(self):
        output = ClinicalReasoningOutput(
            reasoning=["Clear UTI symptoms"],
            recommendations=["Start treatment"],
            stewardship_considerations=["Short course preferred"],
        )

        narrative = output.as_narrative()
        assert "Key reasoning:" in narrative
        assert "• Clear UTI symptoms" in narrative
        assert "Recommendations:" in narrative
        assert "• Start treatment" in narrative
        assert "Stewardship:" in narrative
        assert "• Short course preferred" in narrative


class TestSafetyValidationOutput:
    def test_safety_validation_creation(self):
        output = SafetyValidationOutput(
            safety_flags=["Monitor renal function"],
            contraindications=["Pregnancy"],
            drug_interactions=["ACE inhibitor interaction"],
            monitoring_requirements=["Check potassium"],
            risk_level=RiskLevel.moderate,
            approval_recommendation=ApprovalDecision.conditional,
            rationale="Conditional due to renal function",
        )

        assert output.safety_flags == ["Monitor renal function"]
        assert output.contraindications == ["Pregnancy"]
        assert output.drug_interactions == ["ACE inhibitor interaction"]
        assert output.risk_level == RiskLevel.moderate
        assert output.approval_recommendation == ApprovalDecision.conditional
        assert output.rationale == "Conditional due to renal function"

    def test_safety_validation_as_narrative(self):
        output = SafetyValidationOutput(
            risk_level=RiskLevel.high,
            contraindications=["Severe renal impairment"],
            drug_interactions=["ACE inhibitor"],
            monitoring_requirements=["Monitor potassium"],
        )

        narrative = output.as_narrative()
        assert "Risk level: high" in narrative
        assert "Contraindications:" in narrative
        assert "• Severe renal impairment" in narrative
        assert "Interactions:" in narrative
        assert "• ACE inhibitor" in narrative
        assert "Monitoring:" in narrative
        assert "• Monitor potassium" in narrative


class TestFactoryIntegration:
    def test_simple_uti_patient_factory(self):
        patient = SimpleUTIPatientFactory()

        assert isinstance(patient, PatientState)
        assert patient.age == 25
        assert patient.sex == Sex.female
        assert patient.symptoms.dysuria is True
        assert patient.symptoms.urgency is True

    def test_patient_state_factory_randomization(self):
        # Test that factory generates different patients
        patients = [PatientStateFactory() for _ in range(5)]

        # At least some should be different ages (probabilistic test)
        ages = [p.age for p in patients]
        assert len(set(ages)) > 1 or len(ages) == 1  # Allow for rare case of all same

    def test_factory_with_validation(self):
        # Test that factory-created patients are valid
        patient = PatientStateFactory()

        # Should not raise validation errors
        assert isinstance(patient, PatientState)
        assert 0 <= patient.age <= 120
        assert len(patient.locale_code) >= 2
