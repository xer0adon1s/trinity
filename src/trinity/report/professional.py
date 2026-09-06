"""Professional-mode report: a client-ready pentest deliverable. Same
timeline data as educational mode, formatted completely differently —
grouped by severity, stripped of narrative/teaching tone, with proper
engagement front matter (client, scope, authorization, dates). This is
meant to be handed to a client, not read as a story.
"""
from __future__ import annotations

from trinity.report.data import ReportData

_SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]


def generate_professional_report(data: ReportData) -> str:
    """Render a Markdown pentest report: engagement summary, findings
    grouped by severity (most severe first), and a methodology/timeline
    appendix. Every finding traces back to the same shared timeline the
    educational report reads — this mode only changes the presentation."""
    box = data.box
    lines: list[str] = []

    lines.append(f"# Penetration Test Report — {box.name}")
    lines.append("")
    lines.append(f"*Generated {data.generated_at}*")
    lines.append("")

    lines.append("## Engagement Summary")
    lines.append("")
    eng = data.engagement or {}
    lines.append(f"| Field | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Target | `{box.target or 'Not recorded'}` |")
    lines.append(f"| Platform | {box.platform or 'Not recorded'} |")
    lines.append(f"| Client | {eng.get('client_name') or '*[fill in]*'} |")
    lines.append(f"| Tester | {eng.get('tester_name') or '*[fill in]*'} |")
    lines.append(f"| Scope | {eng.get('scope') or '*[fill in]*'} |")
    lines.append(f"| Authorization reference | {eng.get('authorization_ref') or '*[fill in]*'} |")
    lines.append(f"| Test start | {eng.get('start_date') or '*[fill in]*'} |")
    lines.append(f"| Test end | {eng.get('end_date') or '*[fill in]*'} |")
    lines.append("")
    lines.append(
        "*Fields marked [fill in] were not set on this box. Run "
        "`trinity engagement-set` before generating a final deliverable.*"
    )
    lines.append("")

    if not data.events:
        lines.append("## Findings")
        lines.append("")
        lines.append("No findings recorded for this engagement.")
        return "\n".join(lines)

    lines.append("## Executive Summary")
    lines.append("")
    by_sev = data.findings_by_severity
    counts = {sev: len(evs) for sev, evs in by_sev.items()}
    total = sum(counts.values())
    lines.append(f"This assessment identified **{total}** finding(s) across the target scope:")
    lines.append("")
    for sev in _SEVERITY_ORDER:
        if counts.get(sev):
            lines.append(f"- **{counts[sev]}** {sev.capitalize()}")
    lines.append("")

    lines.append("## Findings")
    lines.append("")
    finding_number = 1
    for sev in _SEVERITY_ORDER:
        events = by_sev.get(sev, [])
        if not events:
            continue

        for event in events:
            lines.append(f"### Finding {finding_number}: {event.summary}")
            lines.append("")
            lines.append(f"**Severity:** {sev.capitalize()}")
            lines.append("")
            if event.detail:
                lines.append("**Details:**")
                lines.append("")
                lines.append(event.detail)
                lines.append("")
            lines.append("**Recommendation:** *[tester to fill in remediation guidance]*")
            lines.append("")
            finding_number += 1

    lines.append("## Methodology / Testing Timeline")
    lines.append("")
    lines.append(
        "The following activities were performed during this engagement, in "
        "chronological order:"
    )
    lines.append("")
    lines.append("| Time | Phase | Activity |")
    lines.append("|---|---|---|")
    for event in data.events:
        phase = event.phase or "-"
        lines.append(f"| {event.ts} | {phase} | {event.summary} |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "*This report was assembled with assistance from Trinity, a local "
        "recon-assist tool. All findings should be independently verified "
        "before delivery to a client.*"
    )

    return "\n".join(lines)
