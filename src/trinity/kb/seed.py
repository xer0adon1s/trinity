"""Seed the local KB with a real starter set of known service/vuln
mappings. Small on purpose — enough to prove the match loop end to end.
Expansion (searchsploit shellouts, GTFOBins/PayloadsAllTheThings ingestion)
comes next; this is the hand-curated core covering classic HTB/THM
teaching-box vulnerabilities.
"""
from __future__ import annotations

import sqlite3

SEED_ENTRIES: list[dict[str, str | None]] = [
    {
        "source": "user_curated",
        "title": "vsftpd 2.3.4 backdoor (CVE-2011-2523)",
        "summary": (
            "This exact version has a known backdoor: sending a username "
            "containing ':)' opens a root shell on port 6200. Classic "
            "intentionally-vulnerable teaching box marker."
        ),
        "detail": (
            "Exploit: metasploit `exploit/unix/ftp/vsftpd_234_backdoor`, or "
            "manually connect with a username like 'user:)' via the FTP "
            "control channel, then connect to port 6200 for a root shell."
        ),
        "match_service": "ftp",
        "match_version": "2.3.4",
        "tags": "ftp,backdoor,rce,vsftpd,cve-2011-2523",
        "severity": "critical",
    },
    {
        "source": "user_curated",
        "title": "Anonymous FTP login",
        "summary": (
            "FTP server allows the 'anonymous' user with any/blank "
            "password. Always worth checking before anything else on port 21."
        ),
        "detail": "Try: `ftp <target>` then username `anonymous`, any password.",
        "match_service": "ftp",
        "match_version": None,
        "tags": "ftp,anonymous,misconfiguration",
        "severity": "medium",
    },
    {
        "source": "user_curated",
        "title": "SMB null session / anonymous enumeration",
        "summary": (
            "SMB (port 445/139) often allows unauthenticated enumeration of "
            "shares, users, and groups — a very common early foothold path."
        ),
        "detail": (
            "Try: `smbclient -L //<target>/ -N`, `enum4linux -a <target>`, "
            "or `crackmapexec smb <target> --shares -u '' -p ''`."
        ),
        "match_service": "microsoft-ds",
        "match_version": None,
        "tags": "smb,enumeration,null-session,windows",
        "severity": "medium",
    },
    {
        "source": "user_curated",
        "title": "SSH version banner grabbing for known CVEs",
        "summary": (
            "Old OpenSSH versions occasionally have known auth-bypass or "
            "info-leak CVEs. Check the exact version against searchsploit "
            "before assuming SSH is a dead end."
        ),
        "detail": "Try: `searchsploit openssh <version>`",
        "match_service": "ssh",
        "match_version": None,
        "tags": "ssh,version-check",
        "severity": "info",
    },
    {
        "source": "user_curated",
        "title": "HTTP directory brute-forcing is next after a webserver is found",
        "summary": (
            "Any open HTTP/HTTPS port warrants gobuster/ffuf directory "
            "and vhost brute-forcing before anything else — hidden admin "
            "panels, backup files, and API routes are extremely common."
        ),
        "detail": (
            "Try: `gobuster dir -u http://<target> -w "
            "/usr/share/wordlists/dirb/common.txt -x php,txt,html`"
        ),
        "match_service": "http",
        "match_version": None,
        "tags": "http,enumeration,gobuster,directory-bruteforce",
        "severity": "info",
    },
    {
        "source": "user_curated",
        "title": "SUID binaries are the first privesc check on Linux",
        "summary": (
            "Once you have a foothold, listing SUID binaries is priority "
            "one — many are exploitable via GTFOBins-documented techniques "
            "to escalate straight to root."
        ),
        "detail": (
            "Try: `find / -perm -4000 -type f 2>/dev/null`, then check "
            "each binary found against gtfobins.github.io."
        ),
        "match_service": None,
        "match_version": None,
        "tags": "privesc,suid,linux,gtfobins",
        "severity": "high",
    },
]


def seed(conn: sqlite3.Connection) -> int:
    """Insert seed KB entries if not already present (idempotent by title).
    Returns the number of entries actually inserted."""
    inserted = 0
    for entry in SEED_ENTRIES:
        exists = conn.execute(
            "SELECT 1 FROM kb_entries WHERE title = ?", (entry["title"],)
        ).fetchone()
        if exists:
            continue

        conn.execute(
            """
            INSERT INTO kb_entries
                (source, title, summary, detail, match_service, match_version, tags, severity)
            VALUES (:source, :title, :summary, :detail, :match_service, :match_version, :tags, :severity)
            """,
            entry,
        )
        inserted += 1

    conn.commit()
    return inserted
