"""CLI-layer tests for `trinity notify on/off/test/show`."""
from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from trinity.cli.main import cli
from trinity.db import connect


def _isolated(tmp_path, monkeypatch):
    db_path = tmp_path / "trinity.db"

    def _connect(*_args, **_kwargs):
        return connect(db_path, seed_brain=True)

    monkeypatch.setattr("trinity.cli.main.connect", _connect)
    return CliRunner()


def test_notify_show_off_by_default(tmp_path, monkeypatch):
    runner = _isolated(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["notify", "show"])
    assert result.exit_code == 0, result.output
    assert "Off" in result.output


def test_notify_on_then_show(tmp_path, monkeypatch):
    runner = _isolated(tmp_path, monkeypatch)
    on_result = runner.invoke(cli, ["notify", "on"])
    assert on_result.exit_code == 0, on_result.output
    assert "On" in on_result.output

    show_result = runner.invoke(cli, ["notify", "show"])
    assert "On" in show_result.output


def test_notify_on_then_off(tmp_path, monkeypatch):
    runner = _isolated(tmp_path, monkeypatch)
    runner.invoke(cli, ["notify", "on"])
    off_result = runner.invoke(cli, ["notify", "off"])
    assert off_result.exit_code == 0, off_result.output
    assert "Off" in off_result.output

    show_result = runner.invoke(cli, ["notify", "show"])
    assert "Off" in show_result.output


def test_notify_test_reports_success(tmp_path, monkeypatch):
    runner = _isolated(tmp_path, monkeypatch)
    with patch("trinity.notify.send_test_notification", return_value=True):
        result = runner.invoke(cli, ["notify", "test"])
    assert result.exit_code == 0, result.output
    assert "Sent" in result.output


def test_notify_test_reports_failure_without_crashing(tmp_path, monkeypatch):
    runner = _isolated(tmp_path, monkeypatch)
    with patch("trinity.notify.send_test_notification", return_value=False):
        result = runner.invoke(cli, ["notify", "test"])
    assert result.exit_code == 0, result.output
    assert "Couldn't send" in result.output
