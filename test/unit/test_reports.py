"""Tests for report generation (educational + professional modes)."""
from __future__ import annotations

from trinity.boxes import create_box
from trinity.report.data import gather_report_data
from trinity.report.educational import generate_educational_report
from trinity.report.professional import generate_professional_report
from trinity.timeline import log_event


def _seed_timeline(conn, box_id):
    log_event(conn, box_id, "scan", "nmap scan parsed: 2 open port(s) found", phase="recon")
    log_event(
        conn, box_id, "match", "10.10.10.3:21 matched: vsftpd 2.3.4 backdoor",
        phase="recon", detail="Known backdoor, root shell on port 6200.", severity="critical",
    )
    log_event(
        conn, box_id, "match", "10.10.10.3:80 matched: directory brute-force suggested",
        phase="recon", detail="Standard next step for any webserver.", severity="info",
    )
    log_event(conn, box_id, "suggestion", "suggested: gobuster dir -u http://10.10.10.3", phase="enum")


def test_educational_report_includes_box_name(conn):
    box = create_box(conn, "ReportBox", target="10.10.10.3")
    _seed_timeline(conn, box.id)
    data = gather_report_data(conn, box.id)

    report = generate_educational_report(data)
    assert "ReportBox" in report
    assert "10.10.10.3" in report


def test_educational_report_includes_every_event_summary(conn):
    box = create_box(conn, "ReportBox")
    _seed_timeline(conn, box.id)
    data = gather_report_data(conn, box.id)

    report = generate_educational_report(data)
    assert "vsftpd 2.3.4 backdoor" in report
    assert "directory brute-force suggested" in report
    assert "gobuster dir" in report


def test_educational_report_handles_empty_timeline(conn):
    box = create_box(conn, "EmptyBox")
    data = gather_report_data(conn, box.id)

    report = generate_educational_report(data)
    assert "EmptyBox" in report
    assert "Nothing's been logged" in report


def test_educational_report_summarizes_by_severity(conn):
    box = create_box(conn, "ReportBox")
    _seed_timeline(conn, box.id)
    data = gather_report_data(conn, box.id)

    report = generate_educational_report(data)
    assert "[CRITICAL]" in report


def test_professional_report_includes_engagement_table(conn):
    box = create_box(conn, "ProBox", target="10.10.10.3", platform="htb")
    _seed_timeline(conn, box.id)
    data = gather_report_data(conn, box.id)

    report = generate_professional_report(data)
    assert "Engagement Summary" in report
    assert "10.10.10.3" in report
    assert "htb" in report


def test_professional_report_groups_findings_by_severity(conn):
    box = create_box(conn, "ProBox")
    _seed_timeline(conn, box.id)
    data = gather_report_data(conn, box.id)

    report = generate_professional_report(data)
    critical_pos = report.find("Critical")
    info_pos = report.find("Info")
    assert critical_pos != -1
    assert info_pos != -1
    assert critical_pos < info_pos  # critical findings come before info findings


def test_professional_report_uses_engagement_metadata_when_set(conn):
    box = create_box(conn, "ProBox")
    conn.execute(
        "INSERT INTO engagement_meta (box_id, client_name, tester_name) VALUES (?, ?, ?)",
        (box.id, "Acme Corp", "Alexander"),
    )
    conn.commit()
    _seed_timeline(conn, box.id)
    data = gather_report_data(conn, box.id)

    report = generate_professional_report(data)
    assert "Acme Corp" in report
    assert "Alexander" in report


def test_professional_report_includes_methodology_timeline(conn):
    box = create_box(conn, "ProBox")
    _seed_timeline(conn, box.id)
    data = gather_report_data(conn, box.id)

    report = generate_professional_report(data)
    assert "Methodology" in report
    assert "recon" in report


def test_gather_report_data_raises_for_missing_box(conn):
    import pytest
    with pytest.raises(ValueError):
        gather_report_data(conn, 99999)
