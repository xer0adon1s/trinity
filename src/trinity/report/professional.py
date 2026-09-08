"""Professional-mode report: a client-ready pentest notebook/deliverable.

PROTOTYPE growth (Alexander overrode the 1.10 freeze). Same timeline
spine as educational mode — mode is still a lens. This template adds
document control, a written exec summary, scope/limitations, ATT&CK
draft tags, remediation drafts, evidence, and a methodology appendix.
"""
from __future__ import annotations

from trinity.report.attack import map_attack
from trinity.report.data import ReportData
from trinity.report.remediation import draft_remediation

_SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]


def _eng(data: ReportData, key: str, default: str = "*[fill in]*") -> str:
    eng = data.engagement or {}
    value = eng.get(key)
    return value if value else default


def generate_professional_report(data: ReportData) -> str:
    box = data.box
    classification = _eng(data, "classification", "TLP:CLEAR")
    version = _eng(data, "report_version", "0.1-draft")
    distribution = _eng(data, "distribution", "Authorized recipient only")
    lines: list[str] = []

    lines.append(f"# Penetration Test Report — {box.name}")
    lines.append("")
    lines.append(f"**Classification:** {classification}  ·  **Version:** {version}  ·  **Generated:** {data.generated_at}")
    lines.append("")
    lines.append(f"*Distribution: {distribution}*")
    lines.append("")

    lines.append("## Document Control")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|---|---|")
    lines.append(f"| Document status | Draft — tester must verify before delivery |")
    lines.append(f"| Classification | {classification} |")
    lines.append(f"| Version | {version} |")
    lines.append(f"| Distribution | {distribution} |")
    if data.ai_assisted_steps:
        lines.append(
            f"| **AI-assisted steps** | **{len(data.ai_assisted_steps)} milestone(s) on this "
            "engagement were performed via Trinity's Show Me Mode (an AI agent acting on the "
            "tester's behalf, not manual tester action) — see Scope, Limitations, and Assumptions.** |"
        )
    lines.append("")

    lines.append("## Contents")
    lines.append("")
    lines.append("1. Engagement Summary")
    lines.append("2. Executive Summary")
    lines.append("3. Scope, Limitations, and Assumptions")
    lines.append("4. Findings")
    lines.append("5. Recovered Evidence")
    lines.append("6. Methodology / Testing Timeline")
    lines.append("7. Tools Observed")
    lines.append("")

    lines.append("## Engagement Summary")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| Target | `{box.target or 'Not recorded'}` |")
    lines.append(f"| Platform | {box.platform or 'Not recorded'} |")
    if box.difficulty:
        lines.append(f"| Listed difficulty | {box.difficulty} |")
    if box.shell_level:
        lines.append(f"| Highest declared access | {box.shell_level} shell |")
    lines.append(f"| Client | {_eng(data, 'client_name')} |")
    lines.append(f"| Tester | {_eng(data, 'tester_name')} |")
    lines.append(f"| Scope | {_eng(data, 'scope')} |")
    lines.append(f"| Authorization reference | {_eng(data, 'authorization_ref')} |")
    lines.append(f"| Test start | {_eng(data, 'start_date')} |")
    lines.append(f"| Test end | {_eng(data, 'end_date')} |")
    notes = (data.engagement or {}).get("notes")
    if notes:
        lines.append(f"| Notes | {notes} |")
    lines.append("")
    lines.append(
        "*Fields marked [fill in] were not set on this box. Run "
        "`trinity engagement-set` before generating a final deliverable.*"
    )
    lines.append("")

    by_sev = data.findings_by_severity
    counts = {sev: len(evs) for sev, evs in by_sev.items()}
    total = sum(counts.values())

    lines.append("## Executive Summary")
    lines.append("")
    if total == 0 and not data.loot:
        lines.append(
            "No matched findings or recovered evidence were recorded for this "
            "engagement. The timeline appendix lists activity performed."
        )
        lines.append("")
    else:
        risk = "critical" if counts.get("critical") else "high" if counts.get("high") else "limited"
        access = (
            f" The tester declared a {box.shell_level} shell during the engagement."
            if box.shell_level else ""
        )
        flags = sum(1 for item in data.loot if item.kind == "flag")
        loot_bit = f" {len(data.loot)} evidence item(s) were recorded" + (f", including {flags} flag(s)." if flags else ".")
        lines.append(
            f"This assessment identified **{total}** matched finding(s) against "
            f"`{box.target or box.name}`. Overall residual risk on the recorded "
            f"evidence is **{risk}**.{access}{loot_bit if data.loot else ''}"
        )
        lines.append("")
        if total:
            lines.append("Finding counts by severity:")
            lines.append("")
            for sev in _SEVERITY_ORDER:
                if counts.get(sev):
                    lines.append(f"- **{counts[sev]}** {sev.capitalize()}")
            lines.append("")
        top = by_sev.get("critical") or by_sev.get("high") or []
        if top:
            lines.append("Highest-severity items:")
            lines.append("")
            for event in top[:3]:
                lines.append(f"- {event.summary}")
            lines.append("")

    lines.append("## Scope, Limitations, and Assumptions")
    lines.append("")
    lines.append(f"- **In-scope target:** `{box.target or 'not recorded'}`")
    lines.append(f"- **Stated scope:** {_eng(data, 'scope')}")
    lines.append(f"- **Authorization:** {_eng(data, 'authorization_ref')}")
    lines.append(
        "- **Limitations:** Trinity records tester activity; it does not "
        "autonomously execute exploits by default or certify completeness. "
        "Findings are as-observed from parsed tool output and local matching."
    )
    if data.ai_assisted_steps:
        step_list = "; ".join(
            f"{s.milestone} via {s.agent_used or 'an agent'} ({s.outcome})"
            for s in data.ai_assisted_steps
        )
        lines.append(
            f"- **AI-assisted steps (Show Me Mode):** {len(data.ai_assisted_steps)} "
            f"milestone(s) on this engagement were performed by Trinity's own AI "
            f"agent, at the tester's explicit, disclosed request, NOT by the tester "
            f"manually — {step_list}. These specific milestones should not be read "
            f"as demonstrating the tester's own exploitation skill for those steps; "
            f"everything else in this report reflects tester-performed activity."
        )
    lines.append(
        "- **Assumptions:** The tester operated only against the authorized "
        "target. Tool output files are assumed to be from this engagement."
    )
    lines.append(
        "- **ATT&CK tags** below are a local draft heuristic, not a "
        "validated mapping."
    )
    lines.append("")

    if not data.events and not data.loot:
        lines.append("## Findings")
        lines.append("")
        lines.append("No findings recorded for this engagement.")
        lines.append("")
        lines.extend(_footer())
        return "\n".join(lines)

    lines.append("## Findings")
    lines.append("")
    finding_number = 1
    for sev in _SEVERITY_ORDER:
        for event in by_sev.get(sev, []):
            fid = f"F-{finding_number:02d}"
            attack = map_attack(f"{event.summary} {event.detail or ''}")
            lines.append(f"### {fid}: {event.summary}")
            lines.append("")
            lines.append(f"**Severity:** {sev.capitalize()}")
            lines.append("")
            lines.append(f"**Affected asset:** `{box.target or 'not recorded'}`")
            lines.append("")
            lines.append("**Status:** Open (draft)")
            lines.append("")
            if attack:
                tags = ", ".join(f"{tid} ({name})" for tid, name in attack)
                lines.append(f"**ATT&CK (draft):** {tags}")
                lines.append("")
            if event.detail:
                lines.append("**Details:**")
                lines.append("")
                lines.append(event.detail)
                lines.append("")
            lines.append("**Recommendation:**")
            lines.append("")
            lines.append(draft_remediation(event.summary, event.detail))
            lines.append("")
            finding_number += 1

    if finding_number == 1:
        lines.append("No severity-tagged matches were recorded.")
        lines.append("")

    lines.append("## Recovered Evidence")
    lines.append("")
    if data.loot:
        lines.append("| Kind | Value | Context |")
        lines.append("|---|---|---|")
        for item in data.loot:
            lines.append(f"| {item.kind} | `{item.value}` | {item.note or ''} |")
        lines.append("")
    else:
        lines.append("No evidence items were recorded (`trinity loot add`).")
        lines.append("")

    lines.append("## Methodology / Testing Timeline")
    lines.append("")
    lines.append(
        "Activities recorded during this engagement, in chronological order. "
        "Teaching-oriented events (hints, unlocks) are included when present "
        "so the appendix is honest about how the test was conducted."
    )
    lines.append("")
    lines.append("| Time | Phase | Activity |")
    lines.append("|---|---|---|")
    for event in data.events:
        phase = event.phase or "-"
        lines.append(f"| {event.ts} | {phase} | {event.summary} |")
    lines.append("")

    scans = [e.summary for e in data.events if e.event_type == "scan"]
    lines.append("## Tools Observed")
    lines.append("")
    if scans:
        for summary in scans:
            lines.append(f"- {summary}")
        lines.append("")
    else:
        lines.append("No scan events were recorded.")
        lines.append("")

    lines.extend(_footer())
    return "\n".join(lines)


def _footer() -> list[str]:
    return [
        "---",
        "",
        "*This report was assembled with assistance from Trinity, a local "
        "recon-assist tool. All findings, ATT&CK tags, and remediation "
        "text are drafts and must be independently verified before "
        "delivery to a client. Practice labs and authorized work only.*",
        "",
    ]
