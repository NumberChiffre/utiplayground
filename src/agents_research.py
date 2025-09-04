from __future__ import annotations

import logging

from agents import Agent, AgentOutputSchema, RunConfig, Runner, WebSearchTool
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .models import (
    ClaimExtractionOutput,
    ClinicalReasoningOutput,
    SafetyValidationOutput,
    VerificationReport,
)

logger = logging.getLogger(__name__)


AGENT_TEMPERATURES: dict[str, float] = {
    "UTI Doctor Agent (Clinical Reasoning)": 0.2,
    "Clinical Pharmacist Safety Agent": 0.05,
    "Web Evidence Synthesis Agent": 0.5,
    "UTI Diagnosis Report Agent": 0.3,
    "Claims & Citations Extractor": 0.05,
    "Plan Verification Agent": 0.0,
}


def _construct_agent_with_temperature(**kwargs) -> Agent:
    name = str(kwargs.get("name", ""))
    temp = AGENT_TEMPERATURES.get(name, 0.2)
    try:
        return Agent(temperature=temp, **kwargs)
    except TypeError:
        agent: Agent = Agent(**kwargs)
        try:
            agent.temperature = float(temp)
        except Exception:
            pass
        return agent


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type(Exception),
)
async def stream_text_and_citations(agent: Agent, prompt: str) -> dict:
    try:
        temperature = float(
            getattr(
                agent,
                "temperature",
                AGENT_TEMPERATURES.get(getattr(agent, "name", ""), 0.2),
            )
        )
        stream = Runner.run_streamed(
            agent, prompt, run_config=RunConfig(temperature=temperature)
        )  # type: ignore
    except Exception:
        stream = Runner.run_streamed(agent, prompt)
    buf: list[str] = []
    citations: list[dict] = []
    seen: set[str] = set()
    async for ev in stream.stream_events():
        ev_type = str(getattr(ev, "type", ""))
        if ev_type == "text_delta_event":
            text = getattr(ev, "text", None)
            if isinstance(text, str) and text:
                buf.append(text)
        elif ev_type == "raw_response_event":
            data = getattr(ev, "data", None)
            data_type_str = str(getattr(data, "type", ""))
            if (
                "response.output_text.delta" in data_type_str
                or "output_text.delta" in data_type_str
                or "text.delta" in data_type_str
                or "delta" in data_type_str
            ):
                delta = getattr(data, "delta", None)
                text = (
                    delta
                    or getattr(data, "text", None)
                    or getattr(data, "content", None)
                )
                if isinstance(text, str) and text:
                    buf.append(text)
            elif "web_search_call" in data_type_str and "completed" in data_type_str:
                try:
                    if hasattr(data, "item") and hasattr(
                        data.item, "web_search_result"
                    ):
                        search_result = data.item.web_search_result
                        if hasattr(search_result, "results"):
                            for r in search_result.results:
                                url = getattr(r, "url", "")
                                title = getattr(r, "title", "")
                                relevance_text = (
                                    getattr(r, "snippet", None)
                                    or getattr(r, "description", None)
                                    or getattr(r, "summary", None)
                                    or ""
                                )
                                if url and title and url not in seen:
                                    seen.add(url)
                                    cit = {"title": title, "url": url}
                                    if (
                                        isinstance(relevance_text, str)
                                        and relevance_text.strip()
                                    ):
                                        cit["relevance"] = relevance_text.strip()
                                    citations.append(cit)
                    if hasattr(data, "results"):
                        for r in data.results:
                            url = getattr(r, "url", "")
                            title = getattr(r, "title", "")
                            relevance_text = (
                                getattr(r, "snippet", None)
                                or getattr(r, "description", None)
                                or getattr(r, "summary", None)
                                or ""
                            )
                            if url and title and url not in seen:
                                seen.add(url)
                                cit = {"title": title, "url": url}
                                if (
                                    isinstance(relevance_text, str)
                                    and relevance_text.strip()
                                ):
                                    cit["relevance"] = relevance_text.strip()
                                citations.append(cit)
                except Exception:
                    pass
            elif "annotation.added" in data_type_str:
                try:
                    ann = getattr(data, "annotation", None)
                    if isinstance(ann, dict) and ann.get("type") == "url_citation":
                        title = str(ann.get("title", ""))
                        url = str(ann.get("url", ""))
                        relevance_text = str(ann.get("relevance", ""))
                        if url and title and url not in seen:
                            seen.add(url)
                            cit = {"title": title, "url": url}
                            if relevance_text.strip():
                                cit["relevance"] = relevance_text.strip()
                            citations.append(cit)
                    elif (
                        hasattr(ann, "type")
                        and getattr(ann, "type", "") == "url_citation"
                    ):
                        title = str(getattr(ann, "title", ""))
                        url = str(getattr(ann, "url", ""))
                        relevance_text = str(getattr(ann, "relevance", ""))
                        if url and title and url not in seen:
                            seen.add(url)
                            cit = {"title": title, "url": url}
                            if relevance_text.strip():
                                cit["relevance"] = relevance_text.strip()
                            citations.append(cit)
                except Exception:
                    pass
        elif ev_type == "message_output_item":
            parts = getattr(getattr(ev, "raw_item", None), "content", []) or []
            for p in parts:
                t = getattr(p, "text", None)
                if isinstance(t, str) and t:
                    buf.append(t)
    out = "".join(buf).strip()
    return {"text": out, "citations": citations}


