"""AutoRecon graduation nudge (docs/FEATURES_BACKLOG.md).

Trinity never runs AutoRecon. After the operator has manually done
the HTTP→gobuster pattern enough times, mention that a bigger
calculator exists. Framed as an option, never a replacement.

Fires ONCE per box lifetime, not on every subsequent call past the
threshold -- tracked via a timeline event, same "already logged"
pattern as shoulder.py's milestone detection. Without this, a nudge
that's genuinely useful the first time becomes exactly the repetitive
noise the advisory-arbitration system (advisories.py) exists to
prevent.
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

_NUDGE_EVENT_TYPE = "autorecon_nudge"


def gobuster_completions(conn: sqlite3.Connection, box_id: int | None = None) -> int:
    """Counts completed gobuster-shaped suggestions. Scoped to a
    single box when box_id is given (the correct behavior -- a nudge
    about THIS box's pattern shouldn't fire based on unrelated work on
    a completely different box); box-agnostic only for backwards
    compatibility with any caller that genuinely wants a global count."""
    if box_id is not None:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM suggestions WHERE box_id = ? AND accepted = 1 AND command LIKE 'gobuster%'",
            (box_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM suggestions WHERE accepted = 1 AND command LIKE 'gobuster%'"
        ).fetchone()
    return int(row["n"])


def _already_nudged(conn: sqlite3.Connection, box_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM timeline WHERE box_id = ? AND event_type = ? LIMIT 1",
        (box_id, _NUDGE_EVENT_TYPE),
    ).fetchone()
    return row is not None


def autorecon_nudge(conn: sqlite3.Connection, box_id: int | None = None) -> str | None:
    """Returns the nudge text if the threshold is crossed AND it
    hasn't already fired for this box -- None otherwise. `box_id` is
    optional ONLY for backwards compatibility with the box-agnostic
    gobuster_completions() query; pass it whenever a specific box is
    known (advisories.py always does) so both the box-scoping and the
    once-per-lifetime gate actually apply. Without a box_id, this
    behaves like the old (buggy) always-eligible, cross-box-counting
    version -- callers should always pass box_id in practice."""
    if gobuster_completions(conn, box_id) < NUDGE_AFTER:
        return None
    if box_id is not None and _already_nudged(conn, box_id):
        return None
    return NUDGE


def mark_nudged(conn: sqlite3.Connection, box_id: int) -> None:
    """Records that the AutoRecon nudge fired for this box, so it
    never surfaces again for the same box. Called by advisories.py
    only when this nudge actually wins the single advisory slot --
    never at detection time, so a nudge that was eligible but got
    outranked by something more urgent (e.g. a rabbit-hole signal)
    stays eligible to fire on a later call instead of being silently
    burned."""
    from trinity.timeline import log_event

    log_event(conn, box_id, _NUDGE_EVENT_TYPE, "AutoRecon graduation nudge shown")
