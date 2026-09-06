"""Error diagnosis cache: the same "pay the AI cost once, cache forever"
shape as explain.py's ELI5 cache, but at "why didn't this work"
granularity instead of "what does this command mean". Uses FTS5 fuzzy
matching (not exact-string lookup like command_explanations) because
error text varies more than command syntax -- a stack trace or
connection error rarely repeats verbatim, but the underlying cause
often does. See docs/INSTRUCTOR_MODE.md.
"""
from __future__ import annotations

import re
import sqlite3

from pydantic import BaseModel


class ErrorMatch(BaseModel):
    cause: str
    fix: str
    source: str


def _fts_query(text: str) -> str:
    """Tokenize free text into an FTS5 MATCH query (OR-ing alphanumeric
    tokens), same approach as match/engine.py uses for KB lookups --
    error text is free-form, so exact matching would almost never hit."""
    tokens = re.findall(r"[a-zA-Z0-9_./-]+", text.lower())
    tokens = [t for t in tokens if len(t) > 2]  # skip noise like "a", "in", "to"
    if not tokens:
        return '""'
    return " OR ".join(f'"{t}"' for t in tokens[:20])  # cap to keep queries sane


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zA-Z0-9_./-]+", text.lower()) if len(t) > 2}


# Common English words that show up constantly in error text but carry
# almost no diagnostic specificity on their own -- long enough to have
# tripped the old ">= 8 chars is distinctive" rule, but not actually
# distinctive. A single overlapping word from this list is NEVER
# enough to count as a meaningful match, no matter its length.
_GENERIC_STOPWORDS = {
    "connection", "connections", "connecting", "connected",
    "forbidden", "unexpected", "permission", "permissions",
    "problem", "problems", "failure", "failures", "failed", "failing",
    "timeout", "timed", "refused", "refusing", "denied", "denying",
    "request", "response", "invalid", "unable", "cannot", "couldnt",
    "something", "somewhere", "unknown", "general", "generic",
}


def _is_distinctive_token(token: str) -> bool:
    """A token is distinctive enough to justify a match on its own
    only if it's long AND not a common English word that just happens
    to be long (see _GENERIC_STOPWORDS) -- e.g. 'publickey',
    'xyzzy123', a CVE id, or a specific tool/module name, as opposed
    to 'connection' or 'forbidden'."""
    return len(token) >= 8 and token not in _GENERIC_STOPWORDS


def _is_meaningful_overlap(query_tokens: set[str], candidate_tokens: set[str]) -> bool:
    """FTS5's OR-matching alone is too loose for short free-text error
    queries: two errors sharing only one generic word ('error',
    'connection', 'failed') will still get a MATCH hit and rank #1 by
    default, producing a confident-looking but wrong cache hit. Require
    either multiple overlapping tokens, or a single overlapping token
    that's both long AND not a common-English stopword (see
    _is_distinctive_token) -- 'publickey'/'xyzzy123' qualify,
    'connection'/'forbidden'/'unexpected' do not, even though all are
    >= 8 characters."""
    overlap = query_tokens & candidate_tokens
    if len(overlap) >= 2:
        return True
    if len(overlap) == 1 and _is_distinctive_token(next(iter(overlap))):
        return True
    return False


def find_error_match(conn: sqlite3.Connection, error_text: str) -> ErrorMatch | None:
    """Fuzzy-searches the local error_patterns KB for a known cause/fix.
    Returns the best-ranked match with a meaningful token overlap, or
    None on a genuine miss -- a single shared generic word (e.g. both
    errors happening to say "error") is deliberately NOT enough to
    count as a match; see _is_meaningful_overlap."""
    query = _fts_query(error_text)
    if query == '""':
        return None

    query_tokens = _tokens(error_text)

    rows = conn.execute(
        """
        SELECT ep.error_text, ep.cause, ep.fix, ep.source
        FROM error_patterns_fts
        JOIN error_patterns ep ON ep.id = error_patterns_fts.rowid
        WHERE error_patterns_fts MATCH ?
        ORDER BY rank
        LIMIT 5
        """,
        (query,),
    ).fetchall()

    for row in rows:
        if _is_meaningful_overlap(query_tokens, _tokens(row["error_text"])):
            return ErrorMatch(cause=row["cause"], fix=row["fix"], source=row["source"])

    return None


def save_error_fix(
    conn: sqlite3.Connection, error_text: str, cause: str, fix: str, source: str = "ai_escalation"
) -> None:
    """Caches a confirmed cause/fix for an error, so the next person
    (or the same operator on a future box) who hits it gets an instant,
    free, local answer instead of re-escalating to AI."""
    conn.execute(
        "INSERT INTO error_patterns (error_text, cause, fix, source) VALUES (?, ?, ?, ?)",
        (error_text, cause, fix, source),
    )
    conn.commit()


def build_error_escalation_prompt(error_text: str) -> str:
    """Format a tight, copy-pasteable question for the operator to bring
    to an AI assistant when this error has never been diagnosed before."""
    return (
        "I'm working a CTF/HTB-style box and hit this error. What's the likely "
        "cause, and what's the fix? Keep it to a short paragraph plus a concrete "
        f"fix I can run:\n\n    {error_text}\n"
    )
