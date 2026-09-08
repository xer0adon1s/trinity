"""Recap: a clean, non-gamified end-of-box summary for the operator's
own record. Explicitly NOT the vetoed achievements/stars system (see
docs/FEATURES_BACKLOG.md's "Achievements / gamification system" entry
-- no points, no streaks, no unlockable badges). This is closer to a
study log: what techniques were used, how long each phase took, where
the operator got stuck and how they got unstuck -- derived entirely
from data that already exists in the timeline (report/data.py's
ReportData), never a new tracked/scored dimension.

Distinct from report/render.py's educational/professional reports:
those are written to be shared/handed to someone else (a mentor, a
client). Recap is written for the operator themselves, immediately
after finishing (or pausing) a box -- shorter, more personal, no
mode-switch (same shape regardless of box.mode).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from pydantic import BaseModel

from trinity.report.data import ReportData, gather_report_data

# Same ordering as coach.py's _PHASE_ORDER -- kept independent (not
# imported) since recap only needs display order, not ranking logic.
_PHASE_DISPLAY_ORDER = ["recon", "enum", "foothold", "privesc", "post"]
_PHASE_LABELS = {
    "recon": "Recon", "enum": "Enumeration", "foothold": "Foothold",
    "privesc": "Privilege escalation", "post": "Post-exploitation",
}


class PhaseSpan(BaseModel):
    phase: str
    first_seen: str
    last_seen: str


class RecapData(BaseModel):
    box_name: str
    target: str | None
    shell_level: str | None
    difficulty: str | None
    phases: list[PhaseSpan]
    techniques: list[str]          # distinct KB/searchsploit match titles
    loot_count: int
    nudge_count: int               # rabbit-hole nudges shown -- honest
                                    # "where you got stuck" signal, not
                                    # hidden or held against the operator
    total_events: int
    duration_note: str | None      # human-readable span, best-effort


def _parse_ts(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def build_recap(conn: sqlite3.Connection, box_id: int) -> RecapData:
    """Assembles a RecapData purely from ReportData -- no new schema,
    no new tracked state. If Assimilator/confidence work ever wants a
    "techniques you've now seen across boxes" cross-box view, that is
    the FEATURES_BACKLOG.md-parked "technique journal" idea and stays
    out of scope here (this function is single-box only, by design)."""
    data: ReportData = gather_report_data(conn, box_id)

    phase_spans: dict[str, list[str]] = {}
    for event in data.events:
        if event.phase:
            phase_spans.setdefault(event.phase, []).append(event.ts)

    phases = [
        PhaseSpan(phase=p, first_seen=min(ts_list), last_seen=max(ts_list))
        for p, ts_list in phase_spans.items()
        if ts_list
    ]
    phases.sort(key=lambda ps: _PHASE_DISPLAY_ORDER.index(ps.phase)
                if ps.phase in _PHASE_DISPLAY_ORDER else 99)

    techniques: list[str] = []
    for event in data.events:
        if event.event_type == "match" and event.summary:
            # summary is "{label} matched: {title}" -- keep just the
            # technique title, deduped, in first-seen order.
            title = event.summary.split("matched:", 1)[-1].strip()
            if title and title not in techniques:
                techniques.append(title)

    nudge_count = sum(1 for e in data.events if e.event_type == "nudge")

    all_ts = [t for e in data.events if (t := _parse_ts(e.ts)) is not None]
    duration_note = None
    if len(all_ts) >= 2:
        span = max(all_ts) - min(all_ts)
        hours = span.total_seconds() / 3600
        if hours < 1:
            duration_note = f"~{int(span.total_seconds() / 60)} minutes"
        else:
            duration_note = f"~{hours:.1f} hours"

    return RecapData(
        box_name=data.box.name,
        target=data.box.target,
        shell_level=data.box.shell_level,
        difficulty=data.box.difficulty,
        phases=phases,
        techniques=techniques,
        loot_count=len(data.loot),
        nudge_count=nudge_count,
        total_events=len(data.events),
        duration_note=duration_note,
    )


def render_recap(recap: RecapData) -> str:
    """Plain-text rendering for `trinity recap`. Deliberately short --
    this is a glance-at-it summary, not a report (see module
    docstring)."""
    lines: list[str] = []
    header = f"Recap — {recap.box_name}"
    if recap.target:
        header += f" ({recap.target})"
    lines.append(header)
    lines.append("=" * len(header))

    status = "rooted" if recap.shell_level == "root" else \
        ("user shell" if recap.shell_level == "user" else "in progress")
    lines.append(f"Status: {status}" + (f" · {recap.difficulty}" if recap.difficulty else ""))
    if recap.duration_note:
        lines.append(f"Time span: {recap.duration_note}")
    lines.append("")

    if recap.phases:
        lines.append("Phases touched:")
        for ps in recap.phases:
            label = _PHASE_LABELS.get(ps.phase, ps.phase)
            lines.append(f"  - {label}")
        lines.append("")

    if recap.techniques:
        lines.append(f"Techniques encountered ({len(recap.techniques)}):")
        for t in recap.techniques:
            lines.append(f"  - {t}")
        lines.append("")

    if recap.loot_count:
        lines.append(f"Loot recorded: {recap.loot_count} item(s) (see `trinity loot list`)")

    if recap.nudge_count:
        lines.append(
            f"Got stuck and got a nudge {recap.nudge_count} time(s) — "
            "that's normal, not a black mark (see docs/RABBIT_HOLE_DETECTION.md)."
        )

    lines.append("")
    lines.append(f"Total logged events: {recap.total_events}")
    return "\n".join(lines)
