# UTI Triage Assistant

## Executive Brief
This UTI Triage Assistant is a production-minded prototype that combines a deterministic clinical algorithm with an LLM intelligence layer to deliver fast, safe, and explainable decisions. It fits clinical workflows: the algorithm guarantees guideline adherence, while agents turn decisions into evidence-backed narratives, safety checks, and patient/provider-ready summaries.

## Why it matters (problem → solution)
- **Problem**: UTIs are common, but frontline decisions can be slow, inconsistent, and hard to audit. Guidelines, resistance patterns, and safety constraints change frequently.
- **Solution**: A hybrid system where a deterministic algorithm makes the primary decision and LLM agents provide reasoning, safety validation, and current evidence—always bounded by hard safety gates.

## Safety & compliance at the core
- **Deterministic safety gates**: drug–drug interactions, contraindications, renal thresholds, dose/duration bounds
- **Mandatory human sign‑off**: outputs are drafts for prescriber approval
- **Immutable audit bundle**: inputs → rules fired → rationale → sources → versions
- **PHI protection** and stop conditions for high‑risk cohorts

## Evaluation and proof
- See the full evaluation framework: [Evaluation and Improvement](EVALUATION.md)
- Tracks safety adherence, guideline concordance, escalation appropriateness, latency, cost, and citation faithfulness with clear release gates.

## High‑level architecture
- Deterministic UTI assessment algorithm makes the decision.
- Agents add clinical reasoning, pharmacist safety review, verification, and web evidence synthesis.
- A single audit bundle powers sign‑off, compliance, and continuous improvement.
- Detailed diagrams and technical notes are in the appendix below.

## 🔭 Observability & Tracing (W&B Weave)

We use W&B Weave’s official OpenAI Agents SDK integration to capture end‑to‑end traces of the agentic workflow. Traces are grouped under a single parent operation so you can review the entire patient assessment as one run, with child nodes for each agent/tool call.

### Enable

Weave is initialized automatically when you run the CLI or demo if your environment has the standard variables set. The defaults work out‑of‑the‑box; cloud mode is used if `WANDB_API_KEY` is present, otherwise local mode.

```bash
# Required for LLM calls
export OPENAI_API_KEY=...

# Optional (cloud mode)
export WANDB_API_KEY=...                 # enables hosted dashboards
export WEAVE_PROJECT=utiplayground  # default used if unset

# Run any workflow – links will be printed to the console
uv run python -m src.cli --sample "Sarah Smith" --non-interactive --write-report
```

### What you’ll see

- Parent op: `cli_patient_assessment` (the whole CLI invocation)
- Child ops (agent/tool stages):
  - `uti_complete_patient_assessment`
  - `clinical_reasoning`
  - `safety_validation`
  - `web_research`
  - `deep_research_diagnosis`

Each node includes inputs/outputs, timing, errors (if any), and linkage back to the final report in `uti-cli/reports/`.

#### Dashboard snapshot using GPT 4.1

![Weave Traces Dashboard](static/traces.png)

### Notes

- Tracing is integrated via Weave’s `WeaveTracingProcessor` per the official guide: `https://weave-docs.wandb.ai/guides/integrations/openai_agents/`.
- Runs are grouped so a single link represents the complete assessment chain. Console output will include the Weave dashboard URL.

#### Runtime flags (behavioral controls)

- `STRICT_INTERRUPTS` (default: `true`): Enforces hard interrupts at deterministic referral, safety reject/do_not_start/deny, and validator failures (high severity).
- `DOCTOR_SUMMARY_ON_REFERRAL` (default: `true`): When interrupting for `refer_*` or `no_antibiotics_not_met`, optionally invoke a brief Doctor Summary; disable to save cost.
- `PRESCRIBER_SIGNOFF_REQUIRED` (default: `true`): Marks outputs as requiring prescriber sign‑off; set to `false` to disable the flag.

---

## Appendix: Technical and Setup

## 🎯 Overview

This system implements a conversational AI agent that:
1. **Collects patient information** from structured inputs (demo cases or an external client)
2. **Diagnoses patients** using clinical algorithms for UTI assessment
3. **Recommends treatment/drugs** based on evidence-based protocols
4. **Provides safety validation** and clinical reasoning using advanced LLM capabilities

## 🏗️ Architecture

### Design Philosophy: Why a Hybrid Deterministic-Agentic Architecture?

