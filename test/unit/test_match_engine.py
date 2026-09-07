"""Tests for the match engine and severity heuristics."""
from __future__ import annotations

from trinity.kb.severity import rate_severity, severity_from_cvss
from trinity.match.engine import (
    _path_product_terms,
    _searchsploit_query_terms,
    match_finding,
)
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


def test_generic_vuln_language_does_not_cross_match_unrelated_kb_entry(seeded_conn):
    """Regression test: found live during a Linux/Windows box simulation
    exercise. An nmap smb-vuln-ms17-010 script hit's own detail text
    naturally contains generic security-report vocabulary ("VULNERABLE",
    "CVE", "in") that also happens to appear in the unrelated vsftpd
    backdoor KB entry's title/summary -- the old unfiltered FTS query
    OR'd every token together and cross-matched the two, even though a
    Windows SMB finding has nothing to do with an FTP backdoor. This
    finding has no ftp/vsftpd service anywhere in it."""
    finding = Finding(
        source_tool="nmap", kind="port", host="10.10.10.40", port=445,
        service="microsoft-ds",
        product="Windows 7 Professional 7601 Service Pack 1 microsoft-ds",
        detail=(
            "[smb-vuln-ms17-010] VULNERABLE: Remote Code Execution "
            "vulnerability in Microsoft SMBv1 servers (ms17-010). "
            "Risk factor: HIGH. CVE:CVE-2017-0143"
        ),
    )
    matches = match_finding(seeded_conn, finding)
    assert not any("vsftpd" in m.title.lower() for m in matches)


def test_generic_vuln_language_does_not_cross_match_linux_only_kb_entry(seeded_conn):
    """Same bug, different pairing: a Windows XP smb-vuln-ms08-067 hit
    should not cross-match the Linux-only 'SUID binaries' privesc KB
    entry just because both mention generic vuln-report vocabulary."""
    finding = Finding(
        source_tool="nmap", kind="port", host="10.10.10.4", port=445,
        service="microsoft-ds", product="Windows XP microsoft-ds",
        detail=(
            "[smb-vuln-ms08-067] VULNERABLE: Microsoft Windows system "
            "vulnerable to remote code execution (MS08-067). "
            "CVE:CVE-2008-4250"
        ),
    )
    matches = match_finding(seeded_conn, finding)
    assert not any("suid" in m.title.lower() for m in matches)


def test_ms_bulletin_in_detail_surfaces_matching_searchsploit_exploit(seeded_conn):
    """Regression test, second half of the same simulation-exercise
    finding: nmap's smb-vuln-ms17-010 script confirms EternalBlue BY
    NAME in the finding's own detail text, and searchsploit genuinely
    has matching, verified exploits locally -- but the old code only
    ever queried searchsploit using finding.product/version, so a
    Windows SMB finding whose real signal lives in `detail` (not
    product/version) got nothing back. This needs a live searchsploit
    binary to actually return results; skips cleanly if unavailable."""
    from trinity.kb import searchsploit as searchsploit_module

    if not searchsploit_module.is_available():
        import pytest
        pytest.skip("searchsploit not installed in this environment")

    finding = Finding(
        source_tool="nmap", kind="port", host="10.10.10.40", port=445,
        service="microsoft-ds",
        product="Windows 7 Professional 7601 Service Pack 1 microsoft-ds",
        detail=(
            "[smb-vuln-ms17-010] VULNERABLE: Remote Code Execution "
            "vulnerability in Microsoft SMBv1 servers (ms17-010). "
            "Risk factor: HIGH. CVE:CVE-2017-0143"
        ),
    )
    matches = match_finding(seeded_conn, finding)
    assert any("eternalblue" in m.title.lower() or "ms17-010" in m.title.lower() for m in matches)


