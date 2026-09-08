"""Tests for box status transitions (active/rooted/abandoned) and the
opt-in sharing bundle export."""
from __future__ import annotations

import json

from trinity.boxes import create_box, get_box, set_status, touch_active_box
from trinity.sharing import build_share_bundle, is_sharing_enabled, set_sharing_enabled
from trinity.state import ACTIVE_BOX_ID, get_state, set_state


def test_set_status_updates_box(conn):
    box = create_box(conn, "StatusBox")
    set_status(conn, box.id, "rooted")
    updated = get_box(conn, box.id)
    assert updated.status == "rooted"


def test_set_status_rejects_invalid_value(conn):
    box = create_box(conn, "StatusBox2")
    try:
        set_status(conn, box.id, "not_a_real_status")
        assert False, "should have raised"
    except ValueError:
        pass


def test_marking_rooted_clears_active_box_pointer(conn):
    box = create_box(conn, "StatusBox3")
    set_state(conn, ACTIVE_BOX_ID, str(box.id))
    set_status(conn, box.id, "rooted")
    assert get_state(conn, ACTIVE_BOX_ID) is None


def test_marking_active_does_not_touch_active_pointer(conn):
    box = create_box(conn, "StatusBox4")
    set_state(conn, ACTIVE_BOX_ID, str(box.id))
    set_status(conn, box.id, "active")
    assert get_state(conn, ACTIVE_BOX_ID) == str(box.id)


def test_marking_a_different_box_rooted_does_not_clear_unrelated_active_pointer(conn):
    box_a = create_box(conn, "StatusBoxA")
    box_b = create_box(conn, "StatusBoxB")
    set_state(conn, ACTIVE_BOX_ID, str(box_a.id))
    set_status(conn, box_b.id, "rooted")
    assert get_state(conn, ACTIVE_BOX_ID) == str(box_a.id)


def test_get_or_create_box_does_not_silently_touch_active_pointer(conn):
    # Regression test: get_or_create_box is used by administrative
    # commands (box-status, report, explain, box-mode) that look a box
    # up by name without that meaning "the operator is now working
    # this box." Only touch_active_box (called explicitly from
    # parse-nmap/watch) should move the active-box pointer.
    from trinity.boxes import get_or_create_box

    box_a = create_box(conn, "TouchBoxA")
    box_b = create_box(conn, "TouchBoxB")
    touch_active_box(conn, box_a.id)

    get_or_create_box(conn, "TouchBoxB")  # a mere lookup, not "now working this"
    assert get_state(conn, ACTIVE_BOX_ID) == str(box_a.id)


def test_sharing_disabled_by_default(conn):
    assert is_sharing_enabled(conn) is False


def test_sharing_can_be_enabled(conn):
    set_sharing_enabled(conn, True)
    assert is_sharing_enabled(conn) is True


def test_build_share_bundle_excludes_identifying_fields(conn):
    box = create_box(conn, "ShareBox", target="10.10.10.99")
    conn.execute(
        "INSERT INTO command_explanations (command, explanation, source) VALUES (?, ?, ?)",
        ("nmap -sC -sV -p- 10.10.10.99", "explains nmap flags", "ai_escalation"),
    )
    conn.commit()
    conn.execute(
        "INSERT INTO timeline (box_id, event_type, summary) VALUES (?, 'explanation', ?)",
        (box.id, "explained: nmap -sC -sV -p- 10.10.10.99"),
    )
    conn.commit()

    bundle = build_share_bundle(conn, box.id)
    assert len(bundle.explanation_candidates) == 1
    # The bundle only carries command/explanation text -- no box name,
    # no target IP field, no operator-identifying data structurally
    # present in the candidate dict itself.
    candidate = bundle.explanation_candidates[0]
    assert set(candidate.keys()) == {"command", "explanation"}


def test_build_share_bundle_is_scoped_to_this_box_only(conn):
    # Regression test for Cursor's review finding: command_explanations
    # is a GLOBAL table, not box-scoped. Exporting "box A's bundle"
    # must not leak an AI-escalation explanation that was actually
    # encountered while working an unrelated box B.
    box_a = create_box(conn, "ShareBoxA")
    box_b = create_box(conn, "ShareBoxB")

    conn.execute(
        "INSERT INTO command_explanations (command, explanation, source) VALUES (?, ?, ?)",
        ("some-command-from-box-b", "explanation text", "ai_escalation"),
    )
    conn.commit()
    # Only box B's timeline references this explanation.
    conn.execute(
        "INSERT INTO timeline (box_id, event_type, summary) VALUES (?, 'explanation', ?)",
        (box_b.id, "explained: some-command-from-box-b"),
    )
    conn.commit()

    bundle_a = build_share_bundle(conn, box_a.id)
    bundle_b = build_share_bundle(conn, box_b.id)
    assert bundle_a.explanation_candidates == []
    assert len(bundle_b.explanation_candidates) == 1


def test_build_share_bundle_excludes_finding_detail(conn):
    # Regression test: finding.detail (banners/script output) can
    # carry hostnames/usernames and must never be exported, even
    # though it's a legitimately useful field for local KB matching.
    box = create_box(conn, "ShareBoxDetail")
    conn.execute(
        "INSERT INTO findings (box_id, source_tool, kind, host, port, product, version, detail, matched) "
        "VALUES (?, 'nmap', 'port', 'host', 80, 'SomeProduct', '1.0', 'sensitive banner with hostname', 0)",
        (box.id,),
    )
    conn.commit()

    bundle = build_share_bundle(conn, box.id)
    assert len(bundle.kb_candidates) == 1
    assert "detail" not in bundle.kb_candidates[0]
    assert "sensitive banner" not in json.dumps(bundle.kb_candidates)


