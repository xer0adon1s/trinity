"""The timeline: one shared, chronological event log per box that both
report modes read from. Every part of Trinity that does something
notable — a scan, a match, a suggestion, an explanation, a manual
note — writes here through log_event(). Report generation never writes
to this table, only reads it; mode only changes how the read is
formatted, never what gets recorded.
"""
from __future__ import annotations

import sqlite3


def log_event(
    conn: sqlite3.Connection,
    box_id: int,
    event_type: str,
    summary: str,
    *,
    phase: str | None = None,
    detail: str | None = None,
    severity: str | None = None,
    ref_id: int | None = None,
) -> int:
    """Append one event to a box's timeline. Returns the new row id."""
    cursor = conn.execute(
        """
        INSERT INTO timeline (box_id, phase, event_type, summary, detail, severity, ref_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (box_id, phase, event_type, summary, detail, severity, ref_id),
    )
    conn.commit()
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def get_timeline(conn: sqlite3.Connection, box_id: int) -> list[sqlite3.Row]:
    """Fetch a box's full timeline in chronological order."""
    return conn.execute(
        "SELECT * FROM timeline WHERE box_id = ? ORDER BY ts ASC, id ASC",
        (box_id,),
    ).fetchall()
