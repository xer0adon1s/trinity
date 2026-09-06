"""Tests for the suggestion engine."""
from __future__ import annotations

from trinity.boxes import create_box
from trinity.suggest.engine import suggest_next_commands


def _insert_finding(conn, box_id, **kwargs):
    defaults = {
        "source_tool": "nmap", "kind": "port", "host": "10.10.10.3",
        "port": None, "service": None, "product": None, "version": None,
    }
    defaults.update(kwargs)
    conn.execute(
        """
        INSERT INTO findings (box_id, source_tool, kind, host, port, service, product, version)
        VALUES (:box_id, :source_tool, :kind, :host, :port, :service, :product, :version)
        """,
        {"box_id": box_id, **defaults},
    )
    conn.commit()


def test_http_port_suggests_gobuster(conn):
    box = create_box(conn, "TestBox")
    _insert_finding(conn, box.id, port=80, service="http")

    suggestions = suggest_next_commands(conn, box.id)
    assert any("gobuster" in s.command for s in suggestions)


def test_smb_port_suggests_enum4linux(conn):
    box = create_box(conn, "TestBox")
    _insert_finding(conn, box.id, port=445, service="microsoft-ds")

    suggestions = suggest_next_commands(conn, box.id)
    assert any("enum4linux" in s.command for s in suggestions)


def test_ftp_port_suggests_anonymous_login(conn):
    box = create_box(conn, "TestBox")
    _insert_finding(conn, box.id, port=21, service="ftp")

    suggestions = suggest_next_commands(conn, box.id)
    assert any("ftp " in s.command for s in suggestions)


def test_ssh_port_suggests_searchsploit(conn):
    box = create_box(conn, "TestBox")
    _insert_finding(conn, box.id, port=22, service="ssh", product="OpenSSH", version="4.7p1")

    suggestions = suggest_next_commands(conn, box.id)
    assert any("searchsploit" in s.command for s in suggestions)


def test_already_suggested_commands_are_not_repeated(conn):
    box = create_box(conn, "TestBox")
    _insert_finding(conn, box.id, port=80, service="http")

    first_pass = suggest_next_commands(conn, box.id)
    assert len(first_pass) == 1

    # Simulate the CLI persisting the suggestion, as parse-nmap/suggest do.
    conn.execute(
        "INSERT INTO suggestions (box_id, phase, command, rationale) VALUES (?, ?, ?, ?)",
        (box.id, first_pass[0].phase, first_pass[0].command, first_pass[0].rationale),
    )
    conn.commit()

    second_pass = suggest_next_commands(conn, box.id)
    assert second_pass == []


def test_unrecognized_service_yields_no_suggestion(conn):
    box = create_box(conn, "TestBox")
    _insert_finding(conn, box.id, port=9999, service="totally-obscure-thing")

    suggestions = suggest_next_commands(conn, box.id)
    assert suggestions == []


def test_multiple_findings_yield_multiple_distinct_suggestions(conn):
    box = create_box(conn, "TestBox")
    _insert_finding(conn, box.id, port=80, service="http")
    _insert_finding(conn, box.id, port=445, service="microsoft-ds")
    _insert_finding(conn, box.id, port=21, service="ftp")

    suggestions = suggest_next_commands(conn, box.id)
    assert len(suggestions) == 3
    commands = {s.command for s in suggestions}
    assert len(commands) == 3  # all distinct
