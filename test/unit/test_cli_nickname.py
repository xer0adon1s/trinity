"""CLI-layer tests for `trinity nickname on/off/set/show`."""
from __future__ import annotations

from click.testing import CliRunner

from trinity.cli.main import cli
from trinity.db import connect


def _isolated(tmp_path, monkeypatch):
    db_path = tmp_path / "trinity.db"

    def _connect(*_args, **_kwargs):
        return connect(db_path, seed_brain=True)

    monkeypatch.setattr("trinity.cli.main.connect", _connect)
    return CliRunner()


def test_nickname_show_when_never_set(tmp_path, monkeypatch):
    runner = _isolated(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["nickname", "show"])
    assert result.exit_code == 0, result.output
    assert "Off" in result.output


def test_nickname_set_then_show(tmp_path, monkeypatch):
    runner = _isolated(tmp_path, monkeypatch)
    set_result = runner.invoke(cli, ["nickname", "set", "DocTest"])
    assert set_result.exit_code == 0, set_result.output
    assert "DocTest" in set_result.output

    show_result = runner.invoke(cli, ["nickname", "show"])
    assert "On" in show_result.output
    assert "DocTest" in show_result.output


def test_nickname_off_then_on_recalls_the_name(tmp_path, monkeypatch):
    runner = _isolated(tmp_path, monkeypatch)
    runner.invoke(cli, ["nickname", "set", "DocTest"])

    off_result = runner.invoke(cli, ["nickname", "off"])
    assert off_result.exit_code == 0, off_result.output
    assert "Off" in off_result.output

    show_after_off = runner.invoke(cli, ["nickname", "show"])
    assert "Off" in show_after_off.output
    assert "DocTest" in show_after_off.output  # mentions the saved-but-inactive name

    on_result = runner.invoke(cli, ["nickname", "on"])
    assert on_result.exit_code == 0, on_result.output
    assert "DocTest" in on_result.output

    show_after_on = runner.invoke(cli, ["nickname", "show"])
    assert "On" in show_after_on.output
    assert "DocTest" in show_after_on.output


def test_nickname_on_with_no_name_ever_set_prompts_to_set_one(tmp_path, monkeypatch):
    runner = _isolated(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["nickname", "on"])
    assert result.exit_code == 0, result.output
    assert "nickname set" in result.output
