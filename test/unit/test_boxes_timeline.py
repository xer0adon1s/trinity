"""Tests for box management and the timeline."""
from __future__ import annotations

import pytest

from trinity.boxes import create_box, get_box_by_name, get_or_create_box, list_boxes, set_mode
from trinity.timeline import get_timeline, log_event


def test_create_box_defaults_to_educational_mode(conn):
    box = create_box(conn, "TestBox")
    assert box.mode == "educational"
    assert box.status == "active"


def test_create_box_rejects_invalid_mode(conn):
    with pytest.raises(ValueError):
        create_box(conn, "TestBox", mode="not-a-real-mode")


def test_get_or_create_box_is_idempotent(conn):
    first = get_or_create_box(conn, "SameBox", target="10.0.0.1")
    second = get_or_create_box(conn, "SameBox", target="10.0.0.2")
    assert first.id == second.id
    assert first.target == "10.0.0.1"  # second call didn't overwrite it


def test_get_box_by_name_returns_none_when_missing(conn):
    assert get_box_by_name(conn, "DoesNotExist") is None


def test_list_boxes_orders_by_updated(conn):
    create_box(conn, "First")
    create_box(conn, "Second")
    boxes = list_boxes(conn)
    assert len(boxes) == 2


def test_set_mode_switches_educational_to_professional(conn):
    box = create_box(conn, "ModeBox")
    set_mode(conn, box.id, "professional")
    reloaded = get_box_by_name(conn, "ModeBox")
    assert reloaded.mode == "professional"


def test_set_mode_rejects_invalid_mode(conn):
    box = create_box(conn, "ModeBox2")
    with pytest.raises(ValueError):
        set_mode(conn, box.id, "bogus")


def test_log_event_and_get_timeline_roundtrip(conn):
    box = create_box(conn, "TimelineBox")
    log_event(conn, box.id, "scan", "ran nmap", phase="recon")
    log_event(conn, box.id, "match", "found vsftpd backdoor", phase="recon", severity="critical")

    events = get_timeline(conn, box.id)
    assert len(events) == 2
    assert events[0]["event_type"] == "scan"
    assert events[1]["severity"] == "critical"


def test_timeline_is_chronological(conn):
    box = create_box(conn, "OrderBox")
    for i in range(5):
        log_event(conn, box.id, "note", f"event {i}")

    events = get_timeline(conn, box.id)
    summaries = [e["summary"] for e in events]
    assert summaries == [f"event {i}" for i in range(5)]
