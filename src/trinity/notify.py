"""Critical-match desktop ping (docs/FEATURES_BACKLOG.md, originally
Trinity_suggestions.md 2.11).

Best-effort `notify-send`. Missing binary or a failed spawn is
silent. Never runs an exploit. Deduped by the caller (process.py only
calls this once per newly-inserted critical match, not on re-parses).

Gated behind an explicit on/off toggle (state.py's NOTIFY_ENABLED key,
same on/off/set-name shape as HACKER_NAME_ENABLED) -- asked once at
wizard setup, always re-toggleable via `trinity notify on/off/test`
without re-running setup. Off by default until the operator opts in,
same reasoning as the hacker name: a notification popping up
unannounced the first time a beginner's box matches something is a
worse first impression than just not doing it until asked.
"""
from __future__ import annotations

import shutil
import sqlite3
import subprocess

from trinity.state import NOTIFY_ENABLED, get_state


def is_notify_enabled(conn: sqlite3.Connection) -> bool:
    return get_state(conn, NOTIFY_ENABLED) == "1"


def notify_critical(conn: sqlite3.Connection, title: str, body: str) -> bool:
    """Sends a desktop notification for a critical match, but ONLY if
    the operator has opted in. Returns False (no-op) if disabled,
    notify-send is missing, or the spawn fails -- never raises, never
    blocks the caller's own success path."""
    if not is_notify_enabled(conn):
        return False
    return _send(title, body)


def _send(title: str, body: str) -> bool:
    binary = shutil.which("notify-send")
    if not binary:
        return False
    try:
        subprocess.run(
            [binary, "--expire-time=8000", title, body],
            check=False,
            capture_output=True,
            timeout=3,
        )
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


def send_test_notification() -> bool:
    """Fires one unconditional notification, bypassing the toggle --
    used by the wizard's opt-in prompt and `trinity notify test` to
    prove notify-send actually works on this machine, independent of
    whether the feature is currently enabled."""
    return _send("Trinity", "Desktop notifications are on.")
