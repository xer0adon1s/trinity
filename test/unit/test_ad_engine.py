"""AD enumeration prototype tests.

Negative-control tests (Blue / Legacy) are first on purpose:
docs/AD_ENGINE_PROTOTYPE_PROJECT.md §1 requires proving SMB+RPC
Windows boxes do NOT trigger DC detection before the positive path
is trusted.
"""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from trinity.boxes import create_box
from trinity.cli.main import cli
from trinity.db import connect
from trinity.parsers.ad_recon import (
    detect_ad_signals,
    parse_ad_recon_file,
    parse_getnpusers,
    parse_getuserspns,
    parse_ldapsearch,
)
from trinity.parsers.nmap import Finding, parse_nmap_xml
from trinity.suggest.engine import suggest_next_commands

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _finding(**kwargs) -> Finding:
    defaults = {"source_tool": "nmap", "kind": "port"}
    defaults.update(kwargs)
    return Finding(**defaults)


# --- §1 false-positive discipline: negative controls FIRST ---


def test_blue_real_ports_do_not_trigger_ad_detection():
    """HTB Blue 10.10.10.40 — 0xdf
    https://0xdf.gitlab.io/2021/05/11/htb-blue.html
    Open: 135 msrpc, 139 netbios-ssn, 445 microsoft-ds, 49152-49157 msrpc.
    workgroup WORKGROUP. Single-host EternalBlue box, not a DC."""
    findings = parse_nmap_xml(FIXTURES / "ad_blue.xml")
    ports = {f.port for f in findings}
    assert {135, 139, 445}.issubset(ports)
    assert not {88, 389, 53, 3268, 3269} & ports
    assert detect_ad_signals(findings) is None


def test_legacy_real_ports_do_not_trigger_ad_detection():
    """HTB Legacy 10.10.10.4 — justus.pw writeup + 0xdf
    https://0xdf.gitlab.io/2019/02/21/htb-legacy.html
    Open: 135, 139, 445. Workgroup HTB. Windows XP, not a DC."""
    findings = parse_nmap_xml(FIXTURES / "ad_legacy.xml")
    ports = {f.port for f in findings}
    assert ports == {135, 139, 445}
    assert detect_ad_signals(findings) is None


def test_smb_rpc_only_constructed_findings_do_not_trigger():
    """Same Blue port facts as Finding objects, no XML — guards the
    detector independently of the nmap parser."""
    findings = [
        _finding(host="10.10.10.40", port=135, service="msrpc"),
        _finding(host="10.10.10.40", port=139, service="netbios-ssn"),
        _finding(
            host="10.10.10.40", port=445, service="microsoft-ds",
            detail="workgroup: WORKGROUP",
        ),
    ]
    assert detect_ad_signals(findings) is None


# --- positive detection ---


def test_forest_dc_signature_fires_and_extracts_domain():
    """HTB Forest 10.10.10.161 — https://joenibe.github.io/htb/forest/
    DC port cluster + ldap-rootdse namingContexts DC=htb,DC=local."""
    findings = parse_nmap_xml(FIXTURES / "ad_forest.xml")
    hit = detect_ad_signals(findings)
    assert hit is not None
    assert hit.kind == "ad_domain_controller"
    assert "domain: htb.local" in (hit.detail or "")


def test_ldap_plus_kerberos_without_domain_name_still_fires():
    findings = [
        _finding(host="10.10.10.10", port=389, service="ldap"),
        _finding(host="10.10.10.10", port=88, service="kerberos-sec"),
        _finding(host="10.10.10.10", port=445, service="microsoft-ds"),
    ]
    hit = detect_ad_signals(findings)
    assert hit is not None
    assert hit.kind == "ad_domain_controller"
    assert "domain:" not in (hit.detail or "")


def test_ldap_alone_does_not_fire():
    """A lone LDAP port without Kerberos/DNS and without a naming
    context is not enough — could be a directory app, not a DC."""
    findings = [_finding(host="10.10.10.10", port=389, service="ldap")]
    assert detect_ad_signals(findings) is None


