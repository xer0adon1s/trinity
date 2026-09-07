"""Loot / evidence tracker (docs/FEATURES_BACKLOG.md).

Credentials, hashes, tokens, flags — flows into the timeline and both
report templates. Shared spine (one `loot` table, one `LootItem`
model); the professional-mode report section stays short (count +
flag count + list), matching the "edu is focus, keep professional-mode
report growth minimal for now" call from the agentic-OS pivot session.
"""
from __future__ import annotations

import sqlite3

from pydantic import BaseModel

from trinity.timeline import log_event

VALID_KINDS = {"credential", "hash", "token", "flag", "other"}


class LootItem(BaseModel):
    id: int
    box_id: int
    kind: str
    value: str
    note: str | None = None
    discovered_at: str | None = None


def add_loot(
    conn: sqlite3.Connection,
    box_id: int,
    kind: str,
    value: str,
    note: str | None = None,
) -> LootItem:
    if kind not in VALID_KINDS:
        raise ValueError(f"loot kind must be one of {VALID_KINDS}, got {kind!r}")
    if not value.strip():
        raise ValueError("loot value must not be empty")

    cursor = conn.execute(
        "INSERT INTO loot (box_id, kind, value, note) VALUES (?, ?, ?, ?)",
        (box_id, kind, value.strip(), note),
    )
    conn.commit()
    log_event(
        conn, box_id, "loot",
        f"loot ({kind}): {value.strip()}",
        detail=note,
        phase="post" if kind == "flag" else None,
        ref_id=cursor.lastrowid,
    )
    return list_loot(conn, box_id)[-1]


def list_loot(conn: sqlite3.Connection, box_id: int) -> list[LootItem]:
    rows = conn.execute(
        "SELECT * FROM loot WHERE box_id = ? ORDER BY id", (box_id,)
    ).fetchall()
    return [LootItem(**dict(row)) for row in rows]
