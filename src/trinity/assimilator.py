"""Assimilator: the diagnose -> hypothesize -> verify -> land engine
described in docs/ASSIMILATOR_PROJECT.md. Two triggers feed this SAME
loop -- an offline/batch sweep (Doc, against the Coverage Sim corpus)
and a live/on-demand trigger (a student's `trinity show-me`
invocation, see src/trinity/show_me.py and docs/SHOW_ME_MODE.md). Both
write into the same `assimilator_runs` leverage ledger.

This module owns the shared parts: the diagnosis taxonomy, the ledger
read/write, and the "already known" check that answers "did Trinity
already have this in the KB and the operator/engine just missed
routing to it" -- Alexander's explicit framing: "Assimilator should
take the show me data to ensure that our program doesn't get stuck
there again. OR to tell the user that it may have missed a solution
that was already programmed in."

v1 scope (this pass): the live trigger's diagnose/verify/land
mechanics, wired to Show Me Mode, so the core self-learning loop is
usable from round one of user testing. The offline/batch corpus sweep
(re-running all 122 Coverage Sim boxes) is NOT implemented in this
pass -- see docs/ASSIMILATOR_PROJECT.md §9 for that rollout, still
future work. Nothing here assumes the batch sweep exists; the schema
and taxonomy are shared so it can plug in later without a rewrite.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import datetime, timezone

from pydantic import BaseModel

# The 11-cause taxonomy from docs/ASSIMILATOR_PROJECT.md §3. Kept here
# (not re-derived from the doc at runtime) so it's a real, importable,
# type-checked contract other modules (show_me.py, future offline
# sweep code) share.
PRIMARY_CAUSES = {
    "missing_kb_entry", "searchsploit_routing", "missing_suggest_coverage",
    "capability_gap", "parser_gap", "false_negative_bug",
    "false_positive_match", "fixture_evidence_gap", "ranking_gap",
    "upstream_data_gap", "out_of_model",
}

FIX_SHAPES = {
    "kb_content", "routing_rule", "suggest_rule", "parser", "fixture",
    "sync_policy", "match_policy", "new_subsystem", "none",
}

RESULTS = {
    "verified_fix", "rejected_hypothesis", "escalated_capability_gap",
    "needs_policy_decision", "already_known",
}


class AlreadyKnownHit(BaseModel):
    """The 'you already had this, you just missed it' signal Alexander
    asked for explicitly: Trinity solved something live (via Show Me
    Mode) and it turns out the KB/suggest engine ALREADY covered this
    -- the student (or an earlier pass of the engine) just didn't
    route to it. This is a distinct, cheaper outcome than
    'verified_fix' (which means something NEW was learned) -- it means
    nothing needs to be added to the KB, but the routing/suggestion
    that should have surfaced it needs a look, and the student should
    be pointed back at what Trinity already knew.
    """
    kb_id: int | None
    title: str
    summary: str


def check_already_known(conn: sqlite3.Connection, service: str | None, product: str | None,
                         version: str | None, detail: str | None = None) -> AlreadyKnownHit | None:
    """Before treating a Show Me Mode success as new knowledge, check
    whether Trinity's own KB already covers it. Reuses match_finding's
    exact same lookup path (not a separate heuristic) so 'already
    known' means the same thing here as it does everywhere else in the
    engine. Returns the best existing match if the KB already had a
    real answer, None if this is genuinely new."""
    from trinity.match.engine import match_finding
    from trinity.parsers.nmap import Finding

    finding = Finding(
        source_tool="assimilator_check", kind="port", host=None, port=None,
        service=service, product=product, version=version, detail=detail,
    )
    matches = match_finding(conn, finding)
    # Only a real curated KB hit counts as "already known" -- a bare
    # searchsploit best-guess (see KBMatch.confidence) isn't a
    # confirmed prior answer, it's the same kind of unreviewed hit
    # Show Me Mode was invoked because the student couldn't resolve.
    for m in matches:
        if m.confidence in ("confirmed", "likely"):
            return AlreadyKnownHit(kb_id=m.kb_id, title=m.title, summary=m.summary)
    return None


def _current_commit() -> str | None:
    """Best-effort git SHA of the running Trinity install -- lets a
    ledger row be checked for staleness later (see
    docs/ASSIMILATOR_PROJECT.md §8's corrected 'stale capability_gap'
    example: 4 of 8 rows were fixed by a later commit and nobody
    noticed because nothing recorded which commit scored them).
    Returns None rather than raising if this isn't a git checkout
    (e.g. an installed wheel) -- staleness tracking degrading to
    unavailable is fine, crashing on it is not."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def start_run(
    conn: sqlite3.Connection,
    trigger: str,
    primary_cause: str,
    *,
    box_id: int | None = None,
    box_name: str | None = None,
    hypothesis: str | None = None,
    verification_method: str | None = None,
) -> int:
    """Opens a new assimilator_runs row. Returns its id -- callers
    finish it later via finish_run() once the outcome is known (a run
    can take real wall-clock time, especially the live trigger, so
    this is intentionally two calls, not one)."""
    if trigger not in ("offline", "live"):
        raise ValueError(f"trigger must be 'offline' or 'live', got {trigger!r}")
    if primary_cause not in PRIMARY_CAUSES:
        raise ValueError(f"primary_cause must be one of {PRIMARY_CAUSES}, got {primary_cause!r}")

    cursor = conn.execute(
        """
        INSERT INTO assimilator_runs
            (trigger, box_id, box_name, trinity_commit, primary_cause,
             hypothesis, verification_method, result)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'rejected_hypothesis')
        """,
        (trigger, box_id, box_name, _current_commit(), primary_cause,
         hypothesis, verification_method),
    )
    conn.commit()
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    result: str,
    *,
    self_lifted: bool = False,
    others_lifted: list[str] | None = None,
    already_known_hit: bool = False,
    intake_candidate_id: int | None = None,
    verification_evidence: str | None = None,
) -> None:
    """Closes out a run with its real outcome. `already_known_hit`
    is the specific signal Alexander asked for: Show Me Mode solved
    it, but the KB already had the answer -- see check_already_known()
    above."""
    if result not in RESULTS:
        raise ValueError(f"result must be one of {RESULTS}, got {result!r}")

    conn.execute(
        """
        UPDATE assimilator_runs SET
            result = ?, self_lifted = ?, others_lifted = ?,
            already_known_hit = ?, intake_candidate_id = ?,
            verification_evidence = ?, finished_at = ?
        WHERE id = ?
        """,
        (
            result, int(self_lifted), json.dumps(others_lifted or []),
            int(already_known_hit), intake_candidate_id, verification_evidence,
            datetime.now(timezone.utc).isoformat(), run_id,
        ),
    )
    conn.commit()


