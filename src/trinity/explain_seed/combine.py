"""Combines every pre-authored command-explanation category into one
seed dict, and provides seed_all() to bulk-load them into a DB. Each
category lives in its own module (nmap_seed.py, web_seed.py, etc.) so
the library stays organized and reviewable as it grows — add a new
category by creating a new module and registering it in _MODULES below.
"""
from __future__ import annotations

import sqlite3

from trinity.explain import seed_explanations
from trinity.explain_seed import (
    enum_seed,
    exploit_tools_seed,
    nmap_seed,
    privesc_linux_seed,
    privesc_windows_seed,
    shells_seed,
    web_seed,
)

_MODULES = [
    nmap_seed,
    web_seed,
    enum_seed,
    privesc_linux_seed,
    privesc_windows_seed,
    shells_seed,
    exploit_tools_seed,
]


def all_entries() -> dict[str, str]:
    """Merge every category's ENTRIES dict into one. Raises AssertionError
    on a duplicate command across categories — a genuine authoring bug
    worth catching (two categories explaining the same command
    differently), not something to silently paper over."""
    merged: dict[str, str] = {}
    for module in _MODULES:
        for command, explanation in module.ENTRIES.items():
            assert command not in merged, f"Duplicate seed command across categories: {command!r}"
            merged[command] = explanation
    return merged


def seed_all(conn: sqlite3.Connection) -> int:
    """Bulk-load every pre-authored explanation into the DB, skipping
    anything already cached (never overwrites an operator-verified
    entry). Returns the number of new entries inserted."""
    return seed_explanations(conn, all_entries())
