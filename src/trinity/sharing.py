"""Opt-in community data sharing: exports a box's KB-worthy discoveries
(new-to-Trinity matches, AI-sourced explanations that got confirmed
correct) in a shareable, anonymized format that could be PRed upstream
to grow the shared KB/explain-seed libraries.

Deliberately NOT automatic and NOT a live network push -- this only
ever writes a local file the operator reviews and sends (via a PR, or
any channel) themselves. Trinity never phones home on its own; opt-in
means opt-in at every step, not just at a one-time toggle.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

_IPV4 = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


def scrub_identifying(text: str) -> str:
    """Replace baked IPv4s so a share bundle cannot leak a lab target.
    Debate 2.13 claimed $TARGET would do this 'for free'; it does not
    unless we scrub here — suggestion commands are not in the bundle."""
    return _IPV4.sub("$TARGET", text)

from trinity import db
from trinity.state import get_state, set_state

SHARING_ENABLED_KEY = "sharing_enabled"


def _placeholders(values) -> str:
    """`?,?,?` for a parameterized IN clause."""
    return ",".join("?" for _ in values)


def is_sharing_enabled(conn: sqlite3.Connection) -> bool:
    return get_state(conn, SHARING_ENABLED_KEY) == "1"


def set_sharing_enabled(conn: sqlite3.Connection, enabled: bool) -> None:
    set_state(conn, SHARING_ENABLED_KEY, "1" if enabled else "0")


@dataclass
class ShareBundle:
    """What would actually get exported. Intentionally excludes target
    IPs, box names, and anything else that could identify a specific
    person/engagement -- only the generalizable knowledge (product +
    version + what it means) is shareable."""
    kb_candidates: list[dict] = field(default_factory=list)
    explanation_candidates: list[dict] = field(default_factory=list)
    error_candidates: list[dict] = field(default_factory=list)


def build_share_bundle(conn: sqlite3.Connection, box_id: int) -> ShareBundle:
    """Gathers THIS box's AI-sourced explanations/error-fixes and any
    novel findings that had no local KB match (the exact gaps a shared
    KB should grow to cover) -- stripped of anything box/target/
    operator-identifying.

    "AI-sourced" means every provenance in db.AI_SOURCED, not just the
    'ai_escalation' direct-write default: entries that arrived through
    intake.py's approve_candidate() keep their real source
    ('agent_harness'/'methods_live_draft'/'assimilator') and are just
    as shareable. Filtering on 'ai_escalation' alone silently dropped
    all of them.

    Scoping note: `command_explanations` and `error_patterns` are
    global caches (not box-scoped tables), so this only includes rows
    that were actually REFERENCED from this box's own timeline (i.e.
    genuinely encountered while working this box) rather than every
    AI-sourced explanation ever cached on the machine across every box
    ever worked -- exporting "this box's export" must not leak
    unrelated engagements' cached data.
    """
    bundle = ShareBundle()

    explained_commands = {
        row["summary"].removeprefix("explained: ")
        for row in conn.execute(
            "SELECT summary FROM timeline WHERE box_id = ? AND event_type = 'explanation' "
            "AND summary LIKE 'explained: %'",
            (box_id,),
        ).fetchall()
    }
    if explained_commands:
        # Every AI-sourced provenance, not just 'ai_escalation':
        # intake.py's approve_candidate() preserves a candidate's real
        # source ('agent_harness'/'methods_live_draft'/'assimilator'),
        # so filtering on the direct-write-path default alone silently
        # dropped every approved-candidate entry from the export.
        ai_sources = sorted(db.AI_SOURCED)
        explanations = conn.execute(
            f"SELECT command, explanation FROM command_explanations "
            f"WHERE source IN ({_placeholders(ai_sources)}) "
            f"AND command IN ({_placeholders(explained_commands)})",
            (*ai_sources, *explained_commands),
        ).fetchall()
        for row in explanations:
            bundle.explanation_candidates.append(
                {
                    "command": scrub_identifying(row["command"]),
                    "explanation": scrub_identifying(row["explanation"]),
                }
            )

    diagnosed_errors = {
        row["summary"].removeprefix("diagnosed error: ")
        for row in conn.execute(
            "SELECT summary FROM timeline WHERE box_id = ? AND event_type = 'explanation' "
            "AND summary LIKE 'diagnosed error: %'",
            (box_id,),
        ).fetchall()
    }
    if diagnosed_errors:
        # Timeline truncates the error text to 80 chars (see
        # cli/main.py's error_cmd), so match by prefix rather than
        # exact equality.
        ai_sources = sorted(db.AI_SOURCED)  # see the note on the explanations query above
        error_rows = conn.execute(
            f"SELECT error_text, cause, fix FROM error_patterns "
            f"WHERE source IN ({_placeholders(ai_sources)})",
            tuple(ai_sources),
        ).fetchall()
        for row in error_rows:
            if any(row["error_text"].startswith(prefix) for prefix in diagnosed_errors):
                bundle.error_candidates.append(
                    {"error_text": row["error_text"], "cause": row["cause"], "fix": row["fix"]}
                )

    # Deliberately sourced from unmatched `findings`, never from
    # `kb_entries` -- share the GAP (a product/version the local KB had
    # no answer for), not the answer someone wrote for it. Approved
    # `kb_entry` intake candidates are therefore unreachable here by
    # design; that is not an oversight, do not "fix" it.
    unmatched = conn.execute(
        """
        SELECT source_tool, kind, service, product, version
        FROM findings
        WHERE box_id = ? AND matched = 0 AND product IS NOT NULL
        """,
        (box_id,),
    ).fetchall()
    for row in unmatched:
        # Deliberately excludes `detail` -- nmap script output/banners
        # routinely contain hostnames, usernames, or other engagement-
        # identifying text that has no business in a "generalizable
        # knowledge" export.
        bundle.kb_candidates.append(dict(row))

    return bundle


def write_share_bundle(conn: sqlite3.Connection, box_id: int, output_path: Path) -> int:
    """Writes the share bundle to a local JSON file for manual review
    before it's ever sent anywhere. Returns the total item count."""
    bundle = build_share_bundle(conn, box_id)
    output_path.write_text(json.dumps({
        "kb_candidates": bundle.kb_candidates,
        "explanation_candidates": bundle.explanation_candidates,
        "error_candidates": bundle.error_candidates,
    }, indent=2))
    return len(bundle.kb_candidates) + len(bundle.explanation_candidates) + len(bundle.error_candidates)
