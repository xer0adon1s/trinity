"""PROTOTYPE — rabbit-hole detection (docs/RABBIT_HOLE_DETECTION.md).

Read-only queries over timeline / suggestions / hint_state. Advisory
only — never blocks, never auto-redirects. Thresholds are arguments
because the design doc left "how long is stalled?" open.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from pydantic import BaseModel

from trinity.coach import get_recommendation


class RabbitHoleSignal(BaseModel):
    kind: str
    message: str
    alternative_command: str | None = None


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt)
        except ValueError:
            continue
    return None


def _last_progress_ts(conn: sqlite3.Connection, box_id: int) -> datetime | None:
    row = conn.execute(
        "SELECT ts FROM timeline WHERE box_id = ? AND event_type IN ('finding', 'match', 'loot', 'milestone') "
        "ORDER BY ts DESC, id DESC LIMIT 1",
        (box_id,),
    ).fetchone()
    return _parse_ts(row["ts"]) if row else None


def _phase_dominance(conn: sqlite3.Connection, box_id: int, *, min_events: int, ratio: float) -> str | None:
    rows = conn.execute(
        "SELECT phase FROM timeline WHERE box_id = ? AND phase IS NOT NULL ORDER BY id DESC LIMIT 20",
        (box_id,),
    ).fetchall()
    phases = [r["phase"] for r in rows]
    if len(phases) < min_events:
        return None
    counts: dict[str, int] = {}
    for phase in phases:
        counts[phase] = counts.get(phase, 0) + 1
    top_phase, top_n = max(counts.items(), key=lambda kv: kv[1])
    if top_n / len(phases) >= ratio and len(counts) > 1:
        return top_phase
    if top_n / len(phases) >= ratio:
        return top_phase
    return None


def _untouched_alternative(conn: sqlite3.Connection, box_id: int, current_command: str | None) -> str | None:
    rows = conn.execute(
        "SELECT command FROM suggestions WHERE box_id = ? AND accepted = 0 ORDER BY id",
        (box_id,),
    ).fetchall()
    for row in rows:
        if row["command"] != current_command:
            return row["command"]
    return None


def detect_rabbit_hole(
    conn: sqlite3.Connection,
    box_id: int,
    *,
    finding_gap_minutes: int = 20,
    dominate_ratio: float = 0.8,
    min_events: int = 6,
    maxed_hints: int = 2,
) -> RabbitHoleSignal | None:
    rec = get_recommendation(conn, box_id)
    current = rec.top.command if rec else None
    alternative = _untouched_alternative(conn, box_id, current)

    last_progress = _last_progress_ts(conn, box_id)
    if last_progress is not None:
        # Compare against the newest timeline row's clock if "now" is
        # not useful in unit tests — use max(now, last event) so a
        # fixture with old timestamps still triggers.
        newest = conn.execute(
            "SELECT ts FROM timeline WHERE box_id = ? ORDER BY ts DESC LIMIT 1",
            (box_id,),
        ).fetchone()
        newest_ts = _parse_ts(newest["ts"]) if newest else None
        clock = newest_ts or datetime.utcnow()
        if clock - last_progress >= timedelta(minutes=finding_gap_minutes) and rec is not None:
            return RabbitHoleSignal(
                kind="stalled_progress",
                message=(
                    f"It's been a while since anything new landed, and the "
                    f"recommendation is still `{rec.top.command}`. That's a "
                    f"very normal rabbit-hole shape — not a sign you're bad "
                    f"at this. Time spent on a dead end is how the mental "
                    f"toolbox gets built."
                ),
                alternative_command=alternative,
            )

    maxed = conn.execute(
        "SELECT COUNT(*) AS n FROM hint_state WHERE box_id = ? AND level >= 3",
        (box_id,),
    ).fetchone()["n"]
    if maxed >= maxed_hints and rec is not None:
        return RabbitHoleSignal(
            kind="hint_ladder",
            message=(
                "You've taken the full answer on a few different steps "
                "without a new finding landing afterward. That's a cue to "
                "change the question, not to push harder on the same door."
            ),
            alternative_command=alternative,
        )

    dominant = _phase_dominance(conn, box_id, min_events=min_events, ratio=dominate_ratio)
    if dominant and alternative:
        return RabbitHoleSignal(
            kind="phase_dominance",
            message=(
                f"Most of the recent timeline is still in `{dominant}` while "
                f"other leads sit untouched. The classic trap is deciding "
                f"one port *must* be the answer. Parking it for a bit is allowed."
            ),
            alternative_command=alternative,
        )

    return None


def log_nudge(conn: sqlite3.Connection, box_id: int, signal: RabbitHoleSignal) -> None:
    from trinity.timeline import log_event

    log_event(
        conn, box_id, "nudge",
        f"rabbit-hole note ({signal.kind})",
        detail=signal.message,
        phase=None,
    )


def recent_nudge_count(conn: sqlite3.Connection, box_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM timeline WHERE box_id = ? AND event_type = 'nudge'",
        (box_id,),
    ).fetchone()
    return int(row["n"])