# --- parsers (real-shaped fixtures, formats cited in ad_recon.py) ---


def test_ldapsearch_namingcontexts_is_anon_bind_and_skips_computers():
    findings = parse_ldapsearch(
        (FIXTURES / "ad_ldapsearch_forest.txt").read_text()
    )
    kinds = {f.kind for f in findings}
    assert "ldap_anon" in kinds
    users = [f.detail for f in findings if f.kind == "user"]
    assert "user: svc-alfresco" in users
    assert "user: sebastien" in users
    assert not any("FOREST" in (d or "") for d in users)
    anon = next(f for f in findings if f.kind == "ldap_anon")
    assert "domain: htb.local" in (anon.detail or "")
    assert "anonymous LDAP bind succeeded" in (anon.detail or "")


def test_getnpusers_records_account_not_hash():
    text = (FIXTURES / "ad_getnpusers.txt").read_text()
    findings = parse_getnpusers(text)
    assert len(findings) == 1
    assert findings[0].kind == "asrep_hash"
    assert findings[0].detail == "account: svc-alfresco"
    assert "$krb5asrep$" not in (findings[0].detail or "")
    assert "aaaaaaaa" not in (findings[0].detail or "")


def test_getuserspns_records_account_not_hash():
    text = (FIXTURES / "ad_getuserspns.txt").read_text()
    findings = parse_getuserspns(text)
    assert len(findings) == 1
    assert findings[0].kind == "kerberoastable_account"
    assert findings[0].detail == "account: svc_beacon"
    assert "$krb5tgs$" not in (findings[0].detail or "")


def test_dispatcher_sniffs_each_format():
    assert parse_ad_recon_file(FIXTURES / "ad_getnpusers.txt")[0].kind == "asrep_hash"
    assert parse_ad_recon_file(FIXTURES / "ad_getuserspns.txt")[0].kind == "kerberoastable_account"
    assert any(f.kind == "ldap_anon" for f in parse_ad_recon_file(FIXTURES / "ad_ldapsearch_forest.txt"))