def test_valid_sources_subset_of_ai_sourced():
    # Pinning test: intake's approved-candidate sources and sharing's
    # export filter are two halves of one vocabulary. If a new intake
    # source is added without adding it to db.AI_SOURCED, approved
    # entries carrying it silently drop out of every share bundle --
    # exactly the Fix 1 bug, caught at definition time rather than
    # after an operator notices an empty export.
    from trinity import db, intake

    assert intake.VALID_SOURCES <= db.AI_SOURCED


def test_source_vocabularies_are_immutable():
    # intake.VALID_SOURCES is an alias of db.INTAKE_SOURCES, and
    # db.AI_SOURCED is derived from it once at import time. If the
    # underlying set were mutable, VALID_SOURCES.add("new_source")
    # would widen what intake accepts while leaving AI_SOURCED (and so
    # the share-export filter) stale -- the Fix 1 divergence again, but
    # at runtime where no test can see it. frozenset makes that a
    # TypeError at the call site.
    from trinity import db, intake

    assert isinstance(db.INTAKE_SOURCES, frozenset)
    assert isinstance(db.AI_SOURCED, frozenset)
    assert not hasattr(intake.VALID_SOURCES, "add")


def test_direct_write_path_defaults_are_ai_sourced():
    # The other half of the same vocabulary: the direct write paths
    # (explain/error caching, not going through intake) default to a
    # source that must also be share-exportable.
    import inspect

    from trinity import db
    from trinity.errors import save_error_fix
    from trinity.explain import save_explanation

    assert inspect.signature(save_explanation).parameters["source"].default in db.AI_SOURCED
    assert inspect.signature(save_error_fix).parameters["source"].default in db.AI_SOURCED


def test_approved_intake_explanation_is_share_exportable(conn):
    # Regression test for Fix 1, going through the REAL path
    # (submit -> approve -> export) rather than inserting a
    # command_explanations row directly. Inserting directly is why the
    # original bug survived: every existing test hardcoded
    # source='ai_escalation', which is precisely the value
    # approve_candidate stopped writing.
    from trinity.intake import approve_candidate, submit_candidate

    box = create_box(conn, "IntakeShareBox")
    command = "smbclient -L //fileserver.local -N"
    candidate_id = submit_candidate(
        conn,
        "explanation",
        {"command": command, "explanation": "lists SMB shares anonymously"},
        source="agent_harness",
        box_id=box.id,
    )
    approve_candidate(conn, candidate_id)
    # The candidate landed with its real provenance, not 'ai_escalation'.
    stored_source = conn.execute(
        "SELECT source FROM command_explanations WHERE command = ?", (command,)
    ).fetchone()["source"]
    assert stored_source == "agent_harness"

    conn.execute(
        "INSERT INTO timeline (box_id, event_type, summary) VALUES (?, 'explanation', ?)",
        (box.id, f"explained: {command}"),
    )
    conn.commit()

    bundle = build_share_bundle(conn, box.id)
    assert [c["command"] for c in bundle.explanation_candidates] == [command]


def test_approved_intake_error_pattern_is_share_exportable(conn):
    # Same regression, the error_patterns half of the WHERE clause.
    from trinity.intake import approve_candidate, submit_candidate

    box = create_box(conn, "IntakeShareErrorBox")
    error_text = "NT_STATUS_ACCESS_DENIED listing \\\\*"
    candidate_id = submit_candidate(
        conn,
        "error_pattern",
        {"error_text": error_text, "cause": "anonymous listing refused", "fix": "supply credentials"},
        source="assimilator",
        box_id=box.id,
    )
    approve_candidate(conn, candidate_id)

    conn.execute(
        "INSERT INTO timeline (box_id, event_type, summary) VALUES (?, 'explanation', ?)",
        (box.id, f"diagnosed error: {error_text}"),
    )
    conn.commit()

    bundle = build_share_bundle(conn, box.id)
    assert [c["error_text"] for c in bundle.error_candidates] == [error_text]


def test_approved_intake_explanation_stays_box_scoped(conn):
    # Widening the source filter must not widen the box scope: an
    # approved non-'ai_escalation' explanation encountered while
    # working box B must still be absent from box A's bundle.
    from trinity.intake import approve_candidate, submit_candidate

    box_a = create_box(conn, "IntakeScopeA")
    box_b = create_box(conn, "IntakeScopeB")
    command = "gobuster dir -u http://webhost.local -w /list.txt"
    candidate_id = submit_candidate(
        conn,
        "explanation",
        {"command": command, "explanation": "brute-forces web paths"},
        source="methods_live_draft",
        box_id=box_b.id,
    )
    approve_candidate(conn, candidate_id)
    conn.execute(
        "INSERT INTO timeline (box_id, event_type, summary) VALUES (?, 'explanation', ?)",
        (box_b.id, f"explained: {command}"),
    )
    conn.commit()

    assert build_share_bundle(conn, box_a.id).explanation_candidates == []
    assert len(build_share_bundle(conn, box_b.id).explanation_candidates) == 1