def test_multiple_ms_bulletins_in_detail_are_queried_separately(seeded_conn):
    """Regression: Legacy's port-445 finding carries BOTH smb-vuln-ms08-067
    and smb-vuln-ms17-010 in the same detail string. searchsploit ANDs
    argv terms, so querying them as one call (`ms08-067 ms17-010`)
    returns nothing even though each bulletin has local exploits.
    Each extracted bulletin must be its own searchsploit query."""
    from trinity.kb import searchsploit as searchsploit_module

    if not searchsploit_module.is_available():
        import pytest
        pytest.skip("searchsploit not installed in this environment")

    finding = Finding(
        source_tool="nmap", kind="port", host="10.10.10.4", port=445,
        service="microsoft-ds", product="Windows XP microsoft-ds",
        detail=(
            "[smb-vuln-ms08-067] VULNERABLE: Microsoft Windows system "
            "vulnerable to remote code execution (MS08-067). "
            "CVE:CVE-2008-4250 | "
            "[smb-vuln-ms17-010] VULNERABLE: Remote Code Execution "
            "vulnerability in Microsoft SMBv1 servers (ms17-010). "
            "Risk factor: HIGH. CVE:CVE-2017-0143"
        ),
    )
    matches = match_finding(seeded_conn, finding)
    titles = " ".join(m.title.lower() for m in matches)
    # Default limit=5 is filled by the first bulletin's hits; that's
    # enough to prove the AND-query bug is gone (ms08-067 used to vanish
    # entirely). A wider limit confirms the second bulletin is queried
    # too — we do not change production limit/ordering here.
    assert "ms08-067" in titles or "netapi" in titles or "conficker" in titles
    wide = match_finding(seeded_conn, finding, limit=20)
    wide_titles = " ".join(m.title.lower() for m in wide)
    assert "ms17-010" in wide_titles or "eternalblue" in wide_titles or "eternalromance" in wide_titles


def test_path_product_terms_extracts_product_shaped_last_segment():
    """Last meaningful path segment only, and only when it looks like a
    product/app name — /nibbleblog/ is a CMS, /admin/ is generic noise."""
    assert _path_product_terms("/nibbleblog/") == ["nibbleblog"]
    assert _path_product_terms("/nibbleblog") == ["nibbleblog"]
    assert _path_product_terms("/blog/nibbleblog/") == ["nibbleblog"]
    assert _path_product_terms("/PRTG/") == ["PRTG"]
    assert _path_product_terms("/admin/") == []
    assert _path_product_terms("/login/") == []
    assert _path_product_terms("/backup/") == []
    assert _path_product_terms("/upload/") == []
    assert _path_product_terms("/images/") == []
    assert _path_product_terms("/css/") == []
    assert _path_product_terms("/cgi-bin/") == []
    assert _path_product_terms("/phpmyadmin/") == []
    assert _path_product_terms("/themes/") == []
    assert _path_product_terms("/javascript/") == []
    assert _path_product_terms("/ab/") == []  # too short
    assert _path_product_terms("/1234/") == []  # not letter-led
    assert _path_product_terms("/index.php") == []  # punctuation, plus generic stem


def test_path_finding_surfaces_matching_searchsploit_exploit(seeded_conn):
    """Regression test, same shape as the MS-bulletin searchsploit
    lookup: a gobuster/ffuf path finding (kind='path') never sets
    .product, so the old code never queried searchsploit even when
    ExploitDB already had the matching exploit locally. Nibbleblog's
    file-upload PoC is the concrete case from the 6-box simulation.
    Skips cleanly if searchsploit isn't installed."""
    from trinity.kb import searchsploit as searchsploit_module

    if not searchsploit_module.is_available():
        import pytest
        pytest.skip("searchsploit not installed in this environment")

    finding = Finding(
        source_tool="gobuster", kind="path", host="10.10.10.75",
        path="/nibbleblog/", status_code=301,
    )
    matches = match_finding(seeded_conn, finding)
    assert any("nibbleblog" in m.title.lower() for m in matches)


def test_generic_path_finding_does_not_query_searchsploit_on_admin(seeded_conn):
    """Companion to the product-shaped path lookup: /admin/ must not
    become `searchsploit admin`. A generic-segment query is the noise
    mode this extraction was written to avoid. If searchsploit isn't
    installed the helper already returns [] so this is a no-op skip
    in that environment; with it installed, no searchsploit-sourced
    match should appear for a bare /admin/ path."""
    from trinity.kb import searchsploit as searchsploit_module

    if not searchsploit_module.is_available():
        import pytest
        pytest.skip("searchsploit not installed in this environment")

    finding = Finding(
        source_tool="gobuster", kind="path", host="10.10.10.1",
        path="/admin/", status_code=301,
    )
    matches = match_finding(seeded_conn, finding)
    assert not any(m.source == "searchsploit" for m in matches)


def test_nmap_role_words_stripped_from_searchsploit_product_query():
    """nmap fingerprints include role words searchsploit ANDs against
    and then returns zero. Same shape as the existing smbd/httpd strip.
    Coverage-sim: Icecast / JAMES / Redis product strings."""
    assert _searchsploit_query_terms(
        "Icecast streaming media server", None
    ) == ["Icecast"]
    assert _searchsploit_query_terms("JAMES smtpd", "2.3.2") == ["JAMES", "2.3.2"]
    assert _searchsploit_query_terms(
        "JAMES Remote Admin", "2.3.2"
    ) == ["JAMES", "2.3.2"]
    assert _searchsploit_query_terms(
        "Redis key-value store", "4.0.9"
    ) == ["Redis", "4.0.9"]
    assert _searchsploit_query_terms(
        "Oracle TNS listener", "11.2.0.2.0"
    ) == ["Oracle TNS", "11.2.0.2.0"]
    # existing strip still works
    assert _searchsploit_query_terms("Samba smbd", "3.0.20-Debian") == [
        "Samba", "3.0.20",
    ]