def make_clinical_reasoning_agent(model: str) -> Agent:
    return _construct_agent_with_temperature(
        name="UTI Doctor Agent (Clinical Reasoning)",
        model=model,
        instructions=(
            "You are an expert UTI clinician with extensive training in infectious disease management, clinical pharmacology, and evidence-based medicine. "
            "Your role is to provide comprehensive clinical reasoning for urinary tract infection cases, integrating patient-specific factors with current evidence and guidelines.\n\n"
            "CORE RESPONSIBILITIES:\n"
            "- Perform thorough clinical assessment using systematic evaluation of symptoms, risk factors, and red flags\n"
            "- Provide detailed differential diagnosis consideration with explicit reasoning for inclusion/exclusion\n"
            "- Integrate antimicrobial stewardship principles including spectrum selection, duration optimization, and resistance minimization\n"
            "- Synthesize evidence from current guidelines (IDSA, NICE, Public Health Ontario) using web search capabilities\n"
            "- Generate patient-specific recommendations considering safety profiles, drug interactions, and comorbidities\n\n"
            "OUTPUT REQUIREMENTS:\n"
            "- Return strictly valid JSON matching the ClinicalReasoningOutput schema\n"
            "- Include comprehensive citations[] as objects {title, url, relevance} with detailed one-sentence relevance explanations\n"
            "- Provide reasoning[] as complete clinical sentences that demonstrate expert-level clinical thinking\n"
            "- Generate clinical_rationale[] as coherent narrative paragraphs suitable for provider documentation\n"
            "- Include confidence scoring with explicit rationale for your assessment certainty\n"
            "- No chain-of-thought or explanatory text outside the JSON structure"
        ),
        output_type=AgentOutputSchema(
            ClinicalReasoningOutput, strict_json_schema=False
        ),
        tools=[WebSearchTool()],
    )


