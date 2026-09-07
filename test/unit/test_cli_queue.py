"""CliRunner smoke tests for the night-queue prototype verbs."""
from __future__ import annotations

from click.testing import CliRunner

from trinity.cli.main import cli
from trinity.db import connect


def _iso(tmp_path, monkeypatch):
    db_path = tmp_path / "trinity.db"

    def _connect(*_a, **_k):
        return connect(db_path, seed_brain=True)

    monkeypatch.setattr("trinity.cli.main.connect", _connect)
    return CliRunner(), connect(db_path, seed_brain=True)


def test_methods_lame(tmp_path, monkeypatch):
    runner, _ = _iso(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["methods", "--name", "Lame"])
    assert result.exit_code == 0, result.output
    assert "0xdf" in result.output
    assert "CVE-2007-2447" in result.output


def test_hash_md5(tmp_path, monkeypatch):
    runner, _ = _iso(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["hash", "5f4dcc3b5aa765d61d8327deb882cf99"])
    assert "md5" in result.output.lower()


def test_gtfobins_list_and_vim(tmp_path, monkeypatch):
    runner, _ = _iso(tmp_path, monkeypatch)
    listed = runner.invoke(cli, ["gtfobins"])
    assert "vim" in listed.output
    vim = runner.invoke(cli, ["gtfobins", "vim"])
    assert "gtfobins.github.io" in vim.output
