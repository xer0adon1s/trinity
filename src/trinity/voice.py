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
    """Bulk-insert/refresh the hand-authored corpus. Rows this function
    itself wrote (source='trinity_preseed') are UPSERTed on every
    connect() so a corpus wording fix in voice_seed.py actually reaches
    a machine that already connected once -- teaching prose is exactly
    the kind of content Alexander will want to revise mid-alpha, unlike
    e.g. schema rows. Any row with a DIFFERENT source (a future
    hand-edited or AI-reviewed row, once that exists) is left alone --
    same non-clobber contract as explain.seed_explanations and
    kb.seed.seed for everything that ISN'T Trinity's own preseed.
    Returns the number of rows inserted OR refreshed."""
    touched = 0
    for kb_title, parts in ENTRIES.items():
        existing = conn.execute(
            "SELECT source FROM voice_explanations WHERE kb_title = ?", (kb_title,)
        ).fetchone()
        if existing is not None and existing["source"] != "trinity_preseed":
            continue  # hand-edited/other-sourced row -- never overwrite
        conn.execute(
            """
            INSERT INTO voice_explanations
                (kb_title, what_it_is, why_it_happens, what_to_watch_for, phase, source)
            VALUES (?, ?, ?, ?, ?, 'trinity_preseed')
            ON CONFLICT(kb_title) DO UPDATE SET
                what_it_is = excluded.what_it_is,
                why_it_happens = excluded.why_it_happens,
                what_to_watch_for = excluded.what_to_watch_for,
                phase = excluded.phase
            """,
            (
                kb_title, parts["what_it_is"], parts["why_it_happens"],
                parts["what_to_watch_for"], parts.get("phase", "recon"),
            ),
        )
        touched += 1
    conn.commit()
    return touched


def _instance_paragraph(host: str | None, port: int | None, product: str | None,
                         version: str | None) -> str:
    """The one part of the Voice's output that's assembled locally
    rather than authored -- the student's actual host/port/version, so
    what's on screen can be checked directly against their own scan.
    Guaranteed substitution (real string formatting), not a "please
    quote this back" instruction to a model that might not comply."""
    if host and port is not None:
        where = f"{host}:{port}"
    elif host:
        where = host
    elif port is not None:
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
    shell_level: str | None = None,
) -> str | None:
    """Look up the hand-authored entry for an already-matched finding
    and render it with the student's instance data filled in. Returns
    None if there's no authored entry yet, if the match isn't
    confident enough to narrate (best_guess), or if the entry's phase
    is ahead of where this box actually is -- callers should fall back
    to the existing plain KB summary/why string in every case; the
    Voice is additive, never a hard dependency.

    The phase gate exists because the match engine can and does
    FTS-attach a later-phase KB entry (e.g. the SUID privesc entry) to
    an earlier-phase finding purely on shared vocabulary -- a plain
    recon-phase directory listing containing the word "root" is enough
    to rank the SUID entry into a finding's match list. Every
    individual authored paragraph is written phase-safely on its own,
    but nothing enforced that at display time until this gate:
    `shell_level=None` (recon/enum, no shell yet) can only narrate a
    'recon' entry; 'user' or 'root' unlocks 'privesc' too. This directly
    mirrors coach.py's own phase-ordering vocabulary and boxes.shell_level
    rather than inventing a second one."""
    if confidence not in NARRATABLE_CONFIDENCE:
        return None

    row = conn.execute(
        "SELECT what_it_is, why_it_happens, what_to_watch_for, phase "
        "FROM voice_explanations WHERE kb_title = ?",
        (kb_title,),
    ).fetchone()
    if row is None:
        return None
    if row["phase"] == "privesc" and shell_level not in ("user", "root"):
        return None

    instance = _instance_paragraph(host, port, product, version)
    return (
        f"{row['what_it_is']}\n\n"
        f"{row['why_it_happens']}\n\n"
        f"{instance}\n\n"
        f"{row['what_to_watch_for']}"
    )
