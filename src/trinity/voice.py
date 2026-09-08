"""Trinity's Voice v1 -- plain-English teaching narration over an
already-established finding + KB match.

DESIGN: docs/TRINITY_VOICE_DESIGN.md. Read that first if you're
extending this -- it records why v1 is a hand-authored corpus with a
deterministic local renderer rather than live AI generation (two
independent design reviews found real, unresolved gaps in the
live-generation design: no spoiler gate exists to reuse, no stable
cache key exists in the schema, and injecting live attacker-controlled
banner text into an AI CLI automatically is a real prompt-injection
surface). Live generation is deferred to a v2 that doesn't exist yet.

This module does ONE thing: given a finding that's already been
identified and matched by the local engine (no detection happens
here), look up the hand-authored corpus entry for that match's KB
title, and render it with the student's actual instance data
substituted in. No network calls, no subprocess, no AI CLI invocation
-- fully deterministic and fully unit-testable.
"""
from __future__ import annotations

import sqlite3

from trinity.voice_seed import ENTRIES

# Matches confident enough to narrate. A `best_guess` searchsploit hit
# (an unvetted keyword match -- see match/engine.py's KBMatch.confidence
# docstring) dressed up in four confident instructor paragraphs would
# launder its own uncertainty; the dim "(best guess)" hedge already
# shown in the feed is honest, four paragraphs of prose on top of it
# would not be. Same principle as quarantine finding #6.
NARRATABLE_CONFIDENCE = {"confirmed", "likely"}


def seed_voice_entries(conn: sqlite3.Connection) -> int:
    """Bulk-insert the hand-authored corpus, skipping any kb_title that
    already has an entry (never overwrites something hand-edited after
    the fact, same non-destructive contract as explain.seed_explanations
    and kb.seed.seed). Returns the number of rows actually inserted."""
    inserted = 0
    for kb_title, parts in ENTRIES.items():
        exists = conn.execute(
            "SELECT 1 FROM finding_explanations WHERE kb_title = ?", (kb_title,)
        ).fetchone()
        if exists:
            continue
        conn.execute(
            """
            INSERT INTO finding_explanations
                (kb_title, what_it_is, why_it_happens, what_to_watch_for, source)
            VALUES (?, ?, ?, ?, 'trinity_preseed')
            """,
            (kb_title, parts["what_it_is"], parts["why_it_happens"], parts["what_to_watch_for"]),
        )
        inserted += 1
    conn.commit()
    return inserted


def _instance_paragraph(host: str | None, port: int | None, product: str | None,
                         version: str | None) -> str:
    """The one part of the Voice's output that's assembled locally
    rather than authored -- the student's actual host/port/version, so
    what's on screen can be checked directly against their own scan.
    Guaranteed substitution (real string formatting), not a "please
    quote this back" instruction to a model that might not comply."""
    if host and port:
        where = f"{host}:{port}"
    elif host:
        where = host
    elif port:
        where = f"port {port}"
    else:
        where = "this target"

    what = " ".join(p for p in (product, version) if p) or None
    if what:
        return f"On your scan, this showed up at {where} as {what}."
    return f"On your scan, this showed up at {where}."


def get_voice_text(
    conn: sqlite3.Connection,
    kb_title: str,
    confidence: str,
    *,
    host: str | None = None,
    port: int | None = None,
    product: str | None = None,
    version: str | None = None,
) -> str | None:
    """Look up the hand-authored entry for an already-matched finding
    and render it with the student's instance data filled in. Returns
    None if there's no authored entry yet, or if the match isn't
    confident enough to narrate (best_guess) -- callers should fall
    back to the existing plain KB summary/why string in either case;
    the Voice is additive, never a hard dependency."""
    if confidence not in NARRATABLE_CONFIDENCE:
        return None

    row = conn.execute(
        "SELECT what_it_is, why_it_happens, what_to_watch_for "
        "FROM finding_explanations WHERE kb_title = ?",
        (kb_title,),
    ).fetchone()
    if row is None:
        return None

    instance = _instance_paragraph(host, port, product, version)
    return (
        f"{row['what_it_is']}\n\n"
        f"{row['why_it_happens']}\n\n"
        f"{instance}\n\n"
        f"{row['what_to_watch_for']}"
    )
