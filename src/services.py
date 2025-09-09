from __future__ import annotations

import asyncio
import logging
import os

import weave
from agents import Agent, Runner
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .agents_research import (
    make_claim_extractor_agent,
    make_clinical_reasoning_agent,
    make_diagnosis_agent,
    make_research_agent,
    make_safety_validation_agent,
    make_verifier_agent,
    stream_text_and_citations,
)
from .models import (
    ApprovalDecision,
    AuditBundle,
    ClinicalReasoningOutput,
    ConsensusLabel,
    Decision,
    InterruptStage,
    OrchestrationPath,
    PatientState,
    Recommendation,
    SafetyValidationOutput,
)
from .prompts import (
    make_claim_extractor_prompt,
    make_clinical_reasoning_prompt,
    make_diagnosis_xml_prompt,
    make_reasoning_refinement_prompt,
    make_safety_validation_prompt,
    make_verifier_prompt,
    make_web_research_prompt,
)
from .uti_algo import (
    assess_uti_patient,
    get_contraindications_from_assessment,
    get_enhanced_follow_up_plan,
    state_validator,
)

logger = logging.getLogger(__name__)


def _strict_interrupts_enabled() -> bool:
    raw = os.getenv("STRICT_INTERRUPTS", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _prescriber_signoff_required() -> bool:
    raw = os.getenv("PRESCRIBER_SIGNOFF_REQUIRED", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _doctor_summary_on_referral_enabled() -> bool:
    raw = os.getenv("DOCTOR_SUMMARY_ON_REFERRAL", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _parse_decision(decision_raw: object) -> Decision:
    if isinstance(decision_raw, Decision):
        return decision_raw
    if isinstance(decision_raw, str) and hasattr(Decision, decision_raw):
        return Decision(decision_raw)
    return Decision.no_antibiotics_not_met


def _parse_approval(approval_raw: object) -> ApprovalDecision:
    if isinstance(approval_raw, ApprovalDecision):
        return approval_raw
    approval_str = str(approval_raw).lower()
    if approval_str in [e.value for e in ApprovalDecision]:
        return ApprovalDecision(approval_str)
    return ApprovalDecision.undecided


def _to_dict(obj: object) -> dict:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore[attr-defined]
    if obj is not None:
        return dict(obj)
    return {}


async def _maybe_doctor_summary(
    patient_data: dict, model: str, assessment_details: dict,
) -> dict | None:
    if not _doctor_summary_on_referral_enabled():
        return None
    doc_out = await clinical_reasoning(patient_data, model, assessment_details)
    if not isinstance(doc_out, dict):
        return {"narrative": "Summary unavailable.", "confidence": 0.0, "reasoning": []}
    return {
        "narrative": str(doc_out.get("narrative", "")).strip(),
        "confidence": doc_out.get("confidence", 0.0),
        "reasoning": doc_out.get("reasoning", []),
    }


def _build_output(
    *,
    path: str,
    assessment: dict,
    clinical_reasoning: dict | None,
    safety_validation: dict | None,
    presc: dict | None,
    research: dict | None,
    diagnosis: dict | None,
    follow_up_details: dict | None,
    consensus: str,
    validator: dict | None,
    model: str,
    patient_inputs: dict,
    human_escalation: bool,
    interrupt_stage: str | None = None,
    verification_report: dict | None = None,
    claims_with_citations: dict | None = None,
) -> dict:
    out = {
        "orchestration": "final_consolidated",
        "orchestration_path": path if isinstance(path, str) else str(path),
        "clinical_reasoning": clinical_reasoning,
        "assessment": assessment,
        "safety_validation": safety_validation,
        "prescribing_considerations": presc,
        "research_context": research,
        "diagnosis": diagnosis,
        "follow_up_details": follow_up_details,
        "confidence": float((clinical_reasoning or {}).get("confidence", 0.0) or 0.0),
        "consensus_recommendation": consensus,
        "verification_report": verification_report,
        "prescriber_signoff_required": _prescriber_signoff_required(),
        "claims_with_citations": claims_with_citations,
        "model": model,
        "version": "v1",
        "improvements": [],
        "human_escalation": human_escalation,
    }
    if interrupt_stage:
        out["interrupt_stage"] = (
            interrupt_stage
            if isinstance(interrupt_stage, str)
            else str(interrupt_stage)
        )
    audit = AuditBundle(
        assessment=assessment,
        clinical_reasoning=clinical_reasoning,
        validator=validator,
        safety_validation=safety_validation,
        prescribing_considerations=presc,
        research_context=research,
        diagnosis=diagnosis,
        consensus_recommendation=consensus,
        verification_report=verification_report,
        claims_with_citations=claims_with_citations,
        inputs=patient_inputs,
    )
    out["audit_bundle"] = audit.model_dump()
    return out


@weave.op(name="state_validator_op")
def state_validator_op(
    patient_data: dict, regimen_text: str, safety: dict | None,
) -> dict:
    patient = PatientState(**patient_data)
    val = state_validator(patient, regimen_text, safety)
    return val.model_dump()


@weave.op(name="pharmacist_refinement_op")
def pharmacist_refinement_op(recommendation: dict, safety_result: dict) -> dict:
    chosen: str | None = None
    alts = list((recommendation or {}).get("alternatives", []) or [])
    if isinstance(recommendation, dict) and recommendation:
        rec_text = Recommendation(**recommendation).as_text()
    else:
        rec_text = "None"

    for alt in alts:
        if isinstance(alt, str) and alt.strip() and alt.strip() != rec_text:
            chosen = alt.strip()
            break
    return {
        "approval": str(
            (safety_result or {}).get("approval_recommendation", "undecided"),
        ),
        "original": rec_text,
        "chosen_alternative": chosen,
    }


@weave.op(name="prescriber_signoff_op")
def prescriber_signoff_op(enabled: bool) -> dict:
    return {"prescriber_signoff_required": bool(enabled)}


def _should_verify(
    clinical_reasoning: dict,
    validator: object,
    safety_result: dict | None,
    confidence_threshold: float = 0.8,
) -> bool:
    conf = float((clinical_reasoning or {}).get("confidence", 0.0) or 0.0)
    risk_raw = (
        (safety_result or {}).get("risk_level")
        if isinstance(safety_result, dict)
        else None
    )
    risk_str = str(getattr(risk_raw, "value", risk_raw) or "").lower()
    vdict: dict = _to_dict(validator)
    severity = str(vdict.get("severity", "")).lower()
    passed = bool(vdict.get("passed", True))
    return (
        (not passed)
        or severity in ["moderate", "high"]
        or conf < confidence_threshold
        or risk_str in {"moderate", "high"}
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(Exception),
)
async def _run_agent_stream_with_retry(agent: Agent, prompt: str) -> object:
    stream = Runner.run_streamed(agent, prompt)  # type: ignore[attr-defined]
    async for _ in stream.stream_events():
        pass
    return stream.final_output


@weave.op(name="clinical_reasoning")
async def clinical_reasoning(
    patient_data: dict, model: str = "gpt-4.1", assessment_details: dict | None = None,
) -> dict:
    patient = PatientState(**patient_data)
    prompt = make_clinical_reasoning_prompt(patient, assessment_details)
    agent: Agent = make_clinical_reasoning_agent(model)
    out: ClinicalReasoningOutput = await _run_agent_stream_with_retry(agent, prompt)  # type: ignore[assignment]
    return {
        **out.model_dump(),
        "model": agent.model,
        "version": "v1",
        "narrative": out.as_narrative(),
    }


@weave.op(name="safety_validation")
async def safety_validation(
    patient_data: dict,
    decision: str,
    recommendation: dict | None,
    model: str = "gpt-4.1",
    clinical_reasoning_context: dict | None = None,
) -> dict:
    patient = PatientState(**patient_data)
    rec_text = "None"
    if recommendation:
        rec_text = Recommendation(**recommendation).as_text()
    decision_enum = Decision(decision) if isinstance(decision, str) else decision
    if clinical_reasoning_context and decision_enum == Decision.recommend_treatment:
        proposed = str(
            clinical_reasoning_context.get("proposed_regimen_text", "") or "",
        ).strip()
        if proposed:
            rec_text = proposed
    prompt = make_safety_validation_prompt(
        patient, decision, rec_text, clinical_reasoning_context,
    )
    agent: Agent = make_safety_validation_agent(model)
    out: SafetyValidationOutput = await _run_agent_stream_with_retry(agent, prompt)  # type: ignore[assignment]
    return {
        **out.model_dump(),
        "model": agent.model,
        "version": "v1",
        "narrative": out.as_narrative(),
    }


@weave.op(name="web_research")
async def web_research(query: str, region: str, model: str = "gpt-4.1") -> dict:
    prompt = make_web_research_prompt(query, region)
    agent: Agent = make_research_agent(model)
    streamed = await stream_text_and_citations(agent, prompt)
    out = streamed["text"]
    citations = streamed["citations"]
    narrative = out if out else f"Evidence summary for {region}."
    return {
        "summary": out,
        "region": region,
        "citations": citations,
        "model": agent.model,
        "version": "v1",
        "narrative": narrative,
    }


@weave.op(name="prescribing_considerations")
async def prescribing_considerations(
    patient_data: dict, region: str, model: str = "gpt-4.1",
) -> dict:
    patient = PatientState(**patient_data)
    considerations = [
        "Urine cultures are not routinely recommended for acute uncomplicated cystitis in non-pregnant women, as empirical therapy is typically effective and culture results rarely change management in straightforward cases.",
        "Escherichia coli remains the most common causative organism in uncomplicated cystitis, accounting for approximately 80-90% of cases in otherwise healthy women.",
        f"Current antimicrobial resistance surveillance data for Ontario indicates E. coli resistance rates of approximately 3% for nitrofurantoin and 20% for trimethoprim-sulfamethoxazole, making nitrofurantoin the preferred first-line agent (region: {region}).",
        "While fosfomycin demonstrates low resistance rates, clinical studies suggest it may be slightly less effective than nitrofurantoin for treating uncomplicated cystitis, supporting nitrofurantoin as the primary first-line choice.",
        "Pediatric patients aged 12 years and older may require weight-based dosing adjustments for certain antibiotics, and prescribers should consult pediatric dosing guidelines for optimal therapeutic outcomes.",
        "Fosfomycin is not indicated for patients under 18 years of age due to limited safety and efficacy data in this population.",
        "Clinical decision-making must account for patient-specific factors including documented allergies and intolerances, recent antimicrobial use within the past 3 months, and previous culture results when available.",
        "Healthcare providers should monitor for potential drug-drug interactions, particularly the risk of hyperkalemia when prescribing trimethoprim-sulfamethoxazole to patients taking ACE inhibitors or ARBs.",
        "Short-course antimicrobial therapy (3-5 days) is strongly favored for uncomplicated cystitis, as it provides equivalent clinical efficacy while reducing the risk of adverse effects, antimicrobial resistance, and Clostridioides difficile infection.",
    ]
    assessment = assess_uti_patient(patient)
    contraindications = get_contraindications_from_assessment(assessment)
    if contraindications:
        considerations.extend([f"Patient-specific: {ci}" for ci in contraindications])
    citations: list[dict] = []
    extra = await web_research(
        "Latest regional resistance and any UTI guideline updates (concise)",
        region,
        model,
    )
    if extra.get("summary"):
        considerations.append(f"Current resistance intelligence: {extra['summary']}")
    citations = list(extra.get("citations", []))
    formatted_considerations = []
    for consideration in considerations:
        if not consideration.startswith(
            "Patient-specific:",
        ) and not consideration.startswith("Current resistance intelligence:"):
            formatted_considerations.append(f"• {consideration}")
        else:
            formatted_considerations.append(f"\n{consideration}")
    narrative = "Prescribing Considerations:\n\n" + "\n".join(formatted_considerations)
    return {
        "considerations": considerations,
        "region": region,
        "version": "v1",
        "model": model,
        "citations": citations,
        "narrative": narrative,
    }


@weave.op(name="deep_research_diagnosis")
async def deep_research_diagnosis(
    patient_data: dict,
    model: str = "gpt-4.1",
    doctor_reasoning: dict | None = None,
    safety_validation_context: dict | None = None,
) -> dict:
    patient = PatientState(**patient_data)
    assessment = assess_uti_patient(patient)
    xml = make_diagnosis_xml_prompt(
        patient, assessment, doctor_reasoning, safety_validation_context,
    )
    agent: Agent = make_diagnosis_agent(model)
    streamed = await stream_text_and_citations(agent, xml)
    out = streamed["text"]
    citations = streamed["citations"]
    summary = out
    return {
        "diagnosis": out,
        "citations": citations,
        "model": agent.model,
        "assessment": assessment.model_dump(),
        "version": "v1",
        "narrative": summary,
    }


@weave.op(name="assess_and_plan")
async def assess_and_plan(patient_data: dict) -> dict:
    patient = PatientState(**patient_data)
    result = assess_uti_patient(patient)
    rd = result.model_dump()
    decision = rd.get("decision", "unknown")
    rec_obj = rd.get("recommendation")
    rec_text = Recommendation(**rec_obj).as_text()
    rationale = rd.get("rationale", [])
    follow_up = rd.get("follow_up")

    def _format_assessment_narrative(
        decision: str, rec_text: str, rationale: list[str], follow_up: str | None,
    ) -> str:
        narrative_lines = [
            f"Decision: {decision}",
            f"Recommendation: {rec_text}",
            f"Rationale: {'; '.join(rationale)}",
        ]
        if follow_up:
            narrative_lines.append(f"Follow-up: {follow_up}")
        return " \n".join(narrative_lines)

    rd["version"] = rd.get("version", "v1")
    rd["narrative"] = _format_assessment_narrative(
        decision, rec_text, rationale, follow_up,
    )
    return rd


@weave.op(name="follow_up_plan")
async def follow_up_plan(patient_data: dict) -> dict:
    patient = PatientState(**patient_data)
    plan_details = get_enhanced_follow_up_plan(patient)

    def _format_follow_up_narrative(
        monitoring: list[str], special_instructions: list[str],
    ) -> str:
        narrative_parts = ["72-hour follow-up plan prepared."]
        if monitoring:
            monitoring_formatted = "\n".join([f"• {item}" for item in monitoring])
            narrative_parts.append(f"Monitoring:\n{monitoring_formatted}")
        if special_instructions:
            special_formatted = "\n".join(
                [f"• {item}" for item in special_instructions],
            )
            narrative_parts.append(f"Special Instructions:\n{special_formatted}")
        return " \n".join(narrative_parts)

    narrative = _format_follow_up_narrative(
        plan_details["monitoring_checklist"],
        plan_details["special_instructions"],
    )

    return {
        **plan_details,
        "version": "v1",
        "narrative": narrative,
    }


@weave.op(name="uti_complete_patient_assessment")
async def uti_complete_patient_assessment(
    patient_data: dict, model: str = "gpt-4.1",
) -> dict:
    assessment_result = await assess_and_plan(patient_data)
    assessment_details = {
        "decision": assessment_result.get("decision"),
        "recommendation": assessment_result.get("recommendation"),
        "rationale": assessment_result.get("rationale", []),
        "follow_up": assessment_result.get("follow_up"),
        "audit": assessment_result.get("audit", {}),
    }

    decision = _parse_decision(
        assessment_result.get("decision", Decision.no_antibiotics_not_met),
    )

    if _strict_interrupts_enabled() and decision in {
        Decision.refer_complicated,
        Decision.refer_recurrence,
    }:
        doctor_summary = await _maybe_doctor_summary(
            patient_data, model, assessment_details,
        )
        return _build_output(
            path=OrchestrationPath.deterministic_interrupt,
            assessment=assessment_result,
            clinical_reasoning=doctor_summary
            or {
                "reasoning": [
                    "Deterministic referral triggered. No agentic processing.",
                ],
                "confidence": 1.0,
            },
            safety_validation=None,
            presc=None,
            research=None,
            diagnosis=None,
            follow_up_details=None,
            consensus=ConsensusLabel.deterministic_interrupt.value,
            validator=None,
            model=model,
            patient_inputs=patient_data,
            human_escalation=True,
            interrupt_stage=InterruptStage.deterministic_gate,
        )

    if decision == Decision.recommend_treatment:
        clinical_result = await clinical_reasoning(
            patient_data, model, assessment_details,
        )
    else:
        if _strict_interrupts_enabled():
            doctor_summary = await _maybe_doctor_summary(
                patient_data, model, assessment_details,
            )
            return _build_output(
                path=OrchestrationPath.deterministic_no_rx,
                assessment=assessment_result,
                clinical_reasoning=doctor_summary
                or {"reasoning": ["No antibiotics per algorithm"], "confidence": 1.0},
                safety_validation=None,
                presc=None,
                research=None,
                diagnosis=None,
                follow_up_details=None,
                consensus=ConsensusLabel.no_antibiotics_or_refer.value,
                validator=None,
                model=model,
                patient_inputs=patient_data,
                human_escalation=False,
            )
        clinical_result = {
            "reasoning": ["Referral/no antibiotics per algorithm"],
            "confidence": 1.0,
        }

    safety_result = None
    if decision == Decision.recommend_treatment:
        safety_result = await safety_validation(
            patient_data,
            decision.value,
            assessment_result.get("recommendation"),
            model,
            clinical_reasoning_context=clinical_result,
        )

        sa = _parse_approval(
            (safety_result or {}).get("approval_recommendation", "undecided"),
        )
        if _strict_interrupts_enabled() and sa in [
            ApprovalDecision.reject,
            ApprovalDecision.do_not_start,
            ApprovalDecision.deny,
            ApprovalDecision.refer_no_antibiotics,
        ]:
            return _build_output(
                path=OrchestrationPath.safety_interrupt,
                assessment=assessment_result,
                clinical_reasoning=clinical_result,
                safety_validation=safety_result,
                presc=None,
                research=None,
                diagnosis=None,
                follow_up_details=None,
                consensus=ConsensusLabel.safety_interrupt.value,
                validator=None,
                model=model,
                patient_inputs=patient_data,
                human_escalation=True,
                interrupt_stage=InterruptStage.safety_gate,
            )
        if sa in [
            ApprovalDecision.modify,
            ApprovalDecision.conditional,
            ApprovalDecision.reject,
            ApprovalDecision.do_not_start,
            ApprovalDecision.refer_no_antibiotics,
        ]:
            patient = PatientState(**patient_data)
            refine_prompt = make_reasoning_refinement_prompt(
                patient, clinical_result, safety_result,
            )
            agent = make_clinical_reasoning_agent(model)
            refined_out: ClinicalReasoningOutput = await _run_agent_stream_with_retry(
                agent, refine_prompt,
            )  # type: ignore[assignment]
            if refined_out is not None and hasattr(refined_out, "model_dump"):
                refined_dict = refined_out.model_dump()  # type: ignore[attr-defined]
                clinical_result = {
                    **refined_dict,
                    "model": agent.model,
                    "version": "v1",
                }

    safety_approval = _parse_approval(
        (safety_result or {}).get("approval_recommendation", "undecided"),
    )
    rec = assessment_result.get("recommendation") or {}
    if isinstance(rec, dict) and rec:
        rec_text = Recommendation(**rec).as_text()
    else:
        rec_text = "None"

    consensus_recommendation = ConsensusLabel.no_antibiotics_or_refer.value
    finalized_regimen_text = "None"
    if decision == Decision.recommend_treatment and rec:
        if safety_approval == ApprovalDecision.approve:
            proposed = str(
                clinical_result.get("proposed_regimen_text", "") or "",
            ).strip()
            finalized_regimen_text = proposed or rec_text
            consensus_recommendation = finalized_regimen_text
        elif safety_approval in [ApprovalDecision.modify, ApprovalDecision.conditional]:
            alternatives = list(rec.get("alternatives", []) or [])
            chosen_alt = None
            if alternatives:
                for alt in alternatives:
                    if isinstance(alt, str) and alt.strip() and alt.strip() != rec_text:
                        chosen_alt = alt.strip()
                        break
            if chosen_alt:
                finalized_regimen_text = chosen_alt
                consensus_recommendation = (
                    f"Modify regimen: {chosen_alt} (per safety validation)"
                )
            else:
                finalized_regimen_text = rec_text
                consensus_recommendation = (
                    f"Modify regimen: {rec_text} (see safety validation)"
                )
        elif safety_approval in [
            ApprovalDecision.reject,
            ApprovalDecision.do_not_start,
            ApprovalDecision.deny,
        ]:
            consensus_recommendation = ConsensusLabel.defer_choose_alternative.value
        else:
            finalized_regimen_text = rec_text
            consensus_recommendation = rec_text

    if decision == Decision.recommend_treatment:
        if isinstance(safety_result, dict):
            approval = _parse_approval(
                (safety_result or {}).get("approval_recommendation", "undecided"),
            )
            if approval in [
                ApprovalDecision.reject,
                ApprovalDecision.do_not_start,
                ApprovalDecision.deny,
                ApprovalDecision.refer_no_antibiotics,
            ]:
                consensus_recommendation = ConsensusLabel.defer_revise_plan_safety.value

    validator = state_validator_op(patient_data, finalized_regimen_text, safety_result)
    val_passed = (
        bool(validator.get("passed", True))
        if isinstance(validator, dict)
        else bool(getattr(validator, "passed", True))
    )
    val_severity = (
        str(validator.get("severity", "")).lower()
        if isinstance(validator, dict)
        else str(getattr(validator, "severity", "")).lower()
    )
    if _strict_interrupts_enabled() and val_severity == "high":
        return _build_output(
            path=OrchestrationPath.validator_interrupt,
            assessment=assessment_result,
            clinical_reasoning=clinical_result,
            safety_validation=safety_result,
            presc=None,
            research=None,
            diagnosis=None,
            follow_up_details=None,
            consensus=ConsensusLabel.validator_interrupt.value,
            validator=validator
            if isinstance(validator, dict)
            else getattr(validator, "model_dump", lambda: validator)(),
            model=model,
            patient_inputs=patient_data,
            human_escalation=True,
            interrupt_stage=InterruptStage.validator,
        )
    presc_result = None
    summary_result = None
    diagnosis_result = None
    if val_passed:
        region = patient_data.get("locale_code", "CA-ON")
        presc_task = prescribing_considerations(patient_data, region, model)
        summary_task = web_research(
            "Latest UTI guideline updates and resistance (concise)", region, model,
        )
        diagnosis_task = deep_research_diagnosis(
            patient_data,
            model,
            doctor_reasoning=clinical_result,
            safety_validation_context=safety_result
            if isinstance(safety_result, dict)
            else None,
        )
        presc_result, summary_result, diagnosis_result = await asyncio.gather(
            presc_task,
            summary_task,
            diagnosis_task,
        )

    follow_up_details = None
    if decision == Decision.recommend_treatment:
        follow_up_details = await follow_up_plan(patient_data)

    final_snapshot = {
        "assessment": assessment_result,
        "clinical_reasoning": clinical_result,
        "safety_validation": safety_result,
        "diagnosis": diagnosis_result,
        "prescribing_considerations": presc_result,
        "research_context": summary_result,
        "validator": validator,
        "consensus_recommendation": consensus_recommendation,
    }

    verification_report = None
    should_verify = _should_verify(
        clinical_result, validator, safety_result, confidence_threshold=0.8,
    )

    if should_verify:
        verifier_agent = make_verifier_agent(model)
        verifier_prompt = make_verifier_prompt(final_snapshot)
        verification_report = await _run_agent_stream_with_retry(
            verifier_agent, verifier_prompt,
        )
        if verification_report is not None and hasattr(
            verification_report, "model_dump",
        ):
            verification_report = verification_report.model_dump()  # type: ignore[attr-defined]

    claims_output = None
    claims_agent = make_claim_extractor_agent(model)
    claims_prompt = make_claim_extractor_prompt(final_snapshot)
    claims_output = await _run_agent_stream_with_retry(claims_agent, claims_prompt)
    if claims_output is not None and hasattr(claims_output, "model_dump"):
        claims_output = claims_output.model_dump()  # type: ignore[attr-defined]
    _ = prescriber_signoff_op(_prescriber_signoff_required())

    return _build_output(
        path=OrchestrationPath.standard,
        assessment=assessment_result,
        clinical_reasoning=clinical_result,
        safety_validation=safety_result,
        presc=presc_result,
        research=summary_result,
        diagnosis=diagnosis_result,
        follow_up_details=follow_up_details,
        consensus=consensus_recommendation,
        validator=validator
        if isinstance(validator, dict)
        else getattr(validator, "model_dump", lambda: validator)(),
        model=model,
        patient_inputs=patient_data,
        human_escalation=False,
        verification_report=verification_report,
        claims_with_citations=claims_output,
    )
