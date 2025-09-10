from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import weave
from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .client import ensure_openai_client
from .services import (
    assess_and_plan,
    uti_complete_patient_assessment,
)

load_dotenv()

console = Console()


def _read_json_file(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_sample_patient(name: str | None) -> tuple[str, dict] | None:
    data_path = Path(__file__).resolve().parent.parent / "data" / "sample_patients.json"
    if not data_path.exists():
        return None
    data = _read_json_file(data_path)
    if not isinstance(data, list):
        return None
    if name is None:
        item = data[0]
        return item.get("name", "Sample"), item.get("patient", {})
    lowered = name.strip().lower()
    for item in data:
        if str(item.get("name", "")).strip().lower() == lowered:
            return item.get("name", name), item.get("patient", {})
    return None


def _ask(
    prompt: str,
    default: str | None = None,
    choices: list[str] | None = None,
) -> str:
    suffix = f" [{default}]" if default is not None else ""
    if choices:
        suffix += f" ({'/'.join(choices)})"
    while True:
        console.print(f"[bold]{prompt}[/bold]{suffix}: ", end="")
        val = input().strip()
        if not val and default is not None:
            return default
        if choices and val and val not in choices:
            console.print(f"[red]Please enter one of: {', '.join(choices)}[/red]")
            continue
        if val:
            return val


def _to_bool_fuzzy(text: str) -> bool | None:
    t = text.strip().lower()
    if t == "":
        return None
    positives = {
        "y",
        "yes",
        "true",
        "t",
        "1",
        "present",
        "have",
        "has",
        "on",
        "positive",
        "pos",
        "urgent",
        "urgency",
        "severe",
        "very",
        "often",
        "frequent",
    }
    negatives = {
        "n",
        "no",
        "false",
        "f",
        "0",
        "none",
        "nil",
        "absent",
        "off",
        "negative",
        "neg",
        "n/a",
        "na",
    }
    if t in positives:
        return True
    if t in negatives:
        return False
    try:
        # Accept numeric frequencies like "10 per day" or "2"
        num = "".join(ch for ch in t if (ch.isdigit() or ch == "."))
        if num:
            return float(num) > 0
    except Exception:  # noqa: S110
        pass  # Optional numeric conversion
    keywords_true = [
        "urgent",
        "frequency",
        "frequent",
        "often",
        "blood",
        "hematuria",
        "pain",
    ]
    if any(k in t for k in keywords_true):
        return True
    return None


def _ask_bool(prompt: str, *, default: bool = False) -> bool:
    default_text = "y" if default else "n"
    while True:
        console.print(
            f"[bold]{prompt}[/bold] [y/n or free-text] [{default_text}]: ",
            end="",
        )
        val = input().strip()
        parsed = _to_bool_fuzzy(val)
        if parsed is True:
            return True
        if parsed is False:
            return False
        if parsed is None:
            if val == "":
                return default
            console.print(
                "[yellow]Could not parse; please answer y/n or a descriptive value[/yellow]",
            )


def _ask_float(prompt: str, default: float | None = None) -> float | None:
    default_text = "" if default is None else str(default)
    while True:
        console.print(f"[bold]{prompt}[/bold] [{default_text}]: ", end="")
        val = input().strip()
        if not val:
            return default
        try:
            return float(val)
        except Exception:
            console.print("[yellow]Please enter a number or leave blank[/yellow]")


def _ask_list(prompt: str, default: list[str] | None = None) -> list[str]:
    default = default or []
    default_text = ", ".join(default) if default else ""
    console.print(
        f"[bold]{prompt}[/bold] (comma-separated, 'none' if none) [{default_text}]: ",
        end="",
    )
    val = input().strip()
    if not val:
        return default
    lowered = val.lower().strip()
    if lowered in {"none", "no", "n", "na", "n/a"}:
        return []
    return [x.strip() for x in val.split(",") if x.strip()]


def _wizard(prefill: dict | None = None) -> dict:
    pre = prefill or {}
    symptoms = pre.get("symptoms", {})
    red_flags = pre.get("red_flags", {})
    history = pre.get("history", {})
    recurrence = pre.get("recurrence", {})

    console.print(Panel.fit("UTI CLI Assessment Wizard", style="bold cyan"))

    age = int(_ask("Age (years)", str(pre.get("age", 30))))
    sex = _ask("Sex", pre.get("sex", "female"), ["female", "male", "other", "unknown"])
    pregnancy_status = _ask("Pregnancy status", pre.get("pregnancy_status", "no"))
    renal_function_summary = _ask(
        "Renal function",
        pre.get("renal_function_summary", "normal"),
        ["normal", "impaired", "failure", "unknown"],
    )
    egfr_ml_min = _ask_float("eGFR (mL/min) — optional", pre.get("egfr_ml_min"))
    locale_code = _ask("Region code (e.g., CA-ON)", pre.get("locale_code", "CA-ON"))

    console.print(Panel.fit("Symptoms", style="bold yellow"))
    dysuria = _ask_bool(
        "Dysuria (painful urination)",
        bool(symptoms.get("dysuria", True)),
    )
    urgency = _ask_bool(
        "Urgency (sudden compelling need to urinate)",
        bool(symptoms.get("urgency", True)),
    )
    frequency = _ask_bool(
        "Frequency (above normal for you)",
        bool(symptoms.get("frequency", False)),
    )
    suprapubic_pain = _ask_bool(
        "Suprapubic pain (lower abdomen)",
        bool(symptoms.get("suprapubic_pain", False)),
    )
    hematuria = _ask_bool(
        "Hematuria (visible blood or positive dipstick)",
        bool(symptoms.get("hematuria", False)),
    )
    confusion = _ask_bool(
        "Confusion (nonspecific; triggers referral when criteria not met)",
        bool(symptoms.get("confusion", False)),
    )
    delirium = _ask_bool(
        "Delirium (nonspecific; triggers referral when criteria not met)",
        bool(symptoms.get("delirium", False)),
    )

    console.print(Panel.fit("Red flags (upper/systemic)", style="bold yellow"))
    fever = _ask_bool("Fever ≥38°C (past 24-48h)", bool(red_flags.get("fever", False)))
    rigors = _ask_bool("Rigors (shaking chills)", bool(red_flags.get("rigors", False)))
    flank_pain = _ask_bool(
        "Flank/CVA tenderness",
        bool(red_flags.get("flank_pain", False)),
    )
    back_pain = _ask_bool(
        "Back pain (modifier)",
        bool(red_flags.get("back_pain", False)),
    )
    nausea_vomiting = _ask_bool(
        "Nausea or vomiting",
        bool(red_flags.get("nausea_vomiting", False)),
    )
    systemic = _ask_bool(
        "Systemic illness/sepsis concern",
        bool(red_flags.get("systemic", False)),
    )

    console.print(Panel.fit("History", style="bold yellow"))
    abx_90d = _ask_bool(
        "Any systemic antibiotics in last 90 days?",
        bool(history.get("antibiotics_last_90d", False)),
    )
    allergies = _ask_list("Allergies", list(history.get("allergies", [])))
    meds = _ask_list("Active medications", list(history.get("meds", [])))
    acei_arb = _ask_bool(
        "ACE inhibitor or ARB use?",
        bool(history.get("acei_arb_use", False)),
    )
    catheter = _ask_bool(
        "Indwelling urinary catheter present?",
        bool(history.get("catheter", False)),
    )
    stones = _ask_bool(
        "Known urinary tract stones history?",
        bool(history.get("stones", False)),
    )
    immunocompromised = _ask_bool(
        "Immunocompromised?",
        bool(history.get("immunocompromised", False)),
    )
    neurogenic_bladder = _ask_bool(
        "Neurogenic bladder / abnormal urinary function?",
        bool(history.get("neurogenic_bladder", False)),
    )
    asymptomatic_bacteriuria = _ask_bool(
        "Asymptomatic bacteriuria present? (no urinary symptoms)",
        bool(pre.get("asymptomatic_bacteriuria", False)),
    )

    console.print(Panel.fit("Relapse/Recurrent markers", style="bold yellow"))
    relapse_4w = _ask_bool(
        "Relapse within 4 weeks of therapy?",
        bool(recurrence.get("relapse_within_4w", False)),
    )
    recurrent_6m = _ask_bool(
        "≥2 UTIs within 6 months?",
        bool(recurrence.get("recurrent_6m", False)),
    )
    recurrent_12m = _ask_bool(
        "≥3 UTIs within 12 months?",
        bool(recurrence.get("recurrent_12m", False)),
    )

    patient = {
        "age": age,
        "sex": sex,
        "pregnancy_status": pregnancy_status,
        "renal_function_summary": renal_function_summary,
        "egfr_ml_min": egfr_ml_min,
        "symptoms": {
            "dysuria": dysuria,
            "urgency": urgency,
            "frequency": frequency,
            "suprapubic_pain": suprapubic_pain,
            "hematuria": hematuria,
            "confusion": confusion,
            "delirium": delirium,
        },
        "red_flags": {
            "fever": fever,
            "rigors": rigors,
            "flank_pain": flank_pain,
            "back_pain": back_pain,
            "nausea_vomiting": nausea_vomiting,
            "systemic": systemic,
        },
        "history": {
            "antibiotics_last_90d": abx_90d,
            "allergies": allergies,
            "meds": meds,
            "acei_arb_use": acei_arb,
            "catheter": catheter,
            "stones": stones,
            "immunocompromised": immunocompromised,
            "neurogenic_bladder": neurogenic_bladder,
        },
        "recurrence": {
            "relapse_within_4w": relapse_4w,
            "recurrent_6m": recurrent_6m,
            "recurrent_12m": recurrent_12m,
        },
        "locale_code": locale_code,
        "asymptomatic_bacteriuria": asymptomatic_bacteriuria,
    }

    return {
        "age": age,
        "sex": sex.value,
        "pregnancy_status": pregnancy_status,
        "renal_function_summary": renal_function_summary,
        "egfr_ml_min": egfr_ml_min,
        "symptoms": {
            "dysuria": dysuria,
            "urgency": urgency,
            "frequency": frequency,
            "suprapubic_pain": suprapubic_pain,
            "hematuria": hematuria,
        },
        "red_flags": {
            "fever": fever,
            "rigors": rigors,
            "flank_pain": flank_pain,
            "nausea_vomiting": nausea_vomiting,
            "systemic": systemic,
        },
        "history": {
            "antibiotics_last_90d": antibiotics_last_90d,
            "allergies": allergies,
            "meds": meds,
            "acei_arb_use": acei_arb_use,
            "catheter": catheter,
            "stones": stones,
            "immunocompromised": immunocompromised,
        },
        "recurrence": {
            "relapse_within_4w": relapse_within_4w,
            "recurrent_6m": recurrent_6m,
            "recurrent_12m": recurrent_12m,
        },
        "locale_code": locale_code,
    }


def _print_assessment(result: dict) -> None:  # noqa: C901, PLR0912
    decision = result.get("decision", "unknown")
    # Clean up enum display if needed
    decision_str = str(decision)
    if decision_str.startswith("Decision."):
        decision_str = decision_str.replace("Decision.", "")
    panel_title = f"Decision: {decision_str}"
    console.print(Panel.fit(panel_title, style="bold green"))

    rec: dict[str, Any] | None = result.get("recommendation")
    if rec:
        table = Table(
            title="Treatment Recommendation",
            box=box.SIMPLE_HEAD,
            highlight=True,
        )
        table.add_column("Regimen")
        table.add_column("Dose")
        table.add_column("Frequency")
        table.add_column("Duration")
        table.add_row(
            str(rec.get("regimen", "")),
            str(rec.get("dose", "")),
            str(rec.get("frequency", "")),
            str(rec.get("duration", "")),
        )
        console.print(table)

        alts = list(rec.get("alternatives", []) or [])
        if alts:
            alt_table = Table(title="Acceptable Alternatives", box=box.SIMPLE_HEAD)
            alt_table.add_column("Regimen")
            for alt in alts:
                alt_table.add_row(str(alt))
            console.print(alt_table)

        ci = list(rec.get("contraindications", []) or [])
        if ci:
            ci_table = Table(title="Contraindications", box=box.SIMPLE_HEAD)
            ci_table.add_column("Notes")
            for item in ci:
                ci_table.add_row(str(item))
            console.print(ci_table)

    rationale = list(result.get("rationale", []) or [])
    if rationale:
        rat_table = Table(title="Rationale", box=box.SIMPLE_HEAD)
        rat_table.add_column("Reason")
        for r in rationale:
            rat_table.add_row(str(r))
        console.print(rat_table)

    follow_up = result.get("follow_up")
    if follow_up:
        console.print(Panel.fit("72-hour Follow-up Plan", style="bold cyan"))
        for k, v in dict(follow_up).items():
            key_clean = k.replace("_", " ").title()
            if isinstance(v, list):
                console.print(f"[bold]{key_clean}:[/bold]")
                for item in v:
                    console.print(f"  • {item}")
            else:
                console.print(f"[bold]{key_clean}:[/bold] {v}")
        console.print("")


@weave.op(name="cli_patient_assessment")
async def _run(mode: str, patient: dict, model: str) -> dict:
    """Main CLI assessment function - creates parent Weave operation for all sub-operations."""
    if mode == "deterministic":
        return await assess_and_plan(patient)
    if mode == "agent":
        return await uti_complete_patient_assessment(patient, model)
    det = await assess_and_plan(patient)
    agent_out = await uti_complete_patient_assessment(patient, model)
    return {"deterministic": det, "agent": agent_out}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="uti-cli", description="CLI for UTI CLI agent")
    p.add_argument(
        "--json",
        type=str,
        help="Path to JSON with PatientState payload",
        default=None,
    )
    p.add_argument(
        "--sample",
        type=str,
        help="Sample name from sample_patients.json",
        default=None,
    )
    p.add_argument(
        "--mode",
        type=str,
        choices=["deterministic", "agent", "both"],
        default="agent",
        help="Which pipeline to run",
    )
    p.add_argument("--json-output", action="store_true", help="Print raw JSON output")
    p.add_argument(
        "--model",
        type=str,
        default="gpt-4.1",
        help="LLM model for agent pipeline (e.g., gpt-4.1, gpt-5)",
    )
    p.add_argument(
        "--non-interactive",
        action="store_true",
        help="Do not prompt; use provided --json/--sample as full patient input",
    )
    p.add_argument(
        "--write-report",
        action="store_true",
        help="Write a provider Markdown summary to uti-cli/reports/",
    )
    p.add_argument(
        "--report-dir",
        type=str,
        default=None,
        help="Optional directory to write report(s) to",
    )
    return p


