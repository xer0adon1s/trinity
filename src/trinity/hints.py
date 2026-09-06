"""Instructor Mode's graduated hint ladder: nudge -> stronger nudge ->
full answer, for TECHNIQUE questions ("what should I be thinking about
here") as opposed to command-syntax questions (which `explain.py`
already covers well as a flat cache). See docs/INSTRUCTOR_MODE.md.
"""
from __future__ import annotations

import sqlite3

from pydantic import BaseModel


class Hint(BaseModel):
    level: int  # 1, 2, or 3
    text: str


def get_hint_level(conn: sqlite3.Connection, box_id: int, suggestion_id: int) -> int:
    row = conn.execute(
        "SELECT level FROM hint_state WHERE box_id = ? AND suggestion_id = ?",
        (box_id, suggestion_id),
    ).fetchone()
    return row["level"] if row else 0


def _advance_hint_level(conn: sqlite3.Connection, box_id: int, suggestion_id: int) -> int:
    """Bumps this suggestion's hint level by one (capped at 3) and
    returns the new level. A fresh suggestion (never hinted on before)
    starts at 0 and this call brings it to 1 -- every new stuck point
    starts back at a nudge, never inherits escalation from an
    unrelated earlier suggestion."""
    current = get_hint_level(conn, box_id, suggestion_id)
    new_level = min(current + 1, 3)
    conn.execute(
        "INSERT INTO hint_state (box_id, suggestion_id, level) VALUES (?, ?, ?) "
        "ON CONFLICT(box_id, suggestion_id) DO UPDATE SET level = excluded.level, "
        "updated_at = CURRENT_TIMESTAMP",
        (box_id, suggestion_id, new_level),
    )
    conn.commit()
    return new_level


def build_hint(level: int, phase: str, nudge: str, rationale: str, command: str) -> str:
    """Builds the hint text for a given ladder level. Level 1 is purely
    Socratic (no finding-specific content at all). Level 2 uses
    `nudge` -- a tool-name-free, answer-free description of the area
    to look at, written specifically for this purpose (see
    suggest/engine.py's Suggestion.nudge) -- NEVER `rationale`, which
    routinely names the exact tool/technique and would leak the answer
    one level early. Level 3 is the full answer (rationale + the exact
    command)."""
    if level <= 1:
        return (
            f"You're at the {phase} phase. Before I just tell you what to do — "
            "look at what you've found so far. What's unusual, unexpected, or "
            "different about it compared to a typical box? What would you check first?"
        )
    if level == 2:
        nudge_text = nudge or (
            "Think about what you'd normally check first for a service like this, "
            "before assuming you need something more advanced."
        )
        return f"Here's a stronger nudge: {nudge_text}"
    return (
        f"Here's the answer: {rationale}\n\n"
        f"The command to run: {command}\n\n"
        "(Run `trinity explain \"<command>\"` if you want the flags broken down too.)"
    )


def get_hint(conn: sqlite3.Connection, box_id: int, suggestion_id: int, phase: str,
             nudge: str, rationale: str, command: str) -> Hint:
    """The main entry point: advances this suggestion's hint level by
    one and returns the hint text for the new level. Calling this
    repeatedly on the same suggestion climbs the ladder; a different
    suggestion_id always starts fresh at level 1."""
    level = _advance_hint_level(conn, box_id, suggestion_id)
    return Hint(level=level, text=build_hint(level, phase, nudge, rationale, command))
