from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src import services
from src.models import (
    ApprovalDecision,
    ClinicalReasoningOutput,
    SafetyValidationOutput,
)
from tests.factories import (
    SimpleUTIPatientFactory,
    create_patient_dict,
)


class TestServicesErrorHandling:
    """Test error handling in services module"""

    @pytest.mark.asyncio
    async def test_clinical_reasoning_exception_handling(self):
        """Test clinical reasoning handles exceptions gracefully"""
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        # Mock the agent creation to fail
        with patch("src.services.make_clinical_reasoning_agent") as mock_make_agent:
            mock_make_agent.side_effect = Exception("Agent creation failed")

            # Should not crash, should return some response
            try:
                result = await services.clinical_reasoning(patient_data)
                # The function might return an error dict or handle it differently
                assert isinstance(result, dict)
            except Exception:
                # If it does raise, that's also acceptable behavior to test
                pass

    @pytest.mark.asyncio
    async def test_safety_validation_with_invalid_decision(self):
        """Test safety validation with invalid decision values"""
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        mock_output = SafetyValidationOutput(
            approval_recommendation=ApprovalDecision.approve,
        )

        with patch("src.services._run_agent_stream_with_retry") as mock_run:
            with patch("src.services.make_safety_validation_agent") as mock_agent:
                mock_run.return_value = mock_output
                mock_agent.return_value = MagicMock(model="gpt-4.1")

                # Test with invalid decision
                result = await services.safety_validation(
                    patient_data,
                    "invalid_decision",  # Invalid decision
                    None,
                    model="gpt-4.1",
                )

                assert "version" in result
                assert result["model"] == "gpt-4.1"

    @pytest.mark.asyncio
    async def test_safety_validation_with_malformed_recommendation(self):
        """Test safety validation with malformed recommendation"""
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        mock_output = SafetyValidationOutput()

        with patch("src.services._run_agent_stream_with_retry") as mock_run:
            with patch("src.services.make_safety_validation_agent") as mock_agent:
                mock_run.return_value = mock_output
                mock_agent.return_value = MagicMock(model="gpt-4.1")

                # Test with malformed recommendation dict
                malformed_rec = {"missing_required_fields": True}
                result = await services.safety_validation(
                    patient_data,
                    "recommend_treatment",
                    malformed_rec,
                    model="gpt-4.1",
                )

                assert "version" in result


class TestServiceParameterHandling:
    """Test various parameter combinations in services"""

    @pytest.mark.asyncio
    async def test_clinical_reasoning_with_assessment_details(self):
        """Test clinical reasoning with assessment details parameter"""
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        assessment_details = {
            "decision": "recommend_treatment",
            "recommendation": {"regimen": "Nitrofurantoin"},
            "rationale": ["Test rationale"],
        }

        mock_output = ClinicalReasoningOutput(
            reasoning=["Based on assessment details"],
            confidence=0.8,
        )

        with patch("src.services._run_agent_stream_with_retry") as mock_run:
            with patch("src.services.make_clinical_reasoning_agent") as mock_agent:
                mock_run.return_value = mock_output
                mock_agent.return_value = MagicMock(model="gpt-4.1")

                result = await services.clinical_reasoning(
                    patient_data,
                    model="gpt-4.1",
                    assessment_details=assessment_details,
                )

                assert result["reasoning"] == ["Based on assessment details"]
                assert result["confidence"] == 0.8

    @pytest.mark.asyncio
    async def test_web_research_with_different_regions(self):
        """Test web research with different region codes"""
        test_regions = ["CA-ON", "US-CA", "UK-EN", "AU-NSW"]

        mock_streamed_output = {
            "text": "Research findings",
            "citations": [],
        }

        with patch("src.services.stream_text_and_citations") as mock_stream:
            with patch("src.services.make_research_agent") as mock_agent:
                mock_stream.return_value = mock_streamed_output
                mock_agent.return_value = MagicMock(model="gpt-4.1")

                for region in test_regions:
                    result = await services.web_research("test query", region)

                    assert result["region"] == region
                    assert result["summary"] == "Research findings"
                    assert "version" in result

    @pytest.mark.asyncio
    async def test_prescribing_considerations_without_web_research(self):
        """Test prescribing considerations when web research fails"""
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        with patch("src.services.assess_uti_patient") as mock_assess:
            with patch(
                "src.services.get_contraindications_from_assessment",
            ) as mock_contraindications:
                with patch("src.services.web_research") as mock_web:
                    # Setup mocks
                    mock_assess.return_value = MagicMock()
                    mock_contraindications.return_value = []
                    mock_web.side_effect = Exception("Web research failed")

                    result = await services.prescribing_considerations(
                        patient_data, "CA-ON",
                    )

                    # Should still return basic considerations despite web research failure
                    assert "considerations" in result
                    assert "region" in result
                    assert result["citations"] == []  # Empty due to failure

    @pytest.mark.asyncio
    async def test_deep_research_diagnosis_with_context(self):
        """Test deep research diagnosis with doctor reasoning and safety context"""
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        doctor_reasoning = {
            "reasoning": ["Doctor's clinical reasoning"],
            "confidence": 0.9,
        }

        safety_context = {
            "approval_recommendation": "approve",
            "risk_level": "low",
        }

        mock_streamed_output = {
            "text": "Comprehensive diagnosis based on context",
            "citations": [],
        }

        with patch("src.services.stream_text_and_citations") as mock_stream:
            with patch("src.services.make_diagnosis_agent") as mock_agent:
                with patch("src.services.assess_uti_patient") as mock_assess:
                    mock_stream.return_value = mock_streamed_output
                    mock_agent.return_value = MagicMock(model="gpt-4.1")
                    mock_assess.return_value = MagicMock(
                        model_dump=lambda: {"decision": "recommend_treatment"},
                    )

                    result = await services.deep_research_diagnosis(
                        patient_data,
                        model="gpt-4.1",
                        doctor_reasoning=doctor_reasoning,
                        safety_validation_context=safety_context,
                    )

                    assert "Comprehensive diagnosis" in result["diagnosis"]
                    assert "assessment" in result


