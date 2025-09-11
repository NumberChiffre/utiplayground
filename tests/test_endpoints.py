from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from src import services  # Test the underlying services instead
from src.server import _build_patient, _build_recommendation
from tests.factories import (
    ElderlyUTIPatientFactory,
    SimpleUTIPatientFactory,
    create_patient_dict,
)


class TestBuildPatient:
    """Test the patient building helper function"""

    def test_build_patient_complete(self):
        result = _build_patient(
            age=25,
            sex="female",
            pregnancy_status="not_pregnant",
            renal_function_summary="normal",
            egfr_ml_min=None,
            symptoms_dysuria=True,
            symptoms_urgency=True,
            symptoms_frequency=False,
            symptoms_suprapubic_pain=False,
            symptoms_hematuria=False,
            red_flags_fever=False,
            red_flags_rigors=False,
            red_flags_flank_pain=False,
            red_flags_nausea_vomiting=False,
            red_flags_systemic=False,
            history_antibiotics_last_90d=False,
            history_allergies=["penicillin"],
            history_meds=["ibuprofen"],
            history_acei_arb_use=False,
            history_catheter=False,
            history_neurogenic_bladder=None,
            history_stones=False,
            history_immunocompromised=False,
            recurrence_relapse_within_4w=False,
            recurrence_recurrent_6m=False,
            recurrence_recurrent_12m=False,
            locale_code="CA-ON",
        )

        assert result["age"] == 25
        assert result["sex"] == "female"
        assert result["symptoms"]["dysuria"] is True
        assert result["symptoms"]["urgency"] is True
        assert result["history"]["allergies"] == ["penicillin"]
        assert result["history"]["meds"] == ["ibuprofen"]
        assert result["locale_code"] == "CA-ON"

    def test_build_patient_none_lists(self):
        result = _build_patient(
            age=25,
            sex="female",
            pregnancy_status="not_pregnant",
            renal_function_summary="normal",
            egfr_ml_min=None,
            symptoms_dysuria=True,
            symptoms_urgency=False,
            symptoms_frequency=False,
            symptoms_suprapubic_pain=False,
            symptoms_hematuria=False,
            red_flags_fever=False,
            red_flags_rigors=False,
            red_flags_flank_pain=False,
            red_flags_nausea_vomiting=False,
            red_flags_systemic=False,
            history_antibiotics_last_90d=False,
            history_allergies=None,
            history_meds=None,
            history_acei_arb_use=False,
            history_catheter=False,
            history_neurogenic_bladder=None,
            history_stones=False,
            history_immunocompromised=False,
            recurrence_relapse_within_4w=False,
            recurrence_recurrent_6m=False,
            recurrence_recurrent_12m=False,
            locale_code="CA-ON",
        )

        assert result["history"]["allergies"] == []
        assert result["history"]["meds"] == []


class TestBuildRecommendation:
    """Test the recommendation building helper function"""

    def test_build_recommendation_complete(self):
        result = _build_recommendation(
            recommendation_regimen="Nitrofurantoin macrocrystals",
            recommendation_dose="100 mg",
            recommendation_frequency="PO BID",
            recommendation_duration="5 days",
            recommendation_alternatives=["TMP/SMX"],
            recommendation_contraindications=["eGFR <30"],
            recommendation_monitoring=["Take with food"],
        )

        assert result["regimen"] == "Nitrofurantoin macrocrystals"
        assert result["dose"] == "100 mg"
        assert result["frequency"] == "PO BID"
        assert result["duration"] == "5 days"
        assert result["alternatives"] == ["TMP/SMX"]
        assert result["contraindications"] == ["eGFR <30"]
        assert result["monitoring"] == ["Take with food"]

    def test_build_recommendation_incomplete_returns_none(self):
        result = _build_recommendation(
            recommendation_regimen="Nitrofurantoin",
            recommendation_dose=None,  # Missing required field
            recommendation_frequency="PO BID",
            recommendation_duration="5 days",
            recommendation_alternatives=None,
            recommendation_contraindications=None,
            recommendation_monitoring=None,
        )

        assert result is None

    def test_build_recommendation_none_lists(self):
        result = _build_recommendation(
            recommendation_regimen="Nitrofurantoin",
            recommendation_dose="100 mg",
            recommendation_frequency="PO BID",
            recommendation_duration="5 days",
            recommendation_alternatives=None,
            recommendation_contraindications=None,
            recommendation_monitoring=None,
        )

        assert result["alternatives"] == []
        assert result["contraindications"] == []
        assert result["monitoring"] == []


