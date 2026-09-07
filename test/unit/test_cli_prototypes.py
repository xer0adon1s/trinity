"""CliRunner coverage for the prototype verbs (shell / unlock / loot)."""
from __future__ import annotations

from click.testing import CliRunner

from trinity.boxes import create_box, get_box_by_name
from trinity.cli.main import cli
from trinity.db import connect
from trinity.loot import list_loot


def isolated(tmp_path, monkeypatch):
    db_path = tmp_path / "trinity.db"

    def _connect(*_args, **_kwargs):
        return connect(db_path, seed_brain=False)

    monkeypatch.setattr("trinity.cli.main.connect", _connect)
    return CliRunner(), connect(db_path, seed_brain=False)


def test_shell_then_next_recommends_privesc(tmp_path, monkeypatch):
    runner, conn = isolated(tmp_path, monkeypatch)
    create_box(conn, "ProtoBox")
    result = runner.invoke(cli, ["shell", "--box", "ProtoBox", "--as", "user"])
    assert result.exit_code == 0, result.output
    assert "user shell" in result.output
    assert "sudo -l" in result.output

    nxt = runner.invoke(cli, ["next", "--box", "ProtoBox"])
    assert nxt.exit_code == 0, nxt.output
    assert any(token in nxt.output for token in ("cat /etc/crontab", "sudo -l", "linpeas", "find /"))
    assert "trinity unlock" in nxt.output


def test_unlock_take_and_decline(tmp_path, monkeypatch):
    runner, conn = isolated(tmp_path, monkeypatch)
    create_box(conn, "UnlockCli")
    runner.invoke(cli, ["shell", "--box", "UnlockCli", "--as", "user"])
    taken = runner.invoke(cli, ["unlock", "--box", "UnlockCli", "--take"])
    assert taken.exit_code == 0, taken.output
    assert "privilege escalation" in taken.output.lower() or "foothold" in taken.output.lower()

    empty = runner.invoke(cli, ["unlock", "--box", "UnlockCli"])
    assert "Nothing unlocked" in empty.output


def test_loot_add_and_list(tmp_path, monkeypatch):
    runner, conn = isolated(tmp_path, monkeypatch)
    create_box(conn, "LootCli")
    added = runner.invoke(
        cli, ["loot", "add", "--box", "LootCli", "--kind", "flag", "--value", "HTB{x}", "--note", "root.txt"]
    )
    assert added.exit_code == 0, added.output
    listed = runner.invoke(cli, ["loot", "list", "--box", "LootCli"])
    assert "HTB{x}" in listed.output
    items = list_loot(conn, get_box_by_name(conn, "LootCli").id)
    assert items[0].value == "HTB{x}"


def test_hard_box_next_mentions_difficulty(tmp_path, monkeypatch):
    runner, conn = isolated(tmp_path, monkeypatch)
    box = create_box(conn, "HardCli", difficulty="hard")
    conn.execute(
        "INSERT INTO suggestions (box_id, phase, command, rationale, nudge) "
        "VALUES (?, 'enum', 'ftp $TARGET', 'why', 'nudge')",
        (box.id,),
    )
    conn.commit()
    result = runner.invoke(cli, ["next", "--box", "HardCli"])
    assert result.exit_code == 0, result.output
    assert "Listed as Hard" in result.output
