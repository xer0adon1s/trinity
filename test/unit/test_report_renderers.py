"""Smoke tests for previously-unimported report renderer helpers."""
from __future__ import annotations

from trinity.boxes import create_box
from trinity.report.attack import map_attack
from trinity.report.data import gather_report_data
from trinity.report.notebook import generate_notebook_report
from trinity.report.remediation import draft_remediation
from trinity.timeline import log_event


def _seed_findings(conn, box_id: int) -> None:
    log_event(
        conn, box_id, "match", "10.10.10.3:21 matched: vsftpd 2.3.4 backdoor",
        phase="recon", detail="Known backdoor, root shell on port 6200.", severity="critical",
    )
    log_event(
        conn, box_id, "suggestion", "suggested: gobuster dir -u http://10.10.10.3",
        phase="enum",
    )


def test_notebook_renderer_smoke(conn):
    box = create_box(conn, "NotebookRendererBox", target="10.10.10.3")
    _seed_findings(conn, box.id)
    data = gather_report_data(conn, box.id)
    report = generate_notebook_report(data)
    assert "NotebookRendererBox" in report


def test_attack_mapper_smoke(conn):
    box = create_box(conn, "AttackRendererBox")
    _seed_findings(conn, box.id)
    data = gather_report_data(conn, box.id)
    hits = []
    for event in data.events:
        hits.extend(map_attack(f"{event.summary} {event.detail or ''}"))
    assert hits


def test_remediation_draft_smoke(conn):
    box = create_box(conn, "RemediationRendererBox")
    _seed_findings(conn, box.id)
    data = gather_report_data(conn, box.id)
    finding = next(e for e in data.events if e.event_type == "match")
    text = draft_remediation(finding.summary, finding.detail)
    assert isinstance(text, str) and len(text) > 20
