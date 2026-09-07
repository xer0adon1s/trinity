"""PROTOTYPE — name the win (Trinity_suggestions.md 1.6).

Claude agreed this is the right shape: Trinity asks "shell? user or
root?" and never reads history (docs/CLAUDE_CURSOR_DEBATE.md §2).
This handoff classified the prompt as SHOULD and left it unbuilt.

This draft:
- records an operator-declared shell_level on the box
- writes a timeline milestone
- on a *user* shell, injects a short Linux privesc deck so the
  orphaned explain-seeds (sudo -l, SUID find, crontab) actually
  become coach recommendations
- on a *root* shell, marks the box rooted (same as box-status)

Claude: veto or reshape the verb (`trinity shell` vs folding into
box-status). Do not treat this as shipped product.
"""
from __future__ import annotations

import sqlite3

from trinity.boxes import VALID_SHELL_LEVELS, get_box, set_shell_level, set_status
from trinity.suggest.engine import Suggestion
from trinity.timeline import log_event

# Thin on purpose — four commands that already have ELI5 seeds.
# linpeas is deliberately omitted: required_tool/wget + attacker IP
# is a second design conversation (GTFOBins/explain already mention it).
_PRIVESC_DECK: list[Suggestion] = [
    Suggestion(
        phase="privesc",
        command="id",
        rationale="Know who you are before you try to become someone else.",
        nudge="You have a foothold. The first useful fact is which account you landed as.",
        required_tool="",
    ),
    Suggestion(
        phase="privesc",
        command="sudo -l",
        rationale="If this user can run anything as root, that is often the whole path.",
        nudge="Some accounts are already allowed to run specific commands as a more privileged user.",
        required_tool="",
    ),
    Suggestion(
        phase="privesc",
        command="find / -perm -4000 -type f 2>/dev/null",
        rationale="Unusual SUID binaries are a classic Linux privesc lead.",
        nudge="Some programs on the box run with more privilege than the account that starts them.",
        required_tool="",
    ),
    Suggestion(
        phase="privesc",
        command="cat /etc/crontab",
        rationale="A writable cron job running as root is an easy next step.",
        nudge="Scheduled tasks sometimes run as a privileged user and call scripts you can edit.",
        required_tool="",
    ),
    Suggestion(
        phase="privesc",
        command="linpeas.sh",
        rationale="Optional: a well-known Linux privesc enumerator you run YOURSELF after you have a way to upload it. Trinity will not fetch or execute it.",
        nudge="There is a popular script that automates a lot of the boring privilege checks — only after you know what those checks are for.",
        required_tool="",
    ),
]


def record_shell(conn: sqlite3.Connection, box_id: int, level: str) -> list[str]:
    """Declare a foothold. Returns the privesc commands newly inserted
    (empty on a root milestone, or when the deck was already present)."""
    if level not in VALID_SHELL_LEVELS:
        raise ValueError(f"shell level must be one of {VALID_SHELL_LEVELS}, got {level!r}")

    box = get_box(conn, box_id)
    if box is None:
        raise ValueError(f"No box with id {box_id}")

    # Don't demote root -> user if they already called it.
    if box.shell_level == "root" and level == "user":
        return []

    set_shell_level(conn, box_id, level)
    log_event(
        conn, box_id, "milestone",
        f"operator declared a {level} shell",
        phase="foothold" if level == "user" else "privesc",
        detail="Declared by the operator. Trinity did not inspect any shell history.",
    )

    inserted: list[str] = []
    if level == "user":
        inserted = _inject_privesc_deck(conn, box_id)
    elif level == "root" and box.status != "rooted":
        set_status(conn, box_id, "rooted")
        log_event(conn, box_id, "milestone", "box marked rooted (via shell --as root)")

    return inserted


def _inject_privesc_deck(conn: sqlite3.Connection, box_id: int) -> list[str]:
    already = {
        row["command"]
        for row in conn.execute(
            "SELECT command FROM suggestions WHERE box_id = ?", (box_id,)
        )
    }
    inserted: list[str] = []
    for suggestion in _PRIVESC_DECK:
        if suggestion.command in already:
            continue
        cursor = conn.execute(
            "INSERT INTO suggestions (box_id, phase, command, rationale, nudge, required_tool) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                box_id, suggestion.phase, suggestion.command,
                suggestion.rationale, suggestion.nudge, suggestion.required_tool,
            ),
        )
        log_event(
            conn, box_id, "suggestion", f"suggested: {suggestion.command}",
            phase=suggestion.phase, detail=suggestion.rationale, ref_id=cursor.lastrowid,
        )
        inserted.append(suggestion.command)
    conn.commit()
    return inserted
