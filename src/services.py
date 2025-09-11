from __future__ import annotations

import asyncio
import logging
import weave
from pydantic import BaseModel

from .agents_research import (
    execute_agent,
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
    AssessmentOutput,
    AuditBundle,
    ConsensusLabel,
    Decision,
    InterruptStage,
    OrchestrationPath,
    PatientState,
    SectionStatus,
    Recommendation,
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
from .utils import (
    doctor_summary_on_referral_enabled,
    parse_approval,
    parse_decision,
    prescriber_signoff_required,
    safe_model_dump,
    should_verify,
    strict_interrupts_enabled,
)

logger = logging.getLogger(__name__)


class PatientContext(BaseModel):
    patient_data: dict[str, object]
    patient_state: PatientState
    assessment: AssessmentOutput | None = None
    
    @classmethod
    def from_patient_data(cls, patient_data: dict[str, object]) -> PatientContext:
        return cls(
            patient_data=patient_data,
            patient_state=PatientState(**patient_data),
        )
    
    def get_assessment(self) -> AssessmentOutput:
        if self.assessment is None:
            self.assessment = assess_uti_patient(self.patient_state)
        return self.assessment


def _section_sentinel(status: SectionStatus, reason: str, stage: str | None = None) -> dict:
    s = str(status.value if hasattr(status, "value") else status)
    out = {"status": s, "reason": reason, "version": "v1"}
    if stage is not None:
        out["stage"] = stage
    return out


async def _maybe_doctor_summary(
    patient_data: dict, model: str, assessment_details: dict,
) -> dict | None:
    if not doctor_summary_on_referral_enabled():
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
        "prescriber_signoff_required": prescriber_signoff_required(),
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
        claims_with_citations=safe_model_dump(claims_with_citations),
        inputs=patient_inputs,
    )
    out["audit_bundle"] = audit.model_dump()
    return out


@weave.op(name="state_validator_op")
def state_validator_op(
    patient_data: dict, regimen_text: str, safety: dict | None,
) -> dict:
    context = PatientContext.from_patient_data(patient_data)
    val = state_validator(context.patient_state, regimen_text, safety)
    return safe_model_dump(val)


@weave.op(name="clinical_reasoning")
async def clinical_reasoning(
    patient_data: dict, model: str = "gpt-4.1", assessment_details: dict | None = None,
) -> dict:
    context = PatientContext.from_patient_data(patient_data)
    prompt = make_clinical_reasoning_prompt(context.patient_state, assessment_details)
    agent = make_clinical_reasoning_agent(model)
    out = await execute_agent(
        agent_name=agent.name,
        model=model,
        instructions=agent.instructions,
        prompt=prompt,
        output_type=agent.output_type,
        tools=agent.tools,
    )
    result: dict[str, object] = {"model": model, "version": "v1"}
    if hasattr(out, "model_dump"):
        data = out.model_dump()
        result.update(data)
        if hasattr(out, "as_narrative"):
            result["narrative"] = out.as_narrative()
    elif isinstance(out, dict):
        result.update(out)
        if "narrative" not in result:
            reasoning = result.get("reasoning") or []
            if isinstance(reasoning, list) and reasoning:
                lines = "\n".join([f"• {r}" for r in reasoning])
                result["narrative"] = f"Key reasoning:\n{lines}"
            else:
                result["narrative"] = "Clinical reasoning completed."
    else:
        result["narrative"] = "Clinical reasoning completed."
    return result


@weave.op(name="safety_validation")
async def safety_validation(
    patient_data: dict,
    decision: str,
    recommendation: dict | None,
    model: str = "gpt-4.1",
    clinical_reasoning_context: dict | None = None,
) -> dict:
    context = PatientContext.from_patient_data(patient_data)
    rec_text = "None"
    if isinstance(recommendation, dict) and recommendation:
        parts = [
            str(recommendation.get("regimen", "")).strip(),
            str(recommendation.get("dose", "")).strip(),
            str(recommendation.get("frequency", "")).strip(),
        ]
        head = " ".join([p for p in parts if p])
        dur = str(recommendation.get("duration", "")).strip()
        rec_text_candidate = f"{head} x {dur}".strip() if head or dur else ""
        rec_text = rec_text_candidate or rec_text
    if clinical_reasoning_context and (
        decision == Decision.recommend_treatment
        or str(decision) == getattr(Decision, "recommend_treatment").value
        or str(decision) == "recommend_treatment"
    ):
        proposed = str(
            clinical_reasoning_context.get("proposed_regimen_text", "") or "",
        ).strip()
        if proposed:
            rec_text = proposed
    prompt = make_safety_validation_prompt(
        context.patient_state, decision, rec_text, clinical_reasoning_context,
    )
    agent = make_safety_validation_agent(model)
    out = await execute_agent(
        agent_name=agent.name,
        model=model,
        instructions=agent.instructions,
        prompt=prompt,
        output_type=agent.output_type,
        tools=agent.tools,
    )
    result: dict[str, object] = {"model": model, "version": "v1"}
    if hasattr(out, "model_dump"):
        data = out.model_dump()
        result.update(data)
        if hasattr(out, "as_narrative"):
            result["narrative"] = out.as_narrative()
    elif isinstance(out, dict):
        result.update(out)
        if "narrative" not in result:
            result["narrative"] = "Safety screen complete."
    else:
        result["narrative"] = "Safety screen complete."
    return result


