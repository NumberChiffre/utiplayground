from __future__ import annotations

from src.models import AssessmentOutput, Decision
from src.prompts import (
    make_clinical_reasoning_prompt,
    make_diagnosis_xml_prompt,
    make_safety_validation_prompt,
    make_web_research_prompt,
)
from tests.factories import SimpleUTIPatientFactory


class TestPromptGeneration:
    """Test prompt generation functions"""

    def test_clinical_reasoning_prompt_basic(self):
        """Test basic clinical reasoning prompt generation"""
        patient = SimpleUTIPatientFactory()

        prompt = make_clinical_reasoning_prompt(patient)

        # Should return a string
        assert isinstance(prompt, str)
        # Should contain patient information
        assert str(patient.age) in prompt
        assert patient.sex.value in prompt
        # Should be non-empty
        assert len(prompt) > 100

    def test_clinical_reasoning_prompt_with_assessment(self):
        """Test clinical reasoning prompt with assessment details"""
        patient = SimpleUTIPatientFactory()
        assessment_details = {
            "decision": "recommend_treatment",
            "recommendation": {"regimen": "Nitrofurantoin"},
            "rationale": ["Test rationale"],
        }

        prompt = make_clinical_reasoning_prompt(patient, assessment_details)

        # Should include assessment context
        assert "recommend_treatment" in prompt
        assert "Nitrofurantoin" in prompt
        assert "Test rationale" in prompt
        assert len(prompt) > 100

    def test_safety_validation_prompt_basic(self):
        """Test basic safety validation prompt generation"""
        patient = SimpleUTIPatientFactory()
        decision = "recommend_treatment"
        regimen_text = "Nitrofurantoin 100 mg PO BID x 5 days"

        prompt = make_safety_validation_prompt(patient, decision, regimen_text)

        # Should return a string
        assert isinstance(prompt, str)
        # Should contain key information
        assert decision in prompt
        assert regimen_text in prompt
        assert str(patient.age) in prompt
        # Should be non-empty
        assert len(prompt) > 100

    def test_safety_validation_prompt_with_clinical_context(self):
        """Test safety validation prompt with clinical reasoning context"""
        patient = SimpleUTIPatientFactory()
        decision = "recommend_treatment"
        regimen_text = "Nitrofurantoin 100 mg PO BID x 5 days"
        clinical_context = {
            "reasoning": ["Patient has classic UTI symptoms"],
            "confidence": 0.9,
        }

        prompt = make_safety_validation_prompt(
            patient,
            decision,
            regimen_text,
            clinical_context,
        )

        # Should include clinical context
        assert "classic UTI symptoms" in prompt
        assert "0.9" in prompt
        assert len(prompt) > 100

    def test_web_research_prompt(self):
        """Test web research prompt generation"""
        query = "UTI antibiotic resistance patterns"
        region = "CA-ON"

        prompt = make_web_research_prompt(query, region)

        # Should return a string
        assert isinstance(prompt, str)
        # Should contain query and region
        assert query in prompt
        assert region in prompt
        # Should be non-empty
        assert len(prompt) > 50

    def test_diagnosis_xml_prompt_basic(self):
        """Test XML diagnosis prompt generation"""
        patient = SimpleUTIPatientFactory()
        assessment = AssessmentOutput(
            decision=Decision.recommend_treatment,
            rationale=["Patient meets criteria for UTI treatment"],
        )

        prompt = make_diagnosis_xml_prompt(patient, assessment)

        # Should return a string
        assert isinstance(prompt, str)
        # Should contain patient and assessment info
        assert "recommend_treatment" in prompt
        assert "meets criteria" in prompt
        # Should be substantial
        assert len(prompt) > 200

    def test_diagnosis_xml_prompt_with_contexts(self):
        """Test XML diagnosis prompt with additional contexts"""
        patient = SimpleUTIPatientFactory()
        assessment = AssessmentOutput(
            decision=Decision.recommend_treatment,
            rationale=["Patient meets criteria"],
        )
        doctor_reasoning = {
            "reasoning": ["Clinical assessment shows UTI"],
            "confidence": 0.85,
        }
        safety_context = {
            "approval_recommendation": "approve",
            "risk_level": "low",
        }

        prompt = make_diagnosis_xml_prompt(
            patient,
            assessment,
            doctor_reasoning,
            safety_context,
        )

        # Should include all contexts
        assert "Clinical assessment shows UTI" in prompt
        assert "0.85" in prompt
        assert "approve" in prompt
        assert "low" in prompt
        assert len(prompt) > 300