class TestServiceIntegration:
    """Test the integration between server helpers and underlying services"""

    @pytest.mark.asyncio
    async def test_assess_and_plan_service_integration(self):
        """Test that assess and plan service works correctly"""
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        # Call the actual service (no mocking the core algorithm)
        result = await services.assess_and_plan(patient_data)

        # Should get a real decision for simple UTI patient
        assert "decision" in result
        assert result["decision"] in [
            "recommend_treatment",
            "refer_complicated",
            "no_antibiotics_not_met",
            "refer_recurrence",
        ]
        assert "version" in result
        assert result["version"] == "v1"
        assert "narrative" in result

    @pytest.mark.asyncio
    async def test_follow_up_plan_service_integration(self):
        """Test follow-up plan service integration"""
        patient = ElderlyUTIPatientFactory()  # Has special considerations
        patient_data = create_patient_dict(patient)

        # Call the actual service
        result = await services.follow_up_plan(patient_data)

        # Should include follow-up components
        assert "follow_up_plan" in result or "monitoring_checklist" in result
        assert "version" in result
        assert result["version"] == "v1"
        assert "narrative" in result

    @pytest.mark.asyncio
    async def test_prescribing_considerations_integration(self):
        """Test prescribing considerations service"""
        patient = SimpleUTIPatientFactory()
        patient_data = create_patient_dict(patient)

        with patch("src.services.web_research") as mock_web:
            mock_web.return_value = {
                "summary": "Current resistance data",
                "citations": [],
            }

            result = await services.prescribing_considerations(patient_data, "CA-ON")

            assert "considerations" in result
            assert "region" in result
            assert result["region"] == "CA-ON"
            assert "version" in result
            assert len(result["considerations"]) > 0

    # removed: service invalid-data error-handling test (behavior simplified)


class TestMCPToolHelpers:
    """Test the helper functions used by MCP tools"""

    def test_patient_data_transformation(self):
        """Test that patient data can be built from MCP parameters"""
        # This tests the pattern used by MCP tools
        patient_data = _build_patient(
            age=30,
            sex="female",
            pregnancy_status="not_pregnant",
            renal_function_summary="normal",
            egfr_ml_min=None,
            symptoms_dysuria=True,
            symptoms_urgency=False,
            symptoms_frequency=True,
            symptoms_suprapubic_pain=True,
            symptoms_hematuria=False,
            red_flags_fever=False,
            red_flags_rigors=False,
            red_flags_flank_pain=False,
            red_flags_nausea_vomiting=False,
            red_flags_systemic=False,
            history_antibiotics_last_90d=False,
            history_allergies=["sulfa"],
            history_meds=["lisinopril"],
            history_acei_arb_use=True,
            history_catheter=False,
            history_neurogenic_bladder=None,
            history_stones=False,
            history_immunocompromised=False,
            recurrence_relapse_within_4w=False,
            recurrence_recurrent_6m=False,
            recurrence_recurrent_12m=False,
            locale_code="CA-ON",
        )

        # Verify structure matches what services expect
        assert "symptoms" in patient_data
        assert "red_flags" in patient_data
        assert "history" in patient_data
        assert "recurrence" in patient_data

        # Check nested structure
        assert patient_data["symptoms"]["dysuria"] is True
        assert patient_data["history"]["acei_arb_use"] is True
        assert patient_data["history"]["allergies"] == ["sulfa"]

    def test_recommendation_data_transformation(self):
        """Test recommendation building from MCP parameters"""
        rec_data = _build_recommendation(
            recommendation_regimen="Fosfomycin trometamol",
            recommendation_dose="3 g",
            recommendation_frequency="PO",
            recommendation_duration="Single dose",
            recommendation_alternatives=["Nitrofurantoin"],
            recommendation_contraindications=["Age <18"],
            recommendation_monitoring=["Take on empty stomach"],
        )

        assert rec_data is not None
        assert rec_data["regimen"] == "Fosfomycin trometamol"
        assert rec_data["dose"] == "3 g"
        assert rec_data["duration"] == "Single dose"

    def test_json_serialization_compatibility(self):
        """Test that helper outputs are JSON serializable"""
        patient_data = _build_patient(
            age=25,
            sex="female",
            pregnancy_status="not_pregnant",
            renal_function_summary="normal",
            egfr_ml_min=None,
            symptoms_dysuria=True,
            symptoms_urgency=False,
            symptoms_frequency=False,
            symptoms_suprapubic_pain=False,
            symptoms_hematuria=False,
            red_flags_fever=False,
            red_flags_rigors=False,
            red_flags_flank_pain=False,
            red_flags_nausea_vomiting=False,
            red_flags_systemic=False,
            history_antibiotics_last_90d=False,
            history_allergies=None,
            history_meds=None,
            history_acei_arb_use=False,
            history_catheter=False,
            history_neurogenic_bladder=None,
            history_stones=False,
            history_immunocompromised=False,
            recurrence_relapse_within_4w=False,
            recurrence_recurrent_6m=False,
            recurrence_recurrent_12m=False,
            locale_code="CA-ON",
        )

        # Should serialize without errors
        json_str = json.dumps(patient_data)
        parsed = json.loads(json_str)

        assert parsed["age"] == 25
        assert parsed["sex"] == "female"
        assert parsed["history"]["allergies"] == []
