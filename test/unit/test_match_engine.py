"""Tests for the match engine and severity heuristics."""
from __future__ import annotations

from trinity.kb.severity import rate_severity, severity_from_cvss
from trinity.match.engine import match_finding
from trinity.parsers.nmap import Finding


def test_exact_service_version_match_scores_highest(seeded_conn):
    finding = Finding(source_tool="nmap", kind="port", host="10.10.10.3", port=21,
                       service="ftp", product="vsftpd", version="2.3.4")
    matches = match_finding(seeded_conn, finding)
    assert matches[0].score == 1.0
    assert "backdoor" in matches[0].title.lower()
    assert matches[0].severity == "critical"


def test_service_match_without_version_scores_lower(seeded_conn):
    finding = Finding(source_tool="nmap", kind="port", host="10.10.10.3", port=21,
                       service="ftp", product="vsftpd", version="9.9.9")
    matches = match_finding(seeded_conn, finding)
    # Still matches on service, just not the version-specific top score.
    assert any(m.score == 0.9 for m in matches)
    assert not any(m.score == 1.0 for m in matches)


def test_no_match_returns_empty_list(seeded_conn):
    finding = Finding(source_tool="nmap", kind="port", host="10.10.10.3", port=9999,
                       service="totally-unknown-service-xyz")
    matches = match_finding(seeded_conn, finding)
    assert matches == []


def test_fts_fallback_matches_on_free_text(seeded_conn):
    finding = Finding(source_tool="nmap", kind="port", host="10.10.10.3", port=80,
                       detail="privesc SUID linux binary found")
    matches = match_finding(seeded_conn, finding)
    assert any("SUID" in m.title for m in matches)


def test_result_limit_is_respected(seeded_conn):
    finding = Finding(source_tool="nmap", kind="port", host="10.10.10.3", port=21,
                       service="ftp", product="vsftpd", version="2.3.4")
    matches = match_finding(seeded_conn, finding, limit=1)
    assert len(matches) == 1


# --- severity heuristic ---

def test_backdoor_rated_critical():
    assert rate_severity("vsftpd 2.3.4 - Backdoor Command Execution") == "critical"


def test_privilege_escalation_rated_high():
    assert rate_severity("OpenSSH - Privilege Escalation") == "high"


def test_denial_of_service_rated_low():
    assert rate_severity("Samba - Denial of Service (PoC)") == "low"


def test_unrecognized_title_defaults_medium():
    assert rate_severity("Some obscure thing nobody's seen before") == "medium"


def test_cvss_bands():
    assert severity_from_cvss(9.8) == "critical"
    assert severity_from_cvss(7.5) == "high"
    assert severity_from_cvss(5.0) == "medium"
    assert severity_from_cvss(2.0) == "low"
    assert severity_from_cvss(0.0) == "info"
