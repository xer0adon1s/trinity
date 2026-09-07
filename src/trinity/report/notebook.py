"""PROTOTYPE — lab-notebook tear-out (Trinity_suggestions.md 2.7).

One-page markdown a beginner actually wants to keep: techniques,
loot, errors, commands. Registered on the report renderer seam.
Still local-file only.
"""
from __future__ import annotations

from trinity.report.data import ReportData


def generate_notebook_report(data: ReportData) -> str:
    box = data.box
    lines = [
        f"# Lab notebook — {box.name}",
        "",
        f"*Generated {data.generated_at}*",
        "",
    ]
    if box.difficulty:
        lines.append(f"Listed difficulty: {box.difficulty}")
        lines.append("")
    if box.shell_level:
        lines.append(f"Declared shell: {box.shell_level}")
        lines.append("")

    techniques = [e.summary for e in data.events if e.event_type == "match"]
    if techniques:
        lines.append("## Techniques that landed")
        lines.append("")
        for summary in techniques:
            lines.append(f"- {summary}")
        lines.append("")

    if data.loot:
        lines.append("## Loot")
        lines.append("")
        for item in data.loot:
            extra = f" ({item.note})" if item.note else ""
            lines.append(f"- {item.kind}: `{item.value}`{extra}")
        lines.append("")

    errors = [e for e in data.events if e.event_type == "explanation" and "diagnosed error" in e.summary]
    if errors:
        lines.append("## Errors you cached")
        lines.append("")
        for event in errors:
            lines.append(f"- {event.summary}")
        lines.append("")

    commands = [e.summary for e in data.events if e.event_type == "suggestion"]
    if commands:
        lines.append("## Commands Trinity suggested")
        lines.append("")
        for summary in commands:
            lines.append(f"- {summary}")
        lines.append("")

    if not techniques and not data.loot and not commands:
        lines.append("Nothing recorded yet.")
        lines.append("")

    lines.append("---")
    lines.append("Local file. Not a share-export. Not a writeup.")
    return "\n".join(lines)
