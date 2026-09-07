"""Tests for the evil-winrm CoachProfile (docs/COACH_EVILWINRM_SPEC.md).
Same "feed synthetic line sequences into a fresh CoachSession, assert
on the narration strings" discipline as test_shell_coach.py's
raw-shell tests -- see that file's own docstring for the rationale.

Synthetic lines here are colorless (no ANSI escape codes), matching
how `evil-winrm --no-colors` -- or any capture path that strips ANSI
-- would actually present the prompt text; this is also the simpler,
more common shape the rest of the test suite (and RAW_SHELL_PROFILE's
own tests) uses throughout.
"""
from __future__ import annotations

from trinity.shell_coach import STALL_LINE_THRESHOLD, CoachSession, new_session

_BANNER = "Evil-WinRM shell v4.1"
_PROMPT = "*Evil-WinRM* PS C:\\Users\\victim\\Documents> "
_WHOAMI_PRIV_OUTPUT = "PRIVILEGES INFORMATION"


def _feed_many(session: CoachSession, lines: list[str]) -> list[str]:
    out = []
    for line in lines:
        result = session.feed_line(line)
        if result:
            out.append(result)
    return out


def test_evil_winrm_landing_announces_once():
    session = new_session()
    narrations = _feed_many(session, [_BANNER, _PROMPT + "whoami"])
    assert len(narrations) == 1
    assert "evil-winrm session" in narrations[0]


def test_evil_winrm_does_not_re_announce_on_every_prompt_line():
    session = new_session()
    lines = [_BANNER, _PROMPT + "whoami", _PROMPT + "hostname"]
    narrations = _feed_many(session, lines)
    # The banner only appears once (real evil-winrm behavior); repeated
    # prompt lines re-entering the same profile shouldn't re-announce.
    assert len(narrations) == 1


def test_evil_winrm_prompt_alone_is_recognized_as_a_distinct_tool_from_raw_shell():
    # A colorless evil-winrm prompt line textually CONTAINS raw_shell's
    # own `PS [A-Z]:\S*>` pattern -- this asserts the evil-winrm-
    # specific announcement wins (DEFAULT_PROFILES orders evil-winrm
    # before raw_shell precisely to guarantee this; see the ORDER
    # MATTERS comment in shell_coach.py).
    session = new_session()
    narrations = _feed_many(session, [_PROMPT + "whoami"])
    assert len(narrations) == 1
    assert "evil-winrm session" in narrations[0]


def test_whoami_priv_output_transitions_to_enumerated_and_resets_stall():
    session = new_session()
    session.feed_line(_BANNER)
    session.feed_line(_PROMPT + "whoami /priv")
    # Real `whoami /priv` output header -- transitions "landed" ->
    # "enumerated" (mirrors RAW_SHELL_PROFILE's own id-output-shape
    # transition test).
    session.feed_line(_WHOAMI_PRIV_OUTPUT)
    assert session.active_state is not None
    assert session.active_state.name == "enumerated"
    # Fresh state -> stall counter reset -> a full threshold's worth of
    # unrelated lines is needed before nudging again.
    filler = ["irrelevant"] * (STALL_LINE_THRESHOLD - 1)
    assert _feed_many(session, filler) == []


def test_on_track_command_resets_stall_counter_no_nudge():
    session = new_session()
    session.feed_line(_BANNER)
    # Operator immediately does an expected-next move -- `hostname` --
    # repeated indefinitely should never trigger a stall nudge.
    lines = [_PROMPT + "hostname"] * (STALL_LINE_THRESHOLD * 2)
    narrations = _feed_many(session, lines)
    assert narrations == []


def test_stall_ladder_escalates_through_three_levels_without_naming_whoami_priv_first():
    session = new_session()
    session.feed_line(_BANNER)

    def stall_once():
        filler = ["irrelevant"] * STALL_LINE_THRESHOLD
        results = _feed_many(session, filler)
        assert len(results) == 1
        return results[0]

    level1 = stall_once()
    level2 = stall_once()
    level3 = stall_once()
    level3_again = stall_once()

    # First nudge is Socratic -- must not name the literal command.
    assert "whoami /priv" not in level1
    assert level1 != level2 != level3
    # Ladder caps at level 3 (the literal answer) and stays there.
    assert level3 == level3_again
    assert "whoami /priv" in level3


def test_exit_pattern_ends_active_profile_and_stall_state():
    session = new_session()
    session.feed_line(_BANNER)
    assert session.active_profile is not None
    # Bare "exit" line (not prompt-prefixed) -- same simplification
    # RAW_SHELL_PROFILE's own exit test uses ("logout", not
    # "$ logout"); a real captured line would have the prompt text
    # immediately before the typed command on the same line, which
    # `_EVIL_WINRM_EXIT`'s `^\s*(exit|quit)\s*$` alternative doesn't
    # match -- the "Exiting with code" message (see the next test)
    # is the exit signal that reliably fires either way.
    session.feed_line("exit")
    assert session.active_profile is None
    assert session.stall_counter == 0
    assert session.stall_level == 0


def test_exiting_with_code_message_also_ends_active_profile():
    # Real evil-winrm signal on both graceful exit and a dropped
    # connection (see shell_coach.py's _EVIL_WINRM_EXIT comment) --
    # verified against the evil-winrm 4.1 gem source's custom_exit.
    session = new_session()
    session.feed_line(_BANNER)
    session.feed_line("Exiting with code 0")
    assert session.active_profile is None
