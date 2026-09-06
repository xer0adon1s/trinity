"""Tests for the nmap XML parser."""
from __future__ import annotations

from pathlib import Path

from trinity.parsers.nmap import parse_nmap_xml

FIXTURE = Path(__file__).parent.parent / "fixtures" / "lame_style_scan.xml"


def test_parses_all_open_ports():
    findings = parse_nmap_xml(FIXTURE)
    assert len(findings) == 5


def test_extracts_service_and_version():
    findings = parse_nmap_xml(FIXTURE)
    ftp = next(f for f in findings if f.port == 21)
    assert ftp.service == "ftp"
    assert ftp.product == "vsftpd"
    assert ftp.version == "2.3.4"


def test_extracts_script_output_into_detail():
    findings = parse_nmap_xml(FIXTURE)
    ftp = next(f for f in findings if f.port == 21)
    assert ftp.detail is not None
    assert "Anonymous FTP login allowed" in ftp.detail


def test_host_ip_populated_on_every_finding():
    findings = parse_nmap_xml(FIXTURE)
    assert all(f.host == "10.10.10.3" for f in findings)


def test_source_tool_is_nmap():
    findings = parse_nmap_xml(FIXTURE)
    assert all(f.source_tool == "nmap" for f in findings)
