"""ELI5 command explanations, cached locally so the same command never
costs a token to explain twice, on this box or any future one — the
cache is global across boxes, keyed only by the normalized command text.
"""
from __future__ import annotations

import re
import sqlite3


def normalize(command: str) -> str:
    """Collapse whitespace so trivially-different invocations of the same
    command (extra spaces, trailing newline) share one cache entry."""
    return re.sub(r"\s+", " ", command.strip())


def get_explanation(conn: sqlite3.Connection, command: str) -> str | None:
    """Return the cached ELI5 explanation for a command, or None if it's
    never been explained before."""
    row = conn.execute(
        "SELECT explanation FROM command_explanations WHERE command = ?",
        (normalize(command),),
    ).fetchone()
    return row["explanation"] if row else None


def save_explanation(conn: sqlite3.Connection, command: str, explanation: str) -> None:
    """Cache an ELI5 explanation for a command. Overwrites any existing
    entry for the same normalized command (e.g. if the user wants to
    correct/improve a prior explanation)."""
    conn.execute(
        """
        INSERT INTO command_explanations (command, explanation)
        VALUES (?, ?)
        ON CONFLICT(command) DO UPDATE SET explanation = excluded.explanation
        """,
        (normalize(command), explanation),
    )
    conn.commit()


def build_escalation_prompt(command: str) -> str:
    """Format a tight, copy-pasteable question for the operator to bring
    to an AI assistant when a command has never been explained before.
    Kept short and specific on purpose — this is the whole point of
    Trinity's token-saving design: a focused question, not a full scan
    dump."""
    return (
        f'Explain this command in plain, beginner-friendly (ELI5) terms — '
        f"what it does, what each flag means, and why someone doing "
        f"CTF/HTB recon would run it:\n\n    {command}\n\n"
        f"Keep it to a short paragraph plus a quick per-flag breakdown."
    )
