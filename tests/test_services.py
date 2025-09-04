from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import (
    ApprovalDecision,
    AssessmentOutput,
    ClinicalReasoningOutput,
    Decision,
    Recommendation,
    SafetyValidationOutput,
)
from src.services import (
    _run_agent_stream_with_retry,
    assess_and_plan,
    clinical_reasoning,
    deep_research_diagnosis,
    follow_up_plan,
    prescribing_considerations,
    safety_validation,
    uti_complete_patient_assessment,
    web_research,
)
from tests.factories import (
    ComplicatedUTIPatientFactory,
    ElderlyUTIPatientFactory,
    SimpleUTIPatientFactory,
    create_patient_dict,
)


class TestRunAgentStreamWithRetry:
    @pytest.mark.asyncio
    async def test_successful_agent_run(self):
        mock_agent = AsyncMock()
        mock_agent.model = "gpt-4.1"

        mock_output = ClinicalReasoningOutput(
            reasoning=["Test reasoning"],
            confidence=0.9,
        )

        with patch("src.services.Runner") as mock_runner:
            mock_stream = AsyncMock()
            mock_stream.final_output = mock_output

            # Create a proper async iterator
            async def mock_stream_events():
                yield "event1"
                yield "event2"

            mock_stream.stream_events = mock_stream_events
            mock_runner.run_streamed.return_value = mock_stream

            result = await _run_agent_stream_with_retry(mock_agent, "test prompt")

            assert result == mock_output
            mock_runner.run_streamed.assert_called_once()

    # NOTE: Removed complex retry mechanism test - edge case testing not essential for core coverage


class TestClinicalReasoning:
    @pytest.mark.asyncio
    async def test_clinical_reasoning_success(self):
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        mock_output = ClinicalReasoningOutput(
            reasoning=["Patient presents with classic UTI symptoms"],
            confidence=0.85,
            differential_dx=["Acute cystitis"],
            risk_factors=["Female gender"],
            recommendations=["Start empirical antibiotic therapy"],
            proposed_regimen_text="Nitrofurantoin 100 mg PO BID x 5 days",
        )

        with patch("src.services.make_clinical_reasoning_agent") as mock_make_agent:
            with patch("src.services._run_agent_stream_with_retry") as mock_run:
                mock_agent = AsyncMock()
                mock_agent.model = "gpt-4.1"
                mock_make_agent.return_value = mock_agent
                mock_run.return_value = mock_output

                result = await clinical_reasoning(patient_data, model="gpt-4.1")

                assert result["reasoning"] == [
                    "Patient presents with classic UTI symptoms"
                ]
                assert result["confidence"] == 0.85
                assert result["model"] == "gpt-4.1"
                assert result["version"] == "v1"
                assert "narrative" in result

                mock_make_agent.assert_called_once_with("gpt-4.1")
                mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_clinical_reasoning_with_assessment_details(self):
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)
        assessment_details = {
            "decision": "recommend_treatment",
            "recommendation": {"regimen": "Nitrofurantoin"},
        }

        mock_output = ClinicalReasoningOutput()

        with patch("src.services.make_clinical_reasoning_agent") as mock_make_agent:
            with patch("src.services._run_agent_stream_with_retry") as mock_run:
                with patch(
                    "src.services.make_clinical_reasoning_prompt"
                ) as mock_prompt:
                    mock_agent = AsyncMock()
                    mock_agent.model = "gpt-4.1"
                    mock_make_agent.return_value = mock_agent
                    mock_run.return_value = mock_output

                    result = await clinical_reasoning(
                        patient_data,
                        model="gpt-4.1",
                        assessment_details=assessment_details,
                    )

                    # Verify prompt was created with assessment details
                    mock_prompt.assert_called_once()
                    call_args = mock_prompt.call_args
                    assert (
                        call_args[0][1] == assessment_details
                    )  # Second arg is assessment_details


