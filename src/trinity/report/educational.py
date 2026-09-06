"""Educational-mode report: a narrated walkthrough of the box, written to
teach — every scan, match, suggestion, and explanation given, told in
order, in plain language. This is what a beginner (the "10-year-old with
some computer experience" bar) should be able to read afterward and
actually understand not just what was found, but why each step happened.
"""
from __future__ import annotations

from trinity.report.data import ReportData

_EVENT_ICONS = {
    "scan": "🔍",
    "finding": "📋",
    "match": "💡",
    "suggestion": "➡️",
    "explanation": "📖",
    "note": "📝",
    "milestone": "🏁",
}

_SEVERITY_LABEL = {
    "critical": "**Critical** — this is a serious, likely-exploitable issue.",
    "high": "**High** — a strong lead, worth prioritizing.",
    "medium": "**Medium** — worth investigating, not urgent on its own.",
    "low": "**Low** — minor, unlikely to be the main path in.",
    "info": "Informational — good to know, not a vulnerability itself.",
}


def generate_educational_report(data: ReportData) -> str:
    """Render a Markdown walkthrough of everything that happened on this
    box, narrated in order. Every event in the shared timeline shows up
    here — this mode hides nothing, since the point is to teach the
    full path, dead ends included."""
    box = data.box
    lines: list[str] = []

    lines.append(f"# Walkthrough: {box.name}")
    lines.append("")
    lines.append(f"*Generated {data.generated_at} by Trinity (educational mode)*")
    lines.append("")
    if box.target:
        lines.append(f"**Target:** `{box.target}`" + (f"  ·  **Platform:** {box.platform}" if box.platform else ""))
        lines.append("")

    if not data.events:
        lines.append("Nothing's been logged for this box yet — run a scan and parse it "
                      "with Trinity to start building the walkthrough.")
        return "\n".join(lines)

    lines.append("## What happened, step by step")
    lines.append("")
    lines.append(
        "Everything below happened in the order it actually occurred while "
        "working this box — including things that didn't pan out. Seeing the "
        "dead ends is part of learning how real recon works: you don't know "
        "what matters until you check it."
    )
    lines.append("")

    current_phase = None
    for event in data.events:
        if event.phase and event.phase != current_phase:
            current_phase = event.phase
            lines.append(f"### Phase: {current_phase}")
            lines.append("")

        icon = _EVENT_ICONS.get(event.event_type, "•")
        lines.append(f"{icon} **{event.summary}**")

        if event.event_type == "match" and event.severity:
            lines.append(f"  {_SEVERITY_LABEL.get(event.severity, '')}")

        if event.detail:
            lines.append("")
            lines.append(f"  > {event.detail}")

        lines.append("")

    # Summary at the end: what was found, ranked by how serious it is —
    # gives a beginner a clear "so what actually mattered here" recap.
    by_sev = data.findings_by_severity
    notable = [(sev, evs) for sev, evs in by_sev.items() if evs]
    if notable:
        lines.append("## The short version — what actually mattered")
        lines.append("")
        lines.append(
            "If you only remember one thing from this box, it's this list, "
            "most important first:"
        )
        lines.append("")
        for sev, evs in notable:
            for event in evs:
                lines.append(f"- **[{sev.upper()}]** {event.summary}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "*This walkthrough was assembled automatically from Trinity's local "
        "knowledge base and (for the parts it recognized on its own) never "
        "touched an AI model or the internet — everything above came from "
        "matching real scan output against local reference data.*"
    )

    return "\n".join(lines)