def test_icecast_nmap_product_surfaces_matching_searchsploit_exploit(seeded_conn):
    """THM Ice: nmap product is 'Icecast streaming media server' with no
    version. The unstripped phrase returns zero local exploits; Icecast
    alone has the CVE-2004-1561 Win32 header overwrite used on that box."""
    from trinity.kb import searchsploit as searchsploit_module

    if not searchsploit_module.is_available():
        import pytest
        pytest.skip("searchsploit not installed in this environment")

    finding = Finding(
        source_tool="nmap", kind="port", host="10.10.139.241", port=8000,
        service="http", product="Icecast streaming media server",
    )
    matches = match_finding(seeded_conn, finding)
    assert any("icecast" in m.title.lower() for m in matches)


def test_james_smtpd_product_surfaces_matching_searchsploit_exploit(seeded_conn):
    """HTB SolidState: nmap product 'JAMES smtpd' 2.3.2. The unstripped
    query ANDs smtpd and returns zero; JAMES 2.3.2 has the Apache James
    Server RCE / insecure-user-creation exploits locally."""
    from trinity.kb import searchsploit as searchsploit_module

    if not searchsploit_module.is_available():
        import pytest
        pytest.skip("searchsploit not installed in this environment")

    finding = Finding(
        source_tool="nmap", kind="port", host="10.10.10.51", port=25,
        service="smtp", product="JAMES smtpd", version="2.3.2",
    )
    matches = match_finding(seeded_conn, finding)
    titles = " ".join(m.title.lower() for m in matches)
    assert "james" in titles


def test_version_specific_kb_entry_does_not_fire_without_matching_version(seeded_conn):
    """Regression test: found live during the 2026-09-07 AD/Windows
    simulation exercise (HTB Netmon). The vsftpd 2.3.4 backdoor KB
    entry is version-SPECIFIC (match_version='2.3.4') but stage 1 only
    ever BOOSTED score on a version match, never REQUIRED it -- so any
    finding sharing match_service='ftp' surfaced it at 0.9 confidence
    regardless of actual version, including services with no version
    at all ('Microsoft ftpd', a completely different FTP server).
    Generic, version-agnostic KB entries (e.g. 'Anonymous FTP login')
    are unaffected and must keep firing on service alone."""
    finding = Finding(source_tool="nmap", kind="port", host="10.10.10.152", port=21,
                       service="ftp", product="Microsoft ftpd", version=None)
    matches = match_finding(seeded_conn, finding)
    assert not any("vsftpd" in m.title.lower() for m in matches)


def test_service_scoped_kb_entry_does_not_fts_cross_match_different_service(seeded_conn):
    """Regression test: found live during the AD simulation exercise
    (HTB Netmon). An LDAP-scoped 'anonymous bind' KB entry FTS-attached
    to an Anonymous-FTP finding purely because both texts contain the
    word 'anonymous' -- match_service was set on the KB row but only
    honoured in stage 1's exact filter, not stage 2's FTS fallback.
    A finding with a known, different service must not pull in a
    KB entry scoped to yet another specific service. The AD-flavored
    KB entry itself lives on a separate feature branch, not main, so
    this test inserts an equivalent minimal LDAP-scoped row directly
    to reproduce the exact cross-match shape without depending on that
    branch landing first."""
    seeded_conn.execute(
        "INSERT INTO kb_entries (source, title, summary, detail, match_service, "
        "match_version, tags, severity) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "user_curated",
            "Anonymous LDAP bind on an Active Directory DC",
            "The DC answered an unauthenticated LDAP query.",
            "Dump users/groups next.",
            "ldap",
            None,
            "ad,ldap,anonymous",
            "medium",
        ),
    )
    seeded_conn.commit()

    finding = Finding(source_tool="nmap", kind="port", host="10.10.10.152", port=21,
                       service="ftp", product="Microsoft ftpd",
                       detail="Anonymous FTP login allowed (FTP code 230)")
    matches = match_finding(seeded_conn, finding)
    assert not any("ldap" in m.title.lower() for m in matches)


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
