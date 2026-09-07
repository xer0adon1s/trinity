"""CLI-layer tests for explain/error Agent Harness escalation on a
cache miss (docs/AGENT_HARNESS.md, docs/UPDATE_FRAMEWORK.md).

Mocks trinity.agent_harness.ask_agent so these never depend on a real
agent CLI being installed on the test machine."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from trinity.cli.main import cli
from trinity.db import connect
from trinity.intake import get_candidate, list_pending


@pytest.fixture
def isolated_cli(tmp_path, monkeypatch):
    db_path = tmp_path / "trinity.db"

    def _connect(*_args, **_kwargs):
        return connect(db_path, seed_brain=True)

    monkeypatch.setattr("trinity.cli.main.connect", _connect)
    conn = connect(db_path, seed_brain=True)
    runner = CliRunner()
    return runner, conn


def test_explain_cache_miss_with_agent_available_drafts_and_queues(isolated_cli):
    runner, conn = isolated_cli
    with patch("trinity.agent_harness.ask_agent", return_value=("Sends a SYN packet to each port.", "hermes")):
        result = runner.invoke(cli, ["explain", "nmap -sS -T4 $TARGET"])
    assert result.exit_code == 0, result.output
    assert "asked hermes for you" in result.output
    assert "AI DRAFT" in result.output
    assert "UNVERIFIED" in result.output
    assert "Sends a SYN packet to each port." in result.output
    assert "trinity intake approve" in result.output

    pending = list_pending(conn)
    assert len(pending) == 1
    assert pending[0].kind == "explanation"
    assert pending[0].source == "agent_harness"
    assert pending[0].payload["command"] == "nmap -sS -T4 $TARGET"


def test_explain_cache_miss_with_no_agent_falls_back_to_manual(isolated_cli):
    runner, _conn = isolated_cli
    with patch("trinity.agent_harness.ask_agent", return_value=(None, None)):
        result = runner.invoke(cli, ["explain", "nmap -sS -T4 $TARGET"])
    assert result.exit_code == 0, result.output
    assert "Bring this to your AI assistant" in result.output
    assert "cache-explanation" in result.output
    assert "AI DRAFT" not in result.output


def test_explain_cache_hit_never_touches_agent_harness(isolated_cli):
    runner, conn = isolated_cli
    from trinity.explain import save_explanation

    save_explanation(conn, "nmap -sS -T4 $TARGET", "already cached")
    with patch("trinity.agent_harness.ask_agent") as mock_ask:
        result = runner.invoke(cli, ["explain", "nmap -sS -T4 $TARGET"])
    assert result.exit_code == 0, result.output
    assert "From local cache" in result.output
    mock_ask.assert_not_called()


def test_error_cache_miss_with_agent_available_drafts_and_queues(isolated_cli):
    runner, conn = isolated_cli
    with patch("trinity.agent_harness.ask_agent", return_value=("Try running with sudo.", "claude")):
        result = runner.invoke(cli, ["error", "xyzzy unknown fabricated error string 12345"])
    assert result.exit_code == 0, result.output
    assert "asked claude for you" in result.output
    assert "AI DRAFT" in result.output
    assert "Try running with sudo." in result.output

    pending = list_pending(conn)
    assert len(pending) == 1
    assert pending[0].kind == "error_pattern"
    assert pending[0].payload["fix"] == "Try running with sudo."


def test_error_cache_miss_with_no_agent_falls_back_to_manual(isolated_cli):
    runner, _conn = isolated_cli
    with patch("trinity.agent_harness.ask_agent", return_value=(None, None)):
        result = runner.invoke(cli, ["error", "xyzzy unknown fabricated error string 12345"])
    assert result.exit_code == 0, result.output
    assert "Bring this to your AI assistant" in result.output
    assert "cache-error" in result.output


def test_intake_approve_after_explain_escalation_makes_it_live(isolated_cli):
    runner, conn = isolated_cli
    with patch("trinity.agent_harness.ask_agent", return_value=("Sends a SYN packet.", "hermes")):
        runner.invoke(cli, ["explain", "nmap -sS -T4 $TARGET"])

    pending = list_pending(conn)
    candidate_id = pending[0].id

    approve = runner.invoke(cli, ["intake", "approve", str(candidate_id)])
    assert approve.exit_code == 0, approve.output
    assert "Approved" in approve.output

    second = runner.invoke(cli, ["explain", "nmap -sS -T4 $TARGET"])
    assert "From local cache" in second.output


def test_intake_reject_after_explain_escalation_never_goes_live(isolated_cli):
    runner, conn = isolated_cli
    with patch("trinity.agent_harness.ask_agent", return_value=("a bad hallucinated answer", "hermes")):
        runner.invoke(cli, ["explain", "nmap -sS -T4 $TARGET"])

    pending = list_pending(conn)
    candidate_id = pending[0].id

    reject = runner.invoke(cli, ["intake", "reject", str(candidate_id), "--note", "wrong"])
    assert reject.exit_code == 0, reject.output
    assert "Rejected" in reject.output

    candidate = get_candidate(conn, candidate_id)
    assert candidate.status == "rejected"

    # Cache miss again -- still not live.
    with patch("trinity.agent_harness.ask_agent", return_value=(None, None)):
        second = runner.invoke(cli, ["explain", "nmap -sS -T4 $TARGET"])
    assert "From local cache" not in second.output
