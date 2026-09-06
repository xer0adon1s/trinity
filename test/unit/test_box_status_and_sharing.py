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
