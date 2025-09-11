import os

from .models import ApprovalDecision, Decision


def safe_model_dump(obj: object) -> dict[str, object]:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return dict(obj) if obj is not None else {}


def parse_decision(decision_raw: object) -> Decision:
    if isinstance(decision_raw, Decision):
        return decision_raw
    if isinstance(decision_raw, str) and hasattr(Decision, decision_raw):
        return Decision(decision_raw)
    return Decision.no_antibiotics_not_met


def parse_approval(approval_raw: object) -> ApprovalDecision:
    if isinstance(approval_raw, ApprovalDecision):
        return approval_raw
    approval_str = str(approval_raw).lower()
    if approval_str in [e.value for e in ApprovalDecision]:
        return ApprovalDecision(approval_str)
    return ApprovalDecision.undecided


def strict_interrupts_enabled() -> bool:
    raw = os.getenv("STRICT_INTERRUPTS", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def prescriber_signoff_required() -> bool:
    raw = os.getenv("PRESCRIBER_SIGNOFF_REQUIRED", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def doctor_summary_on_referral_enabled() -> bool:
    raw = os.getenv("DOCTOR_SUMMARY_ON_REFERRAL", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def should_verify(
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
    vdict = safe_model_dump(validator)
    severity = str(vdict.get("severity", "")).lower()
    passed = bool(vdict.get("passed", True))
    return (
        (not passed)
        or severity in ["moderate", "high"]
        or conf < confidence_threshold
        or risk_str in {"moderate", "high"}
    )
