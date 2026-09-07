"""Tests for the msfconsole Coach profile. See
docs/COACH_MSFCONSOLE_SPEC.md and docs/COACH_SUBSYSTEM_DESIGN.md.

Same discipline as test_shell_coach.py: feed synthetic line sequences
into a fresh CoachSession and assert on the narration strings (and,
for the transition test, the active_state name). Prompt fixtures are
the documented default renderings from metasploit-framework's
driver.rb (`msf6 >`, `msf6 exploit(...) >`) — msfconsole was not
installed on the build host, so these are not a live pty paste.
"""
from __future__ import annotations

from trinity.shell_coach import STALL_LINE_THRESHOLD, CoachSession, new_session


def _feed_many(session: CoachSession, lines: list[str]) -> list[str]:
    """Feeds each line, collecting only the non-None narrations."""
    out = []
    for line in lines:
        result = session.feed_line(line)
        if result:
            out.append(result)
    return out


def test_msfconsole_entry_announces_once():
    session = new_session()
    narrations = _feed_many(session, ["msf6 >"])
    assert len(narrations) == 1
    assert "msfconsole" in narrations[0]
    assert "won't type" in narrations[0]


def test_msfconsole_does_not_re_announce_on_every_prompt():
    session = new_session()
    narrations = _feed_many(session, ["msf6 >", "msf6 >"])
    # Second identical prompt stays inside the same profile — should
    # produce nothing, same as the raw-shell re-announce test.
    assert len(narrations) == 1


def test_msfconsole_older_and_module_prompts_also_enter():
    """driver.rb's Prompt is `msf` + major version; older frameworks
    used `msf >` / `msf5 >`, and a selected module adds `type(path)`."""
    for prompt in (
        "msf >",
        "msf5 >",
        "msf6 auxiliary(scanner/smb/smb_version) >",
        "msf6 payload(windows/meterpreter/reverse_tcp) >",
        "msf exploit(unix/misc/distcc_exec) >",
    ):
        session = new_session()
        result = session.feed_line(prompt)
        assert result is not None, prompt
        assert "msfconsole" in result
        assert session.active_profile is not None
        assert session.active_profile.tool_id == "msfconsole"


def test_msfconsole_ansi_wrapped_prompt_still_enters():
    """Default Prompt is `%undmsf%clr`; Rex renders that as underline
    + reset around the `msf6` token. A live pty chunk keeps the CSI."""
    session = new_session()
    result = session.feed_line("\x1b[4mmsf6\x1b[0m >")
    assert result is not None
    assert "msfconsole" in result


def test_msfconsole_search_use_set_run_transitions():
    session = new_session()
    session.feed_line("msf6 >")
    assert session.active_profile is not None
    assert session.active_profile.tool_id == "msfconsole"
    assert session.active_state is None

    session.feed_line("msf6 > search eternalblue")
    assert session.active_state is not None
    assert session.active_state.name == "searching"

    # `use` is both searching's expected_next and module_selected's
    # recognize — new-state matching wins, so this transitions.
    session.feed_line("msf6 > use exploit/windows/smb/ms17_010_eternalblue")
    assert session.active_state.name == "module_selected"

    session.feed_line(
        "msf6 exploit(windows/smb/ms17_010_eternalblue) > set RHOSTS 10.10.10.10"
    )
    assert session.active_state.name == "options_set"

    session.feed_line("msf6 exploit(windows/smb/ms17_010_eternalblue) > run")
    assert session.active_state.name == "fired"


def test_msfconsole_show_options_is_on_track_no_nudge():
    session = new_session()
    session.feed_line("msf6 >")
    session.feed_line("msf6 > use exploit/windows/smb/ms17_010_eternalblue")
    lines = (
        ["msf6 exploit(windows/smb/ms17_010_eternalblue) > show options"]
        * (STALL_LINE_THRESHOLD * 2)
    )
    assert _feed_many(session, lines) == []
    assert session.active_state is not None
    assert session.active_state.name == "module_selected"


def test_msfconsole_stall_ladder_escalates_through_three_levels():
    session = new_session()
    session.feed_line("msf6 >")
    session.feed_line("msf6 > use exploit/windows/smb/ms17_010_eternalblue")

    def stall_once():
        filler = ["irrelevant"] * STALL_LINE_THRESHOLD
        results = _feed_many(session, filler)
        assert len(results) == 1
        return results[0]

    level1 = stall_once()
    level2 = stall_once()
    level3 = stall_once()
    level3_again = stall_once()

    assert level1 != level2 != level3
    # Ladder caps at level 3 (the literal answer) and stays there.
    assert level3 == level3_again
    assert "set RHOSTS" in level3
    # Level 2 names the area without the literal command shape.
    assert "attack" in level2.lower()
    assert "set RHOSTS" not in level2


def test_msfconsole_exit_pattern_ends_active_profile_and_stall_state():
    session = new_session()
    session.feed_line("msf6 >")
    assert session.active_profile is not None
    session.feed_line("msf6 > exit")
    assert session.active_profile is None
    assert session.stall_counter == 0
    assert session.stall_level == 0


def test_msfconsole_back_returns_to_top_level_no_stale_module_nudge():
    """Regression test for docs/COACH_OPEN_QUESTIONS.md's "`back` does
    not deselect": after a module is selected then `back`'d out of,
    the coach must not keep stalling toward module-context advice
    (e.g. `set RHOSTS`) while sitting at the bare `msf6 >` prompt."""
    session = new_session()
    session.feed_line("msf6 >")
    session.feed_line("msf6 > use exploit/windows/smb/ms17_010_eternalblue")
    assert session.active_state.name == "module_selected"

    session.feed_line("msf6 exploit(windows/smb/ms17_010_eternalblue) > back")
    assert session.active_state is not None
    assert session.active_state.name == "top_level"

    filler = ["msf6 >"] * STALL_LINE_THRESHOLD
    results = _feed_many(session, filler)
    # Repeated bare top-level prompts are on-track (not a stall) and
    # must never surface module_selected's stale "set RHOSTS" advice.
    assert results == []
