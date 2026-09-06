"""Box (target) management — create, list, fetch by name."""
from __future__ import annotations

import sqlite3

from pydantic import BaseModel


class Box(BaseModel):
    id: int
    name: str
    target: str | None = None
    platform: str | None = None
    status: str = "active"
    mode: str = "educational"


VALID_MODES = {"educational", "professional"}


def create_box(
    conn: sqlite3.Connection,
    name: str,
    target: str | None = None,
    platform: str | None = None,
    mode: str = "educational",
) -> Box:
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")

    cursor = conn.execute(
        "INSERT INTO boxes (name, target, platform, mode) VALUES (?, ?, ?, ?)",
        (name, target, platform, mode),
    )
    conn.commit()
    assert cursor.lastrowid is not None
    return get_box(conn, cursor.lastrowid)  # type: ignore[return-value]


def get_box(conn: sqlite3.Connection, box_id: int) -> Box | None:
    row = conn.execute("SELECT * FROM boxes WHERE id = ?", (box_id,)).fetchone()
    return Box(**dict(row)) if row else None


def get_box_by_name(conn: sqlite3.Connection, name: str) -> Box | None:
    row = conn.execute(
        "SELECT * FROM boxes WHERE name = ? ORDER BY id DESC LIMIT 1", (name,)
    ).fetchone()
    return Box(**dict(row)) if row else None


def get_or_create_box(
    conn: sqlite3.Connection,
    name: str,
    target: str | None = None,
    platform: str | None = None,
    mode: str = "educational",
) -> Box:
    existing = get_box_by_name(conn, name)
    if existing:
        return existing
    return create_box(conn, name, target=target, platform=platform, mode=mode)


def list_boxes(conn: sqlite3.Connection) -> list[Box]:
    rows = conn.execute("SELECT * FROM boxes ORDER BY updated_at DESC").fetchall()
    return [Box(**dict(row)) for row in rows]


def set_mode(conn: sqlite3.Connection, box_id: int, mode: str) -> None:
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")
    conn.execute(
        "UPDATE boxes SET mode = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (mode, box_id),
    )
    conn.commit()
