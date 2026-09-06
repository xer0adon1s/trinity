"""Tests for the gobuster/ffuf/nikto/whatweb/enum4linux-ng parsers."""
from __future__ import annotations

from pathlib import Path

from trinity.parsers.enum4linux_ng import parse_enum4linux_ng_json
from trinity.parsers.ffuf import parse_ffuf_json
from trinity.parsers.gobuster import parse_gobuster_text
from trinity.parsers.nikto import parse_nikto_json
from trinity.parsers.whatweb import parse_whatweb_json

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_gobuster_parses_all_lines():
    findings = parse_gobuster_text(FIXTURES / "gobuster_sample.txt")
    assert len(findings) == 4


def test_gobuster_extracts_path_status_size():
    findings = parse_gobuster_text(FIXTURES / "gobuster_sample.txt")
    admin = next(f for f in findings if f.path == "/admin")
    assert admin.status_code == 301
    assert admin.detail == "size=178"


def test_gobuster_source_tool():
    findings = parse_gobuster_text(FIXTURES / "gobuster_sample.txt")
    assert all(f.source_tool == "gobuster" and f.kind == "path" for f in findings)


def test_ffuf_parses_all_results():
    findings = parse_ffuf_json(FIXTURES / "ffuf_sample.json")
    assert len(findings) == 2


def test_ffuf_extracts_status_and_url():
    findings = parse_ffuf_json(FIXTURES / "ffuf_sample.json")
    admin = next(f for f in findings if f.status_code == 301)
    assert admin.path == "http://target/admin"
    assert admin.host == "target"


def test_nikto_parses_all_vulnerabilities():
    findings = parse_nikto_json(FIXTURES / "nikto_sample.json")
    assert len(findings) == 2
    assert all(f.source_tool == "nikto" and f.kind == "vuln" for f in findings)


def test_nikto_extracts_host_port_url_msg():
    findings = parse_nikto_json(FIXTURES / "nikto_sample.json")
    indexing = next(f for f in findings if "Directory indexing" in (f.detail or ""))
    assert indexing.host == "target"
    assert indexing.port == 80
    assert indexing.path == "/admin/"


def test_whatweb_parses_plugins_with_version():
    findings = parse_whatweb_json(FIXTURES / "whatweb_sample.jsonl")
    apache = next(f for f in findings if f.product == "Apache")
    assert apache.version == "2.2.8"
    assert apache.host == "http://target"


def test_whatweb_handles_plugin_with_no_version():
    findings = parse_whatweb_json(FIXTURES / "whatweb_sample.jsonl")
    country = next(f for f in findings if f.product == "Country")
    assert country.version is None


def test_enum4linux_ng_parses_users_shares_osinfo():
    findings = parse_enum4linux_ng_json(FIXTURES / "enum4linux_ng_sample.json")
    kinds = {f.kind for f in findings}
    assert kinds == {"user", "share", "os_info"}


def test_enum4linux_ng_user_count():
    findings = parse_enum4linux_ng_json(FIXTURES / "enum4linux_ng_sample.json")
    users = [f for f in findings if f.kind == "user"]
    assert len(users) == 2


def test_enum4linux_ng_share_detail():
    findings = parse_enum4linux_ng_json(FIXTURES / "enum4linux_ng_sample.json")
    backup_share = next(f for f in findings if f.kind == "share" and f.path == "backup")
    assert backup_share.detail == "Backup files"
