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
VALID_STATUSES = {"active", "rooted", "abandoned"}


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


def get_box_or_fail(conn: sqlite3.Connection, name: str) -> Box:
    """For administrative/read commands (box-status, report, next, hint,
    did, skip, box-mode, explain, error) that look a box up by name but
    should NOT silently create a ghost project on a typo -- only wizard/
    parse/watch (which represent the operator actually starting to work
    a box) should create. Raises click.ClickException with a clear
    message rather than a bare KeyError."""
    import click

    box = get_box_by_name(conn, name)
    if box is None:
        raise click.ClickException(
            f"No box named {name!r}. Start one via the wizard (`trinity`) or "
            f"`trinity parse-nmap ... --box {name!r}` / `trinity watch --box {name!r}`."
        )
    return box


def touch_active_box(conn: sqlite3.Connection, box_id: int) -> None:
    """Marks a box as the 'active' one for the wizard's Resume option.
    Called explicitly from commands that represent actually *working*
    a box (parse-nmap, watch) -- NOT from get_or_create_box in general,
    since plenty of commands (box-status, report, explain, box-mode)
    look a box up by name without that meaning 'I am now working this
    box' in the resume-tracking sense."""
    from trinity.state import ACTIVE_BOX_ID, set_state
    set_state(conn, ACTIVE_BOX_ID, str(box_id))


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


def set_status(conn: sqlite3.Connection, box_id: int, status: str) -> None:
    """Marks a box active/rooted/abandoned. Closing a box out (rooted
    or abandoned) also clears it as the wizard's 'active' box, so the
    next bare `trinity` launch correctly offers 'start a new project'
    instead of endlessly offering to resume a box that's already done."""
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
    conn.execute(
        "UPDATE boxes SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, box_id),
    )
    conn.commit()

    if status in ("rooted", "abandoned"):
        from trinity.state import ACTIVE_BOX_ID, get_state, clear_state
        if get_state(conn, ACTIVE_BOX_ID) == str(box_id):
            clear_state(conn, ACTIVE_BOX_ID)
