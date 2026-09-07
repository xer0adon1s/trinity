"""PROTOTYPE — AutoRecon graduation nudge (FEATURES_BACKLOG).

Trinity never runs AutoRecon. After the operator has manually done
the HTTP→gobuster pattern enough times, mention that a bigger
calculator exists. Framed as an option, never a replacement.
"""
from __future__ import annotations

import sqlite3

NUDGE_AFTER = 3

NUDGE = (
    "You've run this manual web-enum pattern a few times now. "
    "AutoRecon (github.com/Tib3rius/AutoRecon) automates exactly that "
    "reasoning — you still run it yourself in your pane; Trinity will "
    "read the files it drops. Only reach for it once the 'why' is boring."
)


def gobuster_completions(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM suggestions WHERE accepted = 1 AND command LIKE 'gobuster%'"
    ).fetchone()
    return int(row["n"])


def autorecon_nudge(conn: sqlite3.Connection) -> str | None:
    if gobuster_completions(conn) >= NUDGE_AFTER:
        return NUDGE
    return None
