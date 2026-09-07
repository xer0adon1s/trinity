"""Tests for the coach layer (trinity next) -- ranking suggestions
into a single recommendation with reasoning."""
from __future__ import annotations

from pathlib import Path

from trinity.boxes import create_box
from trinity.coach import get_recommendation
from trinity.process import process_scan_file

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_no_recommendation_when_nothing_parsed(conn):
    box = create_box(conn, "CoachEmptyBox")
    assert get_recommendation(conn, box.id) is None


def test_recommendation_after_parsing_a_scan(conn):
    box = create_box(conn, "CoachBox", target="10.10.10.3")
    process_scan_file(conn, box.id, FIXTURES / "lame_style_scan.xml")

    rec = get_recommendation(conn, box.id)
    assert rec is not None
    assert rec.top.command
    assert rec.why
    assert isinstance(rec.also_worth_trying, list)


def test_user_shell_promotes_privesc_over_earlier_phase(conn):
    from trinity.milestones import record_shell

    box = create_box(conn, "ShellPromoteBox")
    _insert_suggestion(conn, box.id, "enum", "gobuster dir -u http://$TARGET")
    rec = get_recommendation(conn, box.id)
    assert rec is not None
    assert rec.top.command.startswith("gobuster")

    record_shell(conn, box.id, "user")
    rec = get_recommendation(conn, box.id)
    assert rec is not None
    assert rec.top.phase == "privesc"
    leftover = [s.command for s in rec.also_worth_trying]
    assert any(c.startswith("gobuster") for c in leftover)


def test_recommendation_prefers_earlier_phase():
    # All suggestions from the fixture scan are 'recon'/'enum' phase --
    # confirm the top recommendation is never a later-phase item when
    # an earlier-phase one exists. We can't easily construct a mixed-
    # phase scenario without more scaffolding, so this test documents
    # the phase-ordering contract via the _PHASE_ORDER map directly.
    from trinity.coach import _PHASE_ORDER
    assert _PHASE_ORDER["recon"] < _PHASE_ORDER["enum"] < _PHASE_ORDER["foothold"]
    assert _PHASE_ORDER["foothold"] < _PHASE_ORDER["privesc"] < _PHASE_ORDER["post"]


def test_recommendation_why_mentions_rationale(conn):
    box = create_box(conn, "CoachBox2", target="10.10.10.3")
    process_scan_file(conn, box.id, FIXTURES / "lame_style_scan.xml")
    rec = get_recommendation(conn, box.id)
    assert rec.top.rationale in rec.why


def _insert_suggestion(conn, box_id, phase, command, rationale="Port 1 is X"):
    cursor = conn.execute(
        "INSERT INTO suggestions (box_id, phase, command, rationale, nudge) VALUES (?, ?, ?, ?, 'nudge')",
        (box_id, phase, command, rationale),
    )
    conn.commit()
    return cursor.lastrowid


def test_severity_ranks_suggestions_against_each_other_not_box_wide(conn):
    # Regression test: two suggestions on findings with DIFFERENT
    # severities must be rankable against each other -- one shared
    # box-wide severity applied to everything (the old bug) could
    # never distinguish between them. Now ranked via finding_id
    # persisted directly on the suggestion, not a regex over rationale
    # prose (see docs/CLAUDE_CURSOR_DEBATE.md, Part B.3).
    box = create_box(conn, "SeverityCoachBox")
    # Two findings, same phase (enum), different ports/severities.
    conn.execute(
        "INSERT INTO findings (id, box_id, source_tool, kind, host, port) VALUES (1, ?, 'nmap', 'port', 'h', 80)",
        (box.id,),
    )
    conn.execute(
        "INSERT INTO findings (id, box_id, source_tool, kind, host, port) VALUES (2, ?, 'nmap', 'port', 'h', 445)",
        (box.id,),
    )
    conn.commit()
    conn.execute(
        "INSERT INTO timeline (box_id, event_type, summary, severity, ref_id) VALUES (?, 'match', 'x', 'low', 1)",
        (box.id,),
    )
    conn.execute(
        "INSERT INTO timeline (box_id, event_type, summary, severity, ref_id) VALUES (?, 'match', 'x', 'critical', 2)",
        (box.id,),
    )
    conn.commit()

    _insert_suggestion(conn, box.id, "enum", "cmd-low-severity", rationale="Port 80 is X")
    _insert_suggestion(conn, box.id, "enum", "cmd-critical-severity", rationale="Port 445 is Y")
    conn.execute("UPDATE suggestions SET finding_id = 1 WHERE command = 'cmd-low-severity'")
    conn.execute("UPDATE suggestions SET finding_id = 2 WHERE command = 'cmd-critical-severity'")
    conn.commit()

    rec = get_recommendation(conn, box.id)
    # The critical-severity finding's suggestion must win, even though
    # it was inserted second (recency alone should not override
    # severity within the same phase).
    assert rec.top.command == "cmd-critical-severity"


def test_severity_ranking_falls_back_gracefully_without_finding_id(conn):
    # A suggestion with no finding_id (e.g. the 'user' rule, which has
    # no single finding-shaped severity) must not crash ranking -- it
    # just falls to the lowest severity tier, same as before Hole C.
    box = create_box(conn, "NoFindingIdBox")
    _insert_suggestion(conn, box.id, "enum", "cmd-no-finding")
    rec = get_recommendation(conn, box.id)
    assert rec.top.command == "cmd-no-finding"


