"""Tests for the Update Framework's intake/review pipeline
(intake.py) -- see docs/UPDATE_FRAMEWORK.md."""
from __future__ import annotations

import pytest

from trinity.boxes import create_box
from trinity.explain import get_explanation
from trinity.errors import find_error_match
from trinity.intake import (
    approve_candidate,
    get_candidate,
    list_pending,
    reject_candidate,
    submit_candidate,
)


def test_submit_candidate_does_not_touch_real_tables(conn):
    submit_candidate(
        conn, "explanation", {"command": "nc -lvnp 4444", "explanation": "listens for a reverse shell"},
        "agent_harness",
    )
    assert get_explanation(conn, "nc -lvnp 4444") is None  # not live yet


def test_submit_rejects_invalid_kind(conn):
    with pytest.raises(ValueError):
        submit_candidate(conn, "not-a-real-kind", {}, "agent_harness")


def test_submit_rejects_invalid_source(conn):
    with pytest.raises(ValueError):
        submit_candidate(conn, "explanation", {"command": "x", "explanation": "y"}, "not-a-real-source")


def test_list_pending_only_shows_pending(conn):
    cid = submit_candidate(
        conn, "explanation", {"command": "nc -lvnp 4444", "explanation": "..."}, "agent_harness",
    )
    assert len(list_pending(conn)) == 1
    approve_candidate(conn, cid)
    assert list_pending(conn) == []


def test_approve_explanation_makes_it_live(conn):
    cid = submit_candidate(
        conn, "explanation",
        {"command": "nc -lvnp 4444", "explanation": "Listens on port 4444 for an incoming reverse shell connection."},
        "agent_harness",
    )
    approve_candidate(conn, cid, note="looks correct")
    assert get_explanation(conn, "nc -lvnp 4444") == "Listens on port 4444 for an incoming reverse shell connection."

    candidate = get_candidate(conn, cid)
    assert candidate.status == "approved"
    assert candidate.reviewer_note == "looks correct"
    assert candidate.reviewed_at is not None


def test_approve_error_pattern_makes_it_live(conn):
    cid = submit_candidate(
        conn, "error_pattern",
        {"error_text": "xyzzyerror unusual token", "cause": "a made up cause", "fix": "a made up fix"},
        "agent_harness",
    )
    approve_candidate(conn, cid)
    match = find_error_match(conn, "xyzzyerror unusual token")
    assert match is not None
    assert match.fix == "a made up fix"


def test_approve_kb_entry_makes_it_live(conn):
    cid = submit_candidate(
        conn, "kb_entry",
        {
            "title": "Made-up service backdoor (test)",
            "summary": "A fabricated summary for testing.",
            "match_service": "xyzzysvc",
            "severity": "critical",
        },
        "agent_harness",
    )
    approve_candidate(conn, cid)
    row = conn.execute(
        "SELECT * FROM kb_entries WHERE title = 'Made-up service backdoor (test)'"
    ).fetchone()
    assert row is not None
    # Provenance is preserved through approval (fixed bug: this used to
    # flatten every approved candidate to a hardcoded "ai_escalation"
    # regardless of its real source -- see intake.py's approve_candidate,
    # and findings/design_review_claude.md's A4.4/C3 for how this was found).
    assert row["source"] == "agent_harness"
    assert row["severity"] == "critical"


def test_reject_candidate_never_goes_live(conn):
    cid = submit_candidate(
        conn, "explanation", {"command": "nc -lvnp 4444", "explanation": "bad answer"}, "agent_harness",
    )
    reject_candidate(conn, cid, note="hallucinated, wrong port behavior")
    assert get_explanation(conn, "nc -lvnp 4444") is None
    candidate = get_candidate(conn, cid)
    assert candidate.status == "rejected"
    assert candidate.reviewer_note == "hallucinated, wrong port behavior"


def test_cannot_re_review_an_already_decided_candidate(conn):
    cid = submit_candidate(
        conn, "explanation", {"command": "nc -lvnp 4444", "explanation": "..."}, "agent_harness",
    )
    approve_candidate(conn, cid)
    with pytest.raises(ValueError):
        approve_candidate(conn, cid)
    with pytest.raises(ValueError):
        reject_candidate(conn, cid)


def test_candidate_can_be_box_scoped(conn):
    box = create_box(conn, "IntakeBox")
    cid = submit_candidate(
        conn, "explanation", {"command": "nc -lvnp 4444", "explanation": "..."},
        "agent_harness", box_id=box.id,
    )
    candidate = get_candidate(conn, cid)
    assert candidate.box_id == box.id


def test_method_candidate_approval_does_not_touch_db_only_flips_status(conn):
    # Method records live in methods_index/*.yaml, not a DB table --
    # approving a method candidate here only flips intake status; the
    # actual file write is methods.py's responsibility (it calls
    # approve_candidate AFTER writing the file).
    cid = submit_candidate(
        conn, "method",
        {"box_name": "TestBox", "category": "foothold", "technique": "x",
         "summary": "y", "source_url": "https://example.com", "author": "someone",
         "retrieved_at": "2026-01-01"},
        "methods_live_draft",
    )
    approve_candidate(conn, cid)
    candidate = get_candidate(conn, cid)
    assert candidate.status == "approved"
