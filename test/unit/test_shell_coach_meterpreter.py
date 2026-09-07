"""Tests for the Coach engine's nested-profile stack (Meterpreter
inside msfconsole). See docs/COACH_METERPRETER_NESTING_DESIGN.md for
the full design rationale before touching this file or shell_coach.py.

Same discipline as test_shell_coach_msfconsole.py: feed synthetic line
sequences into a fresh CoachSession and assert on narration strings /
active_profile / active_state. msfconsole was not installed on the
build host (`which msfconsole` missed), so METERPRETER_PROFILE's
prompt/message fixtures are documented Metasploit behavior, not a
live pty paste -- same caveat as the existing msfconsole/evil-winrm
profiles.
"""
from __future__ import annotations

from trinity.shell_coach import STALL_LINE_THRESHOLD, CoachSession, new_session


def _feed_many(session: CoachSession, lines: list[str]) -> list[str]:
    out = []
    for line in lines:
        result = session.feed_line(line)
        if result:
            out.append(result)
    return out


def test_run_success_pushes_into_meterpreter_nested_profile():
    """A successful `run` inside msfconsole, followed by the real
    Meterpreter prompt appearing, must push msfconsole onto the stack
    and switch the active profile to meterpreter -- not misclassify
    it as a generic raw shell, and not stay lost in msfconsole's
    'fired' state believing nothing happened."""
    session = new_session()
    session.feed_line("msf6 >")
    session.feed_line("msf6 > use exploit/windows/smb/ms17_010_eternalblue")
    session.feed_line(
        "msf6 exploit(windows/smb/ms17_010_eternalblue) > set RHOSTS 10.10.10.10"
    )
    session.feed_line("msf6 exploit(windows/smb/ms17_010_eternalblue) > run")
    assert session.active_profile.tool_id == "msfconsole"
    assert session.active_state.name == "fired"

    result = session.feed_line("meterpreter > ")
    assert result is not None
    assert "meterpreter" in result.lower()
    assert session.active_profile is not None
    assert session.active_profile.tool_id == "meterpreter"
    assert [p.tool_id for p in session.profile_stack] == ["msfconsole"]


def test_background_pops_back_to_msfconsole_with_blank_state():
    """Typing `background` at the Meterpreter prompt must pop back to
    msfconsole -- not end the whole coach session -- and must NOT
    restore msfconsole's stale 'fired' state (which would immediately
    nag about `sessions -l` right after the operator was legitimately
    inside the very session that advice was about)."""
    session = new_session()
    session.feed_line("msf6 >")
    session.feed_line("msf6 > use exploit/windows/smb/ms17_010_eternalblue")
    session.feed_line(
        "msf6 exploit(windows/smb/ms17_010_eternalblue) > set RHOSTS 10.10.10.10"
    )
    session.feed_line("msf6 exploit(windows/smb/ms17_010_eternalblue) > run")
    session.feed_line("meterpreter > ")
    assert session.active_profile.tool_id == "meterpreter"

    session.feed_line("meterpreter > background")
    assert session.active_profile is not None
    assert session.active_profile.tool_id == "msfconsole"
    assert session.active_state is None
    assert session.profile_stack == []

    # Sitting at the bare msf6 prompt afterward must not surface
    # stale "sessions -l" nagging from the pre-nesting 'fired' state.
    filler = ["msf6 exploit(windows/smb/ms17_010_eternalblue) > "] * STALL_LINE_THRESHOLD
    assert _feed_many(session, filler) == []


def test_dropped_meterpreter_session_pops_implicitly_without_typed_exit():
    """A dropped connection returns straight to msf6 > with no typed
    exit command (Metasploit's own unprompted 'Meterpreter session N
    closed' message, or just the parent prompt reappearing) -- must
    still pop, not permanently strand the coach inside a dead
    meterpreter profile."""
    session = new_session()
    session.feed_line("msf6 >")
    session.feed_line("msf6 > use exploit/windows/smb/ms17_010_eternalblue")
    session.feed_line("msf6 exploit(windows/smb/ms17_010_eternalblue) > run")
    session.feed_line("meterpreter > ")
    assert session.active_profile.tool_id == "meterpreter"

    session.feed_line("[*] Meterpreter session 1 closed.  Reason: Died")
    assert session.active_profile is not None
    assert session.active_profile.tool_id == "msfconsole"
    assert session.profile_stack == []


def test_meterpreter_stall_ladder_fires_inside_nested_profile():
    """The existing stall-ladder machinery must work unmodified for a
    nested profile's own states, same as any top-level profile."""
    session = new_session()
    session.feed_line("msf6 >")
    session.feed_line("msf6 > use exploit/windows/smb/ms17_010_eternalblue")
    session.feed_line("msf6 exploit(windows/smb/ms17_010_eternalblue) > run")
    session.feed_line("meterpreter > ")
    assert session.active_state is not None
    assert session.active_state.name == "landed"

    filler = ["irrelevant"] * STALL_LINE_THRESHOLD
    results = _feed_many(session, filler)
    assert len(results) == 1
    assert "getuid" not in results[0]  # level 1 is Socratic, no literal command yet
