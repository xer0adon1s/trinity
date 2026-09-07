"""Tests for the Update Framework Part 1 CLI wiring: the top-level
`cli()` group callback (invoke_without_command=True, runs on every
launch) must register a sync function for source='gtfobins' via
run_sync_if_due(), and a sync failure must never raise into a normal
command (silent-degrade contract, docs/UPDATE_FRAMEWORK.md Part 1)."""
from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from trinity.cli.main import cli


def test_cli_group_triggers_gtfobins_sync_on_launch(tmp_path):
    db_path = tmp_path / "trinity.db"
    calls = []

    def fake_run_sync_if_due(conn, source, sync_fn, *args, **kwargs):
        calls.append(source)
        return True

    with patch("trinity.db.DEFAULT_DB_PATH", db_path), \
         patch("trinity.update_sync.run_sync_if_due", side_effect=fake_run_sync_if_due) as mock_run:
        runner = CliRunner()
        result = runner.invoke(cli, ["box-list"])

    assert result.exit_code == 0
    assert mock_run.called
    assert mock_run.call_args.args[1] == "gtfobins"


def test_cli_group_swallows_sync_failure_without_raising(tmp_path):
    db_path = tmp_path / "trinity.db"

    with patch("trinity.db.DEFAULT_DB_PATH", db_path), \
         patch("trinity.update_sync.run_sync_if_due", side_effect=RuntimeError("boom")):
        runner = CliRunner()
        result = runner.invoke(cli, ["box-list"])

    # The command must still succeed even though the sync hook blew up.
    assert result.exit_code == 0
    assert result.exception is None


def test_cli_group_does_not_actually_touch_the_network(tmp_path):
    """Guards against the sync's real git clone/pull firing during a
    normal command run in tests -- the underlying git op must be
    mockable/avoidable, not hard-wired to hit the network."""
    db_path = tmp_path / "trinity.db"

    with patch("trinity.db.DEFAULT_DB_PATH", db_path), \
         patch("trinity.gtfobins._clone_or_pull") as mock_clone, \
         patch("trinity.gtfobins._parse_repo_to_cache", return_value={}):
        runner = CliRunner()
        result = runner.invoke(cli, ["box-list"])

    assert result.exit_code == 0
    # First launch: sync_state has no row for 'gtfobins' yet, so it's due,
    # and the sync function runs -- but only the mocked git op, no real clone.
    assert mock_clone.called
