"""PROTOTYPE tests for the loot / evidence tracker."""
from __future__ import annotations

import pytest

from trinity.boxes import create_box
from trinity.loot import add_loot, list_loot
from trinity.report.data import gather_report_data
from trinity.report.render import render_report
from trinity.timeline import get_timeline


def test_add_and_list_loot(conn):
    box = create_box(conn, "LootBox")
    item = add_loot(conn, box.id, "flag", "HTB{demo}", note="user.txt")
    assert item.kind == "flag"
    assert item.value == "HTB{demo}"
    listed = list_loot(conn, box.id)
    assert len(listed) == 1
    assert listed[0].note == "user.txt"


def test_loot_writes_a_timeline_event(conn):
    box = create_box(conn, "LootTl")
    add_loot(conn, box.id, "hash", "$1$aaa")
    events = get_timeline(conn, box.id)
    assert any(e["event_type"] == "loot" and "$1$aaa" in e["summary"] for e in events)


def test_loot_rejects_unknown_kind(conn):
    box = create_box(conn, "LootBad")
    with pytest.raises(ValueError):
        add_loot(conn, box.id, "password", "x")


def test_loot_shows_in_both_report_modes(conn):
    box = create_box(conn, "LootReport")
    add_loot(conn, box.id, "credential", "admin:admin", note="tomcat")
    data = gather_report_data(conn, box.id)
    assert len(data.loot) == 1
    edu = render_report(data, "educational")
    pro = render_report(data, "professional")
    assert "admin:admin" in edu
    assert "What you pocketed" in edu
    assert "admin:admin" in pro
    assert "Recovered Evidence" in pro


def test_render_report_rejects_unknown_mode(conn):
    box = create_box(conn, "LootMode")
    data = gather_report_data(conn, box.id)
    with pytest.raises(ValueError):
        render_report(data, "pdf")