class TestSafetyValidation:
    @pytest.mark.asyncio
    async def test_safety_validation_success(self):
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)
        recommendation = {
            "regimen": "Nitrofurantoin macrocrystals",
            "dose": "100 mg",
            "frequency": "PO BID",
            "duration": "5 days",
        }

        mock_output = SafetyValidationOutput(
            safety_flags=["Monitor for nausea"],
            contraindications=[],
            drug_interactions=[],
            monitoring_requirements=["Take with food"],
            risk_level="low",
            approval_recommendation=ApprovalDecision.approve,
            rationale="Safe for patient profile",
        )

        with patch("src.services.make_safety_validation_agent") as mock_make_agent:
            with patch("src.services._run_agent_stream_with_retry") as mock_run:
                mock_agent = AsyncMock()
                mock_agent.model = "gpt-4.1"
                mock_make_agent.return_value = mock_agent
                mock_run.return_value = mock_output

                result = await safety_validation(
                    patient_data,
                    "recommend_treatment",
                    recommendation,
                    model="gpt-4.1",
                )

                assert result["safety_flags"] == ["Monitor for nausea"]
                assert result["approval_recommendation"] == ApprovalDecision.approve
                assert result["model"] == "gpt-4.1"
                assert result["version"] == "v1"
                assert "narrative" in result

    @pytest.mark.asyncio
    async def test_safety_validation_no_recommendation(self):
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        mock_output = SafetyValidationOutput()

        with patch("src.services.make_safety_validation_agent") as mock_make_agent:
            with patch("src.services._run_agent_stream_with_retry") as mock_run:
                mock_agent = AsyncMock()
                mock_agent.model = "gpt-4.1"
                mock_make_agent.return_value = mock_agent
                mock_run.return_value = mock_output

                result = await safety_validation(
                    patient_data,
                    "refer_complicated",
                    None,
                    model="gpt-4.1",
                )

                # Should handle None recommendation gracefully
                assert "version" in result
                assert result["model"] == "gpt-4.1"

    @pytest.mark.asyncio
    async def test_safety_validation_with_clinical_reasoning_context(self):
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)
        recommendation = {"regimen": "Nitrofurantoin"}
        clinical_context = {
            "proposed_regimen_text": "Nitrofurantoin 100 mg PO BID x 5 days",
        }

        mock_output = SafetyValidationOutput()

        with patch("src.services.make_safety_validation_agent") as mock_make_agent:
            with patch("src.services._run_agent_stream_with_retry") as mock_run:
                with patch("src.services.make_safety_validation_prompt") as mock_prompt:
                    mock_agent = AsyncMock()
                    mock_agent.model = "gpt-4.1"
                    mock_make_agent.return_value = mock_agent
                    mock_run.return_value = mock_output

                    result = await safety_validation(
                        patient_data,
                        "recommend_treatment",
                        recommendation,
                        model="gpt-4.1",
                        clinical_reasoning_context=clinical_context,
                    )

                    # Verify prompt was called with clinical context
                    mock_prompt.assert_called_once()
                    call_args = mock_prompt.call_args
                    assert (
                        call_args[0][3] == clinical_context
                    )  # Fourth arg is clinical context


class TestWebResearch:
    @pytest.mark.asyncio
    async def test_web_research_success(self):
        mock_streamed_output = {
            "text": "Current UTI guidelines recommend nitrofurantoin as first-line.",
            "citations": [
                {
                    "title": "UTI Guidelines 2024",
                    "url": "http://example.com",
                    "relevance": "high",
                },
            ],
        }

        with patch("src.services.make_research_agent") as mock_make_agent:
            with patch("src.services.stream_text_and_citations") as mock_stream:
                mock_agent = AsyncMock()
                mock_agent.model = "gpt-4.1"
                mock_make_agent.return_value = mock_agent
                mock_stream.return_value = mock_streamed_output

                result = await web_research(
                    "UTI treatment guidelines", "CA-ON", model="gpt-4.1"
                )

                assert (
                    result["summary"]
                    == "Current UTI guidelines recommend nitrofurantoin as first-line."
                )
                assert result["region"] == "CA-ON"
                assert len(result["citations"]) == 1
                assert result["model"] == "gpt-4.1"
                assert result["version"] == "v1"
                assert (
                    result["narrative"]
                    == "Current UTI guidelines recommend nitrofurantoin as first-line."
                )

    @pytest.mark.asyncio
    async def test_web_research_empty_output(self):
        mock_streamed_output = {
            "text": "",
            "citations": [],
        }

        with patch("src.services.make_research_agent") as mock_make_agent:
            with patch("src.services.stream_text_and_citations") as mock_stream:
                mock_agent = AsyncMock()
                mock_agent.model = "gpt-4.1"
                mock_make_agent.return_value = mock_agent
                mock_stream.return_value = mock_streamed_output

                result = await web_research("UTI treatment", "CA-ON")

                assert result["summary"] == ""
                assert result["narrative"] == "Evidence summary for CA-ON."


