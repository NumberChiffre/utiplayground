from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(scope="session")
def event_loop():
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_openai_client():
    with patch("src.client.AsyncOpenAI") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_agent():
    mock = AsyncMock()
    mock.model = "gpt-4.1"
    return mock


@pytest.fixture
def mock_runner():
    with patch("src.services.Runner") as mock_runner:
        mock_stream = AsyncMock()
        mock_stream.final_output = MagicMock()
        mock_stream.stream_events.return_value = AsyncMock().__aiter__()
        mock_runner.run_streamed.return_value = mock_stream
        yield mock_runner


@pytest.fixture
def sample_patient_data() -> dict[str, Any]:
    return {
        "age": 25,
        "sex": "female",
        "pregnancy_status": "not_pregnant",
        "renal_function_summary": "normal",
        "symptoms": {
            "dysuria": True,
            "urgency": True,
            "frequency": False,
            "suprapubic_pain": False,
            "hematuria": False,
        },
        "red_flags": {
            "fever": False,
            "rigors": False,
            "flank_pain": False,
            "nausea_vomiting": False,
            "systemic": False,
        },
        "history": {
            "antibiotics_last_90d": False,
            "allergies": [],
            "meds": [],
            "acei_arb_use": False,
            "catheter": False,
            "stones": False,
            "immunocompromised": False,
        },
        "recurrence": {
            "relapse_within_4w": False,
            "recurrent_6m": False,
            "recurrent_12m": False,
        },
        "locale_code": "CA-ON",
    }


@pytest.fixture
def complicated_patient_data() -> dict[str, Any]:
    return {
        "age": 35,
        "sex": "female",
        "pregnancy_status": "not_pregnant",
        "renal_function_summary": "normal",
        "symptoms": {
            "dysuria": True,
            "urgency": True,
            "frequency": True,
            "suprapubic_pain": False,
            "hematuria": False,
        },
        "red_flags": {
            "fever": True,
            "rigors": True,
            "flank_pain": False,
            "nausea_vomiting": False,
            "systemic": False,
        },
        "history": {
            "antibiotics_last_90d": False,
            "allergies": [],
            "meds": [],
            "acei_arb_use": False,
            "catheter": False,
            "stones": False,
            "immunocompromised": False,
        },
        "recurrence": {
            "relapse_within_4w": False,
            "recurrent_6m": False,
            "recurrent_12m": False,
        },
        "locale_code": "CA-ON",
    }


@pytest.fixture
def male_patient_data() -> dict[str, Any]:
    return {
        "age": 45,
        "sex": "male",
        "pregnancy_status": "not_applicable",
        "renal_function_summary": "normal",
        "symptoms": {
            "dysuria": True,
            "urgency": True,
            "frequency": False,
            "suprapubic_pain": True,
            "hematuria": False,
        },
        "red_flags": {
            "fever": False,
            "rigors": False,
            "flank_pain": False,
            "nausea_vomiting": False,
            "systemic": False,
        },
        "history": {
            "antibiotics_last_90d": False,
            "allergies": [],
            "meds": [],
            "acei_arb_use": False,
            "catheter": False,
            "stones": False,
            "immunocompromised": False,
        },
        "recurrence": {
            "relapse_within_4w": False,
            "recurrent_6m": False,
            "recurrent_12m": False,
        },
        "locale_code": "CA-ON",
    }


@pytest.fixture
def recurrent_patient_data() -> dict[str, Any]:
    return {
        "age": 30,
        "sex": "female",
        "pregnancy_status": "not_pregnant",
        "renal_function_summary": "normal",
        "symptoms": {
            "dysuria": True,
            "urgency": True,
            "frequency": True,
            "suprapubic_pain": False,
            "hematuria": False,
        },
        "red_flags": {
            "fever": False,
            "rigors": False,
            "flank_pain": False,
            "nausea_vomiting": False,
            "systemic": False,
        },
        "history": {
            "antibiotics_last_90d": False,
            "allergies": [],
            "meds": [],
            "acei_arb_use": False,
            "catheter": False,
            "stones": False,
            "immunocompromised": False,
        },
        "recurrence": {
            "relapse_within_4w": False,
            "recurrent_6m": True,
            "recurrent_12m": False,
        },
        "locale_code": "CA-ON",
    }


@pytest.fixture
def patient_with_allergies_data() -> dict[str, Any]:
    return {
        "age": 28,
        "sex": "female",
        "pregnancy_status": "not_pregnant",
        "renal_function_summary": "normal",
        "symptoms": {
            "dysuria": True,
            "urgency": False,
            "frequency": True,
            "suprapubic_pain": True,
            "hematuria": False,
        },
        "red_flags": {
            "fever": False,
            "rigors": False,
            "flank_pain": False,
            "nausea_vomiting": False,
            "systemic": False,
        },
        "history": {
            "antibiotics_last_90d": False,
            "allergies": ["nitrofurantoin", "trimethoprim"],
            "meds": [],
            "acei_arb_use": False,
            "catheter": False,
            "stones": False,
            "immunocompromised": False,
        },
        "recurrence": {
            "relapse_within_4w": False,
            "recurrent_6m": False,
            "recurrent_12m": False,
        },
        "locale_code": "CA-ON",
    }


@pytest.fixture
def elderly_patient_data() -> dict[str, Any]:
    return {
        "age": 75,
        "sex": "female",
        "pregnancy_status": "not_applicable",
        "renal_function_summary": "impaired",
        "egfr_ml_min": 25.0,
        "symptoms": {
            "dysuria": True,
            "urgency": True,
            "frequency": True,
            "suprapubic_pain": False,
            "hematuria": False,
        },
        "red_flags": {
            "fever": False,
            "rigors": False,
            "flank_pain": False,
            "nausea_vomiting": False,
            "systemic": False,
        },
        "history": {
            "antibiotics_last_90d": False,
            "allergies": [],
            "meds": ["lisinopril", "hydrochlorothiazide"],
            "acei_arb_use": True,
            "catheter": False,
            "stones": False,
            "immunocompromised": False,
        },
        "recurrence": {
            "relapse_within_4w": False,
            "recurrent_6m": False,
            "recurrent_12m": False,
        },
        "locale_code": "CA-ON",
    }


@pytest.fixture(autouse=True)
def setup_test_environment():
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    os.environ.setdefault("OPENAI_AGENTS_DISABLE_TRACING", "1")
    yield

    # Clean up
    test_keys = ["OPENAI_API_KEY", "OPENAI_AGENTS_DISABLE_TRACING"]
    for key in test_keys:
        if key in os.environ and os.environ[key] in ["test-key", "1"]:
            del os.environ[key]
