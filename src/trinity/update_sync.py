"""Update Framework, Part 1: sync scheduling for external data sources
(GTFOBins, ExploitDB, PayloadsAllTheThings, ...). This module owns the
"should we sync now" decision and the sync_state bookkeeping; it does
NOT itself know how to sync any particular source -- each source
(gtfobins.py, etc.) registers a sync function and calls
`run_sync_if_due()` with it. See docs/UPDATE_FRAMEWORK.md, "Part 1".

Deliberately silent and automatic per Alexander's explicit call: no
prompt, checks and pulls on launch if something's due. Any failure
degrades to "use what's already local" -- same defensive pattern as
vpn.py's VPN check.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

# Conservative default -- don't re-check literally every command
# invocation within the same session. Individual sources can pass a
# different interval if they have a reason to (e.g. ExploitDB's own
# `searchsploit -u` is cheap enough to run more often).
DEFAULT_MIN_INTERVAL = timedelta(hours=12)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def is_sync_due(conn: sqlite3.Connection, source: str, min_interval: timedelta = DEFAULT_MIN_INTERVAL) -> bool:
    row = conn.execute(
        "SELECT last_synced_at FROM sync_state WHERE source = ?", (source,)
    ).fetchone()
    if row is None or row["last_synced_at"] is None:
        return True
    last = _parse_ts(row["last_synced_at"])
    if last is None:
        return True
    return datetime.now(UTC) - last >= min_interval


def record_sync_result(conn: sqlite3.Connection, source: str, ok: bool, detail: str | None = None) -> None:
    conn.execute(
        "INSERT INTO sync_state (source, last_synced_at, last_status, detail) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(source) DO UPDATE SET last_synced_at = excluded.last_synced_at, "
        "last_status = excluded.last_status, detail = excluded.detail",
        (source, datetime.now(UTC).isoformat(), "ok" if ok else "failed", detail),
    )
    conn.commit()


def run_sync_if_due(
    conn: sqlite3.Connection,
    source: str,
    sync_fn: Callable[[], None],
    min_interval: timedelta = DEFAULT_MIN_INTERVAL,
) -> bool:
    """Runs `sync_fn()` if `source` is due for a sync, records the
    result either way. Any exception from `sync_fn` is caught and
    recorded as a failed sync -- a missed update must never be a hard
    failure for the rest of Trinity (same rule as vpn.py/
    platform_registry.py's Omarchy theme read). Returns True if a sync
    was attempted (regardless of success), False if skipped as not due."""
    if not is_sync_due(conn, source, min_interval):
        return False
    try:
        sync_fn()
        record_sync_result(conn, source, ok=True)
    except Exception as exc:  # noqa: BLE001 -- a sync failure is never fatal
        record_sync_result(conn, source, ok=False, detail=str(exc))
    return True


def get_sync_status(conn: sqlite3.Connection, source: str) -> dict | None:
    row = conn.execute(
        "SELECT source, last_synced_at, last_status, detail FROM sync_state WHERE source = ?",
        (source,),
    ).fetchone()
    return dict(row) if row else None