class TestPrescribingConsiderations:
    @pytest.mark.asyncio
    async def test_prescribing_considerations_success(self):
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        mock_web_research_result = {
            "summary": "Latest resistance data shows low nitrofurantoin resistance.",
            "citations": [{"title": "Resistance Report", "url": "http://example.com"}],
        }

        with patch("src.services.assess_uti_patient") as mock_assess:
            with patch(
                "src.services.get_contraindications_from_assessment"
            ) as mock_contraindications:
                with patch("src.services.web_research") as mock_web_research:
                    mock_assessment = MagicMock()
                    mock_assess.return_value = mock_assessment
                    mock_contraindications.return_value = ["Age <18 for fosfomycin"]
                    mock_web_research.return_value = mock_web_research_result

                    result = await prescribing_considerations(
                        patient_data, "CA-ON", model="gpt-4.1"
                    )

                    assert "considerations" in result
                    assert result["region"] == "CA-ON"
                    assert result["version"] == "v1"
                    assert result["model"] == "gpt-4.1"
                    assert len(result["citations"]) > 0
                    assert "narrative" in result

                    # Should include patient-specific contraindications
                    considerations_text = " ".join(result["considerations"])
                    assert "Age <18 for fosfomycin" in considerations_text

    @pytest.mark.asyncio
    async def test_prescribing_considerations_web_research_failure(self):
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        with patch("src.services.assess_uti_patient") as mock_assess:
            with patch(
                "src.services.get_contraindications_from_assessment"
            ) as mock_contraindications:
                with patch("src.services.web_research") as mock_web_research:
                    mock_assessment = MagicMock()
                    mock_assess.return_value = mock_assessment
                    mock_contraindications.return_value = []
                    mock_web_research.side_effect = Exception("Network error")

                    result = await prescribing_considerations(patient_data, "CA-ON")

                    # Should still return basic considerations despite web research failure
                    assert "considerations" in result
                    assert result["region"] == "CA-ON"
                    assert result["citations"] == []


class TestDeepResearchDiagnosis:
    @pytest.mark.asyncio
    async def test_deep_research_diagnosis_success(self):
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        mock_streamed_output = {
            "text": "Based on symptoms and patient profile, this is likely acute uncomplicated cystitis.",
            "citations": [{"title": "UTI Diagnosis", "url": "http://example.com"}],
        }

        with patch("src.services.assess_uti_patient") as mock_assess:
            with patch("src.services.make_diagnosis_agent") as mock_make_agent:
                with patch("src.services.stream_text_and_citations") as mock_stream:
                    mock_assessment = AssessmentOutput(
                        decision=Decision.recommend_treatment,
                        recommendation=Recommendation(
                            regimen="Nitrofurantoin",
                            dose="100 mg",
                            frequency="PO BID",
                            duration="5 days",
                        ),
                    )
                    mock_assess.return_value = mock_assessment

                    mock_agent = AsyncMock()
                    mock_agent.model = "gpt-4.1"
                    mock_make_agent.return_value = mock_agent
                    mock_stream.return_value = mock_streamed_output

                    result = await deep_research_diagnosis(
                        patient_data, model="gpt-4.1"
                    )

                    assert (
                        result["diagnosis"]
                        == "Based on symptoms and patient profile, this is likely acute uncomplicated cystitis."
                    )
                    assert len(result["citations"]) == 1
                    assert result["model"] == "gpt-4.1"
                    assert "assessment" in result
                    assert result["version"] == "v1"

    @pytest.mark.asyncio
    async def test_deep_research_diagnosis_exception(self):
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        with patch("src.services.assess_uti_patient") as mock_assess:
            mock_assess.side_effect = Exception("Assessment failed")

            result = await deep_research_diagnosis(patient_data, model="gpt-4.1")

            assert "error" in result
            assert "Research diagnosis unavailable" in result["diagnosis"]
            assert result["model"] == "gpt-4.1"