class LeverageSummary(BaseModel):
    total_runs: int
    verified_fixes: int
    already_known_hits: int
    escalated_capability_gaps: int
    others_lifted_total: int  # sum of len(others_lifted) across verified_fix runs


def leverage_summary(conn: sqlite3.Connection) -> LeverageSummary:
    """The headline reporting numbers from docs/ASSIMILATOR_PROJECT.md
    §7: not 'N partials fixed' but leverage (others_lifted) and how
    often Show Me Mode is rediscovering something Trinity already
    knew (already_known_hit) -- a high rate of that specifically means
    the ROUTING/SUGGESTION layer has a real gap even though the KB
    content itself is fine, a different fix shape than 'write a new KB
    entry'."""
    rows = conn.execute("SELECT result, others_lifted, already_known_hit FROM assimilator_runs").fetchall()
    total = len(rows)
    verified = sum(1 for r in rows if r["result"] == "verified_fix")
    already_known = sum(1 for r in rows if r["already_known_hit"])
    escalated = sum(1 for r in rows if r["result"] == "escalated_capability_gap")
    others_total = sum(
        len(json.loads(r["others_lifted"])) if r["others_lifted"] else 0
        for r in rows if r["result"] == "verified_fix"
    )
    return LeverageSummary(
        total_runs=total, verified_fixes=verified, already_known_hits=already_known,
        escalated_capability_gaps=escalated, others_lifted_total=others_total,
    )
