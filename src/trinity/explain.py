"""ELI5 command explanations, cached locally so the same command never
costs a token to explain twice, on this box or any future one — the
cache is global across boxes, keyed only by the normalized command text.
"""
from __future__ import annotations

import re
import sqlite3

# Real suggested commands substitute an actual target (an IP address,
# or the literal string $TARGET when no host is known yet -- see
# suggest/engine.py's _effective_host/_curl_command) in place of a
# placeholder. The entire pre-authored ELI5 library (explain_seed/*.py,
# 86+ entries) is keyed using the literal template token `<target>`
# instead. Before this fix, NO real suggested command could ever hit
# the seed cache: `nmap -sC -sV 10.10.10.3` (real) never matched
# `nmap -sC -sV <target>` (seed key) under plain string equality --
# confirmed live, not a hypothetical, while reviewing the AD engine's
# explain-seed entries (which have the exact same problem as every
# other seed file, not something AD-specific). `<userlist>`/`<realm>`-
# style seed placeholders are intentionally NOT touched here -- those
# vary per-operator/per-box and can't be safely guessed at, unlike a
# target host, which the suggest engine reliably substitutes in one of
# exactly two recognizable shapes.
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_TARGET_VAR_RE = re.compile(r"\$TARGET\b")

# Narrow, STRUCTURAL templating for the two AD-specific command shapes
# that have real-vs-seed mismatches beyond the target host (see
# docs/AD_ENGINE_OPEN_QUESTIONS.md "Explain cache still misses real AD
# commands"). Deliberately scoped to flag/position patterns tied to a
# specific, known command shape -- NOT a general "guess any token is a
# placeholder" scheme, which the open-questions doc correctly flags as
# unsafe (domain/userlist names are genuinely per-operator and must not
# be silently normalized in suggestion TEXT). This only affects the
# explain-cache LOOKUP KEY, never what's shown to the operator -- the
# ELI5 explanation text itself is generic and doesn't reference the
# specific domain/userlist/DN, so templating purely for cache-matching
# purposes is safe here in a way it would not be for suggest/engine.py's
# actual suggestion output.
_GETNPUSERS_DOMAIN_RE = re.compile(r"(?<=GetNPUsers\.py )\S+(?=/)")
_USERSFILE_RE = re.compile(r"(?<=-usersfile )\S+")
_LDAP_BASE_RE = re.compile(r"(?<=-b )'[^']*'")


def normalize(command: str) -> str:
    """Collapse whitespace so trivially-different invocations of the same
    command (extra spaces, trailing newline) share one cache entry."""
    return re.sub(r"\s+", " ", command.strip())


def _templated(command: str) -> str:
    """Replace a real target (IPv4 literal, or the $TARGET placeholder
    used when no host is known yet) with the seed library's `<target>`
    template token, so a real suggested command can hit a pre-authored
    seed entry. Also templates a small, explicitly-listed set of other
    structural placeholders (GetNPUsers.py's domain, -usersfile's
    filename, ldapsearch -b's DN) that are tied to a specific known
    command shape -- everything else (usernames, wordlists in other
    contexts, domain names outside these exact flags) is left alone,
    since those are genuinely per-operator and unsafe to guess-
    normalize in general."""
    templated = _TARGET_VAR_RE.sub("<target>", command)
    templated = _IPV4_RE.sub("<target>", templated)
    if templated.startswith("GetNPUsers.py "):
        templated = _GETNPUSERS_DOMAIN_RE.sub("<domain>", templated)
        templated = _USERSFILE_RE.sub("<userlist>", templated)
    if templated.startswith("ldapsearch "):
        templated = _LDAP_BASE_RE.sub("'<base>'", templated)
    return templated


def get_explanation(conn: sqlite3.Connection, command: str) -> str | None:
    """Return the cached ELI5 explanation for a command, or None if it's
    never been explained before. Tries the exact normalized command
    first, then falls back to the target-templated form so a real
    command like `nmap -sC -sV 10.10.10.3` can still hit the seed
    library's `nmap -sC -sV <target>` entry."""
    normalized = normalize(command)
    row = conn.execute(
        "SELECT explanation FROM command_explanations WHERE command = ?",
        (normalized,),
    ).fetchone()
    if row:
        return row["explanation"]

    templated = normalize(_templated(normalized))
    if templated == normalized:
        return None
    row = conn.execute(
        "SELECT explanation FROM command_explanations WHERE command = ?",
        (templated,),
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