@weave.op(name="web_research")
async def web_research(query: str, region: str, model: str = "gpt-4.1") -> dict:
    prompt = make_web_research_prompt(query, region)
    agent = make_research_agent(model)
    result = await stream_text_and_citations(agent, prompt)
    out = result.get("text", "")
    citations = result.get("citations", [])
    narrative = out if out else f"Evidence summary for {region}."
    return {
        "summary": out,
        "region": region,
        "citations": citations,
        "model": model,
        "version": "v1",
        "narrative": narrative,
    }


@weave.op(name="prescribing_considerations")
async def prescribing_considerations(
    patient_data: dict, region: str, model: str = "gpt-4.1",
) -> dict:
    context = PatientContext.from_patient_data(patient_data)
    
    # Delegate to research agent to synthesize considerations; avoid duplicated constants
    considerations: list[str] = []
    assessment = context.get_assessment()
    contraindications = get_contraindications_from_assessment(assessment)
    if contraindications:
        considerations.extend([f"Patient-specific: {ci}" for ci in contraindications])
    
    # Get research data
    extra = await web_research(
        "Latest regional resistance and any UTI guideline updates (concise)",
        region,
        model,
    )
    if extra.get("summary"):
        considerations.append(f"Current resistance intelligence: {extra['summary']}")
    
    citations = list(extra.get("citations", []))
    
    # Format considerations
    formatted_considerations = []
    for consideration in considerations:
        if not consideration.startswith(("Patient-specific:", "Current resistance intelligence:")):
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
    context = PatientContext.from_patient_data(patient_data)
    assessment = context.get_assessment()
    xml = make_diagnosis_xml_prompt(
        context.patient_state, assessment, doctor_reasoning, safety_validation_context,
    )
    agent = make_diagnosis_agent(model)
    result = await stream_text_and_citations(agent, xml)
    out = result.get("text", "")
    citations = result.get("citations", [])
    return {
        "diagnosis": out or "Research diagnosis unavailable",
        "citations": citations,
        "model": model,
        "assessment": safe_model_dump(assessment),
        "version": "v1",
        "narrative": out or "Research diagnosis unavailable",
    }


@weave.op(name="assess_and_plan")
async def assess_and_plan(patient_data: dict) -> dict:
    context = PatientContext.from_patient_data(patient_data)
    result = context.get_assessment()
    rd = safe_model_dump(result)
    decision = rd.get("decision", "unknown")
    rec_obj = rd.get("recommendation")
    rec_text = Recommendation(**rec_obj).as_text() if rec_obj else "None"
    rationale = rd.get("rationale", [])
    follow_up = rd.get("follow_up")

    narrative_lines = [
        f"Decision: {decision}",
        f"Recommendation: {rec_text}",
        f"Rationale: {'; '.join(rationale)}",
    ]
    if follow_up:
        narrative_lines.append(f"Follow-up: {follow_up}")
    rd["version"] = rd.get("version", "v1")
    rd["narrative"] = " \n".join(narrative_lines)
    return rd


@weave.op(name="follow_up_plan")
async def follow_up_plan(patient_data: dict) -> dict:
    context = PatientContext.from_patient_data(patient_data)
    plan_details = get_enhanced_follow_up_plan(context.patient_state)

    narrative_parts = ["72-hour follow-up plan prepared."]
    monitoring = plan_details.get("monitoring_checklist", [])
    special_instructions = plan_details.get("special_instructions", [])
    if monitoring:
        monitoring_formatted = "\n".join([f"• {item}" for item in monitoring])
        narrative_parts.append(f"Monitoring:\n{monitoring_formatted}")
    if special_instructions:
        special_formatted = "\n".join([f"• {item}" for item in special_instructions])
        narrative_parts.append(f"Special Instructions:\n{special_formatted}")
    narrative = " \n".join(narrative_parts)
    return {
        **plan_details,
        "version": "v1",
        "narrative": narrative,
    }


