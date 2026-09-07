"""Regression tests for the engine bug flagged in
docs/COACH_OPEN_QUESTIONS.md ("A recurring `recognize` pattern
silently disables stall nudges") and fixed in
CoachSession._advance_active_profile.

Root cause: the engine used to short-circuit (return None, skipping
the stall-counting logic below it) on ANY line matching ANY state's
`recognize` pattern -- including a re-match of the state that was
ALREADY active. For a `recognize` pattern that's a genuine one-time
event (a banner line, an `id` command's output shape) this was
harmless. It silently broke the entire stall-nudge ladder for any
state whose `recognize` pattern matches something the tool reprints
on every single line -- exactly what an interactive tool's own live
prompt usually is -- because every operator-typed line would re-match
the already-active state and return early forever, so
`stall_counter` could never reach STALL_LINE_THRESHOLD.

This was discovered independently by two real profiles built in
parallel (evil-winrm, msfconsole), each of which worked around it at
the profile-authoring level (recognizing a one-time banner/command
instead of the live per-line prompt) rather than touching the engine.
These tests exercise the engine fix directly with a minimal synthetic
profile shaped exactly like the failure case, so the underlying bug
has its own coverage independent of either real profile's workaround.
"""
from __future__ import annotations

import re

from trinity.shell_coach import (
    STALL_LINE_THRESHOLD,
    CoachProfile,
    CoachSession,
    CoachState,
)

# A minimal synthetic profile whose ONE state's `recognize` pattern is
# the tool's own live prompt -- reprinted before every command, the
# exact shape that used to starve stall_counter forever.
_LIVE_PROMPT = re.compile(r"^tool>")

_REPRINTING_PROFILE = CoachProfile(
    tool_id="reprints_prompt",
    display_name="a tool that reprints its prompt every line",
    prompt_pattern=_LIVE_PROMPT,
    exit_pattern=re.compile(r"^exit$"),
    states=[
        CoachState(
            name="only_state",
            recognize=_LIVE_PROMPT,
            expected_next=[re.compile(r"^tool> do-the-thing$")],
            stall_nudge="nudge-level-1",
            stall_stronger_nudge="nudge-level-2",
            stall_answer="nudge-level-3",
        ),
    ],
    announce="entered reprinting-prompt tool",
)


def _feed_many(session: CoachSession, lines: list[str]) -> list[str]:
    out = []
    for line in lines:
        result = session.feed_line(line)
        if result:
            out.append(result)
    return out


def test_state_whose_recognize_reprints_every_line_still_reaches_stall_nudge():
    """The core regression: before the fix, this NEVER nudged because
    every 'tool> ...' line re-matched 'only_state' and returned early,
    permanently resetting/never incrementing stall_counter."""
    session = CoachSession(profiles=[_REPRINTING_PROFILE])
    session.feed_line("tool> some command")  # entry announcement
    lines = [f"tool> unrelated-{i}" for i in range(STALL_LINE_THRESHOLD)]
    narrations = _feed_many(session, lines)
    assert narrations == ["nudge-level-1"]


def test_reprinting_prompt_ladder_still_escalates_through_three_levels():
    session = CoachSession(profiles=[_REPRINTING_PROFILE])
    session.feed_line("tool> some command")

    def stall_once():
        lines = [f"tool> unrelated-{i}" for i in range(STALL_LINE_THRESHOLD)]
        results = _feed_many(session, lines)
        assert len(results) == 1
        return results[0]

    assert stall_once() == "nudge-level-1"
    assert stall_once() == "nudge-level-2"
    assert stall_once() == "nudge-level-3"
    assert stall_once() == "nudge-level-3"  # caps, doesn't error past 3


def test_on_track_line_still_resets_stall_counter_with_reprinting_prompt():
    """expected_next matching must still reset the counter even though
    every line ALSO matches the reprinting prompt -- proves the fix
    didn't just move the bug (e.g. by making expected_next unreachable)."""
    session = CoachSession(profiles=[_REPRINTING_PROFILE])
    session.feed_line("tool> some command")
    # Alternate on-track lines with near-threshold filler -- should
    # never nudge, since each on-track line resets the counter.
    for _ in range(3):
        filler = [f"tool> unrelated-{i}" for i in range(STALL_LINE_THRESHOLD - 1)]
        assert _feed_many(session, filler) == []
        assert session.feed_line("tool> do-the-thing") is None
        assert session.stall_counter == 0


def test_genuine_transition_to_a_different_state_still_resets_and_short_circuits():
    """The fix must not break the original, correct behavior: a real
    transition to a DIFFERENT state still resets the stall ladder and
    returns None (no narration) for that line."""
    other_state = CoachState(
        name="other_state",
        recognize=re.compile(r"^switched$"),
        stall_nudge="other-nudge",
    )
    profile = CoachProfile(
        tool_id="two_states",
        display_name="two states",
        prompt_pattern=re.compile(r"^tool>"),
        exit_pattern=re.compile(r"^exit$"),
        states=[_REPRINTING_PROFILE.states[0], other_state],
    )
    session = CoachSession(profiles=[profile])
    session.feed_line("tool> some command")
    assert session.active_state is not None
    assert session.active_state.name == "only_state"

    result = session.feed_line("switched")
    assert result is None
    assert session.active_state is other_state
    assert session.stall_counter == 0
    assert session.stall_level == 0


def test_real_evil_winrm_profile_still_reaches_stall_nudge_end_to_end():
    """Sanity check against the REAL shipped evil-winrm profile (not
    just the synthetic one above): its 'landed' state deliberately
    works around this bug by recognizing a one-time banner instead of
    the live prompt, so it should reach a stall nudge whether or not
    the engine-level fix is present. This test exists to confirm the
    engine fix doesn't regress the existing, already-correct
    workaround-based profiles."""
    from trinity.shell_coach import EVIL_WINRM_PROFILE, new_session

    session = new_session()
    session.feed_line("Evil-WinRM shell v3.5")
    filler = ["some unrelated line"] * STALL_LINE_THRESHOLD
    narrations = _feed_many(session, filler)
    assert len(narrations) == 1
    assert session.active_profile is EVIL_WINRM_PROFILE
