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


def save_explanation(
    conn: sqlite3.Connection, command: str, explanation: str, source: str = "ai_escalation"
) -> None:
    """Cache an ELI5 explanation for a command. Overwrites any existing
    entry for the same normalized command (e.g. if the user wants to
    correct/improve a prior explanation). Default source is
    'ai_escalation' (the normal explain -> cache-explanation flow);
    pass 'trinity_preseed' for bulk-authored library entries or
    'user_curated' for hand-written ones."""
    conn.execute(
        """
        INSERT INTO command_explanations (command, explanation, source)
        VALUES (?, ?, ?)
        ON CONFLICT(command) DO UPDATE SET explanation = excluded.explanation, source = excluded.source
        """,
        (normalize(command), explanation, source),
    )
    conn.commit()


def seed_explanations(conn: sqlite3.Connection, entries: dict[str, str]) -> int:
    """Bulk-insert pre-authored explanations, skipping any command that
    already has a cached explanation (never overwrites something an
    operator may have personally verified/corrected via the normal
    explain flow). Returns the number of entries actually inserted."""
    inserted = 0
    for command, explanation in entries.items():
        exists = conn.execute(
            "SELECT 1 FROM command_explanations WHERE command = ?", (normalize(command),)
        ).fetchone()
        if exists:
            continue
        conn.execute(
            "INSERT INTO command_explanations (command, explanation, source) VALUES (?, ?, 'trinity_preseed')",
            (normalize(command), explanation),
        )
        inserted += 1
    conn.commit()
    return inserted


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