Healthcare AI systems face a fundamental tension between two competing requirements. On one side, we need absolute reliability and safety guarantees that only deterministic systems can provide. On the other, we need the flexibility, explainability, and contextual understanding that modern LLMs excel at delivering. Our hybrid architecture resolves this tension by separating concerns: deterministic algorithms handle safety-critical decisions, while LLM agents provide the intelligence layer for communication, verification, and evidence synthesis.

**Core Design Principles:**

- **Safety First**: The deterministic algorithm serves as an unbreakable safety backbone. Every treatment decision must pass through algorithmic validation before any LLM can propose or modify it. This ensures 100% guideline adherence regardless of LLM behavior.

- **Explainability as a Requirement**: Healthcare providers and patients don't just need correct answers—they need to understand the reasoning. LLM agents transform algorithmic decisions into narratives that build trust and enable informed consent.

- **Defense in Depth**: Multiple independent agents check each other's work. The pharmacist agent can override the doctor agent. The verifier can flag contradictions. This redundancy catches errors that any single component might miss.

- **Evidence-Based Decisions**: Every recommendation must be grounded in current clinical evidence. Agents provide citations, resistance data, and guideline references that the deterministic algorithm alone cannot supply.

### Agentic System Design

```mermaid
flowchart TD
  %% 1) Hard gate first
  A["PatientState"] --> GATE{"Red flags / Exclusions?"}
  GATE -->|Yes| HITL1["Escalate to human (interrupt)"]
  GATE -->|No| B["UTI Assessment (Deterministic)"]
  B --> C{"Decision"}

  %% 2) Manager routes deterministically (code-orchestrated)
  C -->|refer / no_rx| SUMM["Doctor Summary (optional)"]
  C -->|recommend_treatment| CR["Doctor Agent: Plan Rationale"]
  CR --> SV["Pharmacist Safety Agent"]
  SV -->|approve| PF["Deterministic Pharmacist Refinement"]
  SV -->|modify/conditional| PF
  SV -->|reject / do_not_start / refer| HITL1

  %% 3) Single validator & audit bundle
  PF --> VAL["State Validator<br/>(schema + rules: eGFR, allergy class, DDI, dose/duration bounds)"]
  VAL -->|fail| HITL1
  VAL --> AUDIT["Audit Bundle<br/>(inputs -> rules fired -> rationale -> sources)"]

  %% 4) Optional verification (signal, not gate)
  AUDIT -->|risk OR low_confidence| VER["Verifier Agent (consistency checks)"]
  VER --> AUDIT

  %% 5) Evidence synthesis runs by default
  AUDIT --> RS["Web Evidence Synthesis (Deep Research)"]
  RS --> AUDIT

  %% 6) Final prescriber interrupt, then output
  AUDIT --> HITL2["Prescriber Sign-off (interrupt)"]
  HITL2 --> OUT["Final Plan + Patient/Provider Summaries"]
```

### Understanding the Audit Bundle

The **Audit Bundle** is a comprehensive record generated for each assessment that captures:
- **Inputs**: The original patient state and all parameters used
- **Rules Fired**: Which deterministic safety rules were triggered (e.g., "nitrofurantoin contraindicated in renal failure", "TMP-SMX + ACE inhibitor interaction detected")
- **Rationale**: Step-by-step reasoning from both the algorithm and agents
- **Sources**: All evidence citations and guideline references used
- **Timestamps & Versions**: When the assessment occurred and which model versions were used
- **Validation Results**: Whether safety checks passed or failed
- **Confidence Scores**: How certain the system is about its recommendations

This audit trail ensures complete traceability for regulatory compliance, clinical review, and continuous improvement. Every decision can be reconstructed and validated after the fact.

### Why We Need Both Components

**The Deterministic Core Cannot Be Replaced by LLMs:**
- **Reproducibility**: Healthcare regulations demand identical inputs produce identical outputs
- **Auditability**: Clear audit trails for adverse event investigation  
- **Hard Safety Constraints**: 0% failure rate on critical rules (e.g., "never prescribe fosfomycin to patients under 18")
- **Performance**: <50ms processing vs 2-6s for LLMs
- **Regulatory Compliance**: Established FDA/Health Canada approval pathways

