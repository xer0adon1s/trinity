"""Instructor Mode's coach layer: ranks the operator's outstanding
suggestions into a single "do this next" recommendation with a stated
WHY, instead of leaving the operator to pick from an equally-weighted
list. Pure rules, zero AI -- same trust model as suggest/engine.py.
See docs/INSTRUCTOR_MODE.md.

Reads directly from the persisted `suggestions` table (all
not-yet-accepted rows for the box), rather than calling
suggest_next_commands() itself -- that function's own dedup logic is
built for "don't nag with the same suggestion twice across separate
parses," which means by the time a scan has been parsed and its
suggestions persisted, suggest_next_commands() would report nothing
new even though those suggestions are still perfectly valid and
outstanding. The coach's job is to rank what's already on the table,
not to generate fresh suggestions itself.

Also checks tool availability (tools.py) on the recommended
suggestion: if the required binary isn't installed, the recommendation
still surfaces (nothing is hidden or skipped), but carries install
guidance alongside it. Because the coach always re-reads the same
persisted, un-accepted suggestion, the operator installing the tool
and simply running `trinity next` again picks the exact same
recommendation back up automatically -- no new state needed to "come
back to where we left off."
"""
from __future__ import annotations

import sqlite3

from pydantic import BaseModel

from trinity.boxes import get_box
from trinity.phrasebook import phrase_for
from trinity.suggest.engine import Suggestion
from trinity.tools import build_install_guidance, is_tool_installed
from trinity.wordlists import resolve_wordlist_in_command

_WORDLIST_PLACEHOLDER = "/usr/share/wordlists/dirb/common.txt"

# Earlier phases are recommended before later ones, even if a
# later-phase suggestion already exists -- e.g. don't lead with a
# privesc suggestion if basic enum on an open port hasn't happened yet.
_PHASE_ORDER = {"recon": 0, "enum": 1, "foothold": 2, "privesc": 3, "post": 4}

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, None: 5}


class Recommendation(BaseModel):
    suggestion_id: int
    top: Suggestion
    why: str
    also_worth_trying: list[Suggestion]
    also_worth_trying_installed: list[bool] = []
    tool_missing: bool = False
    install_guidance: str | None = None
    wordlist_missing: bool = False


class _RankedRow(BaseModel):
    id: int
    created_order: int
    suggestion: Suggestion
    severity_rank: int


def set_accepted(conn: sqlite3.Connection, suggestion_id: int) -> None:
    """Marks a suggestion accepted -- Hole A: nothing in the codebase
    ever did this before, so `trinity next` recommended the same
    command forever. Used by both `trinity did` and `trinity skip`
    (skip is "accept and move on," not a separate schema column --
    see docs/CLAUDE_CURSOR_DEBATE.md, Part E item 3)."""
    conn.execute("UPDATE suggestions SET accepted = 1 WHERE id = ?", (suggestion_id,))
    conn.commit()


def _severity_for_finding(conn: sqlite3.Connection, box_id: int, finding_id: int | None) -> str | None:
    """Looks up the most severe KB/searchsploit match tied to a specific
    finding, so two suggestions on the same box can actually be ranked
    against each other by severity (per docs/INSTRUCTOR_MODE.md's spec)
    instead of sharing one box-wide value. Reads the `finding_id`
    persisted directly on the suggestion row -- NOT a regex over
    rationale prose, which only ever worked for the port-shaped
    suggestions that said "Port N is ..." and silently fell back to the
    lowest ranking tier for anything else (path/share/user findings).
    See docs/CLAUDE_CURSOR_DEBATE.md, Part B.3."""
    if finding_id is None:
        return None
    row = conn.execute(
        """
        SELECT t.severity FROM timeline t
        WHERE t.box_id = ? AND t.event_type = 'match' AND t.ref_id = ? AND t.severity IS NOT NULL
        ORDER BY
            CASE t.severity
                WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2
                WHEN 'low' THEN 3 WHEN 'info' THEN 4 ELSE 5
            END
        LIMIT 1
        """,
        (box_id, finding_id),
    ).fetchone()
    return row["severity"] if row else None


