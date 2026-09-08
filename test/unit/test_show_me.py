"""Tests for trinity.show_me — the live trigger of Assimilator's core
loop (docs/SHOW_ME_MODE.md). Real agent CLIs aren't available in the
test environment, so detect_agent/invoke_agent are mocked; the runner
logic (denylist, target-pin, milestone detection, ledger writes,
report-integrity population) is exercised for real."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from trinity.agent_harness import AgentInfo
from trinity.boxes import create_box
from trinity.report.data import gather_report_data
from trinity.show_me import (
    VALID_MILESTONES,
    build_disclosure,
    has_any_show_me_runs,
    has_attestation,
    is_command_allowed,
    record_attestation,
    run_show_me,
)

_FAKE_AGENT = AgentInfo("claude", "claude", lambda p: ["claude", "-p", p])


def test_run_show_me_rejects_invalid_milestone(conn):
    box = create_box(conn, "BadMilestone", target="10.10.10.5")
    with pytest.raises(ValueError):
        run_show_me(conn, box.id, "solve_everything")


def test_run_show_me_rejects_box_with_no_target(conn):
    box = create_box(conn, "NoTarget")
    with pytest.raises(ValueError):
        run_show_me(conn, box.id, "foothold")


def test_run_show_me_fails_cleanly_with_no_agent_detected(conn):
    box = create_box(conn, "NoAgent", target="10.10.10.5")
    with patch("trinity.show_me.detect_agent", return_value=None):
        result = run_show_me(conn, box.id, "foothold")
    assert result.outcome == "failed"
    assert "no agent" in result.stop_reason.lower()
    # Still writes a show_me_runs row so the attempt is on record.
    assert has_any_show_me_runs(conn, box.id)


def test_is_command_allowed_blocks_destructive_verbs():
    allowed, reason = is_command_allowed("rm -rf /", "10.10.10.5")
    assert not allowed
    assert "denylist" in reason


def test_is_command_allowed_blocks_off_target_host():
    allowed, reason = is_command_allowed("curl http://10.10.10.99/", "10.10.10.5")
    assert not allowed
    assert "10.10.10.99" in reason


def test_is_command_allowed_permits_on_target_command():
    allowed, reason = is_command_allowed("curl http://10.10.10.5/", "10.10.10.5")
    assert allowed
    assert reason is None


def test_show_me_succeeds_and_populates_report(conn):
    box = create_box(conn, "SuccessBox", target="10.10.10.7")

    def fake_invoke(agent, prompt, timeout=60):
        if "nothing run yet" in prompt:
            return "id"
        return "DONE"

    with patch("trinity.show_me.detect_agent", return_value=_FAKE_AGENT), \
         patch("trinity.show_me.invoke_agent", side_effect=fake_invoke), \
         patch("trinity.show_me.subprocess.run") as mock_run:
        mock_run.return_value.stdout = "uid=33(www-data) gid=33(www-data) groups=33(www-data)"
        mock_run.return_value.stderr = ""
        result = run_show_me(conn, box.id, "foothold")

    assert result.outcome == "succeeded"
    assert result.recipe_for_student == "id"
    assert has_any_show_me_runs(conn, box.id)

    data = gather_report_data(conn, box.id)
    assert len(data.ai_assisted_steps) == 1
    assert data.ai_assisted_steps[0].milestone == "foothold"
    assert data.ai_assisted_steps[0].agent_used == "claude"


def test_show_me_detects_already_known_kb_hit(seeded_conn):
    box = create_box(seeded_conn, "AlreadyKnownBox", target="10.10.10.3")

    def fake_invoke(agent, prompt, timeout=60):
        if "nothing run yet" in prompt:
            return "id"
        return "DONE"

    with patch("trinity.show_me.detect_agent", return_value=_FAKE_AGENT), \
         patch("trinity.show_me.invoke_agent", side_effect=fake_invoke), \
         patch("trinity.show_me.subprocess.run") as mock_run, \
         patch("trinity.show_me.check_already_known") as mock_known:
        mock_run.return_value.stdout = "uid=0(root) gid=0(root)"
        mock_run.return_value.stderr = ""
        from trinity.assimilator import AlreadyKnownHit
        mock_known.return_value = AlreadyKnownHit(kb_id=1, title="vsftpd backdoor", summary="known")
        result = run_show_me(seeded_conn, box.id, "privesc_to_root")

    assert result.outcome == "already_known"
    assert result.already_known_title == "vsftpd backdoor"


def test_disclosure_mentions_own_session_not_students_terminal():
    disclosure = build_disclosure("claude", "foothold")
    assert "ITS OWN session" in disclosure.banner
    assert "not your terminal" in disclosure.banner


def test_attestation_round_trip(conn):
    assert not has_attestation(conn)
    record_attestation(conn)
    assert has_attestation(conn)


def test_all_milestones_are_valid_choices():
    assert VALID_MILESTONES == {"foothold", "privesc_to_user", "privesc_to_root"}
