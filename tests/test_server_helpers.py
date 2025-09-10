from __future__ import annotations

import json

from src.server import _build_patient, _build_recommendation


class TestBuildPatientCoverage:
    """Comprehensive tests for _build_patient helper function"""

    def test_build_patient_minimal_required_fields(self):
        """Test with minimal required fields only"""
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

        # Test all nested structures are created correctly
        assert result["age"] == 25
        assert result["sex"] == "female"
        assert result["pregnancy_status"] == "not_pregnant"
        assert result["renal_function_summary"] == "normal"
        assert result["locale_code"] == "CA-ON"

        # Test symptoms structure
        assert result["symptoms"]["dysuria"] is True
        assert result["symptoms"]["urgency"] is False
        assert result["symptoms"]["frequency"] is False
        assert result["symptoms"]["suprapubic_pain"] is False
        assert result["symptoms"]["hematuria"] is False

        # Test red_flags structure
        assert result["red_flags"]["fever"] is False
        assert result["red_flags"]["rigors"] is False
        assert result["red_flags"]["flank_pain"] is False
        assert result["red_flags"]["nausea_vomiting"] is False
        assert result["red_flags"]["systemic"] is False

        # Test history structure with None handling
        assert result["history"]["antibiotics_last_90d"] is False
        assert result["history"]["allergies"] == []  # None -> []
        assert result["history"]["meds"] == []  # None -> []
        assert result["history"]["acei_arb_use"] is False
        assert result["history"]["catheter"] is False
        assert result["history"]["stones"] is False
        assert result["history"]["immunocompromised"] is False

        # Test recurrence structure
        assert result["recurrence"]["relapse_within_4w"] is False
        assert result["recurrence"]["recurrent_6m"] is False
        assert result["recurrence"]["recurrent_12m"] is False

    def test_build_patient_all_fields_populated(self):
        """Test with all optional fields populated"""
        allergies = ["penicillin", "sulfa"]
        medications = ["lisinopril", "metformin", "ibuprofen"]

        result = _build_patient(
            age=67,
            sex="male",
            pregnancy_status="not_applicable",
            renal_function_summary="impaired",
            egfr_ml_min=None,
            symptoms_dysuria=True,
            symptoms_urgency=True,
            symptoms_frequency=True,
            symptoms_suprapubic_pain=True,
            symptoms_hematuria=True,
            red_flags_fever=True,
            red_flags_rigors=True,
            red_flags_flank_pain=True,
            red_flags_nausea_vomiting=True,
            red_flags_systemic=True,
            history_antibiotics_last_90d=True,
            history_allergies=allergies,
            history_meds=medications,
            history_acei_arb_use=True,
            history_catheter=True,
            history_neurogenic_bladder=None,
            history_stones=True,
            history_immunocompromised=True,
            recurrence_relapse_within_4w=True,
            recurrence_recurrent_6m=True,
            recurrence_recurrent_12m=True,
            locale_code="US-CA",
        )

        # Test all populated fields
        assert result["age"] == 67
        assert result["sex"] == "male"
        assert result["pregnancy_status"] == "not_applicable"
        assert result["renal_function_summary"] == "impaired"
        assert result["locale_code"] == "US-CA"

        # Test symptoms all True
        assert all(result["symptoms"].values())

        # Test red_flags all True
        assert all(result["red_flags"].values())

        # Test history all True/populated
        assert result["history"]["antibiotics_last_90d"] is True
        assert result["history"]["allergies"] == allergies
        assert result["history"]["meds"] == medications
        assert result["history"]["acei_arb_use"] is True
        assert result["history"]["catheter"] is True
        assert result["history"]["stones"] is True
        assert result["history"]["immunocompromised"] is True

        # Test recurrence all True
        assert all(result["recurrence"].values())

    def test_build_patient_empty_lists(self):
        """Test with explicitly empty lists"""
        result = _build_patient(
            age=30,
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
            history_allergies=[],
            history_meds=[],
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


class TestBuildRecommendationCoverage:
    """Comprehensive tests for _build_recommendation helper function"""

    def test_build_recommendation_all_required_fields(self):
        """Test with all required fields provided"""
        result = _build_recommendation(
            recommendation_regimen="Nitrofurantoin macrocrystals",
            recommendation_dose="100 mg",
            recommendation_frequency="PO BID",
            recommendation_duration="5 days",
            recommendation_alternatives=None,
            recommendation_contraindications=None,
            recommendation_monitoring=None,
        )

        assert result is not None
        assert result["regimen"] == "Nitrofurantoin macrocrystals"
        assert result["dose"] == "100 mg"
        assert result["frequency"] == "PO BID"
        assert result["duration"] == "5 days"
        assert result["alternatives"] == []
        assert result["contraindications"] == []
        assert result["monitoring"] == []

    def test_build_recommendation_all_fields_populated(self):
        """Test with all fields populated"""
        alternatives = ["TMP/SMX", "Trimethoprim"]
        contraindications = ["Age <18", "Pregnancy"]
        monitoring = ["Take with food", "Monitor for nausea"]

        result = _build_recommendation(
            recommendation_regimen="Fosfomycin trometamol",
            recommendation_dose="3 g",
            recommendation_frequency="PO",
            recommendation_duration="Single dose",
            recommendation_alternatives=alternatives,
            recommendation_contraindications=contraindications,
            recommendation_monitoring=monitoring,
        )

        assert result is not None
        assert result["regimen"] == "Fosfomycin trometamol"
        assert result["dose"] == "3 g"
        assert result["frequency"] == "PO"
        assert result["duration"] == "Single dose"
        assert result["alternatives"] == alternatives
        assert result["contraindications"] == contraindications
        assert result["monitoring"] == monitoring

    def test_build_recommendation_missing_regimen(self):
        """Test with missing regimen (should return None)"""
        result = _build_recommendation(
            recommendation_regimen=None,
            recommendation_dose="100 mg",
            recommendation_frequency="PO BID",
            recommendation_duration="5 days",
            recommendation_alternatives=None,
            recommendation_contraindications=None,
            recommendation_monitoring=None,
        )

        assert result is None

    def test_build_recommendation_missing_dose(self):
        """Test with missing dose (should return None)"""
        result = _build_recommendation(
            recommendation_regimen="Nitrofurantoin",
            recommendation_dose=None,
            recommendation_frequency="PO BID",
            recommendation_duration="5 days",
            recommendation_alternatives=None,
            recommendation_contraindications=None,
            recommendation_monitoring=None,
        )

        assert result is None

    def test_build_recommendation_missing_frequency(self):
        """Test with missing frequency (should return None)"""
        result = _build_recommendation(
            recommendation_regimen="Nitrofurantoin",
            recommendation_dose="100 mg",
            recommendation_frequency=None,
            recommendation_duration="5 days",
            recommendation_alternatives=None,
            recommendation_contraindications=None,
            recommendation_monitoring=None,
        )

        assert result is None

    def test_build_recommendation_missing_duration(self):
        """Test with missing duration (should return None)"""
        result = _build_recommendation(
            recommendation_regimen="Nitrofurantoin",
            recommendation_dose="100 mg",
            recommendation_frequency="PO BID",
            recommendation_duration=None,
            recommendation_alternatives=None,
            recommendation_contraindications=None,
            recommendation_monitoring=None,
        )

        assert result is None

    def test_build_recommendation_empty_string_fields(self):
        """Test with empty string fields (should return None)"""
        result = _build_recommendation(
            recommendation_regimen="",  # Empty string
            recommendation_dose="100 mg",
            recommendation_frequency="PO BID",
            recommendation_duration="5 days",
            recommendation_alternatives=None,
            recommendation_contraindications=None,
            recommendation_monitoring=None,
        )

        assert result is None

    def test_build_recommendation_empty_lists(self):
        """Test with explicitly empty lists"""
        result = _build_recommendation(
            recommendation_regimen="Trimethoprim",
            recommendation_dose="200 mg",
            recommendation_frequency="PO daily",
            recommendation_duration="3 days",
            recommendation_alternatives=[],
            recommendation_contraindications=[],
            recommendation_monitoring=[],
        )

        assert result is not None
        assert result["alternatives"] == []
        assert result["contraindications"] == []
        assert result["monitoring"] == []


class TestServerHelpersEdgeCases:
    """Edge case tests for server helper functions"""

    def test_patient_data_json_serializable(self):
        """Test that patient data is JSON serializable"""
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
            history_allergies=["test allergy"],
            history_meds=["test med"],
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

        # Should not raise exception
        json_str = json.dumps(patient_data)
        parsed_back = json.loads(json_str)

        # Should preserve structure
        assert parsed_back["age"] == 25
        assert parsed_back["symptoms"]["dysuria"] is True
        assert parsed_back["history"]["allergies"] == ["test allergy"]

    def test_recommendation_data_json_serializable(self):
        """Test that recommendation data is JSON serializable"""
        rec_data = _build_recommendation(
            recommendation_regimen="Test Regimen",
            recommendation_dose="100 mg",
            recommendation_frequency="PO BID",
            recommendation_duration="5 days",
            recommendation_alternatives=["Alt 1", "Alt 2"],
            recommendation_contraindications=["Allergy"],
            recommendation_monitoring=["Monitor closely"],
        )

        # Should not raise exception
        json_str = json.dumps(rec_data)
        parsed_back = json.loads(json_str)

        # Should preserve structure
        assert parsed_back["regimen"] == "Test Regimen"
        assert parsed_back["alternatives"] == ["Alt 1", "Alt 2"]
