"""Tests for the Agent Harness (agent_harness.py) -- detection and
invocation. See docs/AGENT_HARNESS.md.

These tests never actually invoke a real agent CLI -- they mock
subprocess/shutil.which so the suite is fast, deterministic, and
never depends on this test machine's actual installed tools.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from trinity.agent_harness import (
    ask_agent,
    detect_agent,
    invoke_agent,
    is_agent_available,
    is_omarchy,
)


def test_is_agent_available_false_for_unknown_name():
    assert is_agent_available("not-a-real-agent") is False


def test_is_agent_available_checks_path():
    with patch("trinity.agent_harness.shutil.which", return_value=None):
        assert is_agent_available("claude") is False
    with patch("trinity.agent_harness.shutil.which", return_value="/usr/bin/claude"):
        assert is_agent_available("claude") is True


def test_detect_agent_none_when_nothing_on_path():
    with patch("trinity.agent_harness.is_omarchy", return_value=False), \
         patch("trinity.agent_harness.shutil.which", return_value=None):
        assert detect_agent() is None


def test_detect_agent_finds_first_available_on_path_when_not_omarchy():
    def fake_which(binary):
        return "/usr/bin/codex" if binary == "codex" else None

    with patch("trinity.agent_harness.is_omarchy", return_value=False), \
         patch("trinity.agent_harness.shutil.which", side_effect=fake_which):
        agent = detect_agent()
    assert agent is not None
    assert agent.name == "codex"


def test_detect_agent_prefers_hermes_on_omarchy():
    def fake_which(binary):
        # Both claude and hermes "installed" -- hermes should win on Omarchy.
        return f"/usr/bin/{binary}" if binary in ("hermes", "claude") else None

    with patch("trinity.agent_harness.is_omarchy", return_value=True), \
         patch("trinity.agent_harness.shutil.which", side_effect=fake_which):
        agent = detect_agent()
    assert agent is not None
    assert agent.name == "hermes"


def test_detect_agent_falls_through_to_path_scan_if_omarchy_default_missing():
    def fake_which(binary):
        return "/usr/bin/gemini" if binary == "gemini" else None

    with patch("trinity.agent_harness.is_omarchy", return_value=True), \
         patch("trinity.agent_harness._omarchy_default_agent_name", return_value="claude"), \
         patch("trinity.agent_harness.shutil.which", side_effect=fake_which):
        agent = detect_agent()
    assert agent is not None
    assert agent.name == "gemini"


def test_invoke_agent_returns_none_on_missing_binary():
    from trinity.agent_harness import AgentInfo

    info = AgentInfo("fake", "definitely-not-a-real-binary-xyz", lambda p: ["definitely-not-a-real-binary-xyz", p])
    assert invoke_agent(info, "hello") is None


def test_invoke_agent_returns_stdout_on_success():
    from trinity.agent_harness import AgentInfo

    info = AgentInfo("fake", "fake", lambda p: ["echo", p])
    with patch("trinity.agent_harness.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="the answer\n")
        result = invoke_agent(info, "a question")
    assert result == "the answer"


def test_invoke_agent_returns_none_on_nonzero_exit():
    from trinity.agent_harness import AgentInfo

    info = AgentInfo("fake", "fake", lambda p: ["false", p])
    with patch("trinity.agent_harness.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        result = invoke_agent(info, "a question")
    assert result is None


def test_ask_agent_returns_none_none_when_no_agent_detected():
    with patch("trinity.agent_harness.detect_agent", return_value=None):
        answer, name = ask_agent("a question")
    assert answer is None
    assert name is None


def test_ask_agent_returns_answer_and_name_on_success():
    from trinity.agent_harness import AgentInfo

    fake_agent = AgentInfo("fake", "fake", lambda p: ["echo", p])
    with patch("trinity.agent_harness.detect_agent", return_value=fake_agent), \
         patch("trinity.agent_harness.invoke_agent", return_value="a real answer"):
        answer, name = ask_agent("a question")
    assert answer == "a real answer"
    assert name == "fake"