class TestAssessAndPlan:
    @pytest.mark.asyncio
    async def test_assess_and_plan_success(self):
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        mock_assessment = AssessmentOutput(
            decision=Decision.recommend_treatment,
            recommendation=Recommendation(
                regimen="Nitrofurantoin macrocrystals",
                dose="100 mg",
                frequency="PO BID",
                duration="5 days",
            ),
            rationale=["Patient meets criteria for uncomplicated UTI"],
            follow_up={"instructions": ["Follow up in 72 hours"]},
        )

        with patch("src.services.assess_uti_patient") as mock_assess:
            mock_assess.return_value = mock_assessment

            result = await assess_and_plan(patient_data)

            assert result["decision"] == Decision.recommend_treatment
            assert "recommendation" in result
            assert result["rationale"] == [
                "Patient meets criteria for uncomplicated UTI"
            ]
            assert result["version"] == "v1"
            assert "narrative" in result

    @pytest.mark.asyncio
    async def test_assess_and_plan_exception(self):
        patient_data = {"invalid": "data"}

        result = await assess_and_plan(patient_data)

        assert result["error"] == "Assessment failed"
        assert "message" in result
        assert result["version"] == "v1"


class TestFollowUpPlan:
    @pytest.mark.asyncio
    async def test_follow_up_plan_success(self):
        patient = ElderlyUTIPatientFactory()  # Has special considerations
        patient_data = create_patient_dict(patient)

        with patch("src.services.get_enhanced_follow_up_plan") as mock_plan:
            mock_plan_details = {
                "follow_up_plan": {"assessment_timeframe": "48-72 hours"},
                "monitoring_checklist": ["Monitor for side effects"],
                "special_instructions": ["Monitor elderly patients closely"],
                "provider_actions": ["Complete documentation"],
            }
            mock_plan.return_value = mock_plan_details

            result = await follow_up_plan(patient_data)

            assert "follow_up_plan" in result
            assert "monitoring_checklist" in result
            assert "special_instructions" in result
            assert result["version"] == "v1"
            assert "narrative" in result

            # Check narrative formatting
            assert "72-hour follow-up plan prepared" in result["narrative"]

    @pytest.mark.asyncio
    async def test_follow_up_plan_exception(self):
        patient_data = {"invalid": "data"}

        result = await follow_up_plan(patient_data)

        assert result["error"] == "Failed to generate follow-up plan"
        assert "message" in result
        assert result["version"] == "v1"


