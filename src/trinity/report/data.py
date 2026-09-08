"""Shared data gathering for both report modes. One function assembles
everything a report might need from a box's timeline + related tables;
the two report generators (educational.py, professional.py) format the
same ReportData differently. Neither generator queries the DB directly —
this is the single source of truth for "what happened on this box."
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from pydantic import BaseModel

from trinity.boxes import Box, get_box
from trinity.loot import LootItem, list_loot
from trinity.timeline import get_timeline

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, None: 5}


class TimelineEvent(BaseModel):
    ts: str
    phase: str | None = None
    event_type: str
    summary: str
    detail: str | None = None
    severity: str | None = None


class AiAssistedStep(BaseModel):
    """One Show Me Mode run that produced real progress on this box.
    Populated from show_me_runs (src/trinity/show_me.py), independent
    of individual timeline rows -- this is the authoritative,
    non-suppressible disclosure surface docs/SHOW_ME_MODE.md §7
    requires. Whenever this list is non-empty, BOTH report renderers
    must show a disclosure block; neither has a code path that omits
    it."""
    milestone: str
    agent_used: str | None
    outcome: str
    started_at: str


class ReportData(BaseModel):
    box: Box
    events: list[TimelineEvent]
    engagement: dict | None = None
    loot: list[LootItem] = []
    ai_assisted_steps: list[AiAssistedStep] = []
    generated_at: str

    @property
    def findings_by_severity(self) -> dict[str, list[TimelineEvent]]:
        """Match/finding-type events grouped by severity, most severe
        first — the shape a professional report wants."""
        grouped: dict[str, list[TimelineEvent]] = {
            "critical": [], "high": [], "medium": [], "low": [], "info": [],
        }
        for event in self.events:
            if event.event_type == "match" and event.severity in grouped:
                grouped[event.severity].append(event)
        return grouped

    @property
    def phases_covered(self) -> list[str]:
        seen: list[str] = []
        for event in self.events:
            if event.phase and event.phase not in seen:
                seen.append(event.phase)
        return seen


def gather_report_data(conn: sqlite3.Connection, box_id: int) -> ReportData:
    """Pull everything needed to render either report from one box's
    timeline + engagement metadata. Raises ValueError if the box doesn't
    exist — callers should have already resolved the box name to an id."""
    box = get_box(conn, box_id)
    if box is None:
        raise ValueError(f"No box with id {box_id}")

    rows = get_timeline(conn, box_id)
    events = [
        TimelineEvent(
            ts=row["ts"], phase=row["phase"], event_type=row["event_type"],
            summary=row["summary"], detail=row["detail"], severity=row["severity"],
        )
        for row in rows
    ]

    engagement_row = conn.execute(
        "SELECT * FROM engagement_meta WHERE box_id = ?", (box_id,)
    ).fetchone()
    engagement = dict(engagement_row) if engagement_row else None

    show_me_rows = conn.execute(
        "SELECT * FROM show_me_runs WHERE box_id = ? AND outcome IN ('succeeded', 'already_known') "
        "ORDER BY id",
        (box_id,),
    ).fetchall()
    ai_assisted_steps = [
        AiAssistedStep(
            milestone=row["milestone"], agent_used=row["agent_used"],
            outcome=row["outcome"], started_at=row["started_at"],
        )
        for row in show_me_rows
    ]

    return ReportData(
        box=box,
        events=events,
        engagement=engagement,
        ai_assisted_steps=ai_assisted_steps,
        loot=list_loot(conn, box_id),
        generated_at=datetime.now().isoformat(timespec="seconds"),
    )
