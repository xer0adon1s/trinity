"""CliRunner smoke tests for the night-queue prototype verbs."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from trinity.boxes import create_box, set_status
from trinity.cli.main import cli
from trinity.db import connect

FIXTURES = Path(__file__).parent.parent / "fixtures"


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


def test_stats_hidden_without_root(tmp_path, monkeypatch):
    runner, conn = _iso(tmp_path, monkeypatch)
    create_box(conn, "NoRoot")
    result = runner.invoke(cli, ["stats"])
    assert "Root a box first" in result.output


def test_stats_after_root(tmp_path, monkeypatch):
    runner, conn = _iso(tmp_path, monkeypatch)
    box = create_box(conn, "YesRoot")
    set_status(conn, box.id, "rooted")
    result = runner.invoke(cli, ["stats"])
    assert "Rooted" in result.output


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


def test_read_nmap_fixture(tmp_path, monkeypatch):
    runner, _ = _iso(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["read", str(FIXTURES / "lame_style_scan.xml"), "--box", "ReadMe"])
    assert result.exit_code == 0, result.output
    assert "nmap" in result.output.lower()


def test_journal_lists_taxonomy(tmp_path, monkeypatch):
    runner, _ = _iso(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["journal"])
    assert "taxonomy" in result.output
    assert "First real scan" in result.output
