"""PROTOTYPE — trinity stats (DESIGN.md roadmap).

Read-only over boxes + timeline. Per debate 5.9 / suggestions, the
celebration view stays hidden until the operator has rooted at least
one box — streaks do not teach scanning.
"""
from __future__ import annotations

import sqlite3

from pydantic import BaseModel


class Stats(BaseModel):
    rooted: int
    active: int
    abandoned: int
    timeline_events: int
    techniques: list[str]
    streak: int
    ready: bool  # False until first root


def compute_stats(conn: sqlite3.Connection) -> Stats:
    def count(status: str) -> int:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM boxes WHERE status = ?", (status,)
        ).fetchone()
        return int(row["n"])

    rooted = count("rooted")
    titles = [
        row["summary"]
        for row in conn.execute(
            "SELECT DISTINCT summary FROM timeline WHERE event_type = 'match' ORDER BY id"
        ).fetchall()
    ]
    events = conn.execute("SELECT COUNT(*) AS n FROM timeline").fetchone()["n"]

    # Streak: newest boxes first (updated_at), count consecutive rooted.
    rows = conn.execute(
        "SELECT status FROM boxes ORDER BY updated_at DESC, id DESC"
    ).fetchall()
    streak = 0
    for row in rows:
        if row["status"] == "rooted":
            streak += 1
        else:
            break

    return Stats(
        rooted=rooted,
        active=count("active"),
        abandoned=count("abandoned"),
        timeline_events=int(events),
        techniques=titles[:20],
        streak=streak,
        ready=rooted > 0,
    )
