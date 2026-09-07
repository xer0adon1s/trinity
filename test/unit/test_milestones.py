"""PROTOTYPE tests for name-the-win / privesc deck."""
from __future__ import annotations

import pytest

from trinity.boxes import create_box, get_box
from trinity.coach import get_recommendation
from trinity.milestones import record_shell
from trinity.timeline import get_timeline


def test_record_user_shell_injects_privesc_deck(conn):
    box = create_box(conn, "ShellBox")
    inserted = record_shell(conn, box.id, "user")
    assert "sudo -l" in inserted
    assert "id" in inserted
    reloaded = get_box(conn, box.id)
    assert reloaded.shell_level == "user"
    assert reloaded.status == "active"
    rec = get_recommendation(conn, box.id)
    assert rec is not None
    assert rec.top.phase == "privesc"


def test_record_user_shell_is_idempotent(conn):
    box = create_box(conn, "ShellBox2")
    first = record_shell(conn, box.id, "user")
    second = record_shell(conn, box.id, "user")
    assert first
    assert second == []


def test_record_root_shell_marks_box_rooted(conn):
    box = create_box(conn, "RootBox")
    record_shell(conn, box.id, "root")
    reloaded = get_box(conn, box.id)
    assert reloaded.shell_level == "root"
    assert reloaded.status == "rooted"


def test_will_not_demote_root_to_user(conn):
    box = create_box(conn, "NoDemote")
    record_shell(conn, box.id, "root")
    record_shell(conn, box.id, "user")
    assert get_box(conn, box.id).shell_level == "root"


def test_invalid_level_rejected(conn):
    box = create_box(conn, "BadShell")
    with pytest.raises(ValueError):
        record_shell(conn, box.id, "wheel")


def test_shell_writes_a_timeline_milestone(conn):
    box = create_box(conn, "TlShell")
    record_shell(conn, box.id, "user")
    events = get_timeline(conn, box.id)
    assert any(e["event_type"] == "milestone" and "user shell" in e["summary"] for e in events)
    assert any(e["event_type"] == "suggestion" and "sudo -l" in e["summary"] for e in events)
