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
    # The unlock-card teaser is now arbitrated (advisories.py) rather
    # than always printed: a real curiosity card genuinely IS
    # available here, so `trinity unlock` should surface UNLESS a
    # higher-priority advisory (e.g. a rabbit-hole stuck-signal) won
    # the single advisory slot instead -- confirm one of those two
    # explanations holds, not the old "always printed" assumption.
    from trinity.advisories import pick_advisory
    from trinity.boxes import get_box_by_name

    box = get_box_by_name(conn, "ProtoBox")
    advisory = pick_advisory(conn, box)
    if advisory and advisory.kind == "unlock":
        assert "trinity unlock" in nxt.output
    else:
        # A different (higher-priority) advisory won the slot instead
        # -- the unlock card is still genuinely available, just
        # deferred to a future `next` call rather than shown now.
        assert advisory is not None


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
    # Composed into the WHY narration as one flowing sentence now
    # (advisories.py), not a separate standalone line -- see
    # docs/FEATURES_BACKLOG.md's "structural fix" note. Normalize
    # whitespace first: Rich wraps long lines at the terminal width,
    # which can split the sentence across a line break mid-phrase.
    normalized = " ".join(result.output.split())
    assert "listed as Hard" in normalized
    assert "taking a long time here is normal" in normalized