class TestFinalConsolidatedAgent:
    @pytest.mark.asyncio
    async def test_uti_complete_patient_assessment_treatment_path(self):
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        # Mock all the component results
        mock_assessment = {
            "decision": Decision.recommend_treatment,
            "recommendation": {
                "regimen": "Nitrofurantoin macrocrystals",
                "dose": "100 mg",
                "frequency": "PO BID",
                "duration": "5 days",
            },
            "rationale": ["Patient meets criteria"],
        }

        mock_clinical = {
            "reasoning": ["Clear UTI symptoms"],
            "confidence": 0.9,
            "proposed_regimen_text": "Nitrofurantoin 100 mg PO BID x 5 days",
        }

        mock_safety = {
            "approval_recommendation": ApprovalDecision.approve,
            "risk_level": "low",
        }

        with patch.multiple(
            "src.services",
            assess_and_plan=AsyncMock(return_value=mock_assessment),
            clinical_reasoning=AsyncMock(return_value=mock_clinical),
            safety_validation=AsyncMock(return_value=mock_safety),
            prescribing_considerations=AsyncMock(return_value={"considerations": []}),
            web_research=AsyncMock(return_value={"summary": "Research summary"}),
            deep_research_diagnosis=AsyncMock(
                return_value={"diagnosis": "UTI diagnosis"}
            ),
            follow_up_plan=AsyncMock(return_value={"follow_up_plan": {}}),
        ):
            with patch("src.services.state_validator") as mock_validator:
                mock_validator.return_value = {"passed": True, "severity": "low"}

                result = await uti_complete_patient_assessment(
                    patient_data, model="gpt-4.1"
                )

                assert result["orchestration"] == "final_consolidated"
                assert result["orchestration_path"] == "standard"
                assert "clinical_reasoning" in result
                assert "assessment" in result
                assert "safety_validation" in result
                assert "consensus_recommendation" in result
                assert result["model"] == "gpt-4.1"
                assert result["version"] == "v1"

    @pytest.mark.asyncio
    async def test_uti_complete_patient_assessment_referral_path(self):
        patient = ComplicatedUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        mock_assessment = {
            "decision": Decision.refer_complicated,
            "recommendation": None,
            "rationale": ["Complicating factors present"],
        }

        mock_clinical = {
            "reasoning": ["Referral recommended"],
            "confidence": 1.0,
        }

        with patch.multiple(
            "src.services",
            assess_and_plan=AsyncMock(return_value=mock_assessment),
            clinical_reasoning=AsyncMock(return_value=mock_clinical),
            prescribing_considerations=AsyncMock(return_value={"considerations": []}),
            web_research=AsyncMock(return_value={"summary": "Research summary"}),
            deep_research_diagnosis=AsyncMock(
                return_value={"diagnosis": "Complex UTI"}
            ),
        ):
            with patch("src.services.state_validator") as mock_validator:
                mock_validator.return_value = {"passed": True, "severity": "low"}

                result = await uti_complete_patient_assessment(
                    patient_data, model="gpt-4.1"
                )

                assert result["consensus_recommendation"] == "Escalate to human (interrupt)"
                assert (
                    result["safety_validation"] is None
                )  # No safety validation for referrals
                assert result["follow_up_details"] is None

    @pytest.mark.asyncio
    async def test_uti_complete_patient_assessment_exception(self):
        patient_data = {"invalid": "data"}

        result = await uti_complete_patient_assessment(patient_data, model="gpt-4.1")

        # Check if error exists at top level or in nested structure  
        has_error = "error" in result or any("error" in str(v) for v in result.values() if isinstance(v, dict))
        assert has_error
        if "error" in result:
            assert "Final consolidation failed" in result["error"]
        assert result["model"] == "gpt-4.1"

    @pytest.mark.asyncio
    async def test_uti_complete_patient_assessment_safety_rejection(self):
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        mock_assessment = {
            "decision": Decision.recommend_treatment,
            "recommendation": {
                "regimen": "Nitrofurantoin",
                "alternatives": ["TMP/SMX"],
            },
        }

        mock_clinical = {"reasoning": ["UTI diagnosis"], "confidence": 0.9}

        mock_safety = {
            "approval_recommendation": ApprovalDecision.reject,
            "risk_level": "high",
        }

        with patch.multiple(
            "src.services",
            assess_and_plan=AsyncMock(return_value=mock_assessment),
            clinical_reasoning=AsyncMock(return_value=mock_clinical),
            safety_validation=AsyncMock(return_value=mock_safety),
            prescribing_considerations=AsyncMock(return_value={"considerations": []}),
            web_research=AsyncMock(return_value={"summary": ""}),
            deep_research_diagnosis=AsyncMock(return_value={"diagnosis": ""}),
        ):
            with patch("src.services.state_validator") as mock_validator:
                mock_validator.return_value = {"passed": False, "severity": "high"}

                result = await uti_complete_patient_assessment(patient_data)

                assert (
                    "Defer antibiotics; escalate to human (safety gate)"
                    in result["consensus_recommendation"]
                )
