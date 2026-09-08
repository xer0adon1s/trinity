"""Update Framework, Part 2: the intake/review pipeline. Staging area
for any knowledge Trinity's own install generates (Agent Harness
answers, live-drafted Methods Index entries) that hasn't been vetted
by anyone but the one operator's one session. See
docs/UPDATE_FRAMEWORK.md.

Nothing here is trusted automatically. A candidate only becomes real,
live knowledge (readable by `trinity next`/`explain`/`error`/the
coach) once it's approved and copied into its real destination table
via the EXACT SAME insertion functions those tables already use
(`save_explanation`, `save_error_fix`, `kb.seed`-shaped inserts) --
this module is a staging area in front of already-tested write paths,
not a new one.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from pydantic import BaseModel

VALID_KINDS = {"explanation", "error_pattern", "kb_entry", "method"}
VALID_SOURCES = {"agent_harness", "methods_live_draft", "assimilator"}


class IntakeCandidate(BaseModel):
    id: int
    kind: str
    payload: dict
    source: str
    box_id: int | None
    status: str
    reviewer_note: str | None = None
    created_at: str | None = None
    reviewed_at: str | None = None


def submit_candidate(
    conn: sqlite3.Connection,
    kind: str,
    payload: dict,
    source: str,
    box_id: int | None = None,
) -> int:
    """Queue a new candidate for review. Never touches a real KB/cache
    table -- this only ever inserts into intake_candidates. Returns the
    new candidate's id."""
    if kind not in VALID_KINDS:
        raise ValueError(f"kind must be one of {VALID_KINDS}, got {kind!r}")
    if source not in VALID_SOURCES:
        raise ValueError(f"source must be one of {VALID_SOURCES}, got {source!r}")

    cursor = conn.execute(
        "INSERT INTO intake_candidates (kind, payload, source, box_id) VALUES (?, ?, ?, ?)",
        (kind, json.dumps(payload), source, box_id),
    )
    conn.commit()
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def list_pending(conn: sqlite3.Connection) -> list[IntakeCandidate]:
    rows = conn.execute(
        "SELECT * FROM intake_candidates WHERE status = 'pending' ORDER BY id"
    ).fetchall()
    return [_row_to_candidate(r) for r in rows]


def get_candidate(conn: sqlite3.Connection, candidate_id: int) -> IntakeCandidate | None:
    row = conn.execute(
        "SELECT * FROM intake_candidates WHERE id = ?", (candidate_id,)
    ).fetchone()
    return _row_to_candidate(row) if row else None


def _row_to_candidate(row: sqlite3.Row) -> IntakeCandidate:
    return IntakeCandidate(
        id=row["id"], kind=row["kind"], payload=json.loads(row["payload"]),
        source=row["source"], box_id=row["box_id"], status=row["status"],
        reviewer_note=row["reviewer_note"], created_at=row["created_at"],
        reviewed_at=row["reviewed_at"],
    )


def approve_candidate(conn: sqlite3.Connection, candidate_id: int, note: str | None = None) -> None:
    """Marks a candidate approved AND copies it into its real
    destination table, using the same write function that table's
    normal flow already uses -- so an approved Agent Harness
    explanation is indistinguishable, once live, from one cached via
    the ordinary `trinity cache-explanation` flow."""
    candidate = get_candidate(conn, candidate_id)
    if candidate is None:
        raise ValueError(f"No intake candidate with id {candidate_id}")
    if candidate.status != "pending":
        raise ValueError(f"Candidate {candidate_id} is already {candidate.status}")

    if candidate.kind == "explanation":
        from trinity.explain import save_explanation
        save_explanation(
            conn, candidate.payload["command"], candidate.payload["explanation"],
            source=candidate.source,
        )
    elif candidate.kind == "error_pattern":
        from trinity.errors import save_error_fix
        save_error_fix(
            conn, candidate.payload["error_text"], candidate.payload["cause"],
            candidate.payload["fix"], source=candidate.source,
        )
    elif candidate.kind == "kb_entry":
        conn.execute(
            """
            INSERT INTO kb_entries
                (source, title, summary, detail, match_service, match_version, tags, severity)
            VALUES (:source, :title, :summary, :detail, :match_service, :match_version, :tags, :severity)
            """,
            {
                "source": candidate.source,
                "title": candidate.payload["title"],
                "summary": candidate.payload["summary"],
                "detail": candidate.payload.get("detail"),
                "match_service": candidate.payload.get("match_service"),
                "match_version": candidate.payload.get("match_version"),
                "tags": candidate.payload.get("tags"),
                "severity": candidate.payload.get("severity"),
            },
        )
    elif candidate.kind == "method":
        # Methods Index entries are stored as YAML files
        # (methods_index/<box_name>.yaml), not a DB table -- approving
        # a method candidate is the caller's (methods.py's) job, since
        # it needs filesystem access this module deliberately doesn't
        # take on. Approval here only flips the intake status; methods.py
        # is expected to call approve_candidate AFTER it has already
        # written the YAML file, not before.
        pass
    else:  # pragma: no cover -- guarded by VALID_KINDS at submit time
        raise ValueError(f"Unknown candidate kind {candidate.kind!r}")

    conn.execute(
        "UPDATE intake_candidates SET status = 'approved', reviewer_note = ?, reviewed_at = ? WHERE id = ?",
        (note, datetime.now(timezone.utc).isoformat(), candidate_id),
    )
    conn.commit()


def reject_candidate(conn: sqlite3.Connection, candidate_id: int, note: str | None = None) -> None:
    """Marks a candidate rejected. Never deleted -- kept for audit and
    pattern-recognition (if the same kind of bad suggestion keeps
    showing up, that's useful signal)."""
    candidate = get_candidate(conn, candidate_id)
    if candidate is None:
        raise ValueError(f"No intake candidate with id {candidate_id}")
    if candidate.status != "pending":
        raise ValueError(f"Candidate {candidate_id} is already {candidate.status}")

    conn.execute(
        "UPDATE intake_candidates SET status = 'rejected', reviewer_note = ?, reviewed_at = ? WHERE id = ?",
        (note, datetime.now(timezone.utc).isoformat(), candidate_id),
    )
    conn.commit()
