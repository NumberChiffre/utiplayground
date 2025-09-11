from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from ..services import (
    assess_and_plan,
    clinical_reasoning,
    deep_research_diagnosis,
    follow_up_plan,
    prescribing_considerations,
    safety_validation,
    uti_complete_patient_assessment,
    web_research,
)
from .dependencies import ConcurrencyLimiter, limiter, require_clients
from .rate_limit import rate_limiter

if TYPE_CHECKING:
    from ..models import PatientState, Recommendation

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict[str, str]:
    await require_clients()
    return {"ready": "true"}


@router.post("/assess-and-plan")
async def assess_and_plan_endpoint(
    patient: PatientState = Body(...),
    _: None = Depends(rate_limiter),
    guard: ConcurrencyLimiter = Depends(limiter),
) -> dict[str, Any]:
    async with guard.acquire():
        try:
            return await assess_and_plan(patient.model_dump())
        except Exception as e:
            logger.error("assess_and_plan failed: %s", e)
            raise HTTPException(status_code=500, detail="assessment_failed") from e


@router.post("/follow-up-plan")
async def follow_up_plan_endpoint(
    patient: PatientState = Body(...),
    _: None = Depends(rate_limiter),
    guard: ConcurrencyLimiter = Depends(limiter),
) -> dict[str, Any]:
    async with guard.acquire():
        try:
            return await follow_up_plan(patient.model_dump())
        except Exception as e:
            logger.error("follow_up_plan failed: %s", e)
            raise HTTPException(status_code=500, detail="follow_up_failed") from e


@router.post("/prescribing-considerations")
async def prescribing_considerations_endpoint(
    patient: PatientState = Body(...),
    region: str = Query(...),
    model: str = Query("gpt-4.1"),
    _: None = Depends(rate_limiter),
    guard: ConcurrencyLimiter = Depends(limiter),
) -> dict[str, Any]:
    async with guard.acquire():
        try:
            return await prescribing_considerations(patient.model_dump(), region, model)
        except Exception as e:
            logger.error("prescribing_considerations failed: %s", e)
            raise HTTPException(status_code=500, detail="prescribing_failed") from e


@router.post("/clinical-reasoning")
async def clinical_reasoning_endpoint(
    patient: PatientState = Body(...),
    model: str = Query("gpt-4.1"),
    assessment_details: dict | None = Body(None),
    _: None = Depends(rate_limiter),
    guard: ConcurrencyLimiter = Depends(limiter),
) -> dict[str, Any]:
    async with guard.acquire():
        try:
            return await clinical_reasoning(
                patient.model_dump(), model, assessment_details,
            )
        except Exception as e:
            logger.error("clinical_reasoning failed: %s", e)
            raise HTTPException(status_code=500, detail="clinical_reasoning_failed") from e


@router.post("/safety-validation")
async def safety_validation_endpoint(
    patient: PatientState = Body(...),
    decision: str = Query(...),
    recommendation: Recommendation | None = Body(None),
    model: str = Query("gpt-4.1"),
    clinical_reasoning_context: dict | None = Body(None),
    _: None = Depends(rate_limiter),
    guard: ConcurrencyLimiter = Depends(limiter),
) -> dict[str, Any]:
    rec_dict = recommendation.model_dump() if recommendation else None
    async with guard.acquire():
        try:
            return await safety_validation(
                patient.model_dump(),
                decision,
                rec_dict,
                model,
                clinical_reasoning_context,
            )
        except Exception as e:
            logger.error("safety_validation failed: %s", e)
            raise HTTPException(status_code=500, detail="safety_validation_failed") from e


@router.post("/deep-research-diagnosis")
async def deep_research_diagnosis_endpoint(
    patient: PatientState = Body(...),
    model: str = Query("gpt-4.1"),
    doctor_reasoning: dict | None = Body(None),
    safety_validation_context: dict | None = Body(None),
    _: None = Depends(rate_limiter),
    guard: ConcurrencyLimiter = Depends(limiter),
) -> dict[str, Any]:
    async with guard.acquire():
        try:
            return await deep_research_diagnosis(
                patient.model_dump(), model, doctor_reasoning, safety_validation_context,
            )
        except Exception as e:
            logger.error("deep_research_diagnosis failed: %s", e)
            raise HTTPException(status_code=500, detail="deep_research_failed") from e


@router.post("/uti-complete-assessment")
async def uti_complete_assessment_endpoint(
    patient: PatientState = Body(...),
    model: str = Query("gpt-4.1"),
    _: None = Depends(rate_limiter),
    guard: ConcurrencyLimiter = Depends(limiter),
) -> dict[str, Any]:
    async with guard.acquire():
        try:
            return await uti_complete_patient_assessment(patient.model_dump(), model)
        except Exception as e:
            logger.error("uti_complete_assessment failed: %s", e)
            raise HTTPException(status_code=500, detail="complete_assessment_failed") from e


@router.get("/research-summary")
async def research_summary_endpoint(
    query: str = Query(...),
    region: str = Query(...),
    model: str = Query("gpt-4.1"),
    _: None = Depends(rate_limiter),
    guard: ConcurrencyLimiter = Depends(limiter),
) -> dict[str, Any]:
    async with guard.acquire():
        try:
            return await web_research(query, region, model)
        except Exception as e:
            logger.error("web_research failed: %s", e)
            raise HTTPException(status_code=500, detail="research_failed") from e