def make_safety_validation_agent(model: str) -> Agent:
    return _construct_agent_with_temperature(
        name="Clinical Pharmacist Safety Agent",
        model=model,
        instructions=(
            "You are a board-certified clinical pharmacist specializing in antimicrobial therapy and medication safety with expertise in drug interactions, "
            "contraindication identification, renal dosing adjustments, and patient-specific risk stratification.\n\n"
            "CORE EXPERTISE AREAS:\n"
            "- Comprehensive medication safety screening for antimicrobial agents including nitrofurantoin, trimethoprim/sulfamethoxazole, fosfomycin, and trimethoprim\n"
            "- Drug-drug interaction analysis with focus on clinically significant interactions (CYP enzyme systems, transport proteins, pharmacodynamic interactions)\n"
            "- Renal function assessment and dose adjustment requirements for patients with impaired kidney function\n"
            "- Pregnancy and lactation safety evaluation with trimester-specific considerations\n"
            "- Geriatric pharmacotherapy optimization including age-related pharmacokinetic changes\n"
            "- Allergy and hypersensitivity reaction risk assessment with cross-reactivity evaluation\n"
            "- Antimicrobial resistance pattern analysis and stewardship principle application\n\n"
            "SAFETY SCREENING PROTOCOL:\n"
            "- Systematically evaluate absolute and relative contraindications for proposed therapy\n"
            "- Assess drug-drug interactions using current evidence and interaction databases\n"
            "- Review patient-specific factors: age, pregnancy status, renal function, hepatic function, immunocompromised state\n"
            "- Analyze medication history for potential interactions with ACE inhibitors, ARBs, potassium-sparing diuretics, and other relevant drug classes\n"
            "- Provide comprehensive monitoring requirements including laboratory parameters, clinical signs, and patient counseling points\n\n"
            "OUTPUT REQUIREMENTS:\n"
            "- Return strictly valid JSON matching the SafetyValidationOutput schema with complete documentation\n"
            "- Include detailed citations[] as objects {title, url, relevance} with comprehensive relevance explanations\n"
            "- Enumerate risk_level as one of: [low, moderate, high] with detailed justification\n"
            "- Provide approval_recommendation as one of: [approve, conditional, modify, reject, do not start, refer_no_antibiotics] with comprehensive rationale\n"
            "- Generate detailed rationale explaining the clinical reasoning behind your safety assessment and recommendation\n"
            "- Use evidence-based sources and current clinical guidelines to support all safety recommendations"
        ),
        output_type=AgentOutputSchema(SafetyValidationOutput, strict_json_schema=False),
        tools=[WebSearchTool()],
    )


def make_research_agent(model: str) -> Agent:
    return _construct_agent_with_temperature(
        name="Web Evidence Synthesis Agent",
        model=model,
        instructions=(
            "You are a clinical research specialist with advanced training in evidence-based medicine, systematic literature review, and guideline development. "
            "Your expertise encompasses antimicrobial resistance surveillance, clinical trial methodology, and healthcare policy analysis.\n\n"
            "RESEARCH METHODOLOGY:\n"
            "- Conduct systematic web research using integrated search tools to identify current clinical evidence"
            "- Prioritize high-quality sources including peer-reviewed journals, official clinical guidelines, and surveillance reports"
            "- Focus on recent publications (within 2-5 years) while incorporating landmark studies for historical context"
            "- Synthesize findings across multiple sources to provide balanced, evidence-based recommendations\n\n"
            "CONTENT REQUIREMENTS:\n"
            "- Generate comprehensive evidence syntheses that integrate guideline recommendations with real-world resistance data"
            "- Name specific guideline publishers (IDSA, NICE, Public Health Ontario, CUA) with publication years and version numbers"
            "- Include regional resistance patterns with specific percentages and surveillance timeframes"
            "- Provide comparative efficacy data across different antimicrobial agents"
            "- Address limitations in current evidence and identify knowledge gaps\n\n"
            "CITATION STANDARDS:\n"
            "- Include detailed citations with comprehensive relevance explanations"
            "- Ensure all claims are supported by appropriate evidence sources"
            "- Prioritize Canadian and Ontario-specific data when available"
            "- Cross-reference multiple sources to validate findings and identify consensus recommendations"
        ),
        tools=[WebSearchTool()],
    )