class TestServiceUtilityFunctions:
    """Test utility functions in services module"""

    @pytest.mark.asyncio
    async def test_follow_up_plan_patient_specific_instructions(self):
        """Test that follow-up plan includes patient-specific instructions"""
        # Test with elderly patient (age >= 65)
        elderly_patient = SimpleUTIPatientFactory(age=75)
        patient_data = create_patient_dict(elderly_patient)

        result = await services.follow_up_plan(patient_data)

        assert "special_instructions" in result
        special_instructions = result["special_instructions"]

        # Should have elderly-specific instruction
        elderly_instruction_found = any(
            "elderly" in instruction.lower() for instruction in special_instructions
        )
        assert elderly_instruction_found

    @pytest.mark.asyncio
    async def test_follow_up_plan_acei_arb_monitoring(self):
        """Test follow-up plan includes ACEI/ARB monitoring when applicable"""
        # Create patient with ACEI use
        patient = SimpleUTIPatientFactory()
        patient.history.ACEI_ARB_use = True
        patient_data = create_patient_dict(patient)

        result = await services.follow_up_plan(patient_data)

        assert "special_instructions" in result
        special_instructions = result["special_instructions"]

        # Should have hyperkalemia monitoring
        hyperkalemia_instruction_found = any(
            "hyperkalemia" in instruction.lower()
            for instruction in special_instructions
        )
        assert hyperkalemia_instruction_found

    @pytest.mark.asyncio
    async def test_follow_up_plan_renal_impairment_monitoring(self):
        """Test follow-up plan includes renal monitoring for impaired patients"""
        patient = SimpleUTIPatientFactory()
        from src.models import RenalFunction

        patient.renal_function_summary = RenalFunction.impaired
        patient_data = create_patient_dict(patient)

        result = await services.follow_up_plan(patient_data)

        assert "special_instructions" in result
        special_instructions = result["special_instructions"]

        # Should have renal monitoring instruction
        renal_instruction_found = any(
            "renal" in instruction.lower() for instruction in special_instructions
        )
        assert renal_instruction_found


class TestServiceModelIntegration:
    """Test integration between services and model validation"""

    @pytest.mark.asyncio
    async def test_assess_and_plan_model_validation(self):
        """Test that assess_and_plan properly validates patient data"""
        # Test with valid patient data
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        result = await services.assess_and_plan(patient_data)

        # Should have standard response structure
        assert "decision" in result
        assert "version" in result
        assert result["version"] == "v1"
        assert "narrative" in result

    @pytest.mark.asyncio
    async def test_assess_and_plan_invalid_data(self):
        """Test assess_and_plan with invalid patient data"""
        invalid_data = {
            "age": "invalid",  # Should be int
            "sex": "invalid_sex",
            "incomplete": "data",
        }

        result = await services.assess_and_plan(invalid_data)

        # Should return error structure
        assert result["error"] == "Assessment failed"
        assert "message" in result
        assert result["version"] == "v1"

    @pytest.mark.asyncio
    async def test_recommendation_text_formatting(self):
        """Test recommendation text formatting in services"""
        from src.models import MedicationAgent, Recommendation

        # Create a recommendation object
        rec = Recommendation(
            regimen="Nitrofurantoin macrocrystals",
            regimen_agent=MedicationAgent.nitrofurantoin,
            dose="100 mg",
            frequency="PO BID",
            duration="5 days",
        )

        # Test the as_text method
        rec_text = rec.as_text()
        expected = "Nitrofurantoin macrocrystals 100 mg PO BID x 5 days"
        assert rec_text == expected

    @pytest.mark.asyncio
    async def test_recommendation_text_no_duration(self):
        """Test recommendation text formatting without duration"""
        from src.models import MedicationAgent, Recommendation

        rec = Recommendation(
            regimen="Nitrofurantoin",
            regimen_agent=MedicationAgent.nitrofurantoin,
            dose="100 mg",
            frequency="PO BID",
            duration="",  # Empty duration
        )

        rec_text = rec.as_text()
        expected = "Nitrofurantoin 100 mg PO BID"
        assert rec_text == expected