@weave.op(name="uti_complete_patient_assessment")
async def uti_complete_patient_assessment(
    patient_data: dict, model: str = "gpt-4.1",
) -> dict:
    context = PatientContext.from_patient_data(patient_data)
    assessment_result = await assess_and_plan(patient_data)
    
    assessment_details = {
        "decision": assessment_result.get("decision"),
        "recommendation": assessment_result.get("recommendation"),
        "rationale": assessment_result.get("rationale", []),
        "follow_up": assessment_result.get("follow_up"),
        "audit": assessment_result.get("audit", {}),
    }

    decision = parse_decision(
        assessment_result.get("decision", Decision.no_antibiotics_not_met),
    )

    if strict_interrupts_enabled() and decision in {
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
            safety_validation=_section_sentinel(
                SectionStatus.skipped,
                "Skipped due to deterministic interrupt",
                InterruptStage.deterministic_gate,
            ),
            presc=_section_sentinel(
                SectionStatus.skipped,
                "Skipped due to deterministic interrupt",
                InterruptStage.deterministic_gate,
            ),
            research=_section_sentinel(
                SectionStatus.skipped,
                "Skipped due to deterministic interrupt",
                InterruptStage.deterministic_gate,
            ),
            diagnosis=_section_sentinel(
                SectionStatus.skipped,
                "Skipped due to deterministic interrupt",
                InterruptStage.deterministic_gate,
            ),
            follow_up_details=_section_sentinel(
                SectionStatus.not_applicable,
                "Follow-up plan only generated for treatment pathways",
                InterruptStage.deterministic_gate,
            ),
            consensus=ConsensusLabel.deterministic_interrupt.value,
            validator=_section_sentinel(
                SectionStatus.skipped,
                "Validator not run due to deterministic interrupt",
                InterruptStage.deterministic_gate,
            ),
            model=model,
            patient_inputs=patient_data,
            human_escalation=True,
            interrupt_stage=InterruptStage.deterministic_gate,
            verification_report=_section_sentinel(
                SectionStatus.skipped,
                "Verification not run due to deterministic interrupt",
                InterruptStage.deterministic_gate,
            ),
            claims_with_citations=_section_sentinel(
                SectionStatus.skipped,
                "Claims extraction not run due to deterministic interrupt",
                InterruptStage.deterministic_gate,
            ),
        )

    if decision == Decision.recommend_treatment:
        clinical_result = await clinical_reasoning(
            patient_data, model, assessment_details,
        )
    else:
        if strict_interrupts_enabled():
            doctor_summary = await _maybe_doctor_summary(
                patient_data, model, assessment_details,
            )
            return _build_output(
                path=OrchestrationPath.deterministic_no_rx,
                assessment=assessment_result,
                clinical_reasoning=doctor_summary
                or {"reasoning": ["No antibiotics per algorithm"], "confidence": 1.0},
                safety_validation=_section_sentinel(
                    SectionStatus.not_applicable,
                    "Safety validation only runs for treatment pathways",
                    InterruptStage.deterministic_gate,
                ),
                presc=_section_sentinel(
                    SectionStatus.not_applicable,
                    "Prescribing considerations are only generated for treatment pathways",
                    InterruptStage.deterministic_gate,
                ),
                research=_section_sentinel(
                    SectionStatus.skipped,
                    "Skipped for deterministic no-Rx path",
                    InterruptStage.deterministic_gate,
                ),
                diagnosis=_section_sentinel(
                    SectionStatus.skipped,
                    "Skipped for deterministic no-Rx path",
                    InterruptStage.deterministic_gate,
                ),
                follow_up_details=_section_sentinel(
                    SectionStatus.not_applicable,
                    "Follow-up plan only generated for treatment pathways",
                    InterruptStage.deterministic_gate,
                ),
                consensus=ConsensusLabel.no_antibiotics_or_refer.value,
                validator=_section_sentinel(
                    SectionStatus.skipped,
                    "Validator not run for deterministic no-Rx path",
                    InterruptStage.deterministic_gate,
                ),
                model=model,
                patient_inputs=patient_data,
                human_escalation=False,
                verification_report=_section_sentinel(
                    SectionStatus.skipped,
                    "Verification not run for deterministic no-Rx path",
                    InterruptStage.deterministic_gate,
                ),
                claims_with_citations=_section_sentinel(
                    SectionStatus.skipped,
                    "Claims extraction not run for deterministic no-Rx path",
                    InterruptStage.deterministic_gate,
                ),
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

        sa = parse_approval(
            (safety_result or {}).get("approval_recommendation", "undecided"),
        )
        if strict_interrupts_enabled() and sa in [
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
                presc=_section_sentinel(
                    SectionStatus.blocked,
                    "Blocked by safety rejection",
                    InterruptStage.safety_gate,
                ),
                research=_section_sentinel(
                    SectionStatus.skipped,
                    "Skipped due to safety interrupt",
                    InterruptStage.safety_gate,
                ),
                diagnosis=_section_sentinel(
                    SectionStatus.skipped,
                    "Skipped due to safety interrupt",
                    InterruptStage.safety_gate,
                ),
                follow_up_details=_section_sentinel(
                    SectionStatus.skipped,
                    "Follow-up handled by human escalated pathway",
                    InterruptStage.safety_gate,
                ),
                consensus=ConsensusLabel.safety_interrupt.value,
                validator=_section_sentinel(
                    SectionStatus.skipped,
                    "Validator not run due to safety interrupt",
                    InterruptStage.safety_gate,
                ),
                model=model,
                patient_inputs=patient_data,
                human_escalation=True,
                interrupt_stage=InterruptStage.safety_gate,
                verification_report=_section_sentinel(
                    SectionStatus.skipped,
                    "Verification not run due to safety interrupt",
                    InterruptStage.safety_gate,
                ),
                claims_with_citations=_section_sentinel(
                    SectionStatus.skipped,
                    "Claims extraction not run due to safety interrupt",
                    InterruptStage.safety_gate,
                ),
            )
        if sa in [
            ApprovalDecision.modify,
            ApprovalDecision.conditional,
            ApprovalDecision.reject,
            ApprovalDecision.do_not_start,
            ApprovalDecision.refer_no_antibiotics,
        ]:
            refine_prompt = make_reasoning_refinement_prompt(
                context.patient_state, clinical_result, safety_result,
            )
            agent = make_clinical_reasoning_agent(model)
            clinical_result = await execute_agent(
                agent_name=agent.name,
                model=model,
                instructions=agent.instructions,
                prompt=refine_prompt,
                output_type=agent.output_type,
                tools=agent.tools,
            )

    safety_approval = parse_approval(
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
            approval = parse_approval(
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
    if strict_interrupts_enabled() and val_severity == "high":
        return _build_output(
            path=OrchestrationPath.validator_interrupt,
            assessment=assessment_result,
            clinical_reasoning=clinical_result,
            safety_validation=safety_result,
            presc=_section_sentinel(
                SectionStatus.blocked,
                "Blocked by validator (high severity)",
                InterruptStage.validator,
            ),
            research=_section_sentinel(
                SectionStatus.skipped,
                "Skipped due to validator interrupt",
                InterruptStage.validator,
            ),
            diagnosis=_section_sentinel(
                SectionStatus.skipped,
                "Skipped due to validator interrupt",
                InterruptStage.validator,
            ),
            follow_up_details=_section_sentinel(
                SectionStatus.skipped,
                "Follow-up handled by human escalated pathway",
                InterruptStage.validator,
            ),
            consensus=ConsensusLabel.validator_interrupt.value,
            validator=safe_model_dump(validator),
            model=model,
            patient_inputs=patient_data,
            human_escalation=True,
            interrupt_stage=InterruptStage.validator,
            verification_report=_section_sentinel(
                SectionStatus.skipped,
                "Verification not run due to validator interrupt",
                InterruptStage.validator,
            ),
            claims_with_citations=_section_sentinel(
                SectionStatus.skipped,
                "Claims extraction not run due to validator interrupt",
                InterruptStage.validator,
            ),
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
    should_run_verification = should_verify(
        clinical_result, validator, safety_result, confidence_threshold=0.8,
    )

    verification_report = None
    claims_output = None
    
    if should_run_verification:
        verifier_prompt = make_verifier_prompt(final_snapshot)
        claims_prompt = make_claim_extractor_prompt(final_snapshot)
        verifier_agent = make_verifier_agent(model)
        claims_agent = make_claim_extractor_agent(model)
        verification_task = execute_agent(
            agent_name=verifier_agent.name,
            model=model,
            instructions=verifier_agent.instructions,
            prompt=verifier_prompt,
            output_type=verifier_agent.output_type,
            tools=getattr(verifier_agent, "tools", None),
        )
        claims_task = execute_agent(
            agent_name=claims_agent.name,
            model=model,
            instructions=claims_agent.instructions,
            prompt=claims_prompt,
            output_type=claims_agent.output_type,
            tools=getattr(claims_agent, "tools", None),
        )
        verification_report, claims_output = await asyncio.gather(
            verification_task, claims_task,
        )
    else:
        claims_prompt = make_claim_extractor_prompt(final_snapshot)
        claims_agent = make_claim_extractor_agent(model)
        claims_output = await execute_agent(
            agent_name=claims_agent.name,
            model=model,
            instructions=claims_agent.instructions,
            prompt=claims_prompt,
            output_type=claims_agent.output_type,
            tools=getattr(claims_agent, "tools", None),
        )

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
        validator=safe_model_dump(validator),
        model=model,
        patient_inputs=patient_data,
        human_escalation=False,
        verification_report=verification_report,
        claims_with_citations=claims_output,
    )
