from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple

from pydantic import BaseModel, Field, model_validator


class Sex(str, Enum):
    female = "female"
    male = "male"
    other = "other"
    unknown = "unknown"


class RenalFunction(str, Enum):
    normal = "normal"
    impaired = "impaired"
    failure = "failure"
    unknown = "unknown"


class MedicationAgent(str, Enum):
    nitrofurantoin = "nitrofurantoin"
    tmp_smx = "tmp_smx"
    trimethoprim = "trimethoprim"
    fosfomycin = "fosfomycin"


class RiskLevel(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"
    unknown = "unknown"


class ApprovalDecision(str, Enum):
    approve = "approve"
    conditional = "conditional"
    modify = "modify"
    reject = "reject"
    do_not_start = "do not start"
    refer_no_antibiotics = "refer_no_antibiotics"
    deny = "deny"
    undecided = "undecided"


class Decision(str, Enum):
    no_antibiotics_not_met = "no_antibiotics_not_met"
    refer_complicated = "refer_complicated"
    refer_recurrence = "refer_recurrence"
    recommend_treatment = "recommend_treatment"


class PregnancyStatus(str, Enum):
    pregnant = "pregnant"
    not_pregnant = "not_pregnant"
    not_applicable = "not_applicable"
    unknown = "unknown"
    no = "no"


class VerificationVerdict(str, Enum):
    pass_verdict = "pass"  # noqa: S105
    needs_review = "needs_review"
    fail = "fail"


class EvidenceLevel(str, Enum):
    high = "high"
    moderate = "moderate"
    low = "low"
    insufficient = "insufficient"


class IssueSeverity(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"


# ===== Algorithm Support Data Structures =====


@dataclass(frozen=True)
class MedicationSpec:
    """Immutable medication specification for UTI algorithm"""

    regimen: str
    agent: MedicationAgent
    dose: str
    frequency: str
    duration: str
    alternatives: list[str]
    contraindications: list[str]
    monitoring: list[str]


class RecurrenceResult(NamedTuple):
    """Result of recurrence/relapse check"""

    has_recurrence: bool
    reason: str


# Clinical constants for UTI algorithm
PREGNANCY_EXCLUSIONS = {
    PregnancyStatus.no,
    PregnancyStatus.not_pregnant,
    PregnancyStatus.not_applicable,
    PregnancyStatus.unknown,
}
TMP_SMX_ALLERGY_TERMS = {"tmp/smx", "trimethoprim", "sulfamethoxazole", "sulfonamides"}
REJECT_TERMS = {"reject", "do not start", "refer_no_antibiotics"}

# Treatment specifications (immutable clinical data)
TREATMENT_OPTIONS = {
    MedicationAgent.nitrofurantoin: MedicationSpec(
        regimen="Nitrofurantoin macrocrystals",
        agent=MedicationAgent.nitrofurantoin,
        dose="100 mg",
        frequency="PO BID",
        duration="5 days",
        alternatives=["TMP/SMX", "Trimethoprim", "Fosfomycin"],
        contraindications=["eGFR <30 mL/min", "Recent nitrofurantoin use"],
        monitoring=["Take with food", "Monitor for nausea, headache, dark urine"],
    ),
    MedicationAgent.tmp_smx: MedicationSpec(
        regimen="Trimethoprim/Sulfamethoxazole",
        agent=MedicationAgent.tmp_smx,
        dose="160/800 mg",
        frequency="PO BID",
        duration="3 days",
        alternatives=["Nitrofurantoin", "Trimethoprim", "Fosfomycin"],
        contraindications=["ACEI/ARB use (hyperkalemia risk)", "Sulfa allergy"],
        monitoring=["Hydrate adequately", "Monitor for nausea, rash"],
    ),
    MedicationAgent.trimethoprim: MedicationSpec(
        regimen="Trimethoprim",
        agent=MedicationAgent.trimethoprim,
        dose="200 mg",
        frequency="PO once daily",
        duration="3 days",
        alternatives=["Nitrofurantoin", "TMP/SMX", "Fosfomycin"],
        contraindications=["Trimethoprim allergy"],
        monitoring=["Hydrate adequately", "Monitor for nausea, rash"],
    ),
    MedicationAgent.fosfomycin: MedicationSpec(
        regimen="Fosfomycin trometamol",
        agent=MedicationAgent.fosfomycin,
        dose="3 g",
        frequency="PO",
        duration="Single dose",
        alternatives=["Nitrofurantoin", "TMP/SMX", "Trimethoprim"],
        contraindications=["Age <18 years"],
        monitoring=[
            "Dissolve in water, take on empty stomach",
            "Monitor for nausea, diarrhea",
        ],
    ),
}


# ===== Pydantic Models =====


class Symptoms(BaseModel):
    dysuria: bool = Field(
        ...,
        description="Painful urination reported within current episode.",
    )
    urgency: bool = Field(..., description="Sudden compelling need to urinate.")
    frequency: bool = Field(
        ...,
        description="Urination frequency above normal for patient.",
    )
    suprapubic_pain: bool = Field(
        ...,
        description="Pain or discomfort in suprapubic area.",
    )
    hematuria: bool = Field(
        ...,
        description="Visible blood in urine or positive dipstick.",
    )
    gross_hematuria: bool = Field(
        default=False,
        description="Gross hematuria present; nonspecific symptom requiring physician referral per UTI algorithm.",
    )
    confusion: bool = Field(
        default=False,
        description="Confusion present; nonspecific symptom that should trigger referral when criteria not met.",
    )
    delirium: bool = Field(
        default=False,
        description="Delirium present; nonspecific symptom that should trigger referral when criteria not met.",
    )


class RedFlags(BaseModel):
    fever: bool = Field(..., description="Temperature ≥38°C within past 24-48h.")
    rigors: bool = Field(..., description="Shaking chills suggesting bacteremia.")
    flank_pain: bool = Field(
        ...,
        description="Unilateral/bilateral flank or CVA tenderness.",
    )
    back_pain: bool = Field(
        default=False,
        description="Back pain present; included as a red-flag modifier per assessment diagram.",
    )
    nausea_vomiting: bool = Field(..., description="Nausea and/or vomiting present.")
    systemic: bool = Field(
        ...,
        description="Signs of systemic illness or sepsis concern.",
    )


class History(BaseModel):
    antibiotics_last_90d: bool = Field(
        ...,
        description="Any systemic antibiotic exposure within last 90 days.",
    )
    allergies: list[str] = Field(
        default_factory=list,
        description="All reported allergies (free-text).",
    )
    meds: list[str] = Field(default_factory=list, description="Active medication list.")
    acei_arb_use: bool = Field(
        ...,
        description="True if ACE inhibitor or ARB used (hyperkalemia risk with TMP/SMX).",
    )
    catheter: bool = Field(..., description="Indwelling urinary catheter present.")
    stones: bool = Field(..., description="Known urinary tract stones history.")
    immunocompromised: bool = Field(
        ...,
        description="Any condition or therapy causing immunosuppression.",
    )
    neurogenic_bladder: bool = Field(
        default=False,
        description="Neurogenic bladder or other functional abnormality of urinary tract.",
    )

    class MedClass(str, Enum):
        nsaid = "nsaid"
        potassium_sparing = "potassium_sparing_diuretic"
        acei = "acei"
        arb = "arb"

    med_classes: set[MedClass] = Field(
        default_factory=set,
        description="Derived medication classes inferred from meds list (e.g., nsaid, potassium_sparing_diuretic).",
    )

    @model_validator(mode="after")
    def _infer_med_classes(self):
        meds_lower = [m.lower() for m in (self.meds or [])]
        classes: set[History.MedClass] = set()
        for m in meds_lower:
            if any(
                k in m
                for k in [
                    "ibuprofen",
                    "naproxen",
                    "diclofenac",
                    "celecoxib",
                    "indomethacin",
                    "ketorolac",
                ]
            ):
                classes.add(History.MedClass.nsaid)
            if any(
                k in m
                for k in ["spironolactone", "eplerenone", "amiloride", "triamterene"]
            ):
                classes.add(History.MedClass.potassium_sparing)
            if any(
                k in m
                for k in [
                    "lisinopril",
                    "ramipril",
                    "enalapril",
                    "benazepril",
                    "perindopril",
                    "captopril",
                ]
            ):
                classes.add(History.MedClass.acei)
            if any(
                k in m
                for k in [
                    "losartan",
                    "valsartan",
                    "olmesartan",
                    "candesartan",
                    "irbesartan",
                ]
            ):
                classes.add(History.MedClass.arb)
        self.med_classes = classes
        return self


class Recurrence(BaseModel):
    relapse_within_4w: bool = Field(
        ...,
        description="Return of symptoms within 4 weeks post-therapy.",
    )
    recurrent_6m: bool = Field(..., description="≥2 UTIs within 6 months.")
    recurrent_12m: bool = Field(..., description="≥3 UTIs within 12 months.")


class PatientState(BaseModel):
    age: int = Field(..., ge=0, le=120, description="Patient age in years.")
    sex: Sex = Field(..., description="Administrative sex for safety rules.")
    pregnancy_status: PregnancyStatus = Field(
        ...,
        description="Pregnancy status at time of assessment.",
    )
    renal_function_summary: RenalFunction = Field(
        ...,
        description="Clinically summarized renal function.",
    )
    egfr_ml_min: float | None = Field(
        default=None,
        ge=0.0,
        description="Optional numeric eGFR in mL/min if available; used only for supplemental safety checks (e.g., nitrofurantoin <30 mL/min).",
    )
    symptoms: Symptoms = Field(..., description="Presenting UTI-related symptoms.")
    red_flags: RedFlags = Field(..., description="Upper tract/systemic signs.")
    history: History = Field(
        ...,
        description="Allergy and medication context for safety checks.",
    )
    recurrence: Recurrence = Field(..., description="Relapse/recurrent indicators.")
    locale_code: str = Field(
        ...,
        min_length=2,
        max_length=10,
        description="Region code (e.g., CA-ON) for resistance data.",
    )
    asymptomatic_bacteriuria: bool = Field(
        default=False,
        description="Asymptomatic bacteriuria present; antibiotics not indicated per UTI algorithm.",
    )

    @model_validator(mode="after")
    def validate_pregnancy_and_sex(self):
        if self.sex == Sex.male and self.pregnancy_status not in [
            PregnancyStatus.not_applicable,
            PregnancyStatus.unknown,
        ]:
            self.pregnancy_status = PregnancyStatus.not_applicable
        return self


class Recommendation(BaseModel):
    regimen: str = Field(
        ...,
        description="Chosen agent name (e.g., 'Nitrofurantoin macrocrystals').",
    )
    regimen_agent: MedicationAgent | None = Field(
        default=None,
        description="Enumerated agent identity when recognized (nitrofurantoin, tmp_smx, trimethoprim, fosfomycin).",
    )
    dose: str = Field(..., description="Dose string (e.g., '100 mg').")
    frequency: str = Field(..., description="Dosing frequency (e.g., 'PO BID').")
    duration: str = Field(..., description="Course length (e.g., '5 days').")
    alternatives: list[str] = Field(
        default_factory=list,
        description="Acceptable alternatives adhering to algorithm.",
    )
    contraindications: list[str] = Field(
        default_factory=list,
        description="Notable reasons to avoid certain agents.",
    )
    monitoring: list[str] = Field(
        default_factory=list,
        description="Monitoring and counseling bullets.",
    )

    def as_text(self) -> str:
        head = " ".join([p for p in [self.regimen, self.dose, self.frequency] if p])
        return f"{head} x {self.duration}".strip() if self.duration else head


class AssessmentOutput(BaseModel):
    decision: Decision = Field(..., description="Final routing decision per algorithm.")
    recommendation: Recommendation | None = Field(
        None,
        description="Present only if recommend_treatment.",
    )
    rationale: list[str] = Field(
        default_factory=list,
        description="Short bullets mapping evidence to decision.",
    )
    follow_up: dict | None = Field(
        None,
        description="72-hour plan and escalation triggers.",
    )
    audit: dict = Field(
        default_factory=dict,
        description="Model/tool versions, inputs considered, timestamps.",
    )
    triggered_complicating_factors: list[str] = Field(
        default_factory=list,
        description="Complicating factors that evaluated to true for this patient.",
    )
    triggered_recurrence_markers: list[str] = Field(
        default_factory=list,
        description="Recurrence/relapse markers that evaluated to true.",
    )
    eligibility_criteria_met: bool = Field(
        default=False,
        description="Whether initial uncomplicated cystitis eligibility criteria were met.",
    )
    criteria_not_met_reasons: list[str] = Field(
        default_factory=list,
        description="Reasons for failing eligibility criteria, including nonspecific symptoms.",
    )
    version: str = Field("v1", description="Schema version for contract compatibility.")


# ===== Agents SDK Structured Outputs =====


class ClinicalReasoningOutput(BaseModel):
    reasoning: list[str] = Field(
        default_factory=list,
        description="Detailed clinical reasoning bullets supporting assessment and plan.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Model-reported confidence for clinical assessment in range 0.0-1.0.",
    )
    differential_dx: list[str] = Field(
        default_factory=list,
        description="List of alternative diagnoses considered for this presentation.",
    )
    risk_factors: list[str] = Field(
        default_factory=list,
        description="Risk factors and modifiers impacting clinical decision making.",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Actionable recommendations: diagnostics, therapeutics, counseling, follow-up.",
    )
    clinical_rationale: list[str] = Field(
        default_factory=list,
        description="Narrative rationale paragraphs explaining key judgment calls.",
    )
    stewardship_considerations: list[str] = Field(
        default_factory=list,
        description="Antimicrobial stewardship notes: spectrum, duration, resistance, interactions.",
    )
    citations: list[dict] = Field(
        default_factory=list,
        description="List of citations; each item includes {title, url, relevance}.",
    )
    proposed_regimen_text: str = Field(
        default="",
        description="Doctor-proposed regimen text when decision == recommend_treatment (e.g., 'Nitrofurantoin 100 mg PO BID x 5 days').",
    )

    def as_narrative(self) -> str:
        narrative_parts: list[str] = []
        if self.reasoning:
            reasoning_formatted = "\n".join(
                [f"• {reason}" for reason in self.reasoning],
            )
            narrative_parts.append(f"Key reasoning:\n{reasoning_formatted}")
        if self.recommendations:
            recommendations_formatted = "\n".join(
                [f"• {rec}" for rec in self.recommendations],
            )
            narrative_parts.append(f"Recommendations:\n{recommendations_formatted}")
        if self.stewardship_considerations:
            stewardship_formatted = "\n".join(
                [f"• {steward}" for steward in self.stewardship_considerations],
            )
            narrative_parts.append(f"Stewardship:\n{stewardship_formatted}")
        return (
            "\n\n".join(narrative_parts)
            if narrative_parts
            else "Clinical reasoning completed."
        )


class SafetyValidationOutput(BaseModel):
    safety_flags: list[str] = Field(
        default_factory=list,
        description="Flags requiring attention before initiating or continuing therapy.",
    )
    contraindications: list[str] = Field(
        default_factory=list,
        description="Absolute or relative contraindications identified for the regimen.",
    )
    drug_interactions: list[str] = Field(
        default_factory=list,
        description="Potential drug-drug interactions with current medications.",
    )
    monitoring_requirements: list[str] = Field(
        default_factory=list,
        description="Monitoring steps to ensure safety and efficacy of the regimen.",
    )
    risk_level: RiskLevel = Field(
        default=RiskLevel.unknown,
        description="Overall safety and interaction risk classification.",
    )
    approval_recommendation: ApprovalDecision = Field(
        default=ApprovalDecision.undecided,
        description="Recommendation to approve, conditionally approve, modify, or reject therapy.",
    )
    rationale: str | None = Field(
        default=None,
        description="Brief reasoning for the approval recommendation and risk level.",
    )
    citations: list[dict] = Field(
        default_factory=list,
        description="List of citations; each item includes {title, url, relevance}.",
    )

    def as_narrative(self) -> str:
        highlights: list[str] = []
        if self.risk_level:
            rl = getattr(self.risk_level, "value", self.risk_level)
            highlights.append(f"Risk level: {rl}")
        if self.contraindications:
            contraindications_formatted = "\n".join(
                [f"• {ci}" for ci in self.contraindications],
            )
            highlights.append(f"Contraindications:\n{contraindications_formatted}")
        if self.drug_interactions:
            interactions_formatted = "\n".join(
                [f"• {interaction}" for interaction in self.drug_interactions],
            )
            highlights.append(f"Interactions:\n{interactions_formatted}")
        if self.monitoring_requirements:
            monitoring_formatted = "\n".join(
                [f"• {monitor}" for monitor in self.monitoring_requirements],
            )
            highlights.append(f"Monitoring:\n{monitoring_formatted}")
        return "\n\n".join(highlights) if highlights else "Safety screen complete."


class InterruptStage(str, Enum):
    deterministic_gate = "deterministic_gate"
    safety_gate = "safety_gate"
    validator = "validator"


class OrchestrationPath(str, Enum):
    standard = "standard"
    deterministic_interrupt = "deterministic_interrupt"
    deterministic_no_rx = "deterministic_no_rx"
    safety_interrupt = "safety_interrupt"
    validator_interrupt = "validator_interrupt"


class ConsensusLabel(str, Enum):
    deterministic_interrupt = "Escalate to human (interrupt)"
    no_antibiotics_or_refer = "No antibiotics / Refer"
    safety_interrupt = "Defer antibiotics; escalate to human (safety gate)"
    defer_choose_alternative = "Defer antibiotics; refer or choose alternative"
    defer_revise_plan_safety = "Defer antibiotics; refer or revise plan (safety gate)"
    validator_interrupt = "Escalate to human (validator fail)"


class DoctorSummary(BaseModel):
    narrative: str = Field(default="")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: list[str] = Field(default_factory=list)


class ValidatorResult(BaseModel):
    passed: bool = Field(default=True)
    rules_fired: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    severity: str = Field(default="low")


class AuditBundle(BaseModel):
    assessment: dict
    clinical_reasoning: dict | None = None
    validator: dict | None = None
    safety_validation: dict | None = None
    prescribing_considerations: dict | None = None
    research_context: dict | None = None
    diagnosis: dict | None = None
    consensus_recommendation: str
    verification_report: dict | None = None
    claims_with_citations: dict | None = None
    inputs: dict


class Claim(BaseModel):
    claim_text: str = Field(
        ...,
        description="The extracted claim statement in clear, concise language.",
    )
    evidence_level: EvidenceLevel = Field(
        default=EvidenceLevel.insufficient,
        description="Assessment of evidence quality supporting this claim.",
    )
    source_context: str = Field(
        default="",
        description="Context from which this claim was extracted.",
    )
    citations: list[dict] = Field(
        default_factory=list,
        description="Citations supporting this claim with title, url, and relevance.",
    )


class ClaimExtractionOutput(BaseModel):
    claims: list[Claim] = Field(
        default_factory=list,
        description="List of extracted claims with their supporting citations.",
    )
    extraction_metadata: dict = Field(
        default_factory=dict,
        description="Metadata about the extraction process including confidence and coverage.",
    )


class VerificationIssue(BaseModel):
    issue_type: str = Field(
        ...,
        description="Type of verification issue found (contradiction, unsupported_claim, inconsistency).",
    )
    description: str = Field(
        ...,
        description="Detailed description of the verification issue.",
    )
    severity: IssueSeverity = Field(
        default=IssueSeverity.low,
        description="Severity level: low, moderate, high.",
    )
    components_affected: list[str] = Field(
        default_factory=list,
        description="Which components/sections are affected by this issue.",
    )


class VerificationReport(BaseModel):
    contradictions: list[str] = Field(
        default_factory=list,
        description="Identified contradictions between different components.",
    )
    unsupported_claims: list[str] = Field(
        default_factory=list,
        description="Claims that lack adequate evidence support.",
    )
    alignment_notes: list[str] = Field(
        default_factory=list,
        description="Notes about alignment between assessment components.",
    )
    verdict: VerificationVerdict = Field(
        ...,
        description="Overall verification result: pass, needs_review, or fail.",
    )
    issues: list[VerificationIssue] = Field(
        default_factory=list,
        description="Detailed list of verification issues found.",
    )
    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence in the assessment coherence.",
    )
