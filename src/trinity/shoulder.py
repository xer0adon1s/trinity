"""Shoulder Mode: full pty-based terminal session recording + milestone
detection. See docs/SHOULDER_MODE.md.

Two independent halves, deliberately kept separate and separately
testable:

1. Recording (`record_session`) — spawns a real shell inside a pty,
   tee's every byte of output to both the operator's real terminal
   AND a session log file on disk (script(1)-equivalent). This half
   needs a real terminal to exercise live; it is NOT unit-testable in
   the normal sense, so it's kept small and dumb on purpose.

2. Detection (`scan_for_milestones`) — a pure function over already-
   captured text. Fully unit-testable, and IS the part that actually
   matters: turning "operator typed a bunch of stuff" into "operator
   landed a shell" / "operator got root" signals that feed the SAME
   Finding/timeline pipeline everything else uses.

Explicitly NOT covered by this module (see docs/SHOULDER_MODE.md,
"What this does NOT do"): reading a persistent ~/.bash_history file
(that mechanism stays vetoed on its own fragile-across-shells merits),
window/pane orchestration (still `trinity lab`'s territory, still
vetoed), or interpreting/blocking any command the operator types --
Shoulder Mode only ever reads, never writes to or filters the pty.
"""
from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SESSIONS_DIR = Path.home() / ".trinity" / "sessions"


@dataclass
class MilestoneHit:
    name: str          # e.g. "shell_landed", "root_landed"
    phase: str          # foothold / privesc -- same phase vocabulary as suggestions
    shell_level: str | None  # 'user' / 'root' / None if not a shell-level milestone
    matched_text: str


# Ordered specific-before-general on purpose: root patterns are checked
# before generic-shell patterns so a transcript containing both a user
# shell landing and a later privesc doesn't get stuck reporting only
# the earlier, weaker milestone.
_MILESTONE_PATTERNS: list[tuple[str, str, str | None, re.Pattern]] = [
    (
        "root_landed", "privesc", "root",
        re.compile(r"uid=0\(root\)|^# $|^root@\S+:.*[#]\s*$", re.MULTILINE),
    ),
    (
        "shell_landed", "foothold", "user",
        re.compile(
            r"uid=\d+\([^)]+\).*gid=\d+|"          # id/whoami -a style output
            r"^\$ $|"                                # bare shell prompt at line end
            r"www-data@|"                            # common low-priv web-shell user
            r"Microsoft Windows \[Version|"          # cmd.exe banner
            r"PS [A-Z]:\\\S*>",                       # PowerShell prompt
            re.MULTILINE,
        ),
    ),
]


def scan_for_milestones(text: str) -> list[MilestoneHit]:
    """Pure function: scans captured terminal text for shell/root
    signals. Deliberately conservative (specific patterns, not vague
    keyword matches) -- a false positive here would wrongly promote a
    box's shell_level and skip real recommended steps, so patterns
    require actual prompt/id-output shapes, not just the word 'root'
    appearing anywhere (e.g. in an nmap banner mentioning a CVE)."""
    hits: list[MilestoneHit] = []
    for name, phase, shell_level, pattern in _MILESTONE_PATTERNS:
        match = pattern.search(text)
        if match:
            hits.append(MilestoneHit(name=name, phase=phase, shell_level=shell_level, matched_text=match.group(0)))

    # Specific-before-general: if root was detected anywhere in this
    # scan, don't also report the weaker user-level hit for the same
    # pass -- root supersedes it, same rank logic as apply_milestones.
    if any(h.shell_level == "root" for h in hits):
        hits = [h for h in hits if h.shell_level != "user"]
    return hits


def apply_milestones(conn: sqlite3.Connection, box_id: int, hits: list[MilestoneHit]) -> list[MilestoneHit]:
    """Applies detected milestones to a box: logs a timeline event for
    each, and promotes shell_level via the SAME set_shell_level() the
    manual `trinity shell` command already uses -- Shoulder Mode is an
    additional way to trigger it, not a second parallel mechanism.
    Only promotes upward (user -> root), never downgrades, and never
    re-applies a milestone already recorded for this box. Returns the
    hits that were newly applied (for the caller to report to the
    operator)."""
    from trinity.boxes import VALID_SHELL_LEVELS, get_box, set_shell_level
    from trinity.timeline import log_event

    box = get_box(conn, box_id)
    if box is None:
        return []

    already_seen = {
        row["summary"]
        for row in conn.execute(
            "SELECT summary FROM timeline WHERE box_id = ? AND event_type = 'shoulder_milestone'",
            (box_id,),
        ).fetchall()
    }

    newly_applied: list[MilestoneHit] = []
    _rank = {None: 0, "user": 1, "root": 2}
    current_rank = _rank.get(box.shell_level, 0)

    for hit in hits:
        summary = f"shoulder-mode detected: {hit.name}"
        if summary in already_seen:
            continue
        log_event(
            conn, box_id, "shoulder_milestone", summary,
            phase=hit.phase, detail=hit.matched_text[:200],
        )
        newly_applied.append(hit)
        if hit.shell_level and hit.shell_level in VALID_SHELL_LEVELS:
            if _rank[hit.shell_level] > current_rank:
                set_shell_level(conn, box_id, hit.shell_level)
                current_rank = _rank[hit.shell_level]

    return newly_applied


def session_log_path(box_name: str) -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", box_name)
    return SESSIONS_DIR / f"{safe_name}_{stamp}.log"


def record_session(shell: str, log_path: Path) -> None:
    """Spawns `shell` inside a pty, tee-ing every byte of output to
    both the real terminal and `log_path` -- script(1)-equivalent.
    Blocks until the shell exits. Requires a real interactive
    terminal; not meaningfully unit-testable, kept intentionally thin
    so all the actual logic (scan_for_milestones/apply_milestones)
    lives in testable pure functions instead."""
    import pty

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "ab") as logfile:
        def read(fd: int) -> bytes:
            data = os.read(fd, 4096)
            logfile.write(data)
            logfile.flush()
            return data

        pty.spawn([shell], read)