**The Intelligence Layer (LLM Agents) Is Essential Because:**
- **Contextual Understanding**: The algorithm sees "ACE inhibitor = true" as a binary flag. The pharmacist agent understands that lisinopril + TMP-SMX specifically risks hyperkalemia and can recommend monitoring potassium levels at 48-72 hours.
- **Natural Language Generation**: Patients need instructions like "Take this medication with food to reduce stomach upset." The algorithm outputs "Nitrofurantoin 100mg PO BID x 5 days"—technically correct but inadequate for patient education.
- **Dynamic Evidence Integration**: Resistance patterns change monthly. The algorithm uses static thresholds; agents query real-time surveillance data and recent publications.
- **Clinical Judgment Simulation**: Complex cases require weighing multiple factors. The doctor agent can reason about a 72-year-old with mild renal impairment differently than a 25-year-old athlete.
- **Error Detection Through Redundancy**: When the doctor agent proposes a regimen that the pharmacist agent flags as unsafe, this disagreement surfaces edge cases the algorithm might not have anticipated.

### Critical Design Trade-offs

1. **Algorithm Makes Primary Decision**: Ensures 100% safety even if all LLM agents fail. Less flexibility for complex cases, but we accept this for safety.

2. **Agents Cannot Override Safety Gates**: Prevents adversarial prompts or hallucinations from causing harm. Might miss legitimate edge cases where guidelines could be safely bent.

3. **Sequential Agent Chain with Feedback**: Doctor → Pharmacist → Verifier flow catches errors that parallel processing might miss. Increases latency from 2s to 4-6s, but improves safety.

4. **Mandatory Human Sign-off**: Legal liability and ethical considerations demand human oversight. Removes full automation but ensures clinical accountability.

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- OpenAI API key

### Installation

1. **Clone and setup environment:**
```bash
uv sync
```

2. **Set up environment variables:**
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key:
# OPENAI_API_KEY=your_key_here
```

3. **Run a sample case via the CLI:**

- Reports are written under `reports/`.
- Try built-in sample patients in `data/sample_patients.json`.

```bash
# Good standard example with existing synthetic PatientState
uv run python -m src.cli --sample "Sarah Smith" --model gpt-4.1 --non-interactive --write-report

# Human interruption required due to patient's case
uv run python -m src.cli --sample "Daniel Kim Escalation" --model gpt-4.1 --non-interactive --write-report
```

JSON file format (either full object below, or wrap under `{"patient": {...}}`):
```json
{
  "age": 28,
  "sex": "female",
  "pregnancy_status": "no",
  "renal_function_summary": "normal",
  "symptoms": {
    "dysuria": true,
    "urgency": true,
    "frequency": false,
    "suprapubic_pain": false,
    "hematuria": false
  },
  "red_flags": {
    "fever": false,
    "rigors": false,
    "flank_pain": false,
    "nausea_vomiting": false,
    "systemic": false
  },
  "history": {
    "antibiotics_last_90d": false,
    "allergies": [],
    "meds": [],
    "ACEI_ARB_use": false,
    "catheter": false,
    "stones": false,
    "immunocompromised": false
  },
  "recurrence": {
    "relapse_within_4w": false,
    "recurrent_6m": false,
    "recurrent_12m": false
  },
  "locale_code": "CA-ON"
}
```

## 🔧 Technical Features

### Core Components

**Deterministic Core:**
- **UTI Assessment Algorithm**: Makes primary treatment decisions based on clinical guidelines
- **State Validator**: Enforces hard safety constraints (drug interactions, contraindications)
- **Pharmacist Refinement**: Deterministically selects alternatives when safety issues identified

**Intelligence Layer (LLM Agents):**
- **UTI Doctor Agent**: Provides clinical reasoning and differential diagnosis
- **Clinical Pharmacist Safety Agent**: Deep safety screening and interaction checking
- **Web Evidence Synthesis Agent**: Real-time resistance data and guideline updates
- **UTI Diagnosis Report Agent**: Provider-ready documentation
- **Plan Verification Agent**: Cross-checks all outputs for consistency
- **Claims & Citations Extractor**: Maps evidence to specific claims

### Sequence Diagram

```mermaid
sequenceDiagram
  autonumber
  participant User
  participant Core as UTI Assessment (Deterministic)
  participant Doc as Doctor Agent (Reasoning)
  participant Pharm as Pharmacist Safety Agent
  participant Val as State Validator
  participant Ver as Verifier (optional)
  participant ORCH as Orchestrator

  User->>Core: PatientState
  Core-->>ORCH: AssessmentOutput(decision, recommendation?)

  alt decision == recommend_treatment
    ORCH->>Doc: Assessment + Patient data
    Doc-->>ORCH: ClinicalReasoning(proposed_regimen?)
    ORCH->>Pharm: decision + regimen
    Pharm-->>ORCH: Safety(approval_recommendation)
    opt approval needs refinement
      ORCH->>Doc: Refinement with safety feedback
      Doc-->>ORCH: Refined reasoning
    end
    ORCH->>Val: Patient + final regimen + Safety
    Val-->>ORCH: rules_fired, contradictions
  else refer/no_rx
    ORCH-->>User: Referral/No antibiotics summary
  end

  opt low confidence or high risk
    ORCH->>Ver: Final snapshot
    Ver-->>ORCH: VerificationReport
  end

  ORCH-->>User: Final plan + sign-off requirement
