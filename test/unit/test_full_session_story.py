"""End-to-end session story — the debate's non-negotiable acceptance test.

empty DB → brain seeded → parse Lame fixture → next has a command →
did → next changes → hint L1/L2 leak no tool/command → seeded error
hit → report contains the timeline.
"""
from __future__ import annotations

from pathlib import Path

from trinity.boxes import create_box
from trinity.coach import get_recommendation, set_accepted
from trinity.db import connect
from trinity.errors import find_error_match
from trinity.hints import get_hint
from trinity.process import process_scan_file
from trinity.report.data import gather_report_data
from trinity.report.educational import generate_educational_report

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_full_first_box_session_story(tmp_path):
    conn = connect(tmp_path / "story.db", seed_brain=True)

    assert conn.execute("SELECT count(*) AS n FROM kb_entries").fetchone()["n"] > 0
    assert conn.execute("SELECT count(*) AS n FROM command_explanations").fetchone()["n"] > 0
    assert conn.execute("SELECT count(*) AS n FROM error_patterns").fetchone()["n"] > 0

    box = create_box(conn, "Lame", target="10.10.10.3")
    result = process_scan_file(conn, box.id, FIXTURES / "lame_style_scan.xml")
    assert result is not None
    assert result.findings

    first = get_recommendation(conn, box.id)
    assert first is not None
    assert first.top.command
    first_command = first.top.command

    set_accepted(conn, first.suggestion_id)
    second = get_recommendation(conn, box.id)
    assert second is None or second.top.command != first_command

    rec = second or first
    h1 = get_hint(conn, box.id, rec.suggestion_id, rec.top.phase, rec.top.nudge, rec.top.rationale, rec.top.command)
    h2 = get_hint(conn, box.id, rec.suggestion_id, rec.top.phase, rec.top.nudge, rec.top.rationale, rec.top.command)
    assert h1.level == 1 and h2.level == 2
    for text in (h1.text, h2.text):
        assert rec.top.command not in text
        tool = (rec.top.required_tool or rec.top.command.split()[0]).lower()
        if tool and not tool.startswith("#"):
            assert tool not in text.lower()

    match = find_error_match(conn, "Connection refused")
    assert match is not None
    assert match.source == "trinity_preseed"

    data = gather_report_data(conn, box.id)
    report = generate_educational_report(data)
    assert "Lame" in report
    assert "scan" in report.lower() or "nmap" in report.lower() or "matched" in report.lower()