class TestPromptEdgeCases:
    """Test edge cases in prompt generation"""

    def test_clinical_reasoning_prompt_none_assessment(self):
        """Test clinical reasoning prompt with None assessment"""
        patient = SimpleUTIPatientFactory()

        # Should handle None assessment gracefully
        prompt = make_clinical_reasoning_prompt(patient, None)

        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_safety_validation_prompt_none_regimen(self):
        """Test safety validation prompt with None regimen"""
        patient = SimpleUTIPatientFactory()
        decision = "refer_complicated"

        prompt = make_safety_validation_prompt(patient, decision, "None")

        assert isinstance(prompt, str)
        assert decision in prompt
        assert len(prompt) > 100

    def test_web_research_prompt_empty_query(self):
        """Test web research prompt with empty query"""
        prompt = make_web_research_prompt("", "CA-ON")

        # Should still generate a prompt
        assert isinstance(prompt, str)
        assert "CA-ON" in prompt
        assert len(prompt) > 20

    def test_diagnosis_xml_prompt_minimal_assessment(self):
        """Test XML diagnosis prompt with minimal assessment"""
        patient = SimpleUTIPatientFactory()
        assessment = AssessmentOutput(decision=Decision.no_antibiotics_not_met)

        prompt = make_diagnosis_xml_prompt(patient, assessment, None, None)

        assert isinstance(prompt, str)
        assert "no_antibiotics_not_met" in prompt
        assert len(prompt) > 100


class TestPromptConsistency:
    """Test prompt consistency and formatting"""

    def test_prompt_format_consistency(self):
        """Test that prompts have consistent formatting"""
        patient = SimpleUTIPatientFactory()

        # Generate different types of prompts
        clinical_prompt = make_clinical_reasoning_prompt(patient)
        safety_prompt = make_safety_validation_prompt(
            patient, "recommend_treatment", "test regimen"
        )
        research_prompt = make_web_research_prompt("test query", "CA-ON")

        # All should be non-empty strings
        prompts = [clinical_prompt, safety_prompt, research_prompt]
        for prompt in prompts:
            assert isinstance(prompt, str)
            assert len(prompt) > 50
            # Should not have obvious formatting issues
            assert not prompt.startswith(" ")
            assert not prompt.endswith(" ")

    def test_patient_information_inclusion(self):
        """Test that patient information is properly included in prompts"""
        patient = SimpleUTIPatientFactory()
        patient.age = 42  # Set specific age to test

        clinical_prompt = make_clinical_reasoning_prompt(patient)
        safety_prompt = make_safety_validation_prompt(
            patient, "recommend_treatment", "test"
        )

        # Both should include patient age
        assert "42" in clinical_prompt
        assert "42" in safety_prompt

        # Both should include patient sex
        assert patient.sex.value in clinical_prompt
        assert patient.sex.value in safety_prompt

    def test_prompt_length_reasonable(self):
        """Test that prompts are reasonable length (not too short or excessive)"""
        patient = SimpleUTIPatientFactory()
        assessment = AssessmentOutput(decision=Decision.recommend_treatment)

        prompts = [
            make_clinical_reasoning_prompt(patient),
            make_safety_validation_prompt(
                patient, "recommend_treatment", "test regimen"
            ),
            make_web_research_prompt("test query", "CA-ON"),
            make_diagnosis_xml_prompt(patient, assessment),
        ]

        for prompt in prompts:
            # Should be substantial but not excessive
            assert 50 < len(prompt) < 10000
            # Should not be mostly whitespace
            assert len(prompt.strip()) > len(prompt) * 0.8
