"""Tests for the suggestion engine."""
from __future__ import annotations

from trinity.boxes import create_box
from trinity.suggest.engine import suggest_next_commands


def _insert_finding(conn, box_id, **kwargs):
    defaults = {
        "source_tool": "nmap", "kind": "port", "host": "10.10.10.3",
        "port": None, "service": None, "product": None, "version": None,
        "detail": None,
    }
    defaults.update(kwargs)
    conn.execute(
        """
        INSERT INTO findings (box_id, source_tool, kind, host, port, service, product, version, detail)
        VALUES (:box_id, :source_tool, :kind, :host, :port, :service, :product, :version, :detail)
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


def test_every_suggestion_has_a_nonempty_nudge(conn):
    # Every suggestion rule must supply a `nudge` -- the tool-name-free
    # text used by the graduated hint ladder's level 2. A blank nudge
    # would silently fall back to a generic message, hiding the fact a
    # rule forgot to write one.
    box = create_box(conn, "TestBox")
    _insert_finding(conn, box.id, port=80, service="http")
    _insert_finding(conn, box.id, port=445, service="microsoft-ds")
    _insert_finding(conn, box.id, port=21, service="ftp")
    _insert_finding(conn, box.id, port=22, service="ssh", product="OpenSSH", version="7.4")

    suggestions = suggest_next_commands(conn, box.id)
    assert len(suggestions) == 4
    for s in suggestions:
        assert s.nudge and s.nudge.strip()


def test_anonymous_ftp_detail_skips_generic_check(conn):
    # Hole C "free win": nmap's own script output already confirmed
    # anonymous FTP login works -- Trinity should suggest going
    # straight to listing/pulling files, not "check if anonymous login
    # works" (which the operator already knows the answer to).
    box = create_box(conn, "AnonFtpBox")
    _insert_finding(
        conn, box.id, port=21, service="ftp",
        detail="[ftp-anon] Anonymous FTP login allowed (FTP code 230)",
    )

    suggestions = suggest_next_commands(conn, box.id)
    assert len(suggestions) == 1
    assert "ls" in suggestions[0].command or "get" in suggestions[0].command


def test_path_finding_suggests_looking_at_interesting_path(conn):
    box = create_box(conn, "PathBox")
    conn.execute(
        "INSERT INTO findings (box_id, source_tool, kind, host, path, status_code) "
        "VALUES (?, 'gobuster', 'path', '10.10.10.5', '/admin', 200)",
        (box.id,),
    )
    conn.commit()

    suggestions = suggest_next_commands(conn, box.id)
    assert len(suggestions) == 1
    assert "/admin" in suggestions[0].command
    assert suggestions[0].phase == "foothold"


def test_boring_path_finding_yields_no_suggestion(conn):
    box = create_box(conn, "BoringPathBox")
    conn.execute(
        "INSERT INTO findings (box_id, source_tool, kind, host, path, status_code) "
        "VALUES (?, 'gobuster', 'path', '10.10.10.5', '/images', 200)",
        (box.id,),
    )
    conn.commit()

    suggestions = suggest_next_commands(conn, box.id)
    assert suggestions == []


def test_share_finding_suggests_smbclient(conn):
    box = create_box(conn, "ShareBox")
    conn.execute(
        "INSERT INTO findings (box_id, source_tool, kind, host, path) "
        "VALUES (?, 'enum4linux-ng', 'share', '10.10.10.5', 'backup')",
        (box.id,),
    )
    conn.commit()

    suggestions = suggest_next_commands(conn, box.id)
    assert len(suggestions) == 1
    assert "smbclient" in suggestions[0].command
    assert "backup" in suggestions[0].command


def test_user_finding_does_not_default_to_bruteforce(conn):
    box = create_box(conn, "UserBox")
    conn.execute(
        "INSERT INTO findings (box_id, source_tool, kind, host, detail) "
        "VALUES (?, 'enum4linux-ng', 'user', '10.10.10.5', 'user: bob')",
        (box.id,),
    )
    conn.commit()

    suggestions = suggest_next_commands(conn, box.id)
    assert len(suggestions) == 1
    assert "hydra" not in suggestions[0].command.lower()


def test_header_finding_suggests_searchsploit(conn):
    box = create_box(conn, "HeaderBox")
    conn.execute(
        "INSERT INTO findings (box_id, source_tool, kind, host, product, version) "
        "VALUES (?, 'whatweb', 'header', '10.10.10.5', 'PHP', '5.2.4')",
        (box.id,),
    )
    conn.commit()

    suggestions = suggest_next_commands(conn, box.id)
    assert len(suggestions) == 1
    assert "searchsploit" in suggestions[0].command
    assert "PHP" in suggestions[0].command


def test_vuln_finding_suggests_looking_at_the_path(conn):
    box = create_box(conn, "VulnBox")
    conn.execute(
        "INSERT INTO findings (box_id, source_tool, kind, host, path, detail) "
        "VALUES (?, 'nikto', 'vuln', '10.10.10.5', '/backup/', 'Directory indexing found')",
        (box.id,),
    )
    conn.commit()

    suggestions = suggest_next_commands(conn, box.id)
    assert len(suggestions) == 1
    assert "/backup/" in suggestions[0].command


def test_target_gets_rewritten_to_dollar_target(conn):
    # docs/CLAUDE_CURSOR_DEBATE.md 2.13: once a box has a target set,
    # generated commands should say $TARGET instead of baking in the IP.
    box = create_box(conn, "TargetBox", target="10.10.10.9")
    _insert_finding(conn, box.id, host="10.10.10.9", port=80, service="http")

    suggestions = suggest_next_commands(conn, box.id)
    assert len(suggestions) == 1
    assert "$TARGET" in suggestions[0].command
    assert "10.10.10.9" not in suggestions[0].command


def test_every_suggestion_carries_its_finding_id(conn):
    # Required companion of Hole C per docs/CLAUDE_CURSOR_DEBATE.md,
    # Part B.3: coach.py ranks by finding_id, not by regexing rationale
    # prose, so every rule must actually set it.
    box = create_box(conn, "FindingIdBox")
    _insert_finding(conn, box.id, port=80, service="http")

    suggestions = suggest_next_commands(conn, box.id)
    assert len(suggestions) == 1
    assert suggestions[0].finding_id is not None
