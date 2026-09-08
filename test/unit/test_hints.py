"""Tests for the graduated hint ladder."""
from __future__ import annotations

from trinity.boxes import create_box
from trinity.hints import build_hint, get_hint, get_hint_level
from trinity.suggest.engine import _suggest_for_finding


def _make_suggestion(conn, box_id: int, command: str = "gobuster dir ...") -> int:
    cursor = conn.execute(
        "INSERT INTO suggestions (box_id, phase, command, rationale, nudge) VALUES (?, 'enum', ?, 'test rationale', 'test nudge')",
        (box_id, command),
    )
    conn.commit()
    return cursor.lastrowid


def test_hint_level_starts_at_zero(conn):
    box = create_box(conn, "HintBox")
    sid = _make_suggestion(conn, box.id)
    assert get_hint_level(conn, box.id, sid) == 0


def test_first_hint_call_gives_level_1(conn):
    box = create_box(conn, "HintBox2")
    sid = _make_suggestion(conn, box.id)
    hint = get_hint(conn, box.id, sid, "enum", "some nudge", "Port 80 is HTTP, brute-force the directories.", "gobuster ...")
    assert hint.level == 1


def test_repeated_calls_escalate_the_ladder(conn):
    box = create_box(conn, "HintBox3")
    sid = _make_suggestion(conn, box.id)
    h1 = get_hint(conn, box.id, sid, "enum", "nudge text", "rationale text", "cmd")
    h2 = get_hint(conn, box.id, sid, "enum", "nudge text", "rationale text", "cmd")
    h3 = get_hint(conn, box.id, sid, "enum", "nudge text", "rationale text", "cmd")
    assert (h1.level, h2.level, h3.level) == (1, 2, 3)


def test_ladder_caps_at_level_3(conn):
    box = create_box(conn, "HintBox4")
    sid = _make_suggestion(conn, box.id)
    hint = None
    for _ in range(5):
        hint = get_hint(conn, box.id, sid, "enum", "nudge", "rationale", "cmd")
    assert hint.level == 3


def test_different_suggestion_starts_fresh(conn):
    box = create_box(conn, "HintBox5")
    sid1 = _make_suggestion(conn, box.id, "cmd1")
    sid2 = _make_suggestion(conn, box.id, "cmd2")

    get_hint(conn, box.id, sid1, "enum", "nudge", "rationale", "cmd")
    get_hint(conn, box.id, sid1, "enum", "nudge", "rationale", "cmd")  # suggestion 1 now at level 2

    fresh = get_hint(conn, box.id, sid2, "privesc", "different nudge", "different rationale", "cmd2")
    assert fresh.level == 1


def test_level_3_hint_includes_the_command():
    text = build_hint(3, "enum", "some nudge", "some rationale", "gobuster dir -u http://x -w list.txt")
    assert "gobuster dir -u http://x -w list.txt" in text


def test_level_1_and_2_do_not_include_the_command():
    text1 = build_hint(1, "enum", "some nudge", "some rationale", "gobuster dir -u http://x -w list.txt")
    text2 = build_hint(2, "enum", "some nudge", "some rationale", "gobuster dir -u http://x -w list.txt")
    assert "gobuster dir -u http://x" not in text1
    assert "gobuster dir -u http://x" not in text2


def test_level_2_uses_nudge_not_rationale():
    # Regression: level 2 must render the vague `nudge`, never the
    # answer-shaped `rationale` text.
    text = build_hint(2, "enum", "look at what kind of tool finds hidden things",
                       "run gobuster to find hidden directories", "gobuster dir -u x")
    assert "look at what kind of tool finds hidden things" in text
    assert "gobuster" not in text.lower()


def _real_finding_row(conn, service: str, product: str = "", port: int = 80, version: str = ""):
    """Builds a real sqlite3.Row shaped like suggest/engine.py expects,
    by round-tripping through the actual findings table."""
    from trinity.boxes import create_box
    box = create_box(conn, f"tmp_{service}_{port}")
    cursor = conn.execute(
        "INSERT INTO findings (box_id, source_tool, kind, host, port, service, product, version) "
        "VALUES (?, 'nmap', 'port', '10.0.0.1', ?, ?, ?, ?)",
        (box.id, port, service, product, version),
    )
    conn.commit()
    return conn.execute("SELECT * FROM findings WHERE id = ?", (cursor.lastrowid,)).fetchone()


def test_no_real_suggestion_rule_leaks_its_command_at_hint_level_2(conn):
    # Regression test for the exact bug Cursor's review found: every
    # shipped suggestion rule's `nudge` text (used at hint level 2)
    # must never contain the tool name/command it's hinting toward,
    # even though `rationale` (used at level 3) is allowed to.
    cases = [
        ("http", "apache", 80, ""),
        ("microsoft-ds", "samba", 445, ""),
        ("ftp", "", 21, ""),
        ("ssh", "openssh", 22, "7.4"),
    ]
    for service, product, port, version in cases:
        row = _real_finding_row(conn, service, product, port, version)
        suggestion = _suggest_for_finding(row, set())
        assert suggestion is not None, f"expected a suggestion for {service}"

        command_tokens = suggestion.command.lower().split()
        tool_name = command_tokens[0]
        assert tool_name not in suggestion.nudge.lower(), (
            f"{service} suggestion's nudge leaks its tool name {tool_name!r}: {suggestion.nudge!r}"
        )