def main() -> None:  # noqa: C901, PLR0912, PLR0915
    parser = _build_parser()
    args = parser.parse_args()

    prefill: dict | None = None
    title_name: str | None = None

    if args.sample:
        loaded = _load_sample_patient(args.sample)
        if loaded is None:
            console.print(f"[red]Sample not found: {args.sample}[/red]")
            raise SystemExit(2) from None
        title_name, prefill = loaded
    elif args.json:
        try:
            doc = _read_json_file(Path(args.json))
        except Exception as e:
            console.print(f"[red]Failed to read JSON: {e}[/red]")
            raise SystemExit(2) from e
        # Accept either full record or {"patient": {...}}
        prefill = doc.get("patient", doc) if isinstance(doc, dict) else None

    patient: dict
    if args.non_interactive and isinstance(prefill, dict) and prefill:
        patient = prefill
    else:
        patient = _wizard(prefill)
    if title_name:
        console.print(
            Panel.fit(f"Running assessment for: {title_name}", style="bold magenta"),
        )

    # Initialize OpenAI client for agent modes if available
    try:
        if args.mode in {"agent", "both"}:
            ensure_openai_client()
    except Exception:  # noqa: S110
        pass  # Client initialization is optional

    try:
        result = asyncio.run(_run(args.mode, patient, args.model))
    except KeyboardInterrupt:
        console.print("[red]Cancelled[/red]")
        raise SystemExit(130) from None

    if args.json_output:
        console.print_json(data=result)
        return

    def _print_agent(agent: dict) -> None:  # noqa: C901, PLR0912, PLR0915
        consensus = str(agent.get("consensus_recommendation", ""))
        path = agent.get("orchestration_path", "standard")
        console.print(
            Panel.fit(
                f"Consensus Recommendation ({path}):\n{consensus}",
                style="bold blue",
            ),
        )

        # Show prescriber sign-off requirement prominently if present
        try:
            signoff_required = bool(agent.get("prescriber_signoff_required", False))
        except Exception:
            signoff_required = False
        if signoff_required:
            console.print(Panel.fit("Prescriber sign-off required", style="bold red"))

        assess = agent.get("assessment") or {}
        if assess:
            console.print(
                Panel.fit("Deterministic Assessment Snapshot", style="bold green"),
            )
            _print_assessment(assess)

        cr = agent.get("clinical_reasoning") or {}
        if cr:
            # Format confidence as percentage
            confidence = cr.get("confidence", 0)
            if isinstance(confidence, int | float):
                confidence_str = (
                    f"{confidence * 100:.0f}%"
                    if confidence <= 1
                    else f"{confidence:.0f}%"
                )
            else:
                confidence_str = str(confidence)

            console.print(
                Panel.fit(
                    f"Clinical Reasoning - Confidence: {confidence_str}",
                    style="bold yellow",
                ),
            )

            narrative = str(cr.get("narrative", "")).strip()
            console.print(f"[dim]{narrative}[/dim]")
            console.print("")

        sv = agent.get("safety_validation") or {}
        if sv:
            # Clean up enum displays
            approval = str(sv.get("approval_recommendation", ""))
            if approval.startswith("ApprovalDecision."):
                approval = (
                    approval.replace("ApprovalDecision.", "").replace("_", " ").title()
                )

            risk_level = str(sv.get("risk_level", ""))
            if risk_level.startswith("RiskLevel."):
                risk_level = risk_level.replace("RiskLevel.", "").title()

            console.print(
                Panel.fit(
                    f"Safety: {approval} - Risk Level: {risk_level}",
                    style="bold green",
                ),
            )

            nar = str(sv.get("narrative", "")).strip()
            console.print(f"[dim]{nar}[/dim]")
            console.print("")

        rc = agent.get("research_context") or {}
        if rc:
            region = str(rc.get("region", ""))
            summary = str(rc.get("summary", ""))
            console.print(Panel.fit(f"Research Context ({region})", style="bold blue"))
            console.print(f"[dim]{summary}[/dim]")
            console.print("")

        pc = agent.get("prescribing_considerations") or {}
        if pc:
            nar = str(pc.get("narrative", ""))
            if nar:
                console.print(
                    Panel.fit("Prescribing Considerations", style="bold magenta"),
                )
                # Clean up the narrative formatting
                if nar.startswith("Prescribing considerations: "):
                    nar = nar.replace("Prescribing considerations: ", "")
                if nar.startswith("Prescribing Considerations:"):
                    nar = nar.replace("Prescribing Considerations:", "")
                console.print(f"[dim]{nar.strip()}[/dim]")
                console.print("")

        diag = agent.get("diagnosis") or {}
        if diag:
            diag_text = str(diag.get("diagnosis", "")).strip()
            if diag_text:
                # Clean up markdown code fences
                if diag_text.startswith("```markdown"):
                    diag_text = (
                        diag_text.replace("```markdown", "").replace("```", "").strip()
                    )

                # Extract just the executive summary or first paragraph
                lines = diag_text.split("\n")
                summary_lines = []
                in_summary = False

                for line in lines:
                    if (
                        "executive summary" in line.lower()
                        or "## executive summary" in line.lower()
                    ):
                        in_summary = True
                        continue
                    if (
                        in_summary
                        and line.startswith("##")
                        and "executive" not in line.lower()
                    ):
                        break
                    if in_summary and line.strip():
                        summary_lines.append(line.strip())

                if summary_lines:
                    summary_text = " ".join(summary_lines)
                    console.print(
                        Panel.fit("Clinical Diagnosis Summary", style="bold cyan"),
                    )
                    console.print(f"[dim]{summary_text}[/dim]")
                else:
                    snippet = diag_text
                    console.print(Panel.fit("Diagnosis Brief", style="bold cyan"))
                    console.print(f"[dim]{snippet}[/dim]")
                console.print("")

        ver = agent.get("verification_report") or {}
        if ver:
            verdict = str(ver.get("verdict", "pass"))
            console.print(
                Panel.fit(f"Verification verdict: {verdict}", style="bold yellow"),
            )

    if args.mode == "both":
        console.print(Panel.fit("Deterministic Assessment", style="bold green"))
        _print_assessment(result.get("deterministic", {}))
        console.print(Panel.fit("Collaborative Agent Output", style="bold blue"))
        _print_agent(result.get("agent", {}))
        if args.write_report:
            _write_report_md(result, args.report_dir, title_name)
        return

    if args.mode == "deterministic":
        _print_assessment(result)
        if args.write_report:
            _write_report_md({"deterministic": result}, args.report_dir, title_name)
        return

    _print_agent(result)
    if args.write_report:
        _write_report_md({"agent": result}, args.report_dir, title_name)