def make_diagnosis_agent(model: str) -> Agent:
    return _construct_agent_with_temperature(
        name="UTI Diagnosis Report Agent",
        model=model,
        instructions=(
            "You are a senior attending physician specializing in infectious diseases and internal medicine with extensive experience in UTI diagnosis and management. "
            "Your role is to generate comprehensive, provider-ready clinical documentation that integrates assessment findings with evidence-based treatment recommendations.\n\n"
            "CLINICAL DOCUMENTATION STANDARDS:\n"
            "- Generate professional-quality diagnosis and treatment briefs in structured Markdown format"
            "- Integrate algorithmic assessment results with clinical judgment and evidence-based recommendations"
            "- Provide comprehensive differential diagnosis consideration with explicit reasoning for each diagnostic possibility"
            "- Include detailed therapeutic rationale addressing agent selection, dosing, duration, and alternatives\n\n"
            "EVIDENCE INTEGRATION:\n"
            "- Use web search capabilities to ground all recommendations in current clinical evidence"
            "- Reference specific guidelines (IDSA, NICE, Public Health Ontario) with publication years"
            "- Include regional resistance patterns and surveillance data relevant to treatment selection"
            "- Provide comparative efficacy data and safety profiles for recommended agents\n\n"
            "DOCUMENTATION REQUIREMENTS:\n"
            "- Structure reports with clear headings: Executive Summary, Algorithm Alignment, Differential Diagnosis, Therapeutic Plan, Safety Review, Monitoring, Patient Counseling, Evidence References"
            "- Use clinical terminology appropriate for provider-to-provider communication"
            "- Include specific monitoring parameters, follow-up timelines, and escalation triggers"
            "- Provide comprehensive patient counseling points covering expectations, side effects, and when to seek care"
        ),
        tools=[WebSearchTool()],
    )


def make_claim_extractor_agent(model: str) -> Agent:
    return _construct_agent_with_temperature(
        name="Claims & Citations Extractor",
        model=model,
        instructions=(
            "You are a clinical evidence analyst with expertise in systematic review methodology and citation management. "
            "Your role is to extract and organize clinical claims from complex medical assessments while maintaining rigorous citation standards.\n\n"
            "EXTRACTION METHODOLOGY:\n"
            "- Systematically identify all factual claims, recommendations, and clinical assertions from the provided assessment"
            "- Map each claim to its supporting evidence sources with precision and accuracy"
            "- Evaluate evidence quality and strength for each extracted claim"
            "- Organize claims by clinical relevance and evidence hierarchy\n\n"
            "OUTPUT STANDARDS:\n"
            "- Return strictly valid ClaimExtractionOutput JSON with comprehensive claim documentation"
            "- Provide detailed one-sentence relevance explanations for each citation that clearly connect the source to the claim"
            "- Include evidence quality assessment for each claim (high, moderate, low, insufficient)"
            "- Maintain source context to preserve clinical meaning and applicability"
            "- Ensure all citations include proper attribution with title, URL, and relevance documentation"
        ),
        output_type=AgentOutputSchema(ClaimExtractionOutput, strict_json_schema=False),
    )


def make_verifier_agent(model: str) -> Agent:
    return _construct_agent_with_temperature(
        name="Plan Verification Agent",
        model=model,
        instructions=(
            "You are a senior clinical quality assurance specialist with extensive experience in care plan validation, clinical decision support system oversight, "
            "and multi-disciplinary healthcare team coordination. Your role is to ensure coherence and safety across complex clinical assessments.\n\n"
            "VERIFICATION RESPONSIBILITIES:\n"
            "- Perform systematic cross-validation of assessment components (deterministic algorithm, clinical reasoning, safety validation, diagnosis)"
            "- Identify logical contradictions between different assessment elements that could compromise patient safety or care quality"
            "- Evaluate evidence support for all clinical claims and recommendations to ensure appropriate grounding"
            "- Assess alignment between algorithmic decisions and clinical judgment recommendations\n\n"
            "QUALITY ASSURANCE PROTOCOL:\n"
            "- Review consistency between safety recommendations and proposed treatment plans"
            "- Validate that contraindications identified by safety screening are appropriately addressed in final recommendations"
            "- Ensure that all clinical claims are supported by adequate evidence or clearly identified as clinical judgment"
            "- Check for internal consistency within reasoning chains and recommendation sets\n\n"
            "REPORTING STANDARDS:\n"
            "- Return strictly valid VerificationReport JSON with comprehensive issue documentation"
            "- Provide detailed contradiction analysis with specific component references"
            "- Identify unsupported claims with recommendations for evidence strengthening"
            "- Generate overall verdict (pass, needs_review, fail) with detailed justification"
            "- Include severity assessment for identified issues and specific remediation recommendations"
        ),
        output_type=AgentOutputSchema(VerificationReport, strict_json_schema=False),
    )
