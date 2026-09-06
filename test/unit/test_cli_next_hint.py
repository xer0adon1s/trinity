"""CLI-layer tests for next / hint / did / skip (debate Part A.4).

These drive Click's CliRunner and assert on printed text, not just
coach.py internals. The real ~/.trinity DB is never touched."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from trinity.boxes import create_box
from trinity.cli.main import cli
from trinity.db import connect
from trinity.process import process_scan_file

FIXTURES = Path(__file__).parent.parent / "fixtures"
FAKE_TOOL = "xyzzytool"


@pytest.fixture
def isolated_cli(tmp_path, monkeypatch):
    db_path = tmp_path / "trinity.db"

    def _connect(*_args, **_kwargs):
        return connect(db_path, seed_brain=True)

    monkeypatch.setattr("trinity.cli.main.connect", _connect)
    monkeypatch.setattr(
        "trinity.coach.is_tool_installed",
        lambda name: name != FAKE_TOOL,
    )
    conn = connect(db_path, seed_brain=True)
    runner = CliRunner()
    return runner, conn


def _insert_outstanding(conn, box_id, *, command, required_tool, phase="enum", rationale="why"):
    conn.execute(
        "INSERT INTO suggestions (box_id, phase, command, rationale, nudge, required_tool) "
        "VALUES (?, ?, ?, ?, 'look around', ?)",
        (box_id, phase, command, rationale, required_tool),
    )
    conn.commit()


def test_next_tool_missing_still_shows_command_and_also_worth_trying(isolated_cli):
    runner, conn = isolated_cli
    box = create_box(conn, "CliBox")
    _insert_outstanding(
        conn, box.id, command="xyzzytool -x", required_tool=FAKE_TOOL, phase="recon",
    )
    _insert_outstanding(
        conn, box.id, command="ftp $TARGET", required_tool="ftp", phase="enum",
    )

    result = runner.invoke(cli, ["next", "--box", "CliBox"])
    assert result.exit_code == 0, result.output
    assert "xyzzytool -x" in result.output
    assert "xyzzytool" in result.output
    assert "install" in result.output.lower()
    assert "ftp $TARGET" in result.output
    assert "Also worth trying" in result.output


def test_hint_educational_hides_tool_until_level_3(isolated_cli):
    runner, conn = isolated_cli
    box = create_box(conn, "HintCli", mode="educational")
    _insert_outstanding(
        conn, box.id,
        command=f"{FAKE_TOOL} --go",
        required_tool=FAKE_TOOL,
        rationale="run the secret tool now",
    )

    l1 = runner.invoke(cli, ["hint", "--box", "HintCli"])
    l2 = runner.invoke(cli, ["hint", "--box", "HintCli"])
    l3 = runner.invoke(cli, ["hint", "--box", "HintCli"])
    assert l1.exit_code == l2.exit_code == l3.exit_code == 0

    assert FAKE_TOOL not in l1.output
    assert "install" not in l1.output.lower()
    assert FAKE_TOOL not in l2.output
    assert "install" not in l2.output.lower()

    assert FAKE_TOOL in l3.output
    assert "install" in l3.output.lower()


def test_hint_professional_shows_install_immediately(isolated_cli):
    runner, conn = isolated_cli
    box = create_box(conn, "ProHint", mode="professional")
    _insert_outstanding(
        conn, box.id, command=f"{FAKE_TOOL} --go", required_tool=FAKE_TOOL,
    )

    result = runner.invoke(cli, ["hint", "--box", "ProHint"])
    assert result.exit_code == 0, result.output
    assert "install" in result.output.lower()
    assert FAKE_TOOL in result.output


def test_did_then_next_recommends_something_else(isolated_cli):
    runner, conn = isolated_cli
    box = create_box(conn, "DidBox", target="10.10.10.3")
    process_scan_file(conn, box.id, FIXTURES / "lame_style_scan.xml")

    first = runner.invoke(cli, ["next", "--box", "DidBox"])
    assert first.exit_code == 0, first.output
    assert "Recommended next" in first.output

    did = runner.invoke(cli, ["did", "--box", "DidBox"])
    assert did.exit_code == 0, did.output
    assert "Marked done" in did.output

    second = runner.invoke(cli, ["next", "--box", "DidBox"])
    assert second.exit_code == 0, second.output
    # After accepting the top rec, printed next command must change
    # (or we run out of suggestions).
    assert "Marked done" not in second.output or "Next up" in did.output
    assert did.output != first.output
    assert "Next up:" in did.output


def test_suggest_and_engagement_set_fail_closed_on_unknown_box(isolated_cli):
    runner, _conn = isolated_cli
    suggest = runner.invoke(cli, ["suggest", "--box", "GhostBox"])
    engagement = runner.invoke(cli, ["engagement-set", "--box", "GhostBox", "--client", "Nope"])
    assert suggest.exit_code != 0
    assert engagement.exit_code != 0
    assert "No box named" in suggest.output
    assert "No box named" in engagement.output