def _write_report_md(  # noqa: C901, PLR0915
    result: dict,
    report_dir: str | None = None,
    name: str | None = None,
) -> None:
    try:
        base_dir = (
            Path(report_dir)
            if report_dir
            else Path(__file__).resolve().parents[1] / "reports"
        )
        base_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "_".join(str(name or "uti_case").lower().split())
        ts = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
        path = base_dir / f"{safe_name}_{ts}.md"

        def _summarize_agent(agent_out: dict) -> list[str]:  # noqa: C901, PLR0912
            md: list[str] = []
            dx = agent_out.get("diagnosis", {}) or {}
            assessment = agent_out.get("assessment", {}) or {}
            safety = agent_out.get("safety_validation", {}) or {}
            reasoning = agent_out.get("clinical_reasoning", {}) or {}
            follow = agent_out.get("follow_up_details", {}) or {}
            consensus = agent_out.get("consensus_recommendation", "-")
            md.append("## Summary")
            decision = str(assessment.get("decision", "-"))
            if decision.startswith(("Decision.", "ApprovalDecision.", "RiskLevel.")):
                decision = decision.split(".", 1)[1] if "." in decision else decision
            md.append(f"Decision: {decision}")
            md.append(f"Consensus: {consensus}")
            # Include prescriber sign-off flag if available
            try:
                signoff_required = bool(
                    agent_out.get("prescriber_signoff_required", False),
                )
                md.append(
                    f"Prescriber Sign-off Required: {'Yes' if signoff_required else 'No'}",
                )
            except Exception:  # noqa: S110
                pass  # Best effort safety formatting
            if safety.get("approval_recommendation"):
                approval = str(safety.get("approval_recommendation", ""))
                risk_level = str(safety.get("risk_level", "-"))
                if approval.startswith("ApprovalDecision."):
                    approval = approval.replace("ApprovalDecision.", "")
                if risk_level.startswith("RiskLevel."):
                    risk_level = risk_level.replace("RiskLevel.", "")
                md.append(f"Safety: {approval} ({risk_level})")
            if isinstance(reasoning.get("reasoning"), list) and reasoning.get(
                "reasoning",
            ):
                md.append("")
                md.append("### Key Reasoning")
                for r in reasoning.get("reasoning", []):
                    md.append(f"- {r}")
            if isinstance(assessment.get("rationale"), list) and assessment.get(
                "rationale",
            ):
                md.append("")
                md.append("### Algorithm Rationale")
                for r in assessment.get("rationale", []):
                    md.append(f"- {r}")
            if isinstance(follow.get("monitoring_checklist"), list) and follow.get(
                "monitoring_checklist",
            ):
                md.append("")
                md.append("### Monitoring & Follow-up")
                for m in follow.get("monitoring_checklist", []):
                    md.append(f"- {m}")
            if isinstance(dx.get("diagnosis"), str) and dx.get("diagnosis"):
                md.append("")
                md.append("### Diagnosis Brief")
                diagnosis_text = dx.get("diagnosis")
                # Clean up markdown code fences if present
                if diagnosis_text.startswith("```markdown"):
                    diagnosis_text = (
                        diagnosis_text.replace("```markdown", "")
                        .replace("```", "")
                        .strip()
                    )
                md.append(diagnosis_text)
            return md

        md_lines: list[str] = []
        title = name or "UTI CLI Case"
        md_lines.append(f"# Plan Summary — {title}")
        md_lines.append("")
        if "agent" in result and isinstance(result["agent"], dict):
            md_lines.extend(_summarize_agent(result["agent"]))
        if "deterministic" in result and isinstance(result["deterministic"], dict):
            md_lines.append("")
            md_lines.append("## Deterministic Assessment")
            det = result["deterministic"]
            det_decision = str(det.get("decision", "-"))
            if det_decision.startswith("Decision."):
                det_decision = det_decision.replace("Decision.", "")
            md_lines.append(f"Decision: {det_decision}")
            if isinstance(det.get("rationale"), list) and det.get("rationale"):
                md_lines.append("Rationale:")
                for r in det.get("rationale", []):
                    md_lines.append(f"- {r}")
        path.write_text("\n".join(md_lines))
        console.print(f"[green]Saved report:[/green] {path}")
    except Exception as e:
        console.print(f"[yellow]Failed to write report: {e!s}[/yellow]")


if __name__ == "__main__":
    main()
