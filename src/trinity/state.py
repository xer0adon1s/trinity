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


def claim_state(conn: sqlite3.Connection, key: str) -> bool:
    """Atomically claims a one-time-ever gate. Returns True only for the
    caller that actually wins the insert; every other (concurrent)
    caller gets False and should skip whatever the claim guards.

    Exists because `trinity.db` is shared across all Trinity worktree
    checkouts (~/.trinity/trinity.db, not per-worktree), and Alexander
    routinely runs several AI agent terminals against the same worktree
    at once. A plain "get_state(...) is None" read-then-write check
    (like the old notify/hacker-name wizard gates) is a TOCTOU race: two
    or three processes can all read None before any of them commits,
    and all act on it -- e.g. all firing a one-time-ever test
    notification, producing duplicate desktop popups. A raw INSERT
    (not the upsert set_state uses) only ever succeeds once per key;
    every later/concurrent attempt hits the PRIMARY KEY and loses.
    """
    try:
        conn.execute(
            "INSERT INTO local_state (key, value) VALUES (?, '1')", (key,),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        conn.rollback()
        return False


def clear_state(conn: sqlite3.Connection, key: str) -> None:
    conn.execute("DELETE FROM local_state WHERE key = ?", (key,))
    conn.commit()


# Well-known keys
SETUP_DONE = "setup_done"        # "1" once the intro wizard has run
ACTIVE_BOX_ID = "active_box_id"  # id of the box currently being worked
HACKER_NAME = "hacker_name"      # operator's chosen handle, asked once at setup
HACKER_NAME_ENABLED = "hacker_name_enabled"  # "1"/"0" -- separate from
    # whether a name is stored, so disabling-then-re-enabling recalls
    # the old name instead of re-asking from scratch (see `trinity
    # nickname` CLI group / wizard.py's get_hacker_name()).
NOTIFY_ENABLED = "notify_enabled"  # "1"/"0" -- desktop notify-send on
    # critical matches. Off by default, opt-in at setup or via
    # `trinity notify on/off/test`. See notify.py.
