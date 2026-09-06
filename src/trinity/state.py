"""Tiny key/value helpers over the local_state table -- machine-local
onboarding state (has setup run, which box is "active"), not anything
report-relevant."""
from __future__ import annotations

import sqlite3


def get_state(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM local_state WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_state(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO local_state (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def clear_state(conn: sqlite3.Connection, key: str) -> None:
    conn.execute("DELETE FROM local_state WHERE key = ?", (key,))
    conn.commit()


# Well-known keys
SETUP_DONE = "setup_done"        # "1" once the intro wizard has run
ACTIVE_BOX_ID = "active_box_id"  # id of the box currently being worked