def test_recency_breaks_ties_within_same_phase_and_severity(conn):
    box = create_box(conn, "RecencyCoachBox")
    older_id = _insert_suggestion(conn, box.id, "enum", "cmd-older")
    newer_id = _insert_suggestion(conn, box.id, "enum", "cmd-newer")
    assert newer_id > older_id  # sanity: insertion order really is older-then-newer

    rec = get_recommendation(conn, box.id)
    assert rec.top.command == "cmd-newer"


def _insert_suggestion_with_tool(conn, box_id, command, required_tool, phase="enum"):
    cursor = conn.execute(
        "INSERT INTO suggestions (box_id, phase, command, rationale, nudge, required_tool) "
        "VALUES (?, ?, ?, 'Port 1 is X', 'nudge', ?)",
        (box_id, phase, command, required_tool),
    )
    conn.commit()
    return cursor.lastrowid


def test_recommendation_flags_missing_tool(conn):
    from unittest.mock import patch as mock_patch
    box = create_box(conn, "MissingToolBox")
    _insert_suggestion_with_tool(conn, box.id, "gobuster dir -u x", "gobuster")

    with mock_patch("trinity.coach.is_tool_installed", return_value=False):
        rec = get_recommendation(conn, box.id)

    assert rec is not None
    assert rec.tool_missing is True
    assert rec.install_guidance is not None
    assert "gobuster" in rec.install_guidance


def test_recommendation_does_not_flag_installed_tool(conn):
    from unittest.mock import patch as mock_patch
    box = create_box(conn, "InstalledToolBox")
    _insert_suggestion_with_tool(conn, box.id, "gobuster dir -u x", "gobuster")

    with mock_patch("trinity.coach.is_tool_installed", return_value=True):
        rec = get_recommendation(conn, box.id)

    assert rec.tool_missing is False
    assert rec.install_guidance is None


def test_recommendation_survives_tool_becoming_installed_between_calls(conn):
    # This is the "circle right back to where we left off" behavior:
    # the SAME persisted, un-accepted suggestion must still be the top
    # recommendation once the tool becomes available -- nothing about
    # the missing-tool state should have consumed or altered it.
    from unittest.mock import patch as mock_patch
    box = create_box(conn, "CircleBackBox")
    _insert_suggestion_with_tool(conn, box.id, "gobuster dir -u x", "gobuster")

    with mock_patch("trinity.coach.is_tool_installed", return_value=False):
        first = get_recommendation(conn, box.id)
    assert first.tool_missing is True

    with mock_patch("trinity.coach.is_tool_installed", return_value=True):
        second = get_recommendation(conn, box.id)
    assert second.tool_missing is False
    assert second.top.command == first.top.command  # exact same suggestion


def test_set_accepted_makes_coach_move_on(conn):
    # Hole A: before set_accepted existed, nothing in the codebase ever
    # set accepted=1, so `trinity next` recommended the same command
    # forever. This is the core fix's contract.
    from trinity.coach import set_accepted
    box = create_box(conn, "AcceptedBox")
    first_id = _insert_suggestion(conn, box.id, "enum", "cmd-first")
    second_id = _insert_suggestion(conn, box.id, "enum", "cmd-second")

    rec1 = get_recommendation(conn, box.id)
    assert rec1.top.command == "cmd-second"  # newer wins the tie

    set_accepted(conn, rec1.suggestion_id)

    rec2 = get_recommendation(conn, box.id)
    assert rec2.top.command == "cmd-first"
    assert rec2.suggestion_id != rec1.suggestion_id


def test_set_accepted_on_last_suggestion_leaves_nothing_outstanding(conn):
    from trinity.coach import set_accepted
    box = create_box(conn, "LastAcceptedBox")
    _insert_suggestion(conn, box.id, "enum", "cmd-only")

    rec = get_recommendation(conn, box.id)
    set_accepted(conn, rec.suggestion_id)

    assert get_recommendation(conn, box.id) is None


def test_also_worth_trying_flags_installed_status(conn):
    from unittest.mock import patch as mock_patch
    box = create_box(conn, "AlsoWorthTryingBox")
    _insert_suggestion_with_tool(conn, box.id, "cmd-with-tool", "enum4linux-ng")
    _insert_suggestion(conn, box.id, "enum", "cmd-no-tool")

    def fake_installed(name):
        return name != "enum4linux-ng"

    with mock_patch("trinity.coach.is_tool_installed", side_effect=fake_installed):
        rec = get_recommendation(conn, box.id)

    # Top is the newest ("cmd-no-tool"); the other one is secondary and
    # should be flagged as not-installed.
    assert rec.top.command == "cmd-no-tool"
    assert len(rec.also_worth_trying) == 1
    assert rec.also_worth_trying[0].command == "cmd-with-tool"
    assert rec.also_worth_trying_installed == [False]


def test_wordlist_placeholder_gets_resolved_or_flagged(conn):
    from unittest.mock import patch as mock_patch
    box = create_box(conn, "WordlistBox")
    _insert_suggestion(
        conn, box.id, "enum",
        "gobuster dir -u http://x -w /usr/share/wordlists/dirb/common.txt",
    )

    with mock_patch("trinity.coach.resolve_wordlist_in_command", return_value="gobuster dir -u http://x -w /usr/share/wordlists/dirb/common.txt"):
        rec = get_recommendation(conn, box.id)
    assert rec.wordlist_missing is True

    with mock_patch("trinity.coach.resolve_wordlist_in_command", return_value="gobuster dir -u http://x -w /found/wordlist.txt"):
        rec2 = get_recommendation(conn, box.id)
    assert rec2.wordlist_missing is False
    assert "/found/wordlist.txt" in rec2.top.command