```

Verification gate: triggers on validator severity (moderate/high), Doctor confidence < 0.8, or safety `risk_level` in {moderate, high}.

Validator precedes evidence synthesis: research and diagnosis run only after the validator passes.

### Clinical Algorithm Implementation
- **Deterministic sequential policy**: Structured clinical decision flow
- **Safety Guardrails**: Multiple validation layers and stop conditions
- **Evidence-Based**: Implements OCP UTI prescribing algorithm exactly
- **Regional context**: Canada/Ontario-first. Resistance intelligence is surfaced in prescribing considerations and web research narratives.
- **Note on resistance-aware selection**: The deterministic algorithm does not auto-rank by local resistance; pharmacist and research layers surface this for clinician review.

### MCP Server Integration
- **FastMCP Server**: Expose all UTI agents as MCP tools for AI assistants
- **Pydantic Validation**: Type-safe tool parameters with detailed descriptions  
- **Clinical Tool Suite**: 8 specialized tools for UTI assessment and research
- **Compatible Clients**: Works with Claude Desktop, Cursor, and other MCP clients

#### MCP Tools Available
- `assess_and_plan` - Execute deterministic UTI assessment algorithm
- `uti_complete_patient_assessment` - Full orchestrated flow (assessment → reasoning → safety → validator → evidence → diagnosis → follow-up)
- `clinical_reasoning` - Generate detailed clinical reasoning with confidence scores
- `safety_validation` - Medication safety screening and contraindication checking
- `prescribing_considerations` - Region-aware resistance data and prescribing guidance
- `research_summary` - Evidence-based research with current guidelines
- `deep_research_diagnosis` - Multi-agent provider-ready diagnosis briefs
- `follow_up_plan` - Standardized 72-hour follow-up protocols
- `ocr_extract_pdf` - Extract text from PDF documents for processing


Additional optional inputs supported across tools (for closer parity with the deterministic algorithm):
- `egfr_mL_min` (float|None)
- `asymptomatic_bacteriuria` (bool)
- `symptoms_confusion`, `symptoms_delirium`, `symptoms_gross_hematuria` (bool)
- `red_flags_back_pain` (bool)
- `history_neurogenic_bladder` (bool)

#### Running the MCP Server
```bash
# Start MCP server for AI assistant integration
uv run uti-mcp

# Or use directly
uv run python -m src.server
```

#### MCP Tool Sample Query + Input
Tools use flattened parameters (no nested `params` wrapper). Example: `uti_complete_patient_assessment`.

```json
Generate me a full report for uti assessment for my patient, in full markdown report fully verbose, here are the patients' detail:
{
  "age": 28,
  "sex": "female",
  "pregnancy_status": "no",
  "renal_function_summary": "normal",
  "symptoms": {
    "dysuria": true,
    "urgency": true,
    "frequency": false,
    "suprapubic_pain": false,
    "hematuria": false
  },
  "red_flags": {
    "fever": false,
    "rigors": false,
    "flank_pain": false,
    "nausea_vomiting": false,
    "systemic": false
  },
  "history": {
    "antibiotics_last_90d": false,
    "allergies": [],
    "meds": [],
    "ACEI_ARB_use": false,
    "catheter": false,
    "stones": false,
    "immunocompromised": false
  },
  "recurrence": {
    "relapse_within_4w": false,
    "recurrent_6m": false,
    "recurrent_12m": false
  },
  "locale_code": "CA-ON"
}
```

The server also accepts the optional fields listed above; they are merged into nested `symptoms`, `red_flags`, and `history` objects.

#### MCP Tool call

The result you get from the above query and input is shown as follows in Cursor Chat (or Claude Desktop if you'd like). You can always ask the chat to save the full report in verbose mode in markdown format.

![MCP Tool Call](static/mcp_tool.png)


## 🧪 Testing & Development

### Run Tests
```bash
uv run pytest tests/
```



### Start MCP Server (for external clients)
```bash
uv run uti-mcp
```

### Code Quality
```bash
uv run ruff check .    # Linting
uv run ruff format .   # Formatting  
uv run mypy src/      # Type checking
```
