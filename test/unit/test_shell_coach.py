"""Tests for the Coach subsystem engine (coach.py). See
docs/COACH_SUBSYSTEM_DESIGN.md for the design this implements.

All tests here exercise CoachSession.feed_line() directly, feeding
synthetic line sequences — the same "pure function over already-
captured text" testing discipline shoulder.py's scan_for_milestones
already uses, since coach.py's engine is deliberately built the same
way (see coach.py's own docstring).
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


def test_no_narration_before_any_recognized_prompt():
    session = new_session()
    narrations = _feed_many(session, ["ls -la", "cd /tmp", "cat notes.txt"])
    assert narrations == []


def test_raw_shell_landing_announces_once():
    session = new_session()
    narrations = _feed_many(session, ["uid=33(www-data) gid=33(www-data) groups=33(www-data)"])
    assert len(narrations) == 1
    assert "landed a shell" in narrations[0]


def test_raw_shell_does_not_re_announce_on_every_matching_line():
    session = new_session()
    lines = [
        "uid=33(www-data) gid=33(www-data) groups=33(www-data)",
        "uid=33(www-data) gid=33(www-data) groups=33(www-data)",
    ]
    narrations = _feed_many(session, lines)
    # Second identical line re-enters the SAME state, not a fresh
    # profile-entry announcement -- should produce nothing.
    assert len(narrations) == 1


def test_on_track_command_resets_stall_counter_no_nudge():
    session = new_session()
    session.feed_line("uid=33(www-data) gid=33(www-data) groups=33(www-data)")
    # Operator immediately does the expected next thing -- id/whoami --
    # repeated indefinitely should never trigger a stall nudge.
    lines = ["id"] * (STALL_LINE_THRESHOLD * 2)
    narrations = _feed_many(session, lines)
    assert narrations == []


def test_stall_produces_ladder_nudge_after_threshold_unrecognized_lines():
    session = new_session()
    session.feed_line("uid=33(www-data) gid=33(www-data) groups=33(www-data)")
    # Feed threshold-1 unrelated lines: no nudge yet.
    filler = ["some random unrelated command output"] * (STALL_LINE_THRESHOLD - 1)
    assert _feed_many(session, filler) == []
    # One more unrelated line crosses the threshold -- level-1 nudge.
    result = session.feed_line("another unrelated line")
    assert result is not None
    assert "stabiliz" in result.lower() or "check" in result.lower()


def test_stall_ladder_escalates_through_three_levels():
    session = new_session()
    session.feed_line("uid=33(www-data) gid=33(www-data) groups=33(www-data)")

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
    assert "python3" in level3 or "stabilize" in level3.lower()


def test_expected_next_transitions_to_new_state_and_resets_stall():
    session = new_session()
    session.feed_line("uid=33(www-data) gid=33(www-data) groups=33(www-data)")
    # A real `id` output shape transitions into the 'identified' state.
    session.feed_line("uid=33(www-data)(gid=33(www-data))")
    # Fresh state -> stall counter reset -> should take a full
    # threshold's worth of unrelated lines before nudging again, not
    # carry over any partial count from the previous state.
    filler = ["irrelevant"] * (STALL_LINE_THRESHOLD - 1)
    assert _feed_many(session, filler) == []


def test_exit_pattern_ends_active_profile_and_stall_state():
    session = new_session()
    session.feed_line("uid=33(www-data) gid=33(www-data) groups=33(www-data)")
    assert session.active_profile is not None
    session.feed_line("logout")
    assert session.active_profile is None
    assert session.stall_counter == 0
    assert session.stall_level == 0


def test_engine_never_returns_anything_resembling_pty_input():
    """Guardrail test for the hard rule in coach.py's own docstring:
    feed_line() must be a pure function returning str|None -- there is
    no method on CoachSession that could plausibly write back into a
    pty. This test exists to make future contributors trip over it if
    they ever add one.
    """
    session = new_session()
    assert not hasattr(session, "send_input")
    assert not hasattr(session, "write")
    assert not hasattr(session, "inject")
