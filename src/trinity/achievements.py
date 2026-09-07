"""PROTOTYPE — local achievements / technique journal (FEATURES_BACKLOG).

Single-player, offline, no leaderboard. Taxonomy is versioned so new
categories can be added later without wiping old unlocks — they just
appear as locked until the operator hits them.
"""
from __future__ import annotations

import sqlite3

from pydantic import BaseModel

TAXONOMY_VERSION = 1

# id, title, how we detect it
_CATEGORIES: list[tuple[str, str, str]] = [
    ("nmap_scan", "First real scan", "timeline scan nmap"),
    ("web_enum", "Looked inside a website", "suggestion gobuster accepted or path finding"),
    ("smb_enum", "Asked SMB a question", "enum4linux or smbclient"),
    ("user_shell", "Declared a user shell", "shell_level user/root"),
    ("root_shell", "Declared a root shell", "shell_level root or status rooted"),
    ("first_flag", "Recorded a flag", "loot kind=flag"),
    ("cached_error", "Paid the error cache once", "timeline diagnosed error"),
]


class Achievement(BaseModel):
    id: str
    title: str
    unlocked: bool
    how: str


def evaluate(conn: sqlite3.Connection) -> list[Achievement]:
    scans = conn.execute(
        "SELECT COUNT(*) AS n FROM timeline WHERE event_type = 'scan'"
    ).fetchone()["n"]
    paths = conn.execute(
        "SELECT COUNT(*) AS n FROM findings WHERE kind = 'path'"
    ).fetchone()["n"]
    smb = conn.execute(
        "SELECT COUNT(*) AS n FROM timeline WHERE summary LIKE '%smb%' OR summary LIKE '%enum4linux%'"
    ).fetchone()["n"]
    shells = {
        row["shell_level"]
        for row in conn.execute("SELECT shell_level FROM boxes WHERE shell_level IS NOT NULL")
    }
    rooted = conn.execute(
        "SELECT COUNT(*) AS n FROM boxes WHERE status = 'rooted'"
    ).fetchone()["n"]
    flags = conn.execute(
        "SELECT COUNT(*) AS n FROM loot WHERE kind = 'flag'"
    ).fetchone()["n"]
    errors = conn.execute(
        "SELECT COUNT(*) AS n FROM timeline WHERE summary LIKE 'diagnosed error:%'"
    ).fetchone()["n"]

    unlocked = {
        "nmap_scan": scans > 0,
        "web_enum": paths > 0,
        "smb_enum": smb > 0,
        "user_shell": bool(shells & {"user", "root"}),
        "root_shell": "root" in shells or rooted > 0,
        "first_flag": flags > 0,
        "cached_error": errors > 0,
    }
    return [
        Achievement(id=cid, title=title, unlocked=unlocked[cid], how=how)
        for cid, title, how in _CATEGORIES
    ]