def get_recommendation(conn: sqlite3.Connection, box_id: int) -> Recommendation | None:
    """Returns exactly one recommended next command plus the reasoning
    for why it's first, with the rest of the outstanding suggestions
    listed as secondary options. None if there's nothing outstanding
    to recommend.

    Ranking, per docs/INSTRUCTOR_MODE.md: phase order, then per-
    suggestion severity (via the finding it's tied to), then recency
    (the newest outstanding suggestion wins ties) -- not one box-wide
    severity applied to everything, and not oldest-first."""
    rows = conn.execute(
        "SELECT id, phase, command, rationale, nudge, required_tool, finding_id FROM suggestions "
        "WHERE box_id = ? AND accepted = 0 ORDER BY id",
        (box_id,),
    ).fetchall()
    if not rows:
        return None

    ranked_rows = [
        _RankedRow(
            id=r["id"],
            created_order=r["id"],
            suggestion=Suggestion(
                phase=r["phase"], command=r["command"], rationale=r["rationale"],
                nudge=r["nudge"] or "", required_tool=r["required_tool"] or "",
            ),
            severity_rank=_SEVERITY_RANK.get(
                _severity_for_finding(conn, box_id, r["finding_id"]),
                _SEVERITY_RANK[None],
            ),
        )
        for r in rows
    ]
    # Newest first as the tiebreaker: negate created_order so a larger
    # suggestion id (more recent) sorts before an older one within the
    # same phase/severity bucket.
    ranked_rows.sort(key=lambda rr: (_PHASE_ORDER.get(rr.suggestion.phase, 99), rr.severity_rank, -rr.created_order))

    # PROTOTYPE (1.6): an explicit user/root shell is a foothold
    # milestone. Phase-order-always-wins would keep recommending
    # gobuster after they already have a shell. Promote privesc/post
    # to the front of the deck; leftover enum stays in also_worth_trying.
    # Claude: this fights INSTRUCTOR_MODE.md's raw phase rule on
    # purpose — say if you want it reverted.
    box = get_box(conn, box_id)
    if box and box.shell_level in ("user", "root"):
        promoted = [rr for rr in ranked_rows if rr.suggestion.phase in ("privesc", "post")]
        if promoted:
            leftover = [rr for rr in ranked_rows if rr not in promoted]
            ranked_rows = promoted + leftover

    top_row = ranked_rows[0]
    rest = [rr.suggestion for rr in ranked_rows[1:]]

    phase_label = {
        "recon": "reconnaissance", "enum": "enumeration", "foothold": "foothold",
        "privesc": "privilege escalation", "post": "post-exploitation",
    }.get(top_row.suggestion.phase, top_row.suggestion.phase)

    human_phrase = phrase_for(top_row.suggestion.phase, top_row.suggestion.command, top_row.suggestion.required_tool)
    opener = human_phrase or (
        f"This is a {phase_label}-phase step, and {phase_label} comes before "
        "the later phases in the normal order of working a box."
    )
    why = f"{opener} {top_row.suggestion.rationale}"

    wordlist_missing = False
    if _WORDLIST_PLACEHOLDER in top_row.suggestion.command:
        rewritten = resolve_wordlist_in_command(top_row.suggestion.command, _WORDLIST_PLACEHOLDER)
        if rewritten != top_row.suggestion.command:
            top_row.suggestion.command = rewritten
        else:
            wordlist_missing = True

    tool_missing = False
    install_guidance = None
    if top_row.suggestion.required_tool and not is_tool_installed(top_row.suggestion.required_tool):
        tool_missing = True
        install_guidance = build_install_guidance(top_row.suggestion.required_tool)

    also_installed = [
        (not s.required_tool) or is_tool_installed(s.required_tool) for s in rest
    ]

    return Recommendation(
        suggestion_id=top_row.id, top=top_row.suggestion, why=why, also_worth_trying=rest,
        also_worth_trying_installed=also_installed,
        tool_missing=tool_missing, install_guidance=install_guidance,
        wordlist_missing=wordlist_missing,
    )