def test_dispatcher_unknown_text_returns_empty(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("just some operator notes, nothing AD-shaped\n")
    assert parse_ad_recon_file(p) == []


# --- suggestion rules ---


def _insert(conn, box_id, **kwargs):
    defaults = {
        "source_tool": "nmap", "kind": "port", "host": "10.10.10.161",
        "port": None, "service": None, "product": None, "version": None,
        "detail": None,
    }
    defaults.update(kwargs)
    conn.execute(
        """
        INSERT INTO findings (box_id, source_tool, kind, host, port, service, product, version, detail)
        VALUES (:box_id, :source_tool, :kind, :host, :port, :service, :product, :version, :detail)
        """,
        {"box_id": box_id, **defaults},
    )
    conn.commit()


def test_ad_signature_suggests_anonymous_ldapsearch(conn):
    box = create_box(conn, "Forest")
    _insert(
        conn, box.id, kind="ad_domain_controller", port=None,
        service=None, detail="domain: htb.local",
    )
    suggestions = suggest_next_commands(conn, box.id)
    assert any("ldapsearch" in s.command and "namingcontexts" in s.command.lower() for s in suggestions)
    assert all(s.phase == "enum" for s in suggestions if "ldapsearch" in s.command)


def test_kerberos_plus_domain_suggests_getnpusers(conn):
    box = create_box(conn, "Forest")
    _insert(conn, box.id, port=88, service="kerberos-sec")
    _insert(
        conn, box.id, kind="ad_domain_controller", port=None,
        service=None, detail="domain: htb.local",
    )
    suggestions = suggest_next_commands(conn, box.id)
    assert any("GetNPUsers.py" in s.command and "htb.local" in s.command for s in suggestions)


def test_kerberos_without_domain_does_not_suggest_getnpusers(conn):
    box = create_box(conn, "NoDomain")
    _insert(conn, box.id, port=88, service="kerberos-sec")
    suggestions = suggest_next_commands(conn, box.id)
    assert not any("GetNPUsers" in s.command for s in suggestions)


def test_ldap_anon_suggests_user_enum(conn):
    box = create_box(conn, "Forest")
    _insert(
        conn, box.id, kind="ldap_anon", port=None, service=None,
        detail="anonymous LDAP bind succeeded; domain: htb.local",
    )
    suggestions = suggest_next_commands(conn, box.id)
    assert any("objectClass=user" in s.command or "sAMAccountName" in s.command for s in suggestions)


def test_ad_suggestion_nudges_do_not_name_the_tool(conn):
    box = create_box(conn, "Forest")
    _insert(
        conn, box.id, kind="ad_domain_controller", port=None,
        service=None, detail="domain: htb.local",
    )
    _insert(conn, box.id, port=88, service="kerberos-sec")
    _insert(
        conn, box.id, kind="ldap_anon", port=None, service=None,
        detail="anonymous LDAP bind succeeded; domain: htb.local",
    )
    for s in suggest_next_commands(conn, box.id):
        first = s.command.split()[0].split("/")[-1]
        if first in ("ldapsearch", "GetNPUsers.py"):
            assert first.lower() not in s.nudge.lower()


def test_dns_service_does_not_fts_match_ad_kb(seeded_conn):
    """Live Forest parse: nmap names port 53 service=domain (DNS).
    AD KB prose that said 'domain controller' FTS-matched that port
    and claimed SMB-signing / AS-REP / anonymous LDAP on a DNS
    service. Entries were reworded; this guards the regression."""
    from trinity.kb.ad_seed import seed as seed_ad
    from trinity.match.engine import match_finding

    seed_ad(seeded_conn)
    finding = Finding(
        source_tool="nmap", kind="port", host="10.10.10.161",
        port=53, service="domain",
    )
    matches = match_finding(seeded_conn, finding)
    titles = " ".join(m.title.lower() for m in matches)
    assert "ldap" not in titles
    assert "as-rep" not in titles
    assert "signing" not in titles


def test_process_scan_file_adds_ad_finding_for_forest_not_blue(conn):
    from trinity.process import process_scan_file

    forest = create_box(conn, "Forest", target="10.10.10.161")
    result = process_scan_file(conn, forest.id, FIXTURES / "ad_forest.xml")
    assert result is not None
    kinds = {fr.finding.kind for fr in result.findings}
    assert "ad_domain_controller" in kinds
    assert any("ldapsearch" in cmd for cmd in result.suggestions)

    blue = create_box(conn, "Blue", target="10.10.10.40")
    blue_result = process_scan_file(conn, blue.id, FIXTURES / "ad_blue.xml")
    assert blue_result is not None
    assert not any(fr.finding.kind == "ad_domain_controller" for fr in blue_result.findings)


def test_parse_nmap_cli_surfaces_ad_suggestion(tmp_path, monkeypatch):
    """End-to-end: real parse-nmap against the Forest fixture must print
    the anonymous-LDAP suggestion. `next` is exercised so the coach
    path doesn't crash; it may rank SMB enum first (same phase)."""
    db_path = tmp_path / "trinity.db"

    def _connect(*_args, **_kwargs):
        return connect(db_path, seed_brain=True)

    monkeypatch.setattr("trinity.cli.main.connect", _connect)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["parse-nmap", str(FIXTURES / "ad_forest.xml"), "--box", "Forest",
         "--target", "10.10.10.161", "--platform", "htb"],
    )
    assert result.exit_code == 0, result.output
    assert "ldapsearch" in result.output
    assert "namingcontexts" in result.output.lower()

    nxt = runner.invoke(cli, ["next", "--box", "Forest"])
    assert nxt.exit_code == 0, nxt.output

